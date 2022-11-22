import asyncio
import html
import pathlib
import subprocess
from tempfile import NamedTemporaryFile, TemporaryDirectory
from time import perf_counter

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.misc import modules_help, prefix
from utils.scripts import with_args


def compile(code: str, compiler: str, lang: str):
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
        return result


async def compiler_task(message: Message, compiler: str, lang: str):
    await message.edit_text(
        f"<i><emoji id=5821116867309210830>🔃</emoji> Compiling {lang} code...</i>"
    )

    _, code = message.text.split(maxsplit=1)
    result = compile(code, compiler, lang)

    await message.edit_text(result)


@Client.on_message(filters.command(["gcc", "gpp"], prefix) & filters.me)
@with_args("<b>Code is not provided</b>")
async def gnu_compiler(_, message: Message):
    if message.command[0] == "gcc":
        asyncio.get_running_loop().create_task(compiler_task(message, "gcc", "C"))
    elif message.command[0] == "gpp":
        asyncio.get_running_loop().create_task(compiler_task(message, "g++", "C++"))


modules_help["compiler"] = {
    "gcc [c code]": "Execute C code",
    "gpp [c code]": "Execute C++ code",
}
