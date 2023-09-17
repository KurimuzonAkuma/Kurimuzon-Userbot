import asyncio
import html
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from time import perf_counter
from traceback import print_exc

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import paste_neko


async def aexec(code, *args, timeout=None):
    exec(
        f"async def __todo(client, message, *args):\n"
        + " app = client; "
        + " m = message; "
        + " r = m.reply_to_message; "
        + " u = m.from_user; "
        + " ru = getattr(r, 'from_user', None)\n"
        + "".join(f"\n {_l}" for _l in code.split("\n"))
    )

    f = StringIO()
    with redirect_stdout(f):
        await asyncio.wait_for(locals()["__todo"](*args), timeout=timeout)

    return f.getvalue()


code_result = (
    "<b><emoji id=5821388137443626414>🌐</emoji> Language:</b>\n"
    "<code>{language}</code>\n\n"
    "<b><emoji id=5431376038628171216>💻</emoji> Code:</b>\n"
    '<pre language="{pre_language}">{code}</pre>\n\n'
    "{result}"
)


@Client.on_message(~filters.scheduled & command(["py", "rpy"]) & filters.me & ~filters.forwarded)
async def python_exec(client: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rpy":
        return await message.edit("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rpy":
        code = message.reply_to_message.text
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    try:
        start_time = perf_counter()
        result = await aexec(code, client, message, timeout=60)
        stop_time = perf_counter()

        if len(result) > 3072:
            result = html.escape(await paste_neko(result))
        else:
            result = f"<code>{html.escape(result)}</code>"

        return await message.edit(
            code_result.format(
                language="Python",
                pre_language="python",
                code=code,
                result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                f"{result}\n"
                f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>",
            )
        )
    except asyncio.TimeoutError:
        return await message.edit(
            code_result.format(
                language="Python",
                pre_language="python",
                code=code,
                result="<b><emoji id=5465665476971471368>❌</emoji> Timeout Error!</b>",
            )
        )
    except Exception as e:
        err = StringIO()
        with redirect_stderr(err):
            print_exc()

        return await message.edit(
            code_result.format(
                language="Python",
                pre_language="python",
                code=code,
                result=f"<b><emoji id=5465665476971471368>❌</emoji> {e.__class__.__name__}: {e}</b>\n"
                f"Traceback: {html.escape(await paste_neko(err.getvalue()))}",
            )
        )


@Client.on_message(~filters.scheduled & command(["gcc", "rgcc"]) & filters.me & ~filters.forwarded)
async def gcc_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rpy":
        return await message.edit("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rpy":
        code = message.reply_to_message.text
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".c", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            comp_start_time = perf_counter()
            compiled_file = subprocess.run(
                f"gcc -o output {file.name}",
                shell=True,
                capture_output=True,
                text=True,
                cwd=tempdir,
                executable=db.get("shell", "executable"),
            )
            comp_stop_time = perf_counter()

            if compiled_file.returncode != 0:
                return await message.edit_text(
                    code_result.format(
                        language="C",
                        pre_language="c",
                        code=code,
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error with status code {compiled_file.returncode}:</b>\n"
                        f"<code>{html.escape(compiled_file.stderr)}</code>",
                    )
                )

            exec_start_time = perf_counter()
            result = subprocess.run(
                "./output",
                shell=True,
                capture_output=True,
                text=True,
                cwd=tempdir,
                executable=db.get("shell", "executable"),
            )
            exec_stop_time = perf_counter()

            if result.stderr:
                return await message.edit_text(
                    code_result.format(
                        language="C",
                        pre_language="c",
                        code=code,
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {compiled_file.returncode}:</b>\n"
                        f"<code>{html.escape(compiled_file.stderr)}</code>",
                    )
                )

            if len(result.stdout) > 3072:
                result = html.escape(await paste_neko(result.stdout))
            else:
                result = f"<code>{html.escape(result.stdout)}</code>"

            return await message.edit_text(
                code_result.format(
                    language="C",
                    pre_language="c",
                    code=code,
                    result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                    f"{result}\n"
                    f"<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n"
                    f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                )
            )


@Client.on_message(~filters.scheduled & command(["gpp", "rgpp"]) & filters.me & ~filters.forwarded)
async def gpp_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rgpp":
        return await message.edit("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rgpp":
        code = message.reply_to_message.text
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".cpp", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            comp_start_time = perf_counter()
            compiled_file = subprocess.run(
                f"g++ -o output {file.name}",
                shell=True,
                capture_output=True,
                text=True,
                cwd=tempdir,
                executable=db.get("shell", "executable"),
            )
            comp_stop_time = perf_counter()

            if compiled_file.returncode != 0:
                return await message.edit_text(
                    code_result.format(
                        language="C++",
                        pre_language="c++",
                        code=code,
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error with status code {compiled_file.returncode}:</b>\n"
                        f"<code>{html.escape(compiled_file.stderr)}</code>",
                    )
                )

            exec_start_time = perf_counter()
            result = subprocess.run(
                "./output",
                shell=True,
                capture_output=True,
                text=True,
                cwd=tempdir,
                executable=db.get("shell", "executable"),
            )
            exec_stop_time = perf_counter()

            if result.stderr:
                return await message.edit_text(
                    code_result.format(
                        language="C++",
                        pre_language="c++",
                        code=code,
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error with status code {compiled_file.returncode}:</b>\n"
                        f"<code>{html.escape(compiled_file.stderr)}</code>",
                    )
                )

            if len(result.stdout) > 3072:
                result = html.escape(await paste_neko(result.stdout))
            else:
                result = f"<code>{html.escape(result.stdout)}</code>"

            return await message.edit_text(
                code_result.format(
                    language="C++",
                    pre_language="c++",
                    code=code,
                    result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                    f"{result}\n"
                    f"<b>Compiled in {round(comp_stop_time - comp_start_time, 5)}s.</b>\n"
                    f"<b>Completed in {round(exec_stop_time - exec_start_time, 5)}s.</b>",
                )
            )


@Client.on_message(~filters.scheduled & command(["lua", "rlua"]) & filters.me & ~filters.forwarded)
async def lua_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rlua":
        return await message.edit("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rlua":
        code = message.reply_to_message.text
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".lua", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            start_time = perf_counter()
            result = subprocess.run(
                f"lua {file.name}",
                shell=True,
                capture_output=True,
                text=True,
                cwd=tempdir,
                executable=db.get("shell", "executable"),
            )
            stop_time = perf_counter()

            if result.stderr:
                return await message.edit_text(
                    code_result.format(
                        language="C++",
                        pre_language="c++",
                        code=code,
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error with status code {result.returncode}</b>\n"
                        f"<code>{html.escape(result.stderr)}</code>",
                    )
                )

            if len(result.stdout) > 3072:
                result = html.escape(await paste_neko(result.stdout))
            else:
                result = f"<code>{html.escape(result.stdout)}</code>"

            return await message.edit_text(
                code_result.format(
                    language="Lua",
                    pre_language="lua",
                    code=code,
                    result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                    f"{result}\n"
                    f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>",
                )
            )


@Client.on_message(~filters.scheduled & command(["go", "rgo"]) & filters.me & ~filters.forwarded)
async def go_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rgo":
        return await message.edit("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rgo":
        code = message.reply_to_message.text
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".go", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            start_time = perf_counter()
            result = subprocess.run(
                f"go run {file.name}",
                shell=True,
                capture_output=True,
                text=True,
                cwd=tempdir,
                executable=db.get("shell", "executable"),
            )
            stop_time = perf_counter()

            if result.stderr:
                return await message.edit_text(
                    code_result.format(
                        language="Go",
                        pre_language="go",
                        code=code,
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error with status code {result.returncode}</b>\n"
                        f"<code>{html.escape(result.stderr)}</code>",
                    )
                )

            if len(result.stdout) > 3072:
                result = html.escape(await paste_neko(result.stdout))
            else:
                result = f"<code>{html.escape(result.stdout)}</code>"

            return await message.edit_text(
                code_result.format(
                    language="Go",
                    pre_language="go",
                    code=code,
                    result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                    f"{result}\n"
                    f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>",
                )
            )


@Client.on_message(
    ~filters.scheduled & command(["node", "rnode"]) & filters.me & ~filters.forwarded
)
async def node_exec(_: Client, message: Message):
    if len(message.command) == 1 and message.command[0] != "rnode":
        return await message.edit("<b>Code to execute isn't provided</b>")

    if message.command[0] == "rnode":
        code = message.reply_to_message.text
    else:
        code = message.text.split(maxsplit=1)[1]

    await message.edit("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

    with tempfile.TemporaryDirectory() as tempdir:
        with tempfile.NamedTemporaryFile("w+", suffix=".js", dir=tempdir) as file:
            file.write(code)
            file.seek(0)

            start_time = perf_counter()
            result = subprocess.run(
                f"node {file.name}",
                shell=True,
                capture_output=True,
                text=True,
                cwd=tempdir,
                executable=db.get("shell", "executable"),
            )
            stop_time = perf_counter()

            if result.stderr:
                return await message.edit_text(
                    code_result.format(
                        language="Node.js",
                        pre_language="javascript",
                        code=code,
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error with status code {result.returncode}</b>\n"
                        f"<code>{html.escape(result.stderr)}</code>",
                    )
                )

            if len(result.stdout) > 3072:
                result = html.escape(await paste_neko(result.stdout))
            else:
                result = f"<code>{html.escape(result.stdout)}</code>"

            return await message.edit_text(
                code_result.format(
                    language="Node.js",
                    pre_language="javascript",
                    code=code,
                    result=f"<b><emoji id=5472164874886846699>✨</emoji> Result</b>:\n"
                    f"{result}\n"
                    f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>",
                )
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
