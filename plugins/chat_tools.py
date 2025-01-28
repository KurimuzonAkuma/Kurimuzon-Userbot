import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args_raw, with_reply


@Client.on_message(
    ~filters.scheduled & command(["d", "del"]) & filters.me & ~filters.forwarded
)
async def del_msg(_, message: Message):
    await message.delete()
    await message.reply_to_message.delete()


@Client.on_message(
    ~filters.scheduled & command("purge") & filters.me & ~filters.forwarded
)
@with_reply
async def purge(client: Client, message: Message):
    chunk = []
    async for msg in client.get_chat_history(
        chat_id=message.chat.id,
    ):
        if msg.id < message.reply_to_message.id:
            break
        chunk.append(msg.id)
        if len(chunk) >= 100:
            await client.delete_messages(message.chat.id, chunk)
            chunk.clear()
            await asyncio.sleep(1)

    if chunk:
        await client.delete_messages(message.chat.id, chunk)


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


module = modules_help.add_module("chat_tools", __file__)
module.add_command(
    "purge", "Purge (delete all messages) chat from replied message to last", "[reply]"
)
module.add_command("del", "Delete replied message", "[reply]", aliases=["d"])
module.add_command("tagall", "Tag all chat participants", "[text]")
