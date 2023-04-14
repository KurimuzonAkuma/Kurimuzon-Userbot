import subprocess
import sys
from time import perf_counter

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import format_exc, get_commits, restart


@Client.on_message(
    ~filters.scheduled & command(["restart", "рестарт"]) & filters.me & ~filters.forwarded
)
async def _restart(_: Client, message: Message):
    db.set(
        "core.updater",
        "restart_info",
        {
            "chat_id": message.chat.id,
            "message_id": message.id,
            "time": perf_counter(),
            "type": "restart",
        },
    )
    await message.edit("<code>Restarting...</code>")
    restart()


@Client.on_message(
    ~filters.scheduled & command(["update", "апдейт"]) & filters.me & ~filters.forwarded
)
async def _update(_: Client, message: Message):
    repo = get_commits()
    db.set(
        "core.updater",
        "restart_info",
        {
            "chat_id": message.chat.id,
            "message_id": message.id,
            "time": perf_counter(),
            "version": repo.get("current_hash"),
            "type": "update",
        },
    )
    await message.edit("<code>Updating...</code>")

    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-U", "pip"])
        subprocess.run(["git", "pull"])
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-U",
                "-r",
                "requirements.txt",
            ]
        )
    except Exception as e:
        await message.edit(format_exc(e))
        db.remove("core.updater", "restart_info")
    else:
        restart()


modules_help["updater"] = {
    "restart": "Useful when you want to reload a bot",
    "update": "Update the userbot from the repository",
}
