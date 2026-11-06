import asyncio
import html
import os
import shutil
from time import perf_counter

from pyrogram import filters
from pyrogram.types import Message

from utils import loader
from utils.db import db
from utils.loader import CommandArg, Plugin
from utils.scripts import get_args, get_args_raw, shell_exec


class Shell(Plugin):
    @loader.command(
        ["shell", "sh"],
        description="Execute a command in the shell",
        args=[CommandArg("command", "shell command to execute", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def shell(self, _, message: Message):
        cmd_text = get_args_raw(message)
        if not cmd_text:
            return await message.edit("<b>Command is not provided</b>")

        await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")
        text = (
            "<b><emoji id=5821388137443626414>🌐</emoji> Language:</b>\n<code>Shell</code>\n\n"
            "<b><emoji id=5431376038628171216>💻</emoji> Command:</b>\n"
            f'<pre language="sh">{html.escape(cmd_text)}</pre>\n\n'
        )
        timeout = db.get("shell", "timeout", 60)

        try:
            start_time = perf_counter()
            rcode, stdout, stderr = await shell_exec(
                command=cmd_text,
                executable=db.get("shell", "executable"),
                timeout=timeout,
            )
        except asyncio.exceptions.TimeoutError:
            text += (
                "<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n"
                f"<b>Timeout expired ({timeout} seconds)</b>"
            )
        else:
            stop_time = perf_counter()
            text += "<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
            text += f"<code>{html.escape(stderr or stdout)}</code>"
            text += (
                f"<b>Completed in {round(stop_time - start_time, 5)} seconds with code {rcode}</b>"
            )

        await message.edit(text)

    @loader.command(
        "shcfg",
        description="Configure shell execution",
        args=[
            CommandArg("-t", "timeout", required=False),
            CommandArg("-e", "executable", required=False),
        ],
        filters=filters.me,
    )
    async def shcfg(self, _, message: Message):
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
                return await message.edit_text("-e should be an executable path")
            db.set("shell", "executable", executable)

        if timeout:
            if not timeout.lstrip("-").isdigit():
                return await message.edit_text("-t should be a number")
            db.set("shell", "timeout", float(timeout))

        return await message.edit_text(
            "<b>Parameters set!</b>\n\n<b>Current config:</b>\n"
            f"<b>• Executable:</b> <code>{db.get('shell', 'executable')}</code>\n"
            f"<b>• Timeout:</b> <code>{db.get('shell', 'timeout')}</code>"
        )
