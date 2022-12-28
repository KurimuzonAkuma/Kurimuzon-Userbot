import html
from subprocess import PIPE, Popen, TimeoutExpired
from time import perf_counter

from pyrogram import Client, filters, types

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import with_args


@Client.on_message(command(["shell", "sh"]) & filters.me)
@with_args("<b>Command is not provided</b>")
async def shell(_, message: types.Message):
    await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    cmd_text = message.text.split(maxsplit=1)[1]
    cmd_obj = Popen(
        cmd_text,
        shell=True,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
        executable="/usr/bin/zsh",
    )

    text = (
        "<b><emoji id=5821388137443626414>🌐</emoji> Language:</b>\n<code>Shell</code>\n\n"
        "<b><emoji id=5431376038628171216>💻</emoji> Command:</b>\n"
        f'<pre language="sh">{html.escape(cmd_text)}</pre>\n\n'
    )

    try:
        start_time = perf_counter()
        stdout, stderr = cmd_obj.communicate(timeout=60)
    except TimeoutExpired:
        text += (
            "<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n"
            "<b>Timeout expired (60 seconds)</b>"
        )
    else:
        stop_time = perf_counter()
        text += (
            "<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
            f"<code>{html.escape(stderr or stdout)}</code>"
        )
        text += f"<b>Completed in {round(stop_time - start_time, 5)} seconds with code {cmd_obj.returncode}</b>"
    await message.edit(text)
    cmd_obj.kill()


modules_help["shell"] = {"sh [command]": "Execute command in shell"}
