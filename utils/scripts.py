import asyncio
import logging
import os
import shlex
import sys
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import arrow
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pyrogram import Client, enums, errors
from pyrogram.enums import ChatType
from pyrogram.session import Session
from pyrogram.storage import Storage
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


def get_full_name(obj: Union[User, Chat]) -> str:
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
        trigger: Optional[Union[CronTrigger, IntervalTrigger]] = IntervalTrigger(seconds=3600),
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


def humanize_seconds(seconds: Union[int, float]) -> str:
    """Returns humanized time delta from seconds"""
    current_time = arrow.get()
    target_time = current_time.shift(seconds=-seconds)
    return target_time.humanize(current_time, only_distance=True)


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


def get_entity_url(
    entity: Union[User, Chat],
    openmessage: bool = False,
) -> str:
    """
    Get link to object, if available
    :param entity: Entity to get url of
    :param openmessage: Use tg://openmessage link for users
    :return: Link to object or empty string
    """
    return (
        (f"tg://openmessage?user_id={entity.id}" if openmessage else f"tg://user?id={entity.id}")
        if isinstance(entity, User)
        else (
            f"tg://resolve?domain={entity.username}" if getattr(entity, "username", None) else ""
        )
    )


def get_message_link(
    message: Message,
    chat: Optional[Chat] = None,
) -> str:
    """
    Get link to message
    :param message: Message to get link of
    :param chat: Chat, where message was sent
    :return: Link to message
    """
    if message.chat.type == ChatType.PRIVATE:
        return f"tg://openmessage?user_id={message.chat.id}&message_id={message.id}"

    return (
        f"https://t.me/{chat.username}/{message.id}"
        if getattr(chat, "username", False)
        else f"https://t.me/c/{chat.id}/{message.id}"
    )


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


