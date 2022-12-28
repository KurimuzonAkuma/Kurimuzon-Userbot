import asyncio
import itertools

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help


@Client.on_message(command(["ah"]) & filters.me)
async def colorful_hearts(client: Client, message: Message):
    command = message.text.split(maxsplit=1)
    cycles = command[-1]
    if len(message.command) == 1 or not cycles.isdigit():
        cycles = 1

    hearts = ["🧡", "💛", "💚", "💙", "💜", "🤎", "🖤", "🤍", "❤️"]
    for _, heart in itertools.product(range(int(cycles)), hearts):
        await message.edit_text(heart)
        await asyncio.sleep(0.35)


modules_help["colorful heart"] = {"ah [cyclec]": "Animated colorful hearts"}
