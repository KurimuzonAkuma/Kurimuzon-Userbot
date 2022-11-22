from pyrogram import Client, filters
from pyrogram.types import Message

from utils.misc import modules_help, prefix
from utils.scripts import paste_neko, with_args


@Client.on_message(filters.command(["nekobin", "neko"], prefix) & filters.me)
@with_args("<b>Text to paste is not provided</b>")
async def nekobin(client: Client, message: Message):
    await message.edit_text("<code>Pasting...</code>")
    await message.edit_text(
        await paste_neko(message.text.split(" ", 1)[1]), disable_web_page_preview=True
    )


modules_help["nekobin"] = {
    "nekobin [code]": "Paste text on nekobin",
    "neko [code]": "Paste text on nekobin",
}
