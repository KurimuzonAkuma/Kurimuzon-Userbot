import logging
import os
import sys
import typing

import aiohttp
import git
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pyrogram import Client, errors
from pyrogram.enums import ChatType
from pyrogram.types import Chat, Message, User

from utils.db import db
from utils.misc import modules_help, script_path


class CustomFormatter(logging.Formatter):
    # Colors
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    gray = "\x1b[38m"
    # Styles
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    COLORS = {
        logging.DEBUG: gray + bold,
        logging.INFO: blue + bold,
        logging.WARNING: yellow + bold,
        logging.ERROR: red,
        logging.CRITICAL: red + bold,
    }

    def format(self, record):
        log_color = self.COLORS[record.levelno]
        fmt = "(black){asctime}(reset) (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        fmt = fmt.replace("(black)", self.black + self.bold)
        fmt = fmt.replace("(reset)", self.reset)
        fmt = fmt.replace("(levelcolor)", log_color)
        fmt = fmt.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(fmt, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)


def restart():
    os.execvp(sys.executable, [sys.executable, "main.py"])


def get_full_name(obj: typing.Union[User, Chat]) -> str:
    if isinstance(obj, Chat):
        if obj.type == ChatType.PRIVATE:
            return f"{obj.first_name} {obj.last_name}" if obj.last_name else obj.first_name
        return obj.title
    elif isinstance(obj, User):
        return f"{obj.first_name} {obj.last_name}" if obj.last_name else obj.first_name
    else:
        raise TypeError("obj must be User or Chat")


def format_exc(e: Exception, suffix="") -> str:
    if isinstance(e, errors.RPCError):
        return (
            f"<b>Telegram API error!</b>\n"
            f"<code>[{e.CODE} {e.ID or e.NAME}] — {e.MESSAGE.format(value=e.value)}</code>\n\n"
            f"<b>{suffix}</b>"
        )
    return f"<code>{e.__class__.__name__}: {e}</code>\n\n<b>{suffix}</b>"


def with_reply(func):
    async def wrapped(client: Client, message: Message):
        if not message.reply_to_message:
            await message.edit("<b>Reply to message is required</b>")
        else:
            return await func(client, message)

    return wrapped


def with_args(text: str):
    def decorator(func):
        async def wrapped(client: Client, message: Message):
            if message.text and len(message.text.split()) == 1:
                await message.edit(text)
            else:
                return await func(client, message)

        return wrapped

    return decorator


def with_premium(func):
    async def wrapped(client: Client, message: Message):
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
        help_text += f"<code>{get_prefix()}{cmd[0]}</code>{args} — <i>{desc}</i>\n"

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


def get_commits():
    repo = git.Repo(script_path)

    current_hash = repo.head.commit.hexsha
    latest_hash = repo.remotes.origin.refs.master.commit.hexsha

    return {
        "latest": (len(list(repo.iter_commits(f"05c3cfe..{latest_hash}"))) + 1),
        "latest_hash": latest_hash,
        "current": len(list(repo.iter_commits(f"05c3cfe..{current_hash}"))) + 1,
        "current_hash": current_hash,
        "branch": repo.active_branch,
    }


def get_prefix():
    return db.get("core.main", "prefix", default=".")


def get_args_raw(message: typing.Union[Message, str]) -> str:
    if isinstance(message, Message):
        message = message.text
    elif not isinstance(message, str):
        return ""

    return args[1] if len(args := message.split(maxsplit=1)) > 1 else ""


class ScheduleJob:
    def __init__(
        self,
        func: callable,
        trigger: typing.Optional[typing.Union[DateTrigger, IntervalTrigger, CronTrigger]] = None,
        *args,
        **kwargs,
    ):
        self.func = func
        self.args = args or []
        self.kwargs = kwargs or {}
        self.id = func.__name__

        trigger_data = db.get("triggers", self.func.__name__, {"type": "interval", "value": 3600})
        if trigger_data["type"] == "cron":
            db_trigger = CronTrigger.from_crontab(trigger_data["value"])
        else:
            db_trigger = IntervalTrigger(seconds=trigger_data["value"])

        self.trigger = trigger or db_trigger
