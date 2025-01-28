import asyncio
import datetime
import logging
import os
import random
import shlex
import string
import traceback
from time import perf_counter
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import git
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pyrogram import Client, errors
from pyrogram.enums import ChatType
from pyrogram.types import Chat, Message, User

from utils.db import db


class Formatter(logging.Formatter):
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


def get_proxy(proxies_path: str = "proxies.txt") -> dict:
    try:
        with open(proxies_path, "r") as f:
            proxies = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    except FileNotFoundError:
        return None

    if not proxies:
        return None

    random_proxy = random.choice(
        [line.strip() for line in proxies if line.strip() and not line.startswith("#")]
    )

    if not random_proxy:
        return None

    protocol, proxy = random_proxy.split()
    proxy = proxy.split("@")

    if len(proxy) == 2:
        username, password = proxy[0].split(":")

        proxy = dict(
            scheme=protocol, server=proxy[1], username=username, password=password
        )
    else:
        proxy = dict(scheme=protocol, server=proxy[0])

    return proxy


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
        if not (await client.get_users("me")).is_premium:
            await message.edit("<b>Premium account is required</b>")
        else:
            return await func(client, message)

    return wrapped


def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


async def paste_yaso(code: str, expiration_time: int = 10080):
    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        ) as session:
            async with session.post(
                "https://api.yaso.su/v1/auth/guest",
            ) as auth:
                auth.raise_for_status()

            async with session.post(
                "https://api.yaso.su/v1/records",
                json={
                    "captcha": generate_random_string(569),
                    "codeLanguage": "auto",
                    "content": code,
                    "expirationTime": expiration_time,
                },
            ) as paste:
                paste.raise_for_status()
                result = await paste.json()
    except Exception:
        return "Pasting failed"
    else:
        return f"https://yaso.su/{result['url']}"


def get_prefix():
    return db.get("core.main", "prefix", default=".")


def get_args_raw(message: Union[Message, str], use_reply: bool = None) -> str:
    """Returns text after command.

    Args:
        message (Union[Message, str]): Message or text.

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
    message: Union[Message, str], use_reply: bool = None
) -> Tuple[List[str], Dict[str, str]]:
    """Returns list of common args and a dictionary with named args.

    Args:
        message (Union[Message, str]): Message or text.

        use_reply (bool, optional): Try to get args from reply message if no args in message. Defaults to None.

    Returns:
        List[str]: List of args.
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
            if i + 1 < len(args) and (
                not args[i + 1].startswith("-") or len(args[i + 1].split()) > 1
            ):
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
        trigger: Optional[Union[CronTrigger, IntervalTrigger]] = IntervalTrigger(
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


class Command:
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        args: Optional[str] = None,
        aliases: Optional[List[str]] = None,
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
        description: Optional[str] = None,
        args: Optional[str] = None,
        aliases: Optional[List[str]] = None,
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

    def help(self) -> List[str]:
        prefix = get_prefix()
        result = []

        help_text = f"For more help on how to use a command, type <code>{prefix}help [module]</code>\n\nAvailable Modules:\n"

        for module_name, module in sorted(self.modules.items(), key=lambda x: x[0]):
            help_text += f"• {module_name.title()}: {' '.join([f'<code>{prefix + cmd_name}</code>' for cmd_name in module.commands.keys()])}\n"

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
            help_text += f"{' '.join([f'<code>{prefix}{alias}</code>' for alias in command.aliases])}\n"

        help_text += f"\n<b>Module: {module.name}</b> (<code>{prefix}help {module.name}</code>)\n\n"
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


async def shell_exec(
    command: str,
    executable: Optional[str] = None,
    timeout: Optional[Union[int, float]] = None,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
) -> Tuple[int, str, str]:
    """Executes shell command and returns tuple with return code, decoded stdout and stderr"""
    process = await asyncio.create_subprocess_shell(
        cmd=command, stdout=stdout, stderr=stderr, shell=True, executable=executable
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.exceptions.TimeoutError as e:
        process.kill()
        raise e

    return process.returncode, stdout.decode(), stderr.decode()


async def handle_restart(client: Client):
    restart_info = db.get("core.updater", "restart_info")

    if restart_info:
        try:
            if restart_info["type"] == "restart":
                logging.info(
                    f"{client.me.username}#{client.me.id} | Userbot succesfully restarted."
                )
                await client.edit_message_text(
                    chat_id=restart_info["chat_id"],
                    message_id=restart_info["message_id"],
                    text=f"<code>Restarted in {perf_counter() - restart_info['time']:.3f}s...</code>",
                )
            elif restart_info["type"] == "update":
                current_hash = git.Repo().head.commit.hexsha
                git.Repo().remote("origin").fetch()

                update_text = (
                    f"Userbot succesfully updated from {restart_info['hash'][:7]} "
                    f"to {current_hash[:7]} version."
                )

                logging.info(f"{client.me.username}#{client.me.id} | {update_text}.")
                await client.edit_message_text(
                    chat_id=restart_info["chat_id"],
                    message_id=restart_info["message_id"],
                    text=(
                        f"<code>{update_text}.\n\n"
                        f"Restarted in {perf_counter() - restart_info['time']:.3f}s...</code>"
                    ),
                )
        except Exception:
            print("Error when updating!")
            traceback.print_exc()

        db.remove("core.updater", "restart_info")
    else:
        logging.info(
            f"{client.me.username}#{client.me.id} on {git.Repo().active_branch.name}"
            f"@{git.Repo().head.commit.hexsha[:7]}"
            " | Userbot succesfully started."
        )


def time_diff(dt: datetime.datetime) -> str:
    now = datetime.datetime.now()
    diff = dt - now

    if diff.total_seconds() < 0:
        diff = now - dt
        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "just now"
    else:
        if diff.days > 0:
            return f"in {diff.days} days"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"in {hours} hours"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"in {minutes} minutes"
        else:
            return "soon"
