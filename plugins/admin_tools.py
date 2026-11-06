import asyncio
import datetime
import re

from pyrogram import Client, enums, errors, filters
from pyrogram.types import ChatPermissions, Message

from utils import loader
from utils.loader import CommandArg, Plugin
from utils.scripts import format_exc, get_args


def _get_target_user_id(message: Message, args: list[str]):
    if message.reply_to_message:
        sender = message.reply_to_message.from_user or message.reply_to_message.sender_chat
        return sender.id if sender else None

    if args:
        return int(args[0]) if args[0].isdigit() else args[0]

    return None


def _parse_duration(value: str | None) -> datetime.timedelta | None:
    if value is None:
        return None

    match = re.fullmatch(r"(\d+)([smhd])", value.lower())
    if match is None:
        raise ValueError("Use a duration such as 30s, 15m, 2h, or 1d")

    amount = int(match.group(1))
    unit = {
        "s": "seconds",
        "m": "minutes",
        "h": "hours",
        "d": "days",
    }[match.group(2)]
    duration = datetime.timedelta(**{unit: amount})
    if duration < datetime.timedelta(seconds=30) or duration > datetime.timedelta(days=366):
        raise ValueError("Duration must be between 30 seconds and 366 days")

    return duration


class AdminTools(Plugin):
    @loader.command(
        "kickdel",
        description="Kick all deleted accounts from chat",
        filters=~filters.scheduled & filters.me,
    )
    async def kickdel(self, client: Client, message: Message):
        await message.edit("<b>Kicking deleted accounts...</b>")
        try:
            values = [
                await message.chat.ban_member(
                    member.user.id,
                    datetime.datetime.now() + datetime.timedelta(seconds=31),
                )
                async for member in client.get_chat_members(message.chat.id)
                if member.user.is_deleted
            ]
        except Exception as e:
            return await message.edit(format_exc(e))

        await message.edit(f"<b>Successfully kicked {len(values)} deleted account(s)</b>")
        await asyncio.sleep(5)
        await message.delete()

    @loader.command(
        "kick",
        description="Kick user from chat",
        args=[CommandArg("user_id", "user id or reply", required=False)],
        filters=~filters.scheduled & filters.me,
    )
    async def kick(self, client: Client, message: Message):
        if message.chat.type not in (
            enums.ChatType.FORUM,
            enums.ChatType.SUPERGROUP,
            enums.ChatType.GROUP,
        ):
            return await message.edit("Invalid chat type")

        args, _ = get_args(message)
        user_id = _get_target_user_id(message, args)

        if not user_id:
            return await message.edit("User not found")

        try:
            await message.chat.ban_member(user_id, until_date=datetime.timedelta(seconds=31))
            await message.edit(f"User <code>{user_id}</code> has been kicked")
        except errors.UserAdminInvalid:
            return await message.edit("You can't change rights of this user")
        except errors.ChatAdminRequired:
            return await message.edit("You don't have admin rights")
        except Exception as e:
            return await message.edit(format_exc(e))

        await asyncio.sleep(5)
        await message.delete()

    @loader.command(
        "mute",
        description="Mute user in chat",
        args=[
            CommandArg("user_id", "user id or reply", required=False),
            CommandArg("duration", "e.g. 30m, 2h, 1d", required=False),
        ],
        filters=~filters.scheduled & filters.me,
    )
    async def mute(self, client: Client, message: Message):
        if message.chat.type not in (
            enums.ChatType.FORUM,
            enums.ChatType.SUPERGROUP,
            enums.ChatType.GROUP,
        ):
            return await message.edit("Invalid chat type")

        args, _ = get_args(message)
        user_id = _get_target_user_id(message, args)
        if not user_id:
            return await message.edit("User not found")

        duration_arg = (
            args[0] if message.reply_to_message and args else args[1] if len(args) > 1 else None
        )
        try:
            duration = _parse_duration(duration_arg)
        except ValueError as e:
            return await message.edit(str(e))

        try:
            await client.restrict_chat_member(
                message.chat.id,
                user_id,
                ChatPermissions(
                    can_send_messages=False,
                    can_send_audios=False,
                    can_send_documents=False,
                    can_send_photos=False,
                    can_send_videos=False,
                    can_send_video_notes=False,
                    can_send_voice_notes=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_react_to_messages=False,
                ),
                until_date=duration,
            )
            suffix = f" for {duration_arg}" if duration_arg else ""
            await message.edit(f"User <code>{user_id}</code> has been muted{suffix}")
        except errors.UserAdminInvalid:
            return await message.edit("You can't change rights of this user")
        except errors.ChatAdminRequired:
            return await message.edit("You don't have admin rights")
        except Exception as e:
            return await message.edit(format_exc(e))

        await asyncio.sleep(5)
        await message.delete()

    @loader.command(
        "unmute",
        description="Unmute user in chat",
        args=[CommandArg("user_id", "user id or reply", required=False)],
        filters=~filters.scheduled & filters.me,
    )
    async def unmute(self, client: Client, message: Message):
        if message.chat.type not in (
            enums.ChatType.FORUM,
            enums.ChatType.SUPERGROUP,
            enums.ChatType.GROUP,
        ):
            return await message.edit("Invalid chat type")

        args, _ = get_args(message)
        user_id = _get_target_user_id(message, args)
        if not user_id:
            return await message.edit("User not found")

        try:
            await client.restrict_chat_member(
                message.chat.id,
                user_id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_react_to_messages=True,
                ),
            )
            await message.edit(f"User <code>{user_id}</code> has been unmuted")
        except errors.UserAdminInvalid:
            return await message.edit("You can't change rights of this user")
        except errors.ChatAdminRequired:
            return await message.edit("You don't have admin rights")
        except Exception as e:
            return await message.edit(format_exc(e))

        await asyncio.sleep(5)
        await message.delete()

    @loader.command(
        "ban",
        description="Ban user from chat",
        args=[
            CommandArg("user_id", "user id or reply", required=False),
            CommandArg("duration", "e.g. 30m, 2h, 1d", required=False),
        ],
        filters=~filters.scheduled & filters.me,
    )
    async def ban(self, client: Client, message: Message):
        if message.chat.type not in (
            enums.ChatType.FORUM,
            enums.ChatType.SUPERGROUP,
            enums.ChatType.GROUP,
        ):
            return await message.edit("Invalid chat type")

        args, _ = get_args(message)
        user_id = _get_target_user_id(message, args)

        if not user_id:
            return await message.edit("User not found")

        duration_arg = (
            args[0] if message.reply_to_message and args else args[1] if len(args) > 1 else None
        )
        try:
            duration = _parse_duration(duration_arg)
        except ValueError as e:
            return await message.edit(str(e))

        try:
            await message.chat.ban_member(user_id, until_date=duration)
            suffix = f" for {duration_arg}" if duration_arg else ""
            await message.edit(f"User <code>{user_id}</code> has been banned{suffix}")
        except errors.UserAdminInvalid:
            return await message.edit("You can't change rights of this user")
        except errors.ChatAdminRequired:
            return await message.edit("You don't have admin rights")
        except Exception as e:
            return await message.edit(format_exc(e))

        await asyncio.sleep(5)
        await message.delete()

    @loader.command(
        "unban",
        description="Unban user from chat",
        args=[CommandArg("user_id", "user id or reply", required=False)],
        filters=~filters.scheduled & filters.me,
    )
    async def unban(self, client: Client, message: Message):
        if message.chat.type not in (
            enums.ChatType.FORUM,
            enums.ChatType.SUPERGROUP,
            enums.ChatType.GROUP,
        ):
            return await message.edit("Invalid chat type")

        args, _ = get_args(message)
        user_id = _get_target_user_id(message, args)

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
            return await message.edit(format_exc(e))

        await asyncio.sleep(5)
        await message.delete()
