import asyncio
import contextlib
import html
import logging
import random
import re
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from time import perf_counter
from traceback import format_exc
from typing import Optional

import pyrogram
from pyrogram import Client, enums, filters, raw, types
from pyrogram import utils as pyroutils
from pyrogram.types import LinkPreviewOptions, Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import format_bytes, format_time, paste_yaso, shell_exec

log = logging.getLogger(__name__)

async def progress(
    current: int,
    total: int,
    message: Optional["Message"] = None,
    update_interval: float = 1,
    width: int = 30,
    start_time: Optional[float] = None
) -> str:
    percentage = min((current / total) * 100, 100)
    filled = int((current / total) * width)
    bar = '█' * filled + '░' * (width - filled)

    is_download_done = total == 0 or current == total

    if is_download_done:
        percentage = "Done!"
    else:
        percentage = f"{percentage:5.1f}%"

    result = f"{percentage} |{bar}| [{format_bytes(current)}/{format_bytes(total)}"

    if start_time is not None:
        elapsed_time = time.time() - start_time

        if current > 0 and elapsed_time > 0:
            speed = current / elapsed_time

            result += f", {format_bytes(speed)}/s"

            if current < total:
                remaining = total - current
                eta_seconds = remaining / speed

                if not is_download_done:
                    result += f", ETA: {format_time(eta_seconds) if speed > 0 else '∞'}"

            result += f", Elapsed: {format_time(elapsed_time)}]"
    else:
        result += "]"

    if not is_download_done and (start_time is not None and not elapsed_time % update_interval < 0.1):
        return None

    log.info(result)

    if message:
        try:
            await message.edit(result)
        except Exception as e:
            log.error(e)

async def aexec(code, client: Client, message: Message, timeout=None):
    exec_globals = {
        "app": client,
        "c": client,
        "m": message,
        "r": message.reply_to_message,
        "u": message.from_user,
        "ru": getattr(message.reply_to_message, "from_user", None),
        "p": print,
        "here": message.chat.id,
        "db": db,
        "raw": raw,
        "rf": raw.functions,
        "rt": raw.types,
        "types": types,
        "enums": enums,
        "utils": pyroutils,
        "pyrogram": pyrogram,
        "progress": progress,
        "asyncio": asyncio
    }

    exec(
        "async def __todo(client, message, *args):\n"
        + "".join(f"\n {_l}" for _l in code.split("\n")),
        exec_globals,
    )

    f = StringIO()

    with redirect_stdout(f):
        await asyncio.wait_for(exec_globals["__todo"](client, message), timeout=timeout)

    return f.getvalue()


code_result = (
    "<blockquote><emoji id=5431376038628171216>💻</emoji> Code:</blockquote>\n"
    '<pre language="{pre_language}">{code}</pre>\n\n'
    "{result}"
)


def extract_code_from_reply(message: Message, language: str = None) -> Optional[str]:
    """Извлекает python-код из реплая или возвращает None."""
    if not message.reply_to_message:
        return None

    if language and message.reply_to_message.entities:
        for entity in message.reply_to_message.entities:
            if entity.type == enums.MessageEntityType.PRE and entity.language == language:
                return message.reply_to_message.content[
                    entity.offset : entity.offset + entity.length
                ]

    return message.reply_to_message.content


