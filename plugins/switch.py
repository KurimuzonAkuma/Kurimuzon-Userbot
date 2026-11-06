from pyrogram import filters
from pyrogram.types import Message

from utils import loader
from utils.loader import CommandArg, Plugin


class Switch(Plugin):
    ru_keys = """ёйцукенгшщзхъфывапролджэячсмитьбю.Ё"№;%:?ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭ/ЯЧСМИТЬБЮ,"""
    en_keys = """`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{}ASDFGHJKL:"|ZXCVBNM<>?"""
    table = str.maketrans(ru_keys + en_keys, en_keys + ru_keys)

    @loader.command(
        ["switch", "sw"],
        description="Switch the keyboard layout",
        args=[CommandArg("text", "text to switch", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def switch(self, _, message: Message):
        if len(message.command) == 1:
            if message.reply_to_message:
                text = message.reply_to_message.text
            else:
                await message.edit("<b>Text to switch not found</b>")
                return
        else:
            text = message.text.split(maxsplit=1)[1]

        await message.edit(str.translate(text, self.table))
