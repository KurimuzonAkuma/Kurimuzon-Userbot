import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import git
import pyrogram
from pyrogram import Client, filters
from pyrogram.types import LinkPreviewOptions, Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help, uptime
from utils.scripts import (
    format_exc,
    get_args,
    get_cpu_usage,
    get_prefix,
    get_ram_usage,
    shell_exec,
    time_diff,
    with_args,
    format_bytes
)


@Client.on_message(~filters.scheduled & command(["help", "h"]) & filters.me & ~filters.forwarded)
async def help_cmd(_, message: Message):
    args, _ = get_args(message)
    try:
        if not args:
            msg_edited = False

            for text in modules_help.help():
                if msg_edited:
                    await message.reply(
                        text, link_preview_options=LinkPreviewOptions(is_disabled=True)
                    )
                else:
                    await message.edit(
                        text, link_preview_options=LinkPreviewOptions(is_disabled=True)
                    )
                    msg_edited = True
        elif args[0] in modules_help.modules:
            await message.edit(
                modules_help.module_help(args[0]),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        else:
            await message.edit(
                modules_help.command_help(args[0]),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
    except ValueError as e:
        await message.edit(e)


@Client.on_message(~filters.scheduled & command(["restart"]) & filters.me & ~filters.forwarded)
async def _restart(_: Client, message: Message):
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


@Client.on_message(~filters.scheduled & command(["update"]) & filters.me & ~filters.forwarded)
async def _update(_: Client, message: Message):
    await message.edit("<code>Updating...</code>")
    args, nargs = get_args(message)

    current_hash = git.Repo().head.commit.hexsha

    git.Repo().remote("origin").fetch()

    branch = git.Repo().active_branch.name
    upcoming = next(git.Repo().iter_commits(f"origin/{branch}", max_count=1)).hexsha

    if current_hash == upcoming:
        return await message.edit("<b>Userbot already up to date</b>")

    if "--hard" in args:
        await shell_exec("git reset --hard HEAD")

    try:
        git.Repo().remote("origin").pull()
    except git.exc.GitCommandError as e:
        return await message.edit_text(
            "<b>Update failed! Try again with --hard argument.</b>\n\n"
            f"<code>{e.stderr.strip()}</code>"
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
        subprocess.run([sys.executable, "-m", "pip", "install", "-U", "pip"])
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-U",
                "-r",
                "requirements.txt",
            ]
        )
    except Exception as e:
        await message.edit(format_exc(e))
        db.remove("core.updater", "restart_info")
    else:
        os.execvp(sys.executable, [sys.executable, *sys.argv])


@Client.on_message(
    ~filters.scheduled & command(["kprefix", "prefix"]) & filters.me & ~filters.forwarded
)
async def set_prefix(_, message: Message):
    args, _ = get_args(message)
    prefix = get_prefix()

    if not args:
        return await message.edit_text(
            f"Current prefix: <code>{prefix}</code>\n"
            f"To change prefix use <code>{prefix}{message.command[0]} [new prefix]</code>"
        )

    db.set("core.main", "prefix", args[0])
    await message.edit(f"<b>Prefix changed to:</b> <code>{args[0]}</code>")


@Client.on_message(
    ~filters.scheduled & command(["sendmod", "sm"]) & filters.me & ~filters.forwarded
)
@with_args("<b>Module name to send is not provided</b>")
async def sendmod(client: Client, message: Message):
    args, _ = get_args(message)
    try:
        module_name = args[0]
        if module_name in modules_help.modules:
            await message.delete()
            text = modules_help.module_help(module_name, False)
            if os.path.isfile(modules_help.modules[module_name].path):
                await client.send_document(
                    message.chat.id,
                    modules_help.modules[module_name].path,
                    caption=text,
                )
        else:
            await message.edit(f"<b>Module {module_name} not found!</b>")
    except Exception as e:
        await message.reply(format_exc(e), quote=False)


@Client.on_message(~filters.scheduled & command(["status"]) & filters.me & ~filters.forwarded)
async def _status(client: Client, message: Message):
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

    result = (
        f"<emoji id=5219903664428167948>🤖</emoji> <a href='{repo_link}'>Kurimuzon-Userbot</a> / "
    )
    result += f"<a href='{repo_link}/commit/{current_hash}'>#{current_hash[:7]} ({current_version})</a>\n\n"
    result += f"<b>Pyrogram:</b> <code>{pyrogram.__version__}</code>\n"
    result += f"<b>Python:</b> <code>{sys.version}</code>\n"
    result += "<b>Dev:</b> <a href='https://t.me/KurimuzonAkuma'>KurimuzonAkuma</a>\n\n"

    if "-a" not in args:
        return await message.edit(
            result, link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

    await message.edit("<code>Getting info...</code>")

    cpu_usage = get_cpu_usage()
    ram_usage = get_ram_usage()
    kernel_version = subprocess.run(["uname", "-a"], capture_output=True).stdout.decode().strip()
    system_uptime = subprocess.run(["uptime", "-p"], capture_output=True).stdout.decode().strip()

    result += "<b>Bot status:</b>\n"
    result += f"├─<b>Uptime:</b> <code>{time_diff(uptime)}</code>\n"
    result += f"├─<b>Branch:</b> <code>{branch}</code>\n"
    result += f"├─<b>Current version:</b> <a href='{repo_link}/commit/{current_hash}'>"
    result += f"#{current_hash[:7]} ({current_version})</a>\n"
    result += f"├─<b>Latest version:</b> <a href='{repo_link}/commit/{upcoming}'>"
    result += f"#{upcoming[:7]} ({upcoming_version})</a>\n"
    result += f"├─<b>Prefix:</b> <code>{get_prefix()}</code>\n"
    result += f"├─<b>Modules:</b> <code>{modules_help.modules_count}</code>\n"
    result += f"└─<b>Commands:</b> <code>{modules_help.commands_count}</code>\n\n"

    result += "<b>System status:</b>\n"
    result += f"├─<b>OS:</b> <code>{sys.platform}</code>\n"
    result += f"├─<b>Kernel:</b> <code>{kernel_version}</code>\n"
    result += f"├─<b>Uptime:</b> <code>{system_uptime}</code>\n"
    result += f"├─<b>CPU usage:</b> <code>{cpu_usage}%</code>\n"
    result += f"└─<b>RAM usage:</b> <code>{ram_usage}MB</code>\n\n"

    known_peers, known_usernames = client.storage.conn.execute("SELECT (SELECT COUNT(id) FROM peers) AS peer_count, (SELECT COUNT(username) FROM usernames) AS username_count").fetchone()
    session_size = Path(f"{client.name}.session").stat().st_size

    result += "<b>Session info:</b>\n"
    result += f"├─<b>Known peers:</b> <code>{known_peers:,}</code>\n"
    result += f"├─<b>Known usernames:</b> <code>{known_usernames:,}</code>\n"
    result += f"└─<b>Session size:</b> <code>{format_bytes(session_size)}</code>"

    await message.edit(result, link_preview_options=LinkPreviewOptions(is_disabled=True))


@Client.on_message(~filters.scheduled & command(["ping", "p"]) & filters.me & ~filters.forwarded)
async def ping(_, message: Message):
    start = perf_counter()
    await message.edit("<b>Pong!</b>")
    end = perf_counter()
    await message.edit(f"<b>Pong! {round(end - start, 3)}s</b>")


module = modules_help.add_module("base", __file__)
module.add_command("help", "Get common/module/command help.", "[module/command name]", ["h"])
module.add_command("prefix", "Set custom prefix", None, ["kprefix"])
module.add_command("restart", "Useful when you want to reload a bot")
module.add_command("update", "Update the userbot from the repository")
module.add_command("sendmod", "Send module to chat", "[module_name]", ["sm"])
module.add_command("status", "Get information about the userbot and system", "[-a]")
module.add_command("ping", "Check ping to Telegram servers", aliases=["p"])