@Client.on_message(~filters.scheduled & command(["py", "rpy"]) & filters.me & ~filters.forwarded)
async def python_exec(client: Client, message: Message):
    code = ""

    if message.command[0] == "rpy":
        code = extract_code_from_reply(message, "python") or ""
    elif message.command[0] == "py":
        parts = message.content.split(maxsplit=1)
        code = parts[1] if len(parts) > 1 else ""

    if not code:
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    code = code.replace("\u00a0", "")

    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    try:
        start_time = perf_counter()
        result = await aexec(code, client, message, timeout=db.get("shell", "timeout", 60))
        elapsed = round(perf_counter() - start_time, 5)
    except asyncio.TimeoutError:
        return await message.edit_text(
            code_result.format(
                pre_language="python",
                code=html.escape(code),
                result="<blockquote><emoji id=5465665476971471368>❌</emoji> Timeout Error!</blockquote>",
            ),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        with redirect_stderr(StringIO()):
            err = "\n".join(
                line
                for i, line in enumerate(format_exc().splitlines(), start=1)
                if not 2 <= i <= 9
            )

        log.info("Exception from executed code:")
        for line in err.splitlines():
            log.info(f"\033[31m{line}\033[0m")

        return await message.edit_text(
            code_result.format(
                pre_language="python",
                code=html.escape(code),
                result=f"<blockquote><emoji id=5465665476971471368>❌</emoji> {e.__class__.__name__}: {e}</blockquote>\nTraceback: {html.escape(await paste_yaso(err))}",
            ),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

    # Replace account phone number to anonymous
    random_phone_number = "".join(str(random.randint(0, 9)) for _ in range(8))
    result = result.replace(client.me.phone_number, f"888{random_phone_number}")

    paste_result = ""

    if not result:
        result = "No result"
    elif len(result) > 512:
        paste_result = html.escape(await paste_yaso(result))

        if paste_result == "Pasting failed":
            error_bytes = BytesIO(result.encode("utf-8"))
            error_bytes.seek(0)
            error_bytes.name = "result.log"

            return await message.reply_document(
                document=error_bytes,
                caption=code_result.format(
                    pre_language="python",
                    code=html.escape(code),
                    result=f"<blockquote><emoji id=5472164874886846699>✨</emoji> Result is too long</blockquote>\n"
                    f"<i>Completed in {elapsed}s.</i>",
                ),
            )

    elif not re.match(r"^(https?):\/\/[^\s\/$.?#].[^\s]*$", result):
        result = f"<pre>{html.escape(result)}</pre>"

    if paste_result:
        return await message.edit_text(
            code_result.format(
                pre_language="python",
                code=html.escape(code),
                result=f"<blockquote><emoji id=5472164874886846699>✨</emoji> Result:</blockquote>\n"
                f"<pre>{result[:512]}...</pre>\n<blockquote><b><a href='{paste_result}'>More</a></b></blockquote>\n"
                f"<i>Completed in {elapsed}s.</i>",
            ),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    else:
        return await message.edit_text(
            code_result.format(
                pre_language="python",
                code=html.escape(code),
                result=f"<blockquote><emoji id=5472164874886846699>✨</emoji> Result:</blockquote>\n"
                f"{result}\n"
                f"<i>Completed in {elapsed}s.</i>",
            ),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


@Client.on_message(~filters.scheduled & command(["gcc", "rgcc"]) & filters.me & ~filters.forwarded)
async def gcc_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rgcc":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rgcc":
        code = extract_code_from_reply(message, "c")
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".c", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            timeout = db.get("shell", "timeout", 60)
            try:
                comp_start_time = perf_counter()
                rcode, stdout, stderr = await shell_exec(
                    command=f"gcc -o output {file.name}",
                    executable=db.get("shell", "executable"),
                    timeout=timeout,
                )
                comp_stop_time = perf_counter()

                if rcode != 0:
                    return await message.edit_text(
                        code_result.format(
                            pre_language="c",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>\n\n<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n",
                        ),
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )

                exec_start_time = perf_counter()
                rcode, stdout, stderr = await shell_exec(
                    command="./output",
                    executable=db.get("shell", "executable"),
                    timeout=timeout,
                )
                exec_stop_time = perf_counter()
            except asyncio.exceptions.TimeoutError:
                return await message.edit_text(
                    code_result.format(
                        pre_language="c",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            pre_language="c",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )

                result = None

                if len(stdout) > 3072:
                    result = html.escape(await paste_yaso(stdout))
                else:
                    result = f"<pre>{html.escape(stdout)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        pre_language="c",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )


@Client.on_message(~filters.scheduled & command(["gpp", "rgpp"]) & filters.me & ~filters.forwarded)
async def gpp_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rgpp":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rgpp":
        code = extract_code_from_reply(message, "cpp")
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".cpp", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            timeout = db.get("shell", "timeout", 60)
            try:
                comp_start_time = perf_counter()
                rcode, stdout, stderr = await shell_exec(
                    command=f"g++ -o output {file.name}",
                    executable=db.get("shell", "executable"),
                    timeout=timeout,
                )
                comp_stop_time = perf_counter()

                if rcode != 0:
                    return await message.edit_text(
                        code_result.format(
                            pre_language="cpp",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>\n\n<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n",
                        ),
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )

                exec_start_time = perf_counter()
                rcode, stdout, stderr = await shell_exec(
                    command="./output",
                    executable=db.get("shell", "executable"),
                    timeout=timeout,
                )
                exec_stop_time = perf_counter()
            except asyncio.exceptions.TimeoutError:
                return await message.edit_text(
                    code_result.format(
                        pre_language="cpp",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            pre_language="cpp",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )

                if len(stdout) > 3072:
                    result = html.escape(await paste_yaso(stdout))
                else:
                    result = f"<pre>{html.escape(stdout)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        pre_language="cpp",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )


@Client.on_message(~filters.scheduled & command(["lua", "rlua"]) & filters.me & ~filters.forwarded)
async def lua_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rlua":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rlua":
        code = extract_code_from_reply(message, "lua")
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".lua", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            timeout = db.get("shell", "timeout", 60)
            try:
                exec_start_time = perf_counter()
                rcode, stdout, stderr = await shell_exec(
                    command=f"lua {file.name}",
                    executable=db.get("shell", "executable"),
                    timeout=timeout,
                )
                exec_stop_time = perf_counter()
            except asyncio.exceptions.TimeoutError:
                return await message.edit_text(
                    code_result.format(
                        pre_language="lua",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            pre_language="lua",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )

                if len(stdout) > 3072:
                    result = html.escape(await paste_yaso(stdout))
                else:
                    result = f"<pre>{html.escape(stdout)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        pre_language="lua",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )


@Client.on_message(~filters.scheduled & command(["go", "rgo"]) & filters.me & ~filters.forwarded)
async def go_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rgo":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rgo":
        code = extract_code_from_reply(message, "go")
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".go", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            timeout = db.get("shell", "timeout", 60)
            try:
                exec_start_time = perf_counter()
                rcode, stdout, stderr = await shell_exec(
                    command=f"go run {file.name}",
                    executable=db.get("shell", "executable"),
                    timeout=timeout,
                )
                exec_stop_time = perf_counter()
            except asyncio.exceptions.TimeoutError:
                return await message.edit_text(
                    code_result.format(
                        pre_language="go",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            pre_language="go",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )

                if len(stdout) > 3072:
                    result = html.escape(await paste_yaso(stdout))
                else:
                    result = f"<pre>{html.escape(stdout)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        pre_language="go",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )


@Client.on_message(
    ~filters.scheduled & command(["node", "rnode"]) & filters.me & ~filters.forwarded
)
async def node_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rnode":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rnode":
        code = extract_code_from_reply(message, "javascript")
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".js", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            timeout = db.get("shell", "timeout", 60)
            try:
                exec_start_time = perf_counter()
                rcode, stdout, stderr = await shell_exec(
                    command=f"node {file.name}",
                    executable=db.get("shell", "executable"),
                    timeout=timeout,
                )
                exec_stop_time = perf_counter()
            except asyncio.exceptions.TimeoutError:
                return await message.edit_text(
                    code_result.format(
                        pre_language="javascript",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            pre_language="javascript",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )

                if len(stdout) > 3072:
                    result = html.escape(await paste_yaso(stdout))
                else:
                    result = f"<pre>{html.escape(stdout)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        pre_language="javascript",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )


module = modules_help.add_module("code_runner", __file__)
module.add_command("py", "Execute Python code", "[code]")
module.add_command("rpy", "Execute Python code from reply")
module.add_command("gcc", "Execute C code", "[code]")
module.add_command("rgcc", "Execute C code from reply")
module.add_command("gpp", "Execute C++ code", "[code]")
module.add_command("rgpp", "Execute C++ code from reply")
module.add_command("lua", "Execute Lua code", "[code]")
module.add_command("rlua", "Execute Lua code from reply")
module.add_command("go", "Execute Go code", "[code]")
module.add_command("rgo", "Execute Go code from reply")
module.add_command("node", "Execute Node.js code", "[code]")
module.add_command("rnode", "Execute Node.js code from reply")
