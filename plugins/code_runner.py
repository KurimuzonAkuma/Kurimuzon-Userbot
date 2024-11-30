import asyncio
import html
import re
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from time import perf_counter
from traceback import print_exc

from pyrogram import Client, enums, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import paste_neko, shell_exec


async def aexec(code, *args, timeout=None):
    exec(
        "async def __todo(client, message, *args):\n"
        + " from pyrogram import raw, types, enums\n"
        + " from utils.db import db\n"
        + " app = client\n"
        + " m = message\n"
        + " r = m.reply_to_message\n"
        + " u = m.from_user\n"
        + " ru = getattr(r, 'from_user', None)\n"
        + " p = print\n"
        + " here = m.chat.id\n"
        + "".join(f"\n {_l}" for _l in code.split("\n"))
    )

    f = StringIO()
    with redirect_stdout(f):
        await asyncio.wait_for(locals()["__todo"](*args), timeout=timeout)

    return f.getvalue()


code_result = (
    "<b><emoji id={emoji_id}>🌐</emoji> Language:</b>\n"
    "<code>{language}</code>\n\n"
    "<b><emoji id=5431376038628171216>💻</emoji> Code:</b>\n"
    '<pre language="{pre_language}">{code}</pre>\n\n'
    "{result}"
)


@Client.on_message(~filters.scheduled & command(["py", "rpy"]) & filters.me & ~filters.forwarded)
async def python_exec(client: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rpy":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rpy":
        if not message.reply_to_message:
            return await message.edit_text("<b>Code to execute isn't provided</b>")

        # Check if message is a reply to message with already executed code
        for entity in message.reply_to_message.entities:
            if entity.type == enums.MessageEntityType.PRE and entity.language == "python":
                code = message.reply_to_message.text[entity.offset : entity.offset + entity.length]
                break
        else:
            code = message.reply_to_message.text
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    try:
        code = code.replace("\u00A0", "")

        start_time = perf_counter()
        result = await aexec(code, client, message, timeout=db.get("shell", "timeout", 60))
        stop_time = perf_counter()

        # Replace account phone number to anonymous
        result = result.replace(client.me.phone_number, "88806524973")

        if not result:
            result = "No result"
        elif len(result) > 3072:
            paste_result = html.escape(await paste_neko(result))

            if paste_result == "Pasting failed!":
                with open("error.log", "w") as file:
                    file.write(result)

                result = None
            else:
                result = paste_result

        elif re.match(r"^(https?):\/\/[^\s\/$.?#].[^\s]*$", result):
            result = html.escape(result)
        else:
            result = f"<pre>{html.escape(result)}</pre>"

        if result:
            return await message.edit_text(
                code_result.format(
                    emoji_id=5260480440971570446,
                    language="Python",
                    pre_language="python",
                    code=html.escape(code),
                    result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                    f"{result}\n"
                    f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>",
                ),
                disable_web_page_preview=True,
            )
        else:
            return await message.reply_document(
                document="error.log",
                caption=code_result.format(
                    emoji_id=5260480440971570446,
                    language="Python",
                    pre_language="python",
                    code=html.escape(code),
                    result=f"<b><emoji id=5472164874886846699>✨</emoji> Result is too long</b>\n"
                    f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>",
                ),
            )
    except asyncio.TimeoutError:
        return await message.edit_text(
            code_result.format(
                emoji_id=5260480440971570446,
                language="Python",
                pre_language="python",
                code=html.escape(code),
                result="<b><emoji id=5465665476971471368>❌</emoji> Timeout Error!</b>",
            ),
            disable_web_page_preview=True,
        )
    except Exception as e:
        err = StringIO()
        with redirect_stderr(err):
            print_exc()

        return await message.edit_text(
            code_result.format(
                emoji_id=5260480440971570446,
                language="Python",
                pre_language="python",
                code=html.escape(code),
                result=f"<b><emoji id=5465665476971471368>❌</emoji> {e.__class__.__name__}: {e}</b>\n"
                f"Traceback: {html.escape(await paste_neko(err.getvalue()))}",
            ),
            disable_web_page_preview=True,
        )


@Client.on_message(~filters.scheduled & command(["gcc", "rgcc"]) & filters.me & ~filters.forwarded)
async def gcc_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rgcc":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rgcc":
        code = message.reply_to_message.text
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
                            emoji_id=5257955893554721164,
                            language="C",
                            pre_language="c",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>\n\n<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n",
                        ),
                        disable_web_page_preview=True,
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
                        emoji_id=5257955893554721164,
                        language="C",
                        pre_language="c",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    disable_web_page_preview=True,
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            emoji_id=5257955893554721164,
                            language="C",
                            pre_language="c",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        disable_web_page_preview=True,
                    )

                if len(stdout) > 3072:
                    result = html.escape(await paste_neko(stdout))
                else:
                    result = f"<pre>{html.escape(result)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        emoji_id=5257955893554721164,
                        language="C",
                        pre_language="c",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    disable_web_page_preview=True,
                )


