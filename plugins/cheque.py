import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command, viabot
from utils.misc import modules_help
from utils.scripts import with_args


@Client.on_message(~filters.scheduled & viabot("CryptoBot") & ~filters.me)
async def cheque_hunter(client: Client, message: Message):
    if not message.reply_markup:
        return
    if not db.get("chequehunter", "enabled", True):
        return

    if (
        "Получить" in message.reply_markup.inline_keyboard[0][0].text
        or "Receive" in message.reply_markup.inline_keyboard[0][0].text
    ):
        await asyncio.sleep(0.5)
        cheque_url = message.reply_markup.inline_keyboard[0][0].url
        cheque = cheque_url.split("start=")[-1]

        await client.send_message("CryptoBot", f"/start {cheque}")


@Client.on_message(filters.me & command("cheque"))
@with_args("<b>Argument on/off required!</b>")
async def cheque_toggle(_: Client, message: Message):
    if message.command[1] == "on":
        db.set("chequehunter", "enabled", True)
        await message.edit_text("Чек-хантер включен.")
    elif message.command[1] == "off":
        db.set("chequehunter", "enabled", False)
        await message.edit_text("Чек-хантер выключен.")


modules_help["cheque"] = {
    "cheque [on/off]": "On/Off CryptoBot cheque hunter",
}
