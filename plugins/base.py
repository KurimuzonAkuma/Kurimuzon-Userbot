import html
import importlib
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, cast

import git
import pyrogram
from pyrogram import Client, filters, raw
from pyrogram.types import LinkPreviewOptions, Message

from utils import loader
from utils.db import db
from utils.loader import CommandArg, Plugin, help_registry
from utils.misc import uptime
from utils.scripts import (
    format_bytes,
    format_exc,
    get_args,
    get_cpu_usage,
    get_prefix,
    get_ram_usage,
    shell_exec,
    time_diff,
)

if TYPE_CHECKING:
    from utils.storage import EncryptedStorage
    from utils.client import CustomClient


class Base(Plugin):
    @loader.command(
        commands=["help", "h"],
        description="Show general, plugin, or command help",
        args=[CommandArg("name", "module or command name", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def help_cmd(self, _, message: Message):
        args, _ = get_args(message)
        try:
            if not args:
                msg_edited = False
                for text in help_registry.help():
                    if msg_edited:
                        await message.reply(
                            text,
                            link_preview_options=LinkPreviewOptions(is_disabled=True),
                        )
                    else:
                        await message.edit(
                            text,
                            link_preview_options=LinkPreviewOptions(is_disabled=True),
                        )
                        msg_edited = True
                return

            try:
                help_registry.get_module(args[0])
            except ValueError:
                text = help_registry.command_help(args[0])
            else:
                text = help_registry.module_help(args[0])

            await message.edit(
                text,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except ValueError:
            await message.edit(
                f"<b>No module or command named {html.escape(args[0])} was found.</b>"
            )

    @loader.command(
        "restart",
        description="Restart the userbot",
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def _restart(self, client: Client, message: Message):
        del client
        if message.chat is None:
            return
        db.set(
            "core.updater",
            "restart_info",
            {
                "chat_id": message.chat.id,
                "message_id": message.id,
                "time": perf_counter(),
                "type": "restart",
            },
        )

        await message.edit("<code>Restarting...</code>")
        os.execvp(sys.executable, [sys.executable, *sys.argv])

    @loader.command(
        "update",
        description="Update the userbot from the repository",
        args=[CommandArg("hard", "reset repository to HEAD", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def _update(self, client: Client, message: Message):
        del client
        if message.chat is None:
            return
        await message.edit("<code>Updating...</code>")
        args, _ = get_args(message)

        current_hash = git.Repo().head.commit.hexsha
        git.Repo().remote("origin").fetch()

        branch = git.Repo().active_branch.name
        upcoming = next(git.Repo().iter_commits(f"origin/{branch}", max_count=1)).hexsha

        if current_hash == upcoming:
            return await message.edit("<b>Userbot is already up to date</b>")

        if "--hard" in args:
            await shell_exec("git reset --hard HEAD")

        try:
            git.Repo().remote("origin").pull()
        except git.exc.GitCommandError as e:
            return await message.edit_text(
                f"<b>Update failed. Try again with --hard.</b>\n\n<code>{e.stderr.strip()}</code>"
            )

        upcoming_version = len(list(git.Repo().iter_commits()))
        current_version = upcoming_version - (
            len(list(git.Repo().iter_commits(f"{current_hash}..{upcoming}")))
        )

        db.set(
            "core.updater",
            "restart_info",
            {
                "chat_id": message.chat.id,
                "message_id": message.id,
                "time": perf_counter(),
                "hash": current_hash,
                "version": f"{current_version}",
                "type": "update",
            },
        )

        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-U", "pip"], check=False)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-U",
                    "-r",
                    "requirements.txt",
                ],
                check=False,
            )
        except Exception as e:
            await message.edit(format_exc(e))
            db.remove("core.updater", "restart_info")
        else:
            os.execvp(sys.executable, [sys.executable, *sys.argv])

    @loader.command(
        ["prefix", "kprefix"],
        description="Set a custom command prefix",
        args=[CommandArg("new_prefix", "new prefix", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def set_prefix(self, client: Client, message: Message):
        del client
        args, _ = get_args(message)
        prefix = get_prefix()

        if not args:
            return await message.edit_text(
                f"Current prefix: <code>{prefix}</code>\n"
                f"To change it, use <code>{prefix}{message.command[0] if message.command else 'prefix'} [new prefix]</code>"
            )

        db.set("core.main", "prefix", args[0])
        await message.edit(f"<b>Prefix changed to:</b> <code>{args[0]}</code>")

    @loader.command(
        "sm",
        description="Send a plugin file by plugin or command name",
        args=[CommandArg("module", "module name", required=True)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def sendmod(self, client: Client, message: Message):
        args, _ = get_args(message)
        if not args:
            return await message.edit("<b>Plugin name or command to send is required</b>")

        try:
            module_name = args[0]
            try:
                module = help_registry.get_module(module_name)
            except ValueError:
                module = None
            if module is None:
                try:
                    module = help_registry.get_module_by_command(module_name)
                except ValueError:
                    module = None

            if module is None or not os.path.isfile(module.path):
                await message.edit(
                    f"<b>Plugin or command {html.escape(module_name)} was not found</b>"
                )
                return

            await message.delete()

            await client.send_document(
                message.chat.id,
                module.path,
                caption=help_registry.module_help(module.name, full=False),
            )
        except Exception as e:
            await message.reply(format_exc(e))

    @loader.command(
        "lm",
        description="Load a plugin from a .py file",
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def load_plugin(self, client: "CustomClient", message: Message):
        reply = message.reply_to_message
        document = reply.document if reply else None
        if document is None:
            return await message.edit("<b>Reply to a .py plugin file</b>")

        document_name = document.file_name
        if not document_name:
            return await message.edit("<b>The plugin filename is invalid</b>")

        filename = Path(document_name).name
        if Path(filename).suffix != ".py" or not Path(filename).stem.isidentifier():
            return await message.edit("<b>Reply to a valid .py plugin file</b>")

        plugin_path = Path(__file__).resolve().parent / "custom_plugins" / filename
        module_path = f"plugins.custom_plugins.{plugin_path.stem}"
        plugin_name = f"custom_plugins.{plugin_path.stem}"

        if plugin_path.exists() or module_path in sys.modules:
            return await message.edit("<b>A plugin with this filename is already installed</b>")

        await message.edit("<b>Loading plugin...</b>")

        try:
            await client.download_media(
                document.file_id,
                file_name=str(plugin_path),
            )
            importlib.invalidate_caches()
            module = importlib.import_module(module_path)
            conflicts = client.get_plugin_registration_conflicts(module, module_path)
            if conflicts:
                sys.modules.pop(module_path, None)
                plugin_path.unlink(missing_ok=True)
                reasons = "\n".join(f"• {html.escape(conflict)}" for conflict in conflicts)
                return await message.edit(
                    f"<b>Plugin not loaded because of conflicts:</b>\n{reasons}"
                )

            registration_count = client._register_class_plugins(module, module_path)

            if not registration_count:
                client.unload_plugin(plugin_name)
                plugin_path.unlink(missing_ok=True)
                return await message.edit(
                    "<b>No Plugin commands, handlers, or loops were found.</b>"
                )
            client.register_plugin_loops()
        except Exception as e:
            client.unload_plugin(plugin_name)
            plugin_path.unlink(missing_ok=True)
            return await message.edit(
                f"<b>Plugin not loaded.</b>\n<b>Reason:</b> <code>{html.escape(str(e))}</code>"
            )

        await message.edit("<b>Plugin loaded.</b>")

    @loader.command(
        "status",
        description="Get information about the userbot and system",
        args=[CommandArg("all", "full system information", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def _status(self, client: Client, message: Message):
        args, _ = get_args(message)

        current_hash = git.Repo().head.commit.hexsha
        git.Repo().remote("origin").fetch()
        branch = git.Repo().active_branch.name
        upcoming = next(git.Repo().iter_commits(f"origin/{branch}", max_count=1)).hexsha
        upcoming_version = len(list(git.Repo().iter_commits()))
        current_version = upcoming_version - (
            len(list(git.Repo().iter_commits(f"{current_hash}..{upcoming}")))
        )
        repo_link = "https://github.com/KurimuzonAkuma/Kurimuzon-Userbot"

        result = f"<emoji id=5219903664428167948>🤖</emoji> <a href='{repo_link}'>Kurimuzon-Userbot</a> / "
        result += f"<a href='{repo_link}/commit/{current_hash}'>#{current_hash[:7]} ({current_version})</a>\n\n"
        result += f"<b>Pyrogram:</b> <code>{pyrogram.__version__}</code>\n"
        result += f"<b>Python:</b> <code>{sys.version}</code>\n"
        result += "<b>Developer:</b> <a href='https://t.me/KurimuzonAkuma'>KurimuzonAkuma</a>\n\n"

        if "-a" not in args:
            return await message.edit(
                result,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )

        await message.edit("<code>Getting system information...</code>")

        cpu_usage = get_cpu_usage()
        ram_usage = get_ram_usage()
        kernel_version = (
            subprocess.run(["uname", "-a"], capture_output=True, check=False)
            .stdout.decode()
            .strip()
        )
        system_uptime = (
            subprocess.run(["uptime", "-p"], capture_output=True, check=False)
            .stdout.decode()
            .strip()
        )

        result += "<b>Bot status:</b>\n"
        result += f"├─<b>Uptime:</b> <code>{time_diff(uptime)}</code>\n"
        result += f"├─<b>Branch:</b> <code>{branch}</code>\n"
        result += f"├─<b>Current version:</b> <a href='{repo_link}/commit/{current_hash}'>"
        result += f"#{current_hash[:7]} ({current_version})</a>\n"
        result += f"├─<b>Latest version:</b> <a href='{repo_link}/commit/{upcoming}'>"
        result += f"#{upcoming[:7]} ({upcoming_version})</a>\n"
        result += f"├─<b>Prefix:</b> <code>{get_prefix()}</code>\n"
        result += f"├─<b>Plugins:</b> <code>{help_registry.modules_count}</code>\n"
        result += f"└─<b>Commands:</b> <code>{help_registry.commands_count}</code>\n\n"

        result += "<b>System status:</b>\n"
        result += f"├─<b>OS:</b> <code>{sys.platform}</code>\n"
        result += f"├─<b>Kernel:</b> <code>{kernel_version}</code>\n"
        result += f"├─<b>Uptime:</b> <code>{system_uptime}</code>\n"
        result += f"├─<b>CPU usage:</b> <code>{cpu_usage}%</code>\n"
        result += f"└─<b>RAM usage:</b> <code>{ram_usage}MB</code>\n\n"

        storage = cast("EncryptedStorage", client.storage)
        connection = storage.conn
        if connection is None:
            return await message.edit("<b>Session storage is not available.</b>")

        cursor = await connection.execute(
            "SELECT (SELECT COUNT(id) FROM peers) AS peer_count, (SELECT COUNT(username) FROM usernames) AS username_count"
        )
        peer_counts = await cursor.fetchone()
        if peer_counts is None:
            return await message.edit("<b>Session storage is not available.</b>")
        known_peers, known_usernames = peer_counts
        session_size = Path(f"{client.name}.session").stat().st_size

        result += "<b>Session info:</b>\n"
        result += f"├─<b>Known peers:</b> <code>{known_peers:,}</code>\n"
        result += f"├─<b>Known usernames:</b> <code>{known_usernames:,}</code>\n"
        result += f"└─<b>Session size:</b> <code>{format_bytes(session_size)}</code>"

        await message.edit(
            result,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

    @loader.command(
        ["ping", "p"],
        description="Check latency to Telegram servers",
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def ping(self, client: Client, message: Message):
        start = perf_counter()
        await client.invoke(raw.functions.Ping(ping_id=0))
        end = perf_counter()
        await message.edit(f"<b>Pong! {int((end - start) * 1000)}ms</b>")
