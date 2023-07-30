from time import perf_counter

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help


@Client.on_message(~filters.scheduled & command(["ping", "p"]) & filters.me & ~filters.forwarded)
async def ping(_, message: Message):
    start = perf_counter()
    await message.edit("<b>Pong!</b>")
    end = perf_counter()
    await message.edit(f"<b>Pong! {round(end - start, 3)}s</b>")


module = modules_help.add_module("ping", __file__)
module.add_command("ping", "Check ping to Telegram servers", aliases=["p"])
