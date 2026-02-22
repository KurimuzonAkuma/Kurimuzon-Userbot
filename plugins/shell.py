import asyncio
import html
import os
import shutil
from time import perf_counter

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args, get_args_raw, shell_exec, with_args


@Client.on_message(
    ~filters.scheduled & command(["shell", "sh"]) & filters.me & ~filters.forwarded
)
@with_args("<b>Command is not provided</b>")
async def shell_handler(_: Client, message: Message):
    await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    cmd_text = get_args_raw(message)

    text = (
        "<b><emoji id=5821388137443626414>🌐</emoji> Language:</b>\n<code>Shell</code>\n\n"
        "<b><emoji id=5431376038628171216>💻</emoji> Command:</b>\n"
        f'<pre language="sh">{html.escape(cmd_text)}</pre>\n\n'
    )

    timeout = db.get("shell", "timeout", 60)
    try:
        start_time = perf_counter()
        rcode, stdout, stderr = await shell_exec(
            command=cmd_text, executable=db.get("shell", "executable"), timeout=timeout
        )
    except asyncio.exceptions.TimeoutError:
        text += (
            "<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n"
            f"<b>Timeout expired ({timeout} seconds)</b>"
        )
    else:
        stop_time = perf_counter()
        text += (
            "<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
            f"<code>{html.escape(stderr or stdout)}</code>"
        )
        text += f"<b>Completed in {round(stop_time - start_time, 5)} seconds with code {rcode}</b>"

    await message.edit(text)


@Client.on_message(command(["shcfg"]) & filters.me)
async def shell_config_handler(_: Client, message: Message):
    args, nargs = get_args(message)

    if not args:
        return await message.edit_text(
            "<b>Current config:</b>\n"
            f"<b>• Executable:</b> <code>{db.get('shell', 'executable')}</code>\n"
            f"<b>• Timeout:</b> <code>{db.get('shell', 'timeout')}</code>"
        )

    executable = nargs.get("-e")
    timeout = nargs.get("-t")

    if executable:
        if not shutil.which(executable) and not os.access(executable, os.X_OK):
            return await message.edit_text("-e should be executable path")
        db.set("shell", "executable", executable)

    if timeout:
        if not nargs.get("-t").lstrip("-").isdigit():
            return await message.edit_text("-t should be number")
        db.set("shell", "timeout", float(timeout))

    return await message.edit_text(
        "<b>Params set!</b>\n\n"
        "<b>Current config:</b>\n"
        f"<b>• Executable:</b> <code>{db.get('shell', 'executable')}</code>\n"
        f"<b>• Timeout:</b> <code>{db.get('shell', 'timeout')}</code>"
    )


module = modules_help.add_module("shell", __file__)
module.add_command("shell", "Execute command in shell", "[command]", ["sh"])
module.add_command("shcfg", "Shell configuration", "[-t] [-e]")
