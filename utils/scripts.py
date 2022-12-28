import logging
import os
import sys
from typing import List, Union

import aiohttp
import git
from pyrogram import Client, errors, types
from pyrogram.filters import Filter

from utils.misc import modules_help, prefix, script_path


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    def __init__(self, fmt):
        super().__init__()
        self.fmt = fmt
        self.FORMATS = {
            logging.DEBUG: self.grey + self.fmt + self.reset,
            logging.INFO: self.blue + self.fmt + self.reset,
            logging.WARNING: self.yellow + self.fmt + self.reset,
            logging.ERROR: self.red + self.fmt + self.reset,
            logging.CRITICAL: self.bold_red + self.fmt + self.reset,
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class startswith(Filter, set):
    """Filter messages starting with text.

    Parameters:
        ignore_case (``bool``, *optional*):
            Pass True to ignore case sensitivity.
            Defaults to True.
    """

    def __init__(self, text: str, ignore_case: bool = True):
        super().__init__()
        self.text = text
        self.ignore_case = ignore_case

    async def __call__(self, _, message: types.Message):
        mtext = message.text or message.caption
        if not mtext:
            return False
        if self.ignore_case:
            mtext = mtext.lower()
        return bool(mtext.startswith(self.text))


class viabot(Filter, set):
    """Filter messages coming with via_bot.

    Parameters:
        bots (``int`` | ``str`` | ``list``):
            Pass one or more bot ids/usernames to filter.
            Defaults to None (any bot).
    """

    def __init__(self, bots: Union[int, str, List[Union[int, str]]] = None):
        bots = [] if bots is None else bots if isinstance(bots, list) else [bots]

        super().__init__(bot.lower().strip("@") if isinstance(bot, str) else bot for bot in bots)

    async def __call__(self, _, message: types.Message):
        return message.via_bot and (
            message.via_bot.id in self
            or (message.via_bot.username and message.via_bot.username.lower() in self)
        )


def restart():
    os.execvp(sys.executable, [sys.executable, "main.py"])


def full_name(user: types.User) -> str:
    return f"{user.first_name} {user.last_name}" if user.last_name else user.first_name


def format_exc(e: Exception, suffix="") -> str:
    if isinstance(e, errors.RPCError):
        return (
            f"<b>Telegram API error!</b>\n"
            f"<code>[{e.CODE} {e.ID or e.NAME}] — {e.MESSAGE.format(value=e.value)}</code>\n\n"
            f"<b>{suffix}</b>"
        )
    return f"<code>{e.__class__.__name__}: {e}</code>\n\n<b>{suffix}</b>"


def with_reply(func):
    async def wrapped(client: Client, message: types.Message):
        if not message.reply_to_message:
            await message.edit("<b>Reply to message is required</b>")
        else:
            return await func(client, message)

    return wrapped


def with_args(text: str):
    def decorator(func):
        async def wrapped(client: Client, message: types.Message):
            if message.text and len(message.text.split()) == 1:
                await message.edit(text)
            else:
                return await func(client, message)

        return wrapped

    return decorator


def with_premium(func):
    async def wrapped(client: Client, message: types.Message):
        if not (await client.get_me()).is_premium:
            await message.edit("<b>Premium account is required</b>")
        else:
            return await func(client, message)

    return wrapped


def format_module_help(module_name: str, full=True):
    commands = modules_help[module_name]

    help_text = f"<b>Help for |{module_name}|\n\nUsage:</b>\n" if full else "<b>Usage:</b>\n"

    for command, desc in commands.items():
        cmd = command.split(maxsplit=1)
        args = f" <code>{cmd[1]}</code>" if len(cmd) > 1 else ""
        help_text += f"<code>{prefix}{cmd[0]}</code>{args} — <i>{desc}</i>\n"

    return help_text


async def paste_neko(code: str):
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                "https://nekobin.com/api/documents",
                json={"content": code},
            ) as paste:
                paste.raise_for_status()
                result = await paste.json()
    except Exception:
        return "Pasting failed"
    else:
        return f"nekobin.com/{result['result']['key']}.py"


def get_commits_count():
    repo = git.Repo(script_path)
    return {
        "latest": (
            len(
                list(
                    repo.iter_commits(
                        f"05c3cfe..{repo.remotes.origin.refs.master.commit.hexsha[:7]}"
                    )
                )
            )
            + 1
        ),
        "current": len(list(repo.iter_commits(f"05c3cfe..{repo.head.commit.hexsha[:7]}"))) + 1,
    }
