from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import paste_neko, with_args


@Client.on_message(
    ~filters.scheduled & command(["nekobin", "neko"]) & filters.me & ~filters.forwarded
)
@with_args("<b>Text to paste is not provided</b>")
async def nekobin(client: Client, message: Message):
    await message.edit_text("<code>Pasting...</code>")
    await message.edit_text(
        await paste_neko(message.text.split(" ", 1)[1]), disable_web_page_preview=True
    )


module = modules_help.add_module("nekobin", __file__)
module.add_command("nekobin", "Paste text on nekobin", "[code]")
module.add_command("neko", "Paste text on nekobin", "[code]")
