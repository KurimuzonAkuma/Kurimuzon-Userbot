import asyncio
import datetime

from pyrogram import Client, enums, errors, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import format_exc, get_args


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

    await asyncio.sleep(5)

    await message.delete()


@Client.on_message(command(["ban"]) & filters.me)
async def ban_handler(client: Client, message: Message):
    if message.chat.type not in (
        enums.ChatType.FORUM,
        enums.ChatType.SUPERGROUP,
        enums.ChatType.GROUP,
    ):
        return await message.edit("Invalid chat type")

    args, _ = get_args(message)

    user_id = None

    if message.reply_to_message:
        user_id = (
            message.reply_to_message.from_user.id
            or message.reply_to_message.sender_chat.id
        )
    elif args:
        if args[0].isdigit():
            user_id = int(args[0])
        else:
            user_id = args[0]

    if not user_id:
        return await message.edit("User not found")

    try:
        await message.chat.ban_member(user_id)
        await message.edit(f"User <code>{user_id}</code> has been banned")
    except errors.UserAdminInvalid:
        return await message.edit("You can't change rights of this user")
    except errors.ChatAdminRequired:
        return await message.edit("You don't have admin rights")
    except Exception as e:
        print(e)

    await asyncio.sleep(5)

    await message.delete()


@Client.on_message(command(["unban"]) & filters.me)
async def unban_handler(client: Client, message: Message):
    if message.chat.type not in (
        enums.ChatType.FORUM,
        enums.ChatType.SUPERGROUP,
        enums.ChatType.GROUP,
    ):
        return await message.edit("Invalid chat type")

    args, _ = get_args(message)

    user_id = None

    if message.reply_to_message:
        user_id = (
            message.reply_to_message.from_user.id
            or message.reply_to_message.sender_chat.id
        )
    elif args:
        if args[0].isdigit():
            user_id = int(args[0])
        else:
            user_id = args[0]

    if not user_id:
        return await message.edit("User not found")

    try:
        await message.chat.unban_member(user_id)
        await message.edit(f"User <code>{user_id}</code> has been unbanned")
    except errors.UserAdminInvalid:
        return await message.edit("You can't change rights of this user")
    except errors.ChatAdminRequired:
        return await message.edit("You don't have admin rights")
    except Exception as e:
        print(e)

    await asyncio.sleep(5)

    await message.delete()


module = modules_help.add_module("admin_tools", __file__)
module.add_command("kickdel", "Kick all deleted accounts from chat")
module.add_command("ban", "Ban user from chat", "[user_id]")
module.add_command("unban", "Unban user from chat", "[user_id]")
