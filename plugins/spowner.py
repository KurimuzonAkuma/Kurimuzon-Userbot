from pyrogram import Client, filters, raw
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import with_reply


@Client.on_message(command(["spowner"]) & filters.me)
@with_reply
async def calc(client: Client, message: Message):
    if not message.reply_to_message.sticker:
        return await message.edit("<b>No sticker found</b>")

    set_name = message.reply_to_message.sticker.set_name

    if message.reply_to_message.sticker and not set_name:
        return await message.edit("<b>Sticker has no set name</b>")

    r = await client.invoke(
        raw.functions.messages.GetStickerSet(
            hash=0,
            stickerset=raw.types.InputStickerSetShortName(short_name=set_name),
        )
    )

    if not r:
        return await message.edit("<b>Sticker set not found</b>")

    owner_id = r.set.id >> 32

    if r.set.id >> 24 & 0xFF:
        owner_id += 0x100000000

    await message.edit_text(f"<b>Sticker set owner id:</b> <code>{owner_id}</code>")


module = modules_help.add_module("spowner", __file__)
module.add_command("spowner", "Get sticker pack owner id", "[reply]*")
