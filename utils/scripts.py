import asyncio
import datetime
import json
import logging
import os
import random
import re
import secrets
import shlex
import string
import subprocess
import time
from time import perf_counter

from Cryptodome.Cipher import AES
from Cryptodome.Hash import SHA256
from Cryptodome.Protocol.KDF import PBKDF2
from Cryptodome.Random import get_random_bytes
import git
import httpx
from pyrogram import Client, errors
from pyrogram.types import Message

from utils.db import db

log = logging.getLogger(__name__)


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
        fmt = "{asctime} (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        fmt = fmt.replace("(black)", self.black + self.bold)
        fmt = fmt.replace("(reset)", self.reset)
        fmt = fmt.replace("(levelcolor)", log_color)
        fmt = fmt.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(fmt, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)


def get_proxy(proxies_path: str = "proxies.txt") -> str | None:
    try:
        with open(proxies_path) as f:
            proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        return None

    if not proxies:
        return None

    return random.choice(
        [line.strip() for line in proxies if line.strip() and not line.startswith("#")]
    )


def get_init_connection_params(
    params_path: str = "init_connection_params.json",
) -> dict | None:
    try:
        with open(params_path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


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


async def paste_yaso(code: str, token: str, expiration_time: int = 10080) -> str:
    try:
        async with httpx.AsyncClient(
            timeout=10,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "Kurimuzon-Userbot (Dubzer krutoy)",
            },
        ) as client:
            response = await client.post(
                "https://api.yaso.su/pub/records",
                json={
                    "codeLanguage": "auto",
                    "content": code,
                    "expirationTime": expiration_time,
                },
            )
            response.raise_for_status()
            result = response.json()
    except Exception as e:
        return f"Pasting failed: {e}"

    return f"https://yaso.su/{result['url']}"


def get_prefix():
    return db.get("core.main", "prefix", default=".")


def get_args_raw(message: Message | str, use_reply: bool | None = None) -> str:
    """Returns text after command.

    Args:
        message (Union[Message, str]): Message or text.

        use_reply (bool, optional): Try to get args from reply message if no args in message. Defaults to None.

    Returns:
        str: Text after command or empty string.
    """
    if isinstance(message, Message):
        text = message.text or message.caption or ""
        parts = text.split(maxsplit=1)
        args = parts[1] if len(parts) > 1 else ""

        if use_reply and not args and message.reply_to_message:
            reply = message.reply_to_message
            args = reply.text or reply.caption or ""
    elif isinstance(message, str):
        args = message
    else:
        return ""

    return args