class KClient(Client):
    """Modified Pyrogram Client, the main means for interacting with Telegram.

    Parameters:
        name (``str``):
            A name for the client, e.g.: "my_account".

        api_id (``int`` | ``str``, *optional*):
            The *api_id* part of the Telegram API key, as integer or string.
            E.g.: 12345 or "12345".

        api_hash (``str``, *optional*):
            The *api_hash* part of the Telegram API key, as string.
            E.g.: "0123456789abcdef0123456789abcdef".

        app_version (``str``, *optional*):
            Application version.
            Defaults to "Pyrogram x.y.z".

        device_model (``str``, *optional*):
            Device model.
            Defaults to *platform.python_implementation() + " " + platform.python_version()*.

        system_version (``str``, *optional*):
            Operating System version.
            Defaults to *platform.system() + " " + platform.release()*.

        lang_code (``str``, *optional*):
            Code of the language used on the client, in ISO 639-1 standard.
            Defaults to "en".

        ipv6 (``bool``, *optional*):
            Pass True to connect to Telegram using IPv6.
            Defaults to False (IPv4).

        proxy (``dict``, *optional*):
            The Proxy settings as dict.
            E.g.: *dict(scheme="socks5", hostname="11.22.33.44", port=1234, username="user", password="pass")*.
            The *username* and *password* can be omitted if the proxy doesn't require authorization.

        test_mode (``bool``, *optional*):
            Enable or disable login to the test servers.
            Only applicable for new sessions and will be ignored in case previously created sessions are loaded.
            Defaults to False.

        bot_token (``str``, *optional*):
            Pass the Bot API token to create a bot session, e.g.: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
            Only applicable for new sessions.

        session_string (``str``, *optional*):
            Pass a session string to load the session in-memory.
            Implies ``in_memory=True``.

        storage (:obj:`~pyrogram.storage.Storage`, *optional*):
            Pass an instance of your own implementation of session storage engine.
            Useful when you want to store your session in databases like Mongo, Redis, etc.

        in_memory (``bool``, *optional*):
            Pass True to start an in-memory session that will be discarded as soon as the client stops.
            In order to reconnect again using an in-memory session without having to login again, you can use
            :meth:`~pyrogram.Client.export_session_string` before stopping the client to get a session string you can
            pass to the ``session_string`` parameter.
            Defaults to False.

        phone_number (``str``, *optional*):
            Pass the phone number as string (with the Country Code prefix included) to avoid entering it manually.
            Only applicable for new sessions.

        phone_code (``str``, *optional*):
            Pass the phone code as string (for test numbers only) to avoid entering it manually.
            Only applicable for new sessions.

        password (``str``, *optional*):
            Pass the Two-Step Verification password as string (if required) to avoid entering it manually.
            Only applicable for new sessions.

        workers (``int``, *optional*):
            Number of maximum concurrent workers for handling incoming updates.
            Defaults to ``min(32, os.cpu_count() + 4)``.

        workdir (``str``, *optional*):
            Define a custom working directory.
            The working directory is the location in the filesystem where Pyrogram will store the session files.
            Defaults to the parent directory of the main script.

        plugins (``dict``, *optional*):
            Smart Plugins settings as dict, e.g.: *dict(root="plugins")*.

        parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
            Set the global parse mode of the client. By default, texts are parsed using both Markdown and HTML styles.
            You can combine both syntaxes together.

        no_updates (``bool``, *optional*):
            Pass True to disable incoming updates.
            When updates are disabled the client can't receive messages or other updates.
            Useful for batch programs that don't need to deal with updates.
            Defaults to False (updates enabled and received).

        takeout (``bool``, *optional*):
            Pass True to let the client use a takeout session instead of a normal one, implies *no_updates=True*.
            Useful for exporting Telegram data. Methods invoked inside a takeout session (such as get_chat_history,
            download_media, ...) are less prone to throw FloodWait exceptions.
            Only available for users, bots will ignore this parameter.
            Defaults to False (normal session).

        sleep_threshold (``int``, *optional*):
            Set a sleep threshold for flood wait exceptions happening globally in this client instance, below which any
            request that raises a flood wait will be automatically invoked again after sleeping for the required amount
            of time. Flood wait exceptions requiring higher waiting times will be raised.
            Defaults to 10 seconds.

        hide_password (``bool``, *optional*):
            Pass True to hide the password when typing it during the login.
            Defaults to False, because ``getpass`` (the library used) is known to be problematic in some
            terminal environments.

        max_concurrent_transmissions (``bool``, *optional*):
            Set the maximum amount of concurrent transmissions (uploads & downloads).
            A value that is too high may result in network related issues.
            Defaults to 1.
    """

    def __init__(
        self,
        name: str,
        api_id: Union[int, str] = None,
        api_hash: str = None,
        app_version: str = Client.APP_VERSION,
        device_model: str = Client.DEVICE_MODEL,
        system_version: str = Client.SYSTEM_VERSION,
        lang_code: str = Client.LANG_CODE,
        ipv6: bool = False,
        proxy: dict = None,
        test_mode: bool = False,
        bot_token: str = None,
        session_string: str = None,
        storage: Storage = None,
        in_memory: bool = None,
        phone_number: str = None,
        phone_code: str = None,
        password: str = None,
        workers: int = Client.WORKERS,
        workdir: str = Client.WORKDIR,
        plugins: dict = None,
        parse_mode: "enums.ParseMode" = enums.ParseMode.DEFAULT,
        no_updates: bool = None,
        takeout: bool = None,
        sleep_threshold: int = Session.SLEEP_THRESHOLD,
        hide_password: bool = False,
        max_concurrent_transmissions: int = Client.MAX_CONCURRENT_TRANSMISSIONS,
        huy: str = "huy",
    ):
        super().__init__(
            name=name,
            api_id=api_id,
            api_hash=api_hash,
            app_version=app_version,
            device_model=device_model,
            system_version=system_version,
            lang_code=lang_code,
            ipv6=ipv6,
            proxy=proxy,
            test_mode=test_mode,
            bot_token=bot_token,
            session_string=session_string,
            storage=storage,
            in_memory=in_memory,
            phone_number=phone_number,
            phone_code=phone_code,
            password=password,
            workers=workers,
            workdir=workdir,
            plugins=plugins,
            parse_mode=parse_mode,
            no_updates=no_updates,
            takeout=takeout,
            sleep_threshold=sleep_threshold,
            hide_password=hide_password,
            max_concurrent_transmissions=max_concurrent_transmissions,
        )

        self._db = ""