@Client.on_message(~filters.scheduled & command(["gpp", "rgpp"]) & filters.me & ~filters.forwarded)
async def gpp_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rgpp":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rgpp":
        code = message.reply_to_message.text
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
                            emoji_id=5258035603852767295,
                            language="C++",
                            pre_language="cpp",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>\n\n<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n",
                        ),
                        disable_web_page_preview=True,
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
                        emoji_id=5258035603852767295,
                        language="C++",
                        pre_language="cpp",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    disable_web_page_preview=True,
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            emoji_id=5258035603852767295,
                            language="C++",
                            pre_language="cpp",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        disable_web_page_preview=True,
                    )

                if len(stdout) > 3072:
                    result = html.escape(await paste_neko(stdout))
                else:
                    result = f"<pre>{html.escape(result)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        emoji_id=5258035603852767295,
                        language="C++",
                        pre_language="cpp",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    disable_web_page_preview=True,
                )


@Client.on_message(~filters.scheduled & command(["lua", "rlua"]) & filters.me & ~filters.forwarded)
async def lua_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rlua":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rlua":
        code = message.reply_to_message.text
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
                        emoji_id=5258338381867266341,
                        language="Lua",
                        pre_language="lua",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    disable_web_page_preview=True,
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            emoji_id=5258338381867266341,
                            language="Lua",
                            pre_language="lua",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        disable_web_page_preview=True,
                    )

                if len(stdout) > 3072:
                    result = html.escape(await paste_neko(stdout))
                else:
                    result = f"<pre>{html.escape(result)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        emoji_id=5258338381867266341,
                        language="Lua",
                        pre_language="lua",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    disable_web_page_preview=True,
                )


@Client.on_message(~filters.scheduled & command(["go", "rgo"]) & filters.me & ~filters.forwarded)
async def go_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rgo":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rgo":
        code = message.reply_to_message.text
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
                        emoji_id=5258117049317603088,
                        language="Go",
                        pre_language="go",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    disable_web_page_preview=True,
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            emoji_id=5258117049317603088,
                            language="Go",
                            pre_language="go",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        disable_web_page_preview=True,
                    )

                if len(stdout) > 3072:
                    result = html.escape(await paste_neko(stdout))
                else:
                    result = f"<pre>{html.escape(result)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        emoji_id=5258117049317603088,
                        language="Go",
                        pre_language="go",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    disable_web_page_preview=True,
                )


@Client.on_message(
    ~filters.scheduled & command(["node", "rnode"]) & filters.me & ~filters.forwarded
)
async def node_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rnode":
        return await message.edit_text("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rnode":
        code = message.reply_to_message.text
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
                        emoji_id=5258042115023188415,
                        language="Node.js",
                        pre_language="javascript",
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    disable_web_page_preview=True,
                )
            else:
                if stderr:
                    return await message.edit_text(
                        code_result.format(
                            emoji_id=5258042115023188415,
                            language="Node.js",
                            pre_language="javascript",
                            code=html.escape(code),
                            result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {rcode}:</b>\n"
                            f"<code>{html.escape(stderr)}</code>",
                        ),
                        disable_web_page_preview=True,
                    )

                if len(stdout) > 3072:
                    result = html.escape(await paste_neko(stdout))
                else:
                    result = f"<pre>{html.escape(result)}</pre>"

                return await message.edit_text(
                    code_result.format(
                        emoji_id=5258042115023188415,
                        language="Node.js",
                        pre_language="javascript",
                        code=html.escape(code),
                        result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                        f"{result}\n\n"
                        f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                    ),
                    disable_web_page_preview=True,
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
