import os
import subprocess
import sys
from time import perf_counter

import arrow
import git
import pyrogram
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import bot_uptime, modules_help
from utils.scripts import (
    format_exc,
    get_args,
    get_cpu_usage,
    get_prefix,
    get_ram_usage,
    restart,
    with_args,
)


@Client.on_message(~filters.scheduled & command(["help", "h"]) & filters.me & ~filters.forwarded)
async def help_cmd(_, message: Message):
    args, _ = get_args(message)
    try:
        if not args:
            msg_edited = False

            for text in modules_help.help():
                if msg_edited:
                    await message.reply(text, disable_web_page_preview=True)
                else:
                    await message.edit(text, disable_web_page_preview=True)
                    msg_edited = True
        elif args[0] in modules_help.modules:
            await message.edit(modules_help.module_help(args[0]), disable_web_page_preview=True)
        else:
            await message.edit(modules_help.command_help(args[0]), disable_web_page_preview=True)
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
    restart()


@Client.on_message(~filters.scheduled & command(["update"]) & filters.me & ~filters.forwarded)
async def _update(_: Client, message: Message):
    repo = git.Repo()
    subprocess.run(["git", "fetch"])
    current_hash = repo.head.commit.hexsha
    latest_hash = repo.remotes.origin.refs.master.commit.hexsha
    latest_version = len(list(repo.iter_commits())) + 1
    current_version = latest_version - (
        len(list(repo.iter_commits(f"{current_hash}..{latest_hash}"))) + 1
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
    await message.edit("<code>Updating...</code>")

    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-U", "pip"])
        subprocess.run(["git", "pull"])
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
        restart()


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

    _prefix = args[0]
    db.set("core.main", "prefix", _prefix)
    await message.edit(f"<b>Prefix changed to:</b> <code>{_prefix}</code>")


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
async def _status(_, message: Message):
    common_args, _ = get_args(message)

    await message.edit("<code>Getting info...</code>")

    prefix = get_prefix()
    repo_link = "https://github.com/KurimuzonAkuma/Kurimuzon-Userbot"
    dev_link = "https://t.me/KurimuzonAkuma"
    cpu_usage = get_cpu_usage()
    ram_usage = get_ram_usage()
    repo = git.Repo()
    subprocess.run(["git", "fetch"])
    current_hash = repo.head.commit.hexsha
    latest_hash = repo.remotes.origin.refs.master.commit.hexsha
    latest_version = len(list(repo.iter_commits())) + 1
    current_version = latest_version - (
        len(list(repo.iter_commits(f"{current_hash}..{latest_hash}"))) + 1
    )
    current_time = arrow.get()
    uptime = current_time.shift(seconds=perf_counter() - bot_uptime)
    kernel_version = subprocess.run(["uname", "-a"], capture_output=True).stdout.decode().strip()
    system_uptime = subprocess.run(["uptime", "-p"], capture_output=True).stdout.decode().strip()

    result = (
        f"<emoji id=5219903664428167948>🤖</emoji> <a href='{repo_link}'>Kurimuzon-Userbot</a> / "
    )
    result += f"<a href='{repo_link}/commit/{current_hash}'>#{current_hash[:7]}</a>\n\n"
    result += f"<b>Pyrogram:</b> <code>{pyrogram.__version__}</code>\n"
    result += f"<b>Python:</b> <code>{sys.version}</code>\n"
    result += f"<b>Dev:</b> <a href='{dev_link}'>KurimuzonAkuma</a>\n\n"
    if "-a" not in common_args:
        return await message.edit(result, disable_web_page_preview=True)

    result += "<b>Bot status:</b>\n"
    result += (
        f"├─<b>Uptime:</b> <code>{uptime.humanize(current_time, only_distance=True)}</code>\n"
    )
    result += f"├─<b>Branch:</b> <code>{repo.active_branch}</code>\n"
    result += f"├─<b>Current version:</b> <a href='{repo_link}/commit/{current_hash}'>"
    result += f"├─#{current_hash[:7]} ({current_version})</a>\n"
    result += f"├─<b>Latest version:</b> <a href='{repo_link}/commit/{latest_hash}'>"
    result += f"├─#{latest_hash[:7]} ({latest_version})</a>\n"
    result += f"├─<b>Prefix:</b> <code>{prefix}</code>\n"
    result += f"├─<b>Modules:</b> <code>{modules_help.modules_count}</code>\n"
    result += f"└─<b>Commands:</b> <code>{modules_help.commands_count}</code>\n\n"

    result += "<b>System status:</b>\n"
    result += f"├─<b>OS:</b> <code>{sys.platform}</code>\n"
    result += f"├─<b>Kernel:</b> <code>{kernel_version}</code>\n"
    result += f"├─<b>Uptime:</b> <code>{system_uptime}</code>\n"
    result += f"├─<b>CPU usage:</b> <code>{cpu_usage}%</code>\n"
    result += f"└─<b>RAM usage:</b> <code>{ram_usage}MB</code>"

    await message.edit(result, disable_web_page_preview=True)


module = modules_help.add_module("base", __file__)
module.add_command("help", "Get common/module/command help.", "[module/command name]", ["h"])
module.add_command("prefix", "Set custom prefix", None, ["kprefix"])
module.add_command("restart", "Useful when you want to reload a bot")
module.add_command("update", "Update the userbot from the repository")
module.add_command("sendmod", "Send module to chat", "[module_name]", ["sm"])
module.add_command("status", "Get information about the userbot and system", "[-a]")
