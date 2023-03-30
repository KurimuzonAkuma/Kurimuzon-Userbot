import asyncio
import html
import pathlib
import subprocess
from tempfile import NamedTemporaryFile, TemporaryDirectory
from time import perf_counter

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import with_args


async def compile(message: Message, compiler: str, lang: str):
    await message.edit_text(
        f"<i><emoji id=5821116867309210830>🔃</emoji> Compiling {lang} code...</i>"
    )

    _, code = message.text.split(maxsplit=1)
    tempdir = TemporaryDirectory()
    path = pathlib.Path(tempdir.name)
    with NamedTemporaryFile("w+", suffix=".c", dir=path) as file:
        file.write(code)
        file.seek(0)

        compiled_file = subprocess.run(
            f"{compiler} -o output {file.name}",
            shell=True,
            capture_output=True,
            text=True,
            cwd=path,
        )

        tag_lang = "c" if lang.lower() == "c" else "cpp"
        result = (
            f"<b><emoji id=5821388137443626414>🌐</emoji> Language:\n</b>"
            f"<code>{lang}</code>\n\n"
            f"<b><emoji id=5431376038628171216>💻</emoji> Code:</b>\n"
            f"<pre language={tag_lang}>{html.escape(code)}</pre>\n\n"
        )

        # returns 0 if compilation was successful
        if compiled_file.returncode != 0:
            result += (
                "<b><emoji id=5465665476971471368>❌</emoji> Compilation error "
                f"with status code {compiled_file.returncode}:</b>\n"
                f"<code>{html.escape(compiled_file.stderr)}</code>\n"
            )
        else:
            start_time = perf_counter()
            program_result = subprocess.run(
                "./output", shell=True, capture_output=True, text=True, cwd=path
            )
            stop_time = perf_counter()

            result += (
                "<b><emoji id=5472164874886846699>✨</emoji> Result:</b>\n"
                f"<code>{html.escape(program_result.stdout)}</code>\n"
            )

            result += f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>"

    await message.edit_text(result)


@Client.on_message(~filters.scheduled & command(["gcc", "gpp"]) & filters.me)
@with_args("<b>Code is not provided</b>")
async def gnu_compiler(_, message: Message):
    if message.command[0] == "gcc":
        await compile(message, "gcc", "C")
    elif message.command[0] == "gpp":
        await compile(message, "g++", "C++")


@Client.on_message(~filters.scheduled & command(["go"]) & filters.me)
@with_args("<b>Code is not provided</b>")
async def go_compiler(_, message: Message):
    await message.edit_text("<i><emoji id=5821116867309210830>🔃</emoji> Compiling Go code...</i>")
    _, code = message.text.split(maxsplit=1)

    tempdir = TemporaryDirectory()
    path = pathlib.Path(tempdir.name)
    with NamedTemporaryFile("w+", suffix=".go", dir=path) as file:
        file.write(code)
        file.seek(0)

        start_time = perf_counter()
        compiled_file = subprocess.run(
            f"go run {file.name}",
            shell=True,
            capture_output=True,
            text=True,
            cwd=path,
        )
        stop_time = perf_counter()

        result = (
            f"<b><emoji id=5821388137443626414>🌐</emoji> Language:\n</b>"
            f"<code>Go</code>\n\n"
            f"<b><emoji id=5431376038628171216>💻</emoji> Code:</b>\n"
            f"<pre language=go>{html.escape(code)}</pre>\n\n"
        )

        if compiled_file.stderr:
            result += (
                "<b><emoji id=5465665476971471368>❌</emoji> Compilation error "
                f"with status code {compiled_file.returncode}:</b>\n"
                f"<code>{html.escape(compiled_file.stderr)}</code>\n"
            )
        else:
            result += (
                "<b><emoji id=5472164874886846699>✨</emoji> Result:</b>\n"
                f"<code>{html.escape(compiled_file.stdout)}</code>\n"
            )
            result += f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>"

        await message.edit_text(result)


@Client.on_message(~filters.scheduled & command(["lua"]) & filters.me)
@with_args("<b>Code is not provided</b>")
async def lua_compiler(_, message: Message):
    await message.edit_text("<i><emoji id=5821116867309210830>🔃</emoji> Compiling Lua code...</i>")
    _, code = message.text.split(maxsplit=1)

    tempdir = TemporaryDirectory()
    path = pathlib.Path(tempdir.name)
    with NamedTemporaryFile("w+", suffix=".lua", dir=path) as file:
        file.write(code)
        file.seek(0)

        start_time = perf_counter()
        compiled_file = subprocess.run(
            f"lua {file.name}",
            shell=True,
            capture_output=True,
            text=True,
            cwd=path,
        )
        stop_time = perf_counter()

        result = (
            f"<b><emoji id=5821388137443626414>🌐</emoji> Language:\n</b>"
            f"<code>Lua</code>\n\n"
            f"<b><emoji id=5431376038628171216>💻</emoji> Code:</b>\n"
            f"<pre language=go>{html.escape(code)}</pre>\n\n"
        )

        if compiled_file.stderr:
            result += (
                "<b><emoji id=5465665476971471368>❌</emoji> Compilation error "
                f"with status code {compiled_file.returncode}:</b>\n"
                f"<code>{html.escape(compiled_file.stderr)}</code>\n"
            )
        else:
            result += (
                "<b><emoji id=5472164874886846699>✨</emoji> Result:</b>\n"
                f"<code>{html.escape(compiled_file.stdout)}</code>\n"
            )
            result += f"<b>Completed in {round(stop_time - start_time, 5)}s.</b>"

        await message.edit_text(result)


modules_help["compiler"] = {
    "gcc [code]": "Execute C code",
    "gpp [code]": "Execute C++ code",
    "go [code]": "Execute Go code",
    "lua [code]": "Execute Lua code",
}
