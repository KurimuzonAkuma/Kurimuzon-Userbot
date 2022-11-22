import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.misc import modules_help, prefix


@Client.on_message(filters.command(["ah"], prefix) & filters.me)
async def colorful_hearts(client: Client, message: Message):
    command = message.text.split(maxsplit=1)
    cycles = command[-1]
    if len(message.command) == 1 or not command[-1].isdigit():
        cycles = 1

    hearts = ["🧡", "💛", "💚", "💙", "💜", "🤎", "🖤", "🤍", "❤️"]
    for _ in range(int(cycles)):
        for heart in hearts:
            await message.edit_text(heart)
            await asyncio.sleep(0.35)


modules_help["colorful heart"] = {"ah [cyclec]": "Animated colorful hearts"}
