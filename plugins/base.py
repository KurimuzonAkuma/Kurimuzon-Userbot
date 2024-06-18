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
    shell_exec,
    with_args,
)


@Client.on_message(~filters.scheduled & command(["help", "h"]) & filters.me & ~filters.forwarded)
async def show_help(client: Client, message: Message):
    args, _ = get_args(message)
    try:
        if not args:
            is_edited = False
            for text in modules_help.help():
                if is_edited:
                    await message.reply(text, disable_web_page_preview=True)
                else:
                    await message.edit(text, disable_web_page_preview=True)
                    is_edited = True
        else:
            if args[0] in modules_help.modules:
                await message.edit(modules_help.module_help(args[0]), disable_web_page_preview=True)
            else:
                await message.edit(modules_help.command_help(args[0]), disable_web_page_preview=True)
    except ValueError as e:
        await message.edit(e)


@Client.on_message(~filters.scheduled & command(["restart"]) & filters.me & ~filters.forwarded)
async def restart_bot(client: Client, message: Message):
    db.set("core.updater", "restart_info", {
        "chat_id": message.chat.id,
        "message_id": message.id,
        "time": perf_counter(),
        "type": "restart"
    })
    await message.edit("<code>Restarting...</code>")
    restart()


@Client.on_message(~filters.scheduled & command(["update"]) & filters.me & ~filters.forwarded)
async def update_bot(client: Client, message: Message):
    await message.edit("<code>Updating...</code>")
    args, _ = get_args(message)

    repo = git.Repo()
    current_hash = repo.head.commit.hexsha
    repo.remote("origin").fetch()
    branch = repo.active_branch.name
    latest_commit = next(repo.iter_commits(f"origin/{branch}", max_count=1)).hexsha

    if current_hash == latest_commit:
        await message.edit("<b>Userbot is already up to date</b>")
        return

    if "--hard" in args:
        await shell_exec("git reset --hard HEAD")

    try:
        repo.remote("origin").pull()
    except git.exc.GitCommandError as e:
        await message.edit(f"<b>Update failed! Try again with --hard argument.</b>\n\n<code>{e.stderr.strip()}</code>")
        return

    current_version = len(list(repo.iter_commits()))
    updated_version = current_version - len(list(repo.iter_commits(f"{current_hash}..{latest_commit}")))

    db.set("core.updater", "restart_info", {
        "chat_id": message.chat.id,
        "message_id": message.id,
        "time": perf_counter(),
        "hash": current_hash,
        "version": f"{updated_version}",
        "type": "update"
    })

    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-U", "pip"])
        subprocess.run([sys.executable, "-m", "pip", "install", "-U", "-r", "requirements.txt"])
    except Exception as e:
        await message.edit(format_exc(e))
        db.remove("core.updater", "restart_info")
    else:
        restart()


@Client.on_message(~filters.scheduled & command(["kprefix", "prefix"]) & filters.me & ~filters.forwarded)
async def change_prefix(client: Client, message: Message):
    args, _ = get_args(message)
    current_prefix = get_prefix()

    if not args:
        await message.edit_text(
            f"Current prefix: <code>{current_prefix}</code>\n"
            f"To change prefix use <code>{current_prefix}{message.command[0]} [new prefix]</code>"
        )
        return

    new_prefix = args[0]
    db.set("core.main", "prefix", new_prefix)
    await message.edit(f"<b>Prefix changed to:</b> <code>{new_prefix}</code>")


@Client.on_message(~filters.scheduled & command(["sendmod", "sm"]) & filters.me & ~filters.forwarded)
@with_args("<b>Module name to send is not provided</b>")
async def send_module(client: Client, message: Message):
    args, _ = get_args(message)
    module_name = args[0]

    if module_name in modules_help.modules:
        await message.delete()
        help_text = modules_help.module_help(module_name, False)
        module_path = modules_help.modules[module_name].path

        if os.path.isfile(module_path):
            await client.send_document(
                message.chat.id,
                module_path,
                caption=help_text,
            )
    else:
        await message.edit(f"<b>Module {module_name} not found!</b>")


