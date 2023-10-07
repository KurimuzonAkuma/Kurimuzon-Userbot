import asyncio
import datetime

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import format_exc, get_args_raw


@Client.on_message(command(["kickdel"]) & filters.me)
async def kick_delete_handler(client: Client, message: Message):
    await message.edit("<b>Kicking deleted accounts...</b>")
    try:
        values = [
            await message.chat.ban_member(
                member.user.id, datetime.datetime.now() + datetime.timedelta(seconds=31)
            )
            async for member in client.get_chat_members(message.chat.id)
            if member.user.is_deleted
        ]
    except Exception as e:
        return await message.edit(format_exc(e))
    await message.edit(f"<b>Successfully kicked {len(values)} deleted account(s)</b>")


module = modules_help.add_module("admintool", __file__)
module.add_command("kickdel", "Kick all deleted accounts from chat")
