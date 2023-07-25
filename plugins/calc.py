from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args_raw, with_args


@Client.on_message(command(["calc", "c"]) & filters.me)
@with_args("Expression required to calculate")
async def calc(_, message: Message):
    args = get_args_raw(message)

    try:
        await message.edit(f"<i>{args}</i><b> = </b><code>{eval(args)}</code>")
    except Exception as e:
        await message.edit(f"<i>{args}</i><b> = </b><code>{e}</code>")


modules_help["calculator"] = {"calc [expression]*": "Evaluate expression and return result"}
