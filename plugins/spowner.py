import re

from pyrogram import Client, enums, filters, raw
from pyrogram.types import Message

from utils import loader
from utils.loader import CommandArg, Plugin


class Spowner(Plugin):
    async def search_user(self, client: Client, user_id: int) -> str | None:
        try:
            r = await client.get_inline_bot_results(
                bot="@tgdb_search_bot",
                query=str(user_id),
            )

            match = re.search(r"(@\w+)", r.results[0].send_message.message)

            if match:
                return match.group(1)
        except TimeoutError:
            pass

        return None

    @loader.command(
        "spowner",
        description="Get the owner ID of a sticker set",
        args=[CommandArg("reply", "sticker or custom emoji", required=False)],
        filters=~filters.scheduled & filters.me,
    )
    async def spowner(self, client: Client, message: Message):
        if not message.reply_to_message:
            return await message.edit("Reply to a sticker or custom emoji")

        input_sticker_set = None
        if message.reply_to_message.sticker:
            if not message.reply_to_message.sticker.set_name:
                return await message.edit("<b>Sticker has no set name</b>")
            input_sticker_set = raw.types.InputStickerSetShortName(
                short_name=message.reply_to_message.sticker.set_name
            )
        elif message.reply_to_message.entities:
            for entity in message.reply_to_message.entities:
                if entity.type == enums.MessageEntityType.CUSTOM_EMOJI:
                    r = await client.invoke(
                        raw.functions.messages.GetCustomEmojiDocuments(
                            document_id=[entity.custom_emoji_id]
                        )
                    )
                    for attr in r[0].attributes:
                        if isinstance(attr, raw.types.DocumentAttributeCustomEmoji):
                            input_sticker_set = attr.stickerset
                            break
                    break

        if not input_sticker_set:
            return await message.edit("<b>Sticker not found</b>")

        r = await client.invoke(
            raw.functions.messages.GetStickerSet(
                hash=0,
                stickerset=input_sticker_set,
            )
        )
        if not r:
            return await message.edit("<b>Sticker set not found</b>")

        owner_id = r.set.id >> 32
        if (r.set.id >> 16 & 0xFF) == 0x3F:
            owner_id |= 0x80000000
        if r.set.id >> 24 & 0xFF:
            owner_id += 0x100000000

        username = await self.search_user(client, owner_id)
        if username:
            return await message.edit_text(
                f"<b>Sticker set owner ID:</b> <code>{owner_id}</code>\n<b>Username:</b> {username}"
            )
        return await message.edit_text(f"<b>Sticker set owner ID:</b> <code>{owner_id}</code>")
