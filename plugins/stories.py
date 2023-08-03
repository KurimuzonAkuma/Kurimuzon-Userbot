from pyrogram import Client, filters
from pyrogram.raw.types import InputPrivacyValueAllowAll
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args


@Client.on_message(command(["story"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def post_story(client: Client, message: Message):
    media = (
        message.video
        or message.photo
        or (
            message.reply_to_message
            and (message.reply_to_message.video or message.reply_to_message.photo)
        )
    )
    if not media:
        return await message.edit_text("<b>No media found!</b>")

    if (message.media and message.media.value not in ["photo", "video", "animation"]) or (
        message.reply_to_message.media
        and message.reply_to_message.media.value not in ["photo", "video", "animation"]
    ):
        return await message.edit_text("<b>Only photos and videos and GIFs are supported!<b>")

    args, nargs = get_args(message=message, use_reply=True)

    if "-c" in args:
        caption = message.caption or (
            message.reply_to_message and message.reply_to_message.caption
        )
    else:
        caption = " ".join(args)

    media = (
        await message.download(in_memory=True)
        if message.media
        else await message.reply_to_message.download(in_memory=True)
    )
    await client.send_story(
        media=media, caption=caption, privacy_rules=[InputPrivacyValueAllowAll()], period=86400 * 7
    )

    await message.edit_text("Story posted!")


module = modules_help.add_module("stories", __file__)
module.add_command(
    "story",
    "Post story from message or reply. Pass the '-c' argument to take the caption from the media, otherwise the message will be used",
    "[reply] [-c]",
)
