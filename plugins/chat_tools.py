import asyncio

from pyrogram import Client, enums, filters
from pyrogram.types import Message

from utils import loader
from utils.loader import CommandArg, Plugin
from utils.scripts import get_args_raw


class ChatTools(Plugin):
    @loader.command(
        ["del", "d"],
        description="Delete the replied message",
        args=[CommandArg("reply", "message to delete", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def del_msg(self, _, message: Message):
        if not message.reply_to_message:
            return await message.edit("Reply to a message first")
        await message.delete()
        await message.reply_to_message.delete()

    @loader.command(
        "purge",
        description="Delete all chat messages from the replied message to the latest",
        args=[CommandArg("reply", "start from replied message", required=False)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def purge(self, client: Client, message: Message):
        if not message.reply_to_message:
            return await message.edit("Reply to a message first")

        message_ids = []
        async for msg in client.get_chat_history(
            chat_id=message.chat.id,
            min_id=message.reply_to_message.id,
            max_id=message.id,
        ):
            if message.message_thread_id != msg.message_thread_id:
                continue
            message_ids.append(msg.id)
            if len(message_ids) >= 100:
                await client.delete_messages(message.chat.id, message_ids)
                message_ids.clear()
                await asyncio.sleep(1)

        if message_ids:
            await client.delete_messages(message.chat.id, message_ids)

    @loader.command(
        "tagall",
        description="Tag all chat participants",
        args=[CommandArg("text", "text to tag with", required=False)],
        filters=~filters.scheduled & filters.me,
    )
    async def tagall(self, client: Client, message: Message):
        if message.chat.type not in (
            enums.ChatType.FORUM,
            enums.ChatType.SUPERGROUP,
            enums.ChatType.GROUP,
        ):
            return await message.edit("This command is only available in groups and supergroups")

        await message.delete()
        args = get_args_raw(message) or '<a href="tg://settings">@all</a>'

        tags = [
            f'<a href="tg://user?id={member.user.id}">\xad</a>'
            async for member in client.get_chat_members(message.chat.id)
        ]

        for i in range(0, len(tags), 5):
            await message.reply(
                args + "".join(tags[i : i + 5]),
            )
            await asyncio.sleep(0.1)