def get_args(
    message: Message | str, use_reply: bool | None = None
) -> tuple[list[str], dict[str, str]]:
    """Returns list of common args and a dictionary with named args.

    Args:
        message (Union[Message, str]): Message or text.

        use_reply (bool, optional): Try to get args from reply message if no args in message. Defaults to None.

    Returns:
        List[str]: List of args.
        Dict[str, str]: Dictionary with named args.
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


def get_ram_usage() -> float:
    """Returns current process tree memory usage in MB"""
    try:
        import psutil  # noqa: PLC0415

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
        import psutil  # noqa: PLC0415

        current_process = psutil.Process(os.getpid())
        cpu = current_process.cpu_percent()
        for child in current_process.children(recursive=True):
            cpu += child.cpu_percent()

        return round(cpu, 1)
    except Exception:
        return 0


async def shell_exec(
    command: str,
    executable: str | None = None,
    timeout: float | None = None,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """Executes shell command and returns tuple with return code, decoded stdout and stderr"""

    def run_command():
        process = subprocess.Popen(
            command,
            shell=True,
            executable=executable,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
        )
        try:
            out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            raise
        return (
            process.returncode,
            out.decode(errors="replace"),
            err.decode(errors="replace"),
        )

    return await asyncio.to_thread(run_command)


async def handle_restart(client: Client):
    restart_info = db.get("core.updater", "restart_info")

    if not restart_info:
        return

    try:
        if restart_info["type"] == "restart":
            log.info(f"{client.me.username}#{client.me.id} | Userbot succesfully restarted.")
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

            log.info(f"{client.me.username}#{client.me.id} | {update_text}.")
            await client.edit_message_text(
                chat_id=restart_info["chat_id"],
                message_id=restart_info["message_id"],
                text=(
                    f"<code>{update_text}.\n\n"
                    f"Restarted in {perf_counter() - restart_info['time']:.3f}s...</code>"
                ),
            )
    except Exception as e:
        print(f"Error when updating: <{e.__class__.__name__}> {e}")

    db.remove("core.updater", "restart_info")


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


class TTLMemoryCache:
    def __init__(self, default_ttl: float | None = None, capacity: int = 1000):
        self.data = {}
        self.default_ttl = default_ttl
        self.capacity = capacity

    def __str__(self):
        self._cleanup()
        return str(self.data)

    def __contains__(self, key):
        self._cleanup()
        return key in self.data

    def _cleanup(self):
        current_time = time.time()
        expired_keys = [
            key
            for key, data in self.data.items()
            if data.get("ttl") is not None and data["expiry_time"] < current_time
        ]
        for key in expired_keys:
            del self.data[key]

    def set(self, key, value, ttl=None):
        self._cleanup()
        ttl = ttl or self.default_ttl
        self.data[key] = {
            "value": value,
            "ttl": ttl,
            "expiry_time": (time.time() + ttl) if ttl is not None else None,
        }

        if len(self.data) > self.capacity:
            for _ in range(self.capacity // 2 + 1):
                del self.data[next(iter(self.data))]

    def get(self, key, default=None):
        self._cleanup()
        return self.data.get(key, {}).get("value", default)

    def delete(self, key):
        self._cleanup()
        try:
            del self.data[key]
        except KeyError:
            return False
        return True


def convert_tags(text: str) -> str:
    """Convert pyrogram html tags to aiogram html tags."""
    if text is None:
        return ""

    if hasattr(text, "html"):
        text = text.html

    patterns = (
        (r"<spoiler>(.*?)</spoiler>", r"<tg-spoiler>\1</tg-spoiler>"),
        (r'<emoji id="(\d+)">(.*?)</emoji>', r'<tg-emoji emoji-id="\1">\2</tg-emoji>'),
        (
            r'<pre language="([^"]+)">([^<]+)</pre>',
            r'<pre><code class="language-\1">\2</code></pre>',
        ),
    )

    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)

    return text


def parse_duration(duration_str: str) -> int:
    match = re.match(r"^(\d+)([smhdwy]|mo)$", duration_str)

    if not match:
        raise ValueError(
            "Invalid duration format. Use a number followed by a unit (s, m, h, d, w, mo, y)."
        )

    value, unit = match.groups()
    value = int(value)

    if unit == "s":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    elif unit == "d":
        return value * 86400
    elif unit == "w":
        return value * 604800
    elif unit == "mo":
        return value * 2592000  # 30 дней в месяц
    elif unit == "y":
        return value * 31536000  # 365 дней в год

    raise ValueError("Invalid duration unit.")


def format_bytes(bytes, units=None) -> str:
    if units is None:
        units = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

    i = 0

    while bytes >= 1024 and i < len(units) - 1:
        bytes /= 1024.0
        i += 1

    return f"{bytes:.2f}{units[i]}"


def format_time(seconds: float) -> str:
    if seconds < 0 or seconds == float("inf"):
        return "-:--:--"

    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    return f"{hours}:{minutes:02d}:{secs:02d}"


def encrypt(data: bytes, password: str) -> bytes:
    if isinstance(data, str):
        data = data.encode()

    key_hash = SHA256.new(data).digest()
    plaintext = key_hash + data

    salt = get_random_bytes(16)
    iv = get_random_bytes(16)

    # PBKDF2 uses HMAC-SHA1 by default; kept for compatibility with stored data
    key = PBKDF2(password, salt, dkLen=32, count=100_000)

    pad_len = 16 - len(plaintext) % 16
    padded = plaintext + bytes([pad_len]) * pad_len

    return salt + iv + AES.new(key, AES.MODE_CBC, iv).encrypt(padded)


def decrypt(data: bytes, password: str) -> bytes:
    if len(data) < 32:
        raise ValueError("Invalid data format")

    salt = data[:16]
    iv = data[16:32]
    ciphertext = data[32:]

    key = PBKDF2(password, salt, dkLen=32, count=100_000)
    decrypted = AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext)

    pad_len = decrypted[-1]

    if not 1 <= pad_len <= 16:
        raise ValueError("Invalid padding")

    plaintext = decrypted[:-pad_len]

    stored_hash = plaintext[:32]
    decoded_data = plaintext[32:]

    computed_hash = SHA256.new(decoded_data).digest()

    if not secrets.compare_digest(stored_hash, computed_hash):
        raise ValueError("Invalid password or corrupted data")

    return decoded_data
