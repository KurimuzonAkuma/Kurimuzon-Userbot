import logging
import os
import shlex
import sys
import typing

import aiohttp
import arrow
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pyrogram import Client, errors
from pyrogram.enums import ChatType
from pyrogram.types import Chat, Message, User

from utils.db import db


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
    os.execvp(sys.executable, [sys.executable, *sys.argv])


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


def get_prefix():
    return db.get("core.main", "prefix", default=".")


def get_args_raw(message: typing.Union[Message, str], use_reply: bool = None) -> str:
    """Returns text after command.

    Args:
        message (typing.Union[Message, str]): Message or text.

        use_reply (bool, optional): Try to get args from reply message if no args in message. Defaults to None.

    Returns:
        str: Text after command or empty string.
    """
    if isinstance(message, Message):
        text = message.text or message.caption
        args = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""

        if use_reply and not args:
            args = message.reply_to_message.text or message.reply_to_message.caption

    elif not isinstance(message, str):
        return ""

    return args or ""


def get_args(
    message: typing.Union[Message, str], use_reply: bool = None
) -> typing.Tuple[typing.List[str], typing.Dict[str, str]]:
    """Returns list of common args and a dictionary with named args.

    Args:
        message (typing.Union[Message, str]): Message or text.

        use_reply (bool, optional): Try to get args from reply message if no args in message. Defaults to None.

    Returns:
        typing.List[str]: List of args.
    """
    raw_args = get_args_raw(message, use_reply)

    try:
        args = list(filter(lambda x: len(x) > 0, shlex.split(raw_args)))
    except ValueError:
        return [raw_args], {}

    common_args = []
    named_args = {}

    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("-"):
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                named_args[arg] = args[i + 1]
                i += 2
            else:
                i += 1
        else:
            i += 1
        common_args.append(arg)
    return common_args, named_args


class ScheduleJob:
    def __init__(
        self,
        func: callable,
        trigger: typing.Optional[typing.Union[CronTrigger, IntervalTrigger]] = IntervalTrigger(
            seconds=3600
        ),
        *args,
        **kwargs,
    ):
        self.func = func
        self.args = args or []
        self.kwargs = kwargs or {}
        self.id = func.__name__
        self.trigger = trigger


def get_ram_usage() -> float:
    """Returns current process tree memory usage in MB"""
    try:
        import psutil

        current_process = psutil.Process(os.getpid())
        mem = current_process.memory_info()[0] / 2.0**20
        for child in current_process.children(recursive=True):
            mem += child.memory_info()[0] / 2.0**20

        return round(mem, 1)
    except Exception:
        return 0


def get_cpu_usage() -> float:
    """Returns current process tree CPU usage in %"""
    try:
        import psutil

        current_process = psutil.Process(os.getpid())
        cpu = current_process.cpu_percent()
        for child in current_process.children(recursive=True):
            cpu += child.cpu_percent()

        return round(cpu, 1)
    except Exception:
        return 0


def humanize_seconds(seconds: typing.Union[int, float]) -> str:
    """Returns humanized time delta from seconds"""
    current_time = arrow.get()
    target_time = current_time.shift(seconds=-seconds)
    return target_time.humanize(current_time, only_distance=True)


class Command:
    def __init__(
        self,
        name: str,
        description: typing.Optional[str] = None,
        args: typing.Optional[str] = None,
        aliases: typing.Optional[typing.List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.args = args
        self.aliases = aliases
        self.hidden = False


class Module:
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.commands = {}
        self.hidden = False

    def add_command(
        self,
        command: str,
        description: typing.Optional[str] = None,
        args: typing.Optional[str] = None,
        aliases: typing.Optional[typing.List[str]] = None,
    ) -> Command:
        if command in self.commands:
            raise ValueError(f"Command {command} already exists")

        self.commands[command] = Command(command, description, args, aliases)

        return self.commands[command]

    def delete_command(self, command: str) -> None:
        if command not in self.commands:
            raise ValueError(f"Command {command} not found")

        del self.commands[command]

    def hide_command(self, command: str) -> None:
        if command not in self.commands:
            raise ValueError(f"Command {command} not found")

        self.commands[command].hidden = True

    def show_command(self, command: str) -> None:
        if command not in self.commands:
            raise ValueError(f"Command {command} not found")

        self.commands[command].hidden = False


class ModuleHelp:
    def __init__(self) -> None:
        self.modules = {}

    def add_module(self, name: str, path: str) -> Module:
        self.modules[name] = Module(name, path)

        return self.modules[name]

    def delete_module(self, name: str) -> None:
        del self.modules[name]

    def hide_module(self, name: str) -> None:
        if name not in self.modules:
            raise ValueError(f"Module {name} not found")

        self.modules[name].hidden = True

    def show_module(self, name: str) -> None:
        if name not in self.modules:
            raise ValueError(f"Module {name} not found")

        self.modules[name].hidden = False

    def get_module(self, name: str) -> Module:
        if name not in self.modules:
            raise ValueError(f"Module {name} not found")

        return self.modules[name]

    def get_module_by_path(self, path: str) -> Module:
        for module in self.modules.values():
            if module.path == path:
                return module

        raise ValueError(f"Module with path {path} not found")

    def help(self) -> typing.List[str]:
        prefix = get_prefix()
        result = []

        help_text = f"For more help on how to use a command, type <code>{prefix}help [module]</code>\n\nAvailable Modules:\n"

        for module_name, module in sorted(self.modules.items(), key=lambda x: x[0]):
            help_text += f'• {module_name.title()}: {" ".join([f"<code>{prefix + cmd_name}</code>" for cmd_name in module.commands.keys()])}\n'

            if len(help_text) >= 2048:
                result.append(help_text)
                help_text = ""

        help_text += f"\nThe number of modules in the userbot: {self.modules_count}\n"
        help_text += f"The number of commands in the userbot: {self.commands_count}"

        result.append(help_text)

        return result

    def module_help(self, module: str, full: bool = True) -> str:
        if module not in self.modules:
            raise ValueError(f"Module {module} not found")

        prefix = get_prefix()
        help_text = ""

        if full:
            help_text += f"<b>Help for |<code>{module}</code>|</b>\n\n"

        help_text += "<b>Usage:</b>\n"
        for command in self.modules[module].commands.values():
            help_text += f"<code>{prefix}{command.name}"
            if command.args:
                help_text += f" {command.args}"
            if command.description:
                help_text += f"</code> — <i>{command.description}</i>\n"

        return help_text

    def command_help(self, command: str) -> str:
        for module in self.modules.values():
            for cmd in module.commands.values():
                if cmd.name == command or (cmd.aliases and command in cmd.aliases):
                    command = cmd
                    break
            else:
                continue
            break
        else:
            raise ValueError(f"Command {command} not found")

        prefix = get_prefix()

        help_text = f"<b>Help for command</b> <code>{prefix}{command.name}</code>\n"
        if command.aliases:
            help_text += "<b>Aliases:</b> "
            help_text += (
                f"{' '.join([f'<code>{prefix}{alias}</code>' for alias in command.aliases])}\n"
            )

        help_text += (
            f"\n<b>Module: {module.name}</b> (<code>{prefix}help {module.name}</code>)\n\n"
        )
        help_text += f"<code>{prefix}{command.name}"

        if command.args:
            help_text += f" {command.args}"
        help_text += "</code>"
        if command.description:
            help_text += f" — <i>{command.description}</i>"

        return help_text

    @property
    def modules_count(self) -> int:
        return len(self.modules)

    @property
    def commands_count(self) -> int:
        return sum(len(module.commands) for module in self.modules.values())
