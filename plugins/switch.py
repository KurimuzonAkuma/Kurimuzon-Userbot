from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help

ru_keys = (
    """ёйцукенгшщзхъфывапролджэячсмитьбю.Ё"№;%:?ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭ/ЯЧСМИТЬБЮ,"""
)
en_keys = (
    """`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{}ASDFGHJKL:"|ZXCVBNM<>?"""
)
table = str.maketrans(ru_keys + en_keys, en_keys + ru_keys)


@Client.on_message(
    ~filters.scheduled & command(["switch", "sw"]) & filters.me & ~filters.forwarded
)
async def switch(client: Client, message: Message):
    if len(message.command) == 1:
        if message.reply_to_message:
            text = message.reply_to_message.text
        else:
            await message.edit("<b>Text to switch not found</b>")
            return
    else:
        text = message.text.split(maxsplit=1)[1]

    await message.edit(str.translate(text, table))


module = modules_help.add_module("switch", __file__)
module.add_command(
    "switch", "Switch keyboard layout", "[reply/text for switch]*", ["sw"]
)
