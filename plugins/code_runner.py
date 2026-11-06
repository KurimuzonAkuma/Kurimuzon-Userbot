import asyncio
import html
import logging
import os
import random
import re
import tempfile
from io import BytesIO, StringIO
from traceback import format_exc

from pyrogram import Client, enums, filters
from pyrogram.types import LinkPreviewOptions, Message

from utils import loader
from utils.db import db
from utils.loader import CommandArg, Plugin
from utils.scripts import paste_yaso, shell_exec

log = logging.getLogger(__name__)


code_result = (
    "<blockquote><emoji id=5431376038628171216>💻</emoji></blockquote>\n"
    '<pre language="{pre_language}">{code}</pre>\n\n'
    "{result}"
)


def extract_code_from_reply(message: Message, language: str | None = None) -> str | None:
    if not message.reply_to_message:
        return None

    if language and message.reply_to_message.entities:
        for entity in message.reply_to_message.entities:
            if entity.type == enums.MessageEntityType.PRE and entity.language == language:
                return message.reply_to_message.content[
                    entity.offset : entity.offset + entity.length
                ]

    return message.reply_to_message.content


class CodeRunner(Plugin):
    async def _extract_code(self, message: Message) -> str:
        if not message.command:
            return ""

        command_name = message.command[0]
        aliases = {
            "rpy": "python",
            "rgcc": "c",
            "rgpp": "cpp",
            "rlua": "lua",
            "rgo": "go",
            "rnode": "javascript",
        }
        if command_name in aliases:
            return extract_code_from_reply(message, aliases[command_name]) or ""

        text = message.text or ""
        parts = text.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""

    async def _exec_python(self, code: str, client: Client, message: Message, timeout: int):
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
            "asyncio": asyncio,
            "pyrogram": __import__("pyrogram"),
            "types": __import__("pyrogram").types,
            "enums": __import__("pyrogram").enums,
            "raw": __import__("pyrogram").raw,
        }

        exec(
            "async def __todo(client, message, *args):\n"
            + "\n".join(f"    {_l}" for _l in code.split("\n")),
            exec_globals,
        )

        stream = StringIO()
        with __import__("contextlib").redirect_stdout(stream):
            await asyncio.wait_for(exec_globals["__todo"](client, message), timeout=timeout)
        return stream.getvalue()

    async def _render_result(
        self, client: Client, message: Message, language: str, code: str, output: str
    ):
        if not output:
            output = "No result"

        output = output.replace(
            client.me.phone_number,
            f"888{''.join(str(random.randint(0, 9)) for _ in range(8))}",
        )

        if len(output) > 512:
            paste_result = await paste_yaso(output, db.get("yaso", "token"))
            if paste_result.startswith("Pasting failed"):
                data = BytesIO(output.encode("utf-8"))
                data.seek(0)
                data.name = "result.log"
                return await message.reply_document(
                    document=data,
                    caption=code_result.format(
                        pre_language=language,
                        code=html.escape(code),
                        result="<blockquote><emoji id=5472164874886846699>✨</emoji> Result is too long</blockquote>",
                    ),
                )
            output = f"<pre>{html.escape(output[:512])}...</pre>\n<blockquote><b><a href='{paste_result}'>More</a></b></blockquote>"
        elif not re.match(r"^(https?):\/\/[^\s\/.?#].*", output):
            output = f"<pre>{html.escape(output)}</pre>"

        return await message.edit_text(
            code_result.format(
                pre_language=language,
                code=html.escape(code),
                result=f"<blockquote><emoji id=5472164874886846699>✨</emoji> Result:</blockquote>\n{output}",
            ),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

    async def _run_shell(
        self,
        client: Client,
        message: Message,
        *,
        language: str,
        code: str,
        file_ext: str,
        compile_cmd: str,
        run_cmd: str,
    ):
        if not code:
            return await message.edit_text("<b>Code to execute isn't provided</b>")

        timeout = db.get("shell", "timeout", 60)
        await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

        with tempfile.TemporaryDirectory() as tempdir:
            source_path = os.path.join(tempdir, f"main{file_ext}")
            program_path = os.path.join(tempdir, "main")

            with open(source_path, "w", encoding="utf-8") as handle:
                handle.write(code)

            try:
                compile_rc, compile_out, compile_err = await shell_exec(
                    f"{compile_cmd} {source_path} -o {program_path}",
                    executable=db.get("shell", "executable"),
                    timeout=timeout,
                )
            except TimeoutError:
                return await message.edit_text(
                    code_result.format(
                        pre_language=language,
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )

            if compile_rc != 0:
                return await message.edit_text(
                    code_result.format(
                        pre_language=language,
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Compilation error:</b>\n<code>{html.escape(compile_err or compile_out)}</code>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )

            try:
                run_rc, run_out, run_err = await shell_exec(
                    run_cmd.format(output=program_path),
                    executable=db.get("shell", "executable"),
                    timeout=timeout,
                )
            except TimeoutError:
                return await message.edit_text(
                    code_result.format(
                        pre_language=language,
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )

            if run_err:
                return await message.edit_text(
                    code_result.format(
                        pre_language=language,
                        code=html.escape(code),
                        result=f"<b><emoji id=5465665476971471368>❌</emoji> Runtime error:</b>\n<code>{html.escape(run_err)}</code>",
                    ),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )

            final_output = run_out or "No result"
            if not re.match(r"^(https?):\/\/[^\s\/.?#].*", final_output):
                final_output = f"<pre>{html.escape(final_output)}</pre>"

            return await message.edit_text(
                code_result.format(
                    pre_language=language,
                    code=html.escape(code),
                    result=f"<blockquote><emoji id=5472164874886846699>✨</emoji> Result:</blockquote>\n{final_output}",
                ),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )

    @loader.command(
        ["py", "rpy"],
        description="Execute Python code",
        args=[CommandArg("code", "code to execute", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def python_exec(self, client: Client, message: Message):
        code = await self._extract_code(message)
        if not code:
            return await message.edit_text("<b>Code to execute isn't provided</b>")

        timeout = db.get("shell", "timeout", 60)
        await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Executing...</b>")

        try:
            result = await self._exec_python(code, client, message, timeout=timeout)
        except TimeoutError:
            return await message.edit_text(
                code_result.format(
                    pre_language="python",
                    code=html.escape(code),
                    result=f"<b><emoji id=5465665476971471368>❌</emoji> Error!</b>\n<b>Timeout expired ({timeout} seconds)</b>",
                ),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception as exc:
            return await message.edit_text(
                code_result.format(
                    pre_language="python",
                    code=html.escape(code),
                    result=f"<blockquote><emoji id=5465665476971471368>❌</emoji> {exc.__class__.__name__}: {exc}</blockquote>\n<code>{html.escape(format_exc())}</code>",
                ),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )

        return await self._render_result(client, message, "python", code, result)

    @loader.command(
        ["gcc", "rgcc"],
        description="Execute C code",
        args=[CommandArg("code", "c code", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def gcc_exec(self, client: Client, message: Message):
        code = await self._extract_code(message)
        return await self._run_shell(
            client,
            message,
            language="c",
            code=code,
            file_ext=".c",
            compile_cmd="gcc",
            run_cmd="{output}",
        )

    @loader.command(
        ["gpp", "rgpp"],
        description="Execute C++ code",
        args=[CommandArg("code", "c++ code", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def gpp_exec(self, client: Client, message: Message):
        code = await self._extract_code(message)
        return await self._run_shell(
            client,
            message,
            language="cpp",
            code=code,
            file_ext=".cpp",
            compile_cmd="g++",
            run_cmd="{output}",
        )

    @loader.command(
        ["lua", "rlua"],
        description="Execute Lua code",
        args=[CommandArg("code", "lua code", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def lua_exec(self, client: Client, message: Message):
        code = await self._extract_code(message)
        return await self._run_shell(
            client,
            message,
            language="lua",
            code=code,
            file_ext=".lua",
            compile_cmd="true",
            run_cmd="lua {output}",
        )

    @loader.command(
        ["go", "rgo"],
        description="Execute Go code",
        args=[CommandArg("code", "go code", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def go_exec(self, client: Client, message: Message):
        code = await self._extract_code(message)
        return await self._run_shell(
            client,
            message,
            language="go",
            code=code,
            file_ext=".go",
            compile_cmd="true",
            run_cmd="go run {output}",
        )

    @loader.command(
        ["node", "rnode"],
        description="Execute Node.js code",
        args=[CommandArg("code", "node.js code", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def node_exec(self, client: Client, message: Message):
        code = await self._extract_code(message)
        return await self._run_shell(
            client,
            message,
            language="javascript",
            code=code,
            file_ext=".js",
            compile_cmd="true",
            run_cmd="node {output}",
        )
