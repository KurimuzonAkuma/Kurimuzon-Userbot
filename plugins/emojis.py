from pyrogram import Client, enums, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import with_premium


@Client.on_message(~filters.scheduled & command(["emojis"]) & filters.me & ~filters.forwarded)
@with_premium
async def emojis(_, message: Message):
    entities = message.entities or message.caption_entities or []

    if message.reply_to_message:
        entities = entities + (
            message.reply_to_message.entities or message.reply_to_message.caption_entities
        )

    if not entities:
        return await message.edit_text("No entities found")

    result = [
        f"<emoji id={entity.custom_emoji_id}>🤨</emoji> - <code>{entity.custom_emoji_id}</code>"
        for entity in entities
        if entity.type == enums.MessageEntityType.CUSTOM_EMOJI
    ]

    if not result:
        return await message.edit_text("No emojis found")

    await message.edit_text("\n".join(result))


module = modules_help.add_module("emojis", __file__)
module.add_command("emojis", "Print custom emojis with their identifiers")
