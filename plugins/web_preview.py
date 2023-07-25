from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args_raw


@Client.on_message(~filters.scheduled & command(["wp", "wpr"]) & filters.me & ~filters.forwarded)
async def web_preview(_, message: Message):
    args = get_args_raw(message)

    if not args and message.command[0] == "wp":
        return await message.edit("<b>Link to site isn't provided</b>")

    if message.command[0] == "wpr" and message.reply_to_message:
        args = message.reply_to_message.text or message.reply_to_message.caption

    await message.reply_photo(photo=f"https://mini.s-shot.ru/1024x768/JPEG/1024/Z100/?{args}")


modules_help["web_preview"] = {
    "wp [link to site]": "Send web preview of site",
    "wpr [reply to message]": "Send web preview of site from replied message",
}
