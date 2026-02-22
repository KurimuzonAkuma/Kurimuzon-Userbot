from pyrogram import Client, filters, raw, enums
from pyrogram.types import Message
import re

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import with_reply


async def search_user(client: Client, user_id: int):
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


@Client.on_message(command(["spowner"]) & filters.me)
@with_reply
async def sticker_pack_owner(client: Client, message: Message):
    input_sticker_set = None

    if message.reply_to_message.sticker:
        if not message.reply_to_message.sticker.set_name:
            return await message.edit("<b>Sticker should have a set name</b>")

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

    username = await search_user(client, owner_id)

    if username:
        return await message.edit_text(
            f"<b>Sticker set owner id:</b> <code>{owner_id}</code>\n<b>Username:</b> {username}"
        )

    return await message.edit_text(
        f"<b>Sticker set owner id:</b> <code>{owner_id}</code>"
    )


module = modules_help.add_module("spowner", __file__)
module.add_command("spowner", "Get sticker pack owner id", "[reply]*")