@Client.on_message(~filters.scheduled & command(["status"]) & filters.me & ~filters.forwarded)
async def show_status(client: Client, message: Message):
    args, _ = get_args(message)
    await message.edit("<code>Getting info...</code>")

    prefix = get_prefix()
    repo_link = "https://github.com/KurimuzonAkuma/Kurimuzon-Userbot"
    dev_link = "https://t.me/KurimuzonAkuma"
    cpu_usage = get_cpu_usage()
    ram_usage = get_ram_usage()
    current_time = arrow.get()
    uptime = current_time.shift(seconds=perf_counter() - bot_uptime)
    kernel_version = subprocess.run(["uname", "-a"], capture_output=True).stdout.decode().strip()
    system_uptime = subprocess.run(["uptime", "-p"], capture_output=True).stdout.decode().strip()

    repo = git.Repo()
    current_hash = repo.head.commit.hexsha
    repo.remote("origin").fetch()
    branch = repo.active_branch.name
    latest_commit = next(repo.iter_commits(f"origin/{branch}", max_count=1)).hexsha
    current_version = len(list(repo.iter_commits()))
    latest_version = current_version - len(list(repo.iter_commits(f"{current_hash}..{latest_commit}")))

    result = (
        f"<emoji id=5219903664428167948>🤖</emoji> <a href='{repo_link}'>Kurimuzon-Userbot</a> / "
        f"<a href='{repo_link}/commit/{current_hash}'>#{current_hash[:7]} ({latest_version})</a>\n\n"
        f"<b>Pyrogram:</b> <code>{pyrogram.__version__}</code>\n"
        f"<b>Python:</b> <code>{sys.version}</code>\n"
        f"<b>Dev:</b> <a href='{dev_link}'>KurimuzonAkuma</a>\n\n"
    )

    if "-a" not in args:
        await message.edit(result, disable_web_page_preview=True)
        return

    result += (
        "<b>Bot status:</b>\n"
        f"├─<b>Uptime:</b> <code>{uptime.humanize(current_time, only_distance=True)}</code>\n"
        f"├─<b>Branch:</b> <code>{branch}</code>\n"
        f"├─<b>Current version:</b> <a href='{repo_link}/commit/{current_hash}'>#{current_hash[:7]} ({current_version})</a>\n"
        f"├─<b>Latest version:</b> <a href='{repo_link}/commit/{latest_commit}'>#{latest_commit[:7]} ({latest_version})</a>\n"
        f"├─<b>Prefix:</b> <code>{prefix}</code>\n"
        f"├─<b>Modules:</b> <code>{modules_help.modules_count}</code>\n"
        f"└─<b>Commands:</b> <code>{modules_help.commands_count}</code>\n\n"
        "<b>System status:</b>\n"
        f"├─<b>OS:</b> <code>{sys.platform}</code>\n"
        f"├─<b>Kernel:</b> <code>{kernel_version}</code>\n"
        f"├─<b>Uptime:</b> <code>{system_uptime}</code>\n"
        f"├─<b>CPU usage:</b> <code>{cpu_usage}%</code>\n"
        f"└─<b>RAM usage:</b> <code>{ram_usage}MB</code>"
    )

    await message.edit(result, disable_web_page_preview=True)


module = modules_help.add_module("base", __file__)
module.add_command("help", "Get common/module/command help.", "[module/command name]", ["h"])
module.add_command("prefix", "Set custom prefix", None, ["kprefix"])
module.add_command("restart", "Useful when you want to reload the bot")
module.add_command("update", "Update the userbot from the repository")
module.add_command("sendmod", "Send module to chat", "[module_name]", ["sm"])
module.add_command("status", "Get information about the userbot and system", "[-a]")
