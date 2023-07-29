import random

from pyrogram import Client, filters
from pyrogram.raw.functions.messages import GetMessages
from pyrogram.raw.functions.stories import SendStory
from pyrogram.raw.types import (
    InputMediaPhoto,
    InputMediaUploadedDocument,
    InputMessageID,
    InputPhoto,
    InputPrivacyValueAllowAll,
)
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import with_reply


@Client.on_message(command(["story"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
@with_reply
async def post_story(client: Client, message: Message):
    if message.reply_to_message.media.value not in ["photo", "video", "animation"]:
        return await message.edit_text("Only photos and videos and GIFs are supported!")

    if message.reply_to_message.photo:
        msg = await client.invoke(GetMessages(id=[InputMessageID(id=message.reply_to_message.id)]))
        photo = msg.messages[0].media.photo
        media = InputMediaPhoto(
            id=InputPhoto(
                id=photo.id,
                access_hash=photo.access_hash,
                file_reference=photo.file_reference,
            )
        )
    else:
        media = InputMediaUploadedDocument(
            file=await client.save_file(
                path=await message.reply_to_message.download(in_memory=True)
            ),
            mime_type="video/mp4",
            attributes=[],
        )

    await client.invoke(
        SendStory(
            media=media,
            privacy_rules=[InputPrivacyValueAllowAll()],
            random_id=random.randint(-1 << 31 - 1, 1 << 31 - 1),
            period=86400,
        )
    )

    await message.edit_text("Story posted!")


modules_help["stories"] = {
    "story [reply]*": "Post story from reply",
}
