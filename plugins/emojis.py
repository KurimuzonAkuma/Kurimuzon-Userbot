from pyrogram import enums, filters
from pyrogram.types import Message

from utils import loader
from utils.loader import Plugin


class Emojis(Plugin):
    @loader.command(
        "emojis",
        description="Print custom emojis with their identifiers",
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def emojis(self, _, message: Message):
        entities = message.entities or message.caption_entities or []

        if message.reply_to_message:
            reply_entities = (
                message.reply_to_message.entities or message.reply_to_message.caption_entities or []
            )
            entities.extend(reply_entities)

        if not entities:
            return await message.edit_text("No entities found")

        result = [
            f"<emoji id={entity.custom_emoji_id}>🤨</emoji> - <code>{entity.custom_emoji_id}</code>"
            for entity in entities
            if entity.type == enums.MessageEntityType.CUSTOM_EMOJI
        ]

        if not result:
            return await message.edit_text("No custom emojis found")

        await message.edit_text("\n".join(result))
