import asyncio
import base64
import datetime
import re
from io import BytesIO
from typing import List, Tuple, Union

import aiosqlite
from apscheduler.triggers.interval import IntervalTrigger
from pyrogram import Client, filters
from pyrogram.types import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from utils.config import api_hash, api_id
from utils.db import db
from utils.filters import command, reactions_filter
from utils.misc import modules_help, scheduler, scheduler_jobs
from utils.scripts import ScheduleJob, get_args_raw, get_full_name


class Govno:
    async def init_bot(self):
        self.bot = Client(
            name="dmessages_bot",
            api_id=api_id,
            api_hash=api_hash,
            in_memory=True,
            bot_token=db.get("dmessages", "bot_token"),
        )
        await self.bot.start()

    async def init_db(self):
        self.db = DMDatabase()
        await self.db.connect()
        await self.db.create_tables()


govno = Govno()
loop = asyncio.get_event_loop()
loop.create_task(govno.init_bot())
loop.create_task(govno.init_db())


class DMDatabase:
    def __init__(self, path: str = "dmessages.db"):
        self.path = path
        self.conn = None
        self.cursor = None

    async def connect(self):
        if self.conn is None:
            self.conn = await aiosqlite.connect(self.path)
            self.cursor = await self.conn.cursor()
            self.cursor.row_factory = aiosqlite.Row

        return self.conn

    async def close(self):
        if self.conn is None:
            return

        await self.cursor.close()
        await self.conn.close()
        self.conn = None
        self.cursor = None

    async def execute(self, query: str, values: tuple = None, commit: bool = True) -> Tuple[dict]:
        await self.cursor.execute(query, values)

        if commit:
            await self.conn.commit()

        return await self.cursor.fetchall()

    async def create_tables(self):
        await self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dmessages (
                message_id INTEGER NOT NULL PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                username TEXT,
                type TEXT NOT NULL,
                text TEXT,
                media TEXT,
                media_group_id INTEGER,
                media_name TEXT,
                date REAL NOT NULL
            )
            """
        )

    async def delete_messages(self, message_ids: Union[int, List[int]]):
        if isinstance(message_ids, int):
            message_ids = [message_ids]

        await self.execute(
            f"DELETE FROM dmessages WHERE message_id IN ({', '.join('?' * len(message_ids))})",
            tuple(message_ids),
        )
        await self.vacuum()

    async def vacuum(self):
        await self.execute("VACUUM;")

    async def delete_old_messages(self, days: int = 1):
        await self.execute(
            "DELETE FROM dmessages WHERE date < ?;",
            (int(datetime.datetime.now().timestamp()) - 86400 * days,),
        )
        await self.vacuum()

    async def update_text_message(self, message: Message):
        user_fullname = get_full_name(message.from_user)

        await self.execute(
            """
            UPDATE dmessages SET
                name = ?,
                username = ?,
                text = ?,
                date = ?
            WHERE message_id = ?
            """,
            (
                user_fullname,
                message.chat.username,
                message.text.html,
                message.date.timestamp(),
                message.id,
            ),
        )

    async def save_text_message(self, message: Message):
        user_fullname = get_full_name(message.from_user)
        await self.execute(
            """
            INSERT INTO dmessages (
                chat_id,
                message_id,
                name,
                username,
                type,
                text,
                date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.chat.id,
                message.id,
                user_fullname,
                message.chat.username,
                "text",
                message.text.html,
                message.date.timestamp(),
            ),
        )

    async def save_media_message(self, message: Message):
        user_fullname = get_full_name(message.from_user)
        media = await message.download(in_memory=True)

        await self.execute(
            """
            INSERT INTO dmessages (
                chat_id,
                message_id,
                name,
                username,
                type,
                text,
                media,
                media_group_id,
                media_name,
                date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.chat.id,
                message.id,
                user_fullname,
                message.chat.username,
                message.media.value,
                message.caption.html if message.caption else "",
                base64.b64encode(bytes(media.getbuffer())).decode(),
                message.media_group_id,
                media.name,
                message.date.timestamp(),
            ),
        )

    async def get_messages(
        self, message_ids: Union[List[int], int], limit: int = 5
    ) -> Union[List[dict], None]:
        if isinstance(message_ids, int):
            message_ids = [message_ids]

        return await self.execute(
            f"SELECT * FROM dmessages WHERE message_id IN ({', '.join('?' * len(message_ids))}) ORDER BY date DESC LIMIT ?",
            tuple(message_ids) + (limit,),
        )

    async def get_media_group(self, media_group_id: int) -> Union[List[dict], None]:
        return await self.execute(
            "SELECT * FROM dmessages WHERE media_group_id = ? ORDER BY date DESC",
            (media_group_id,),
        )


@Client.on_message(~filters.me & ~filters.bot & filters.private & filters.text, group=1000)
async def dmessages_text_handler(client: Client, message: Message):
    if not db.get("dmessages", "enabled", False):
        return

    await govno.db.save_text_message(message)


@Client.on_message(~filters.me & ~filters.bot & filters.private & filters.media, group=1000)
async def dmessages_media_handler(client: Client, message: Message):
    if not db.get("dmessages", "enabled", False):
        return

    await govno.db.save_media_message(message)


@Client.on_edited_message(~filters.me & filters.private & ~reactions_filter, group=1000)
async def dmessages_on_edited_handler(client: Client, message: Message):
    if not db.get("dmessages", "enabled", False):
        return

    old_messages = await govno.db.get_messages(message.id)

    if not old_messages:
        return

    for old_message in old_messages:
        if old_message["type"] == "text":
            if len(old_message["text"]) > 2000:
                await govno.bot.send_message(
                    client.me.id,
                    f"<b>Edited message from {old_message['name']}</b>\n{old_message['text']}",
                )
                await govno.bot.send_message(
                    client.me.id,
                    message.text.html,
                )
            else:
                await govno.bot.send_message(
                    client.me.id,
                    f"<b>Edited message from {old_message['name']}</b>\n"
                    f"{old_message['text']}\n->\n{message.text.html}",
                )

            await govno.db.update_text_message(message)


@Client.on_deleted_messages(group=1000)
async def dmessages_on_deleted_handler(client: Client, messages: List[Message]):
    if not db.get("dmessages", "enabled", False):
        return

    max_to_show = db.get("dmessages", "max_to_show", 5)

    deleted_messages = await govno.db.get_messages(
        message_ids=[message.id for message in messages], limit=max_to_show
    )

    if not deleted_messages:
        return

    processed_media_groups_ids = []

    for deleted_message in deleted_messages:
        if deleted_message["type"] == "text":
            await govno.bot.send_message(
                client.me.id,
                f"<b>Deleted message from {deleted_message['name']}</b>\n{deleted_message['text']}",
            )

        # media group can only be photo/video or document/audio
        elif deleted_message["type"] in ["photo", "video", "document", "audio"]:
            if deleted_message["media_group_id"]:
                if deleted_message["media_group_id"] in processed_media_groups_ids:
                    continue
                processed_media_groups_ids.append(deleted_message["media_group_id"])

                media_group = await govno.db.get_media_group(deleted_message["media_group_id"])
                input_media_group = []

                for media in media_group:
                    data = BytesIO(base64.b64decode(media["media"]))
                    caption = (
                        f"<b>Deleted message from {deleted_message['name']}</b>\n{media['text']}"
                    )
                    if media["type"] == "photo":
                        input_media_group.append(InputMediaPhoto(data, caption))
                    elif media["type"] == "video":
                        input_media_group.append(InputMediaVideo(data, caption))
                    elif media["type"] == "document":
                        input_media_group.append(InputMediaDocument(data, caption))
                    elif media["type"] == "audio":
                        input_media_group.append(InputMediaAudio(data, caption))
                    else:
                        continue

                if input_media_group:
                    await govno.bot.send_media_group(client.me.id, media=input_media_group)
            else:
                await govno.bot.send_document(
                    client.me.id,
                    BytesIO(base64.b64decode(deleted_message["media"])),
                    caption=f"<b>Deleted message from {deleted_message['name']}</b>\n{deleted_message['text']}",
                    file_name=deleted_message["media_name"],
                )

    await govno.db.delete_messages([message["message_id"] for message in deleted_messages])


@Client.on_message(
    command(["dmessages", "dm"]) & filters.me & ~filters.forwarded & ~filters.scheduled
)
async def dmessages_state_handler(client: Client, message: Message):
    args = get_args_raw(message)

    is_enabled = db.get("dmessages", "enabled", False)
    if not args:
        return await message.edit_text(f"<b>Deleted messages enabled: {is_enabled}</b>")
    elif args.lower() not in ("on", "off", "1", "0", "true", "false"):
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> State should be on/off</b>",
            quote=True,
        )

    if args.lower() in ("on", "1", "true"):
        job = scheduler.get_job("dmessages_job")
        if job:
            job.resume()
        db.set("dmessages", "enabled", True)
        return await message.edit_text(
            "<emoji id=5260726538302660868>✅</emoji><b> Deleted messages enabled</b>"
        )
    else:
        db.set("dmessages", "enabled", False)
        return await message.edit_text(
            "<emoji id=5260726538302660868>✅</emoji><b> Deleted messages disabled</b>"
        )


@Client.on_message(
    command(["dmessages_set_token", "dm_st"])
    & filters.me
    & ~filters.forwarded
    & ~filters.scheduled
)
async def dmessages_st_handler(client: Client, message: Message):
    args = get_args_raw(message)

    token = re.search(r"(\d+):([A-Za-z0-9_-]+)", args)
    if not token:
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> Invalid argument</b>"
        )

    db.set("dmessages", "bot_token", token[0])
    await message.edit_text(
        "<emoji id=5260726538302660868>✅</emoji><b> Bot token succesfully set!</b>"
    )

    if isinstance(bot, Client):
        if govno.bot.is_connected:
            await govno.bot.stop()
        govno.bot = Client(
            name="dmessages_bot",
            api_id=api_id,
            api_hash=api_hash,
            in_memory=True,
            bot_token=token[0],
        )
        await govno.bot.start()


@Client.on_message(
    command(["dmessages_max", "dm_max"]) & filters.me & ~filters.forwarded & ~filters.scheduled
)
async def dmessages_max_handler(client: Client, message: Message):
    args = get_args_raw(message)
    if not args or not args.isdigit():
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> Invalid argument</b>"
        )

    db.set("dmessages", "max_to_show", int(args))
    await message.edit_text(
        f"<emoji id=5260726538302660868>✅</emoji><b> Max messages to show set to: {args}</b>"
    )


# First argument always should be client. Because it will be passed automatically in main.py
async def dmessages_job(client: Client):
    if not db.get("dmessages", "enabled", False):
        job = scheduler.get_job("dmessages_job")
        if job:
            job.pause()
        return

    # Delete messages older than 1 day
    await govno.db.delete_old_messages(days=1)


scheduler_jobs.append(ScheduleJob(dmessages_job, IntervalTrigger(hours=1)))

module = modules_help.add_module("dmessages", __file__)
module.add_command("dmessages", "Enable/disable deleted messages", "[on/off]")
module.add_command("dmessages_max", "Set max number of deleted messages to show", "[number]")
module.add_command("dmessages_set_token", "Set bot token")
