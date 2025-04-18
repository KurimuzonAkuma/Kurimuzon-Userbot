from pyrogram import Client, filters
from pyrogram.types import Message, LinkPreviewOptions

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import paste_yaso, with_args


@Client.on_message(
    ~filters.scheduled & command(["yasosu", "yaso"]) & filters.me & ~filters.forwarded
)
@with_args("<b>Text to paste is not provided</b>")
async def yasosu(client: Client, message: Message):
    await message.edit_text("<code>Pasting...</code>")
    await message.edit_text(
        await paste_yaso(message.text.split(" ", 1)[1]),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


module = modules_help.add_module("yasosu", __file__)
module.add_command("yasosu", "Paste text on yaso.su", "[code]")
module.add_command("yaso", "Paste text on yaso.su", "[code]")
