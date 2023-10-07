import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args_raw


@Client.on_message(command(["tagall"]) & filters.me)
async def tagall_handler(client: Client, message: Message):
    await message.delete()

    args = get_args_raw(message) or '<a href="tg://settings">@all</a>'

    tags = [
        f'<a href="tg://user?id={member.user.id}">\xad</a>'
        async for member in client.get_chat_members(message.chat.id)
    ]

    for i in range(0, len(tags), 5):
        await message.reply(args + "".join(tags[i : i + 5]), quote=False)
        await asyncio.sleep(0.1)


module = modules_help.add_module("tagall", __file__)
module.add_command("tagall", "Tag all chat participants", "[text]")
