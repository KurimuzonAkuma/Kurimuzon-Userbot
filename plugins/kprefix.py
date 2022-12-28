from pyrogram import Client, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_prefix


@Client.on_message(command(["kp", "kprefix", "prefix"]) & filters.me)
async def set_prefix(_, message: Message):
    prefix = get_prefix()
    if len(message.command) == 1:
        await message.edit_text(
            f"Current prefix: <code>{prefix}</code>\n"
            f"To change prefix use <code>{prefix}{message.command[0]} [new prefix]</code>"
        )
        return
    _prefix = message.command[1]
    db.set("core.main", "prefix", _prefix)
    await message.edit(f"<b>Prefix changed to:</b> <code>{_prefix}</code>")


modules_help["kprefix"] = {
    "kprefix": "Set custom prefix",
}
