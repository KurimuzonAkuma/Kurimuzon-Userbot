import asyncio
import html
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from time import perf_counter

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import format_exc, paste_neko


async def aexec(code, client, message):
    temp_name = f"__{next(tempfile._get_candidate_names())}"
    code = (
        f"async def {temp_name}(message, client):\n"
        + " app = client\n"
        + " m = message\n"
        + " r = message.reply_to_message\n"
        + "".join(f"\n {_l}" for _l in code.split("\n"))
    )

    f = StringIO()
    exec(code)
    with redirect_stdout(f):
        await locals()[temp_name](message, client)
    return f.getvalue()


async def interpreter_task(client: Client, message: Message):
    if len(message.command) == 1 and message.command[0] not in ["rpy", "rpyne"]:
        await message.edit("<b>Code to execute isn't provided</b>")
        return

    if message.command[0] in ["rpy", "rpyne"]:
        code = message.reply_to_message.text
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    try:
        start_time = perf_counter()
        result = await aexec(code, client, message)
        stop_time = perf_counter()

        if len(result) > 4000:
            result = await paste_neko(result)

        text = (
            "<b><emoji id=5821388137443626414>🌐</emoji> Language:</b>\n<code>Python</code>\n\n"
            "<b><emoji id=5431376038628171216>💻</emoji> Code:</b>\n"
            f'<pre language="python">{html.escape(code)}</pre>\n\n'
            "<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
            f"<code>{html.escape(result)}</code>\n"
            f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>"
        )

        if message.command[0] in ["pyne", "rpyne"]:
            await message.reply(text)
        else:
            await message.edit(text)
    except Exception as ex:
        await message.edit(
            "<b><emoji id=5821388137443626414>🌐</emoji> Language:</b>\n<code>Python</code>\n\n"
            f"<b><emoji id=5431376038628171216>💻</emoji> Code:</b>\n"
            f"<code>{html.escape(code)}</code>\n\n"
            f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n"
            f"<code>{format_exc(ex)}</code>",
        )


@Client.on_message(~filters.scheduled & command(["py", "pyne", "rpy", "rpyne"]) & filters.me)
async def user_exec(client: Client, message: Message):
    client.loop.create_task(interpreter_task(client, message))


modules_help["python"] = {
    "py [python code]": "Execute Python code",
    "pyne [python code]": "Execute Python code and return result with reply",
    "rpy": "Execute Python code from reply",
}
