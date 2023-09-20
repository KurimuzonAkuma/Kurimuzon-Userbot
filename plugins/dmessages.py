import re
from typing import List

import aiogram
from aiocache import Cache
from aiocache.serializers import PickleSerializer
from aiogram import Bot
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args, get_args_raw, get_entity_url, get_full_name, get_message_link

cache = Cache(Cache.MEMORY, ttl=3600, serializer=PickleSerializer())

DEFAULT_MAX_TO_SHOW = 20

reactions = filters.create(lambda _, __, message: bool(message.reactions))

deleted_msg = '🗑 <b>Deleted <a href="{msg_link}">message</a> from <a href="{ent_link}">{ent_name}</a></b>\n{text}'
edited_msg = '📝 <b><a href="{ent_link}">{ent_name}</a> edited <a href="{msg_link}">message</a></b>\n{edit_text}\n<code>Original message</code>\n{orig_text}'


def convert_tags(text: str) -> str:
    text = re.sub("<spoiler", "<tg-spoiler", text)
    text = re.sub("<emoji id", "<tg-emoji emoji-id", text)
    text = re.sub("</emoji", "</tg-emoji", text)
    text = re.sub(
        r'<pre language="([^"]+)">([^<]+)</pre>',
        r'<pre><code class="language-\1">\2</code></pre>',
        text,
    )
    return text


async def get_media_group(media_group_id: int, deleted_messages: List[Message]) -> List[Message]:
    media_group = []

    for dmessage in deleted_messages:
        cached = await cache.get(dmessage.id)
        if cached and cached.media_group_id == media_group_id:
            media_group.append(cached)

    return media_group


@Client.on_message(~filters.me & ~filters.bot & filters.private, group=-1000)
async def dmessages_log_handler(client: Client, message: Message):
    await cache.set(message.id, message)


@Client.on_edited_message(~filters.me & filters.private & ~reactions, group=-1000)
async def dmessages_edited_handler(client: Client, message: Message):
    if not db.get("dmessages", "enabled"):
        return
    if not db.get("dmessages", "bot_token"):
        return

    cached_message: Message = await cache.get(message.id)

    if not cached_message:
        return

    bot = Bot(db.get("dmessages", "bot_token"), parse_mode="HTML")

    edit_text = message.text or message.caption
    text = cached_message.text or cached_message.caption
    text = edited_msg.format(
        ent_link=get_entity_url(message.from_user, True),
        ent_name=get_full_name(message.from_user),
        msg_link=get_message_link(message),
        edit_text=convert_tags(edit_text.html) if edit_text else "",
        orig_text=convert_tags(text.html) if text else "",
    )

    if cached_message.media:
        file_id = getattr(cached_message, cached_message.media.value).file_id
        file = await client.download_media(file_id, in_memory=True)

        await bot.send_document(
            chat_id=client.me.id,
            document=aiogram.types.BufferedInputFile(file.getbuffer(), file.name),
            caption=text,
        )
    else:
        await bot.send_message(
            chat_id=client.me.id,
            text=text,
        )

    await cache.set(message.id, message)
    await bot.session.close()


@Client.on_deleted_messages(group=-1000)
async def dmessages_on_deleted_handler(client: Client, messages: List[Message]):
    if not db.get("dmessages", "enabled"):
        return
    if not db.get("dmessages", "bot_token"):
        return

    cached_messages: List[Message] = list(
        filter(
            None,
            [await cache.get(message.id) for message in messages][
                : db.get("dmessages", "max_to_show", DEFAULT_MAX_TO_SHOW)
            ],
        )
    )

    if not cached_messages:
        return

    bot = Bot(db.get("dmessages", "bot_token"), parse_mode="HTML")
    processed_media_groups_ids = []

    media_types = {
        "photo": aiogram.types.InputMediaPhoto,
        "video": aiogram.types.InputMediaVideo,
        "audio": aiogram.types.InputMediaAudio,
    }

    for cached_message in cached_messages:
        text = cached_message.text or cached_message.caption
        text = deleted_msg.format(
            msg_link=get_message_link(cached_message),
            ent_link=get_entity_url(cached_message.from_user, True),
            ent_name=get_full_name(cached_message.from_user),
            text=convert_tags(text.html) if text else "",
        )

        if cached_message.media:
            if cached_message.media_group_id:
                if cached_message.media_group_id in processed_media_groups_ids:
                    continue
                processed_media_groups_ids.append(cached_message.media_group_id)
                input_media_group = []

                media_group = await get_media_group(cached_message.media_group_id, cached_messages)

                is_first = True
                for media in media_group:
                    mtype = media_types.get(media.media.value, aiogram.types.InputMediaDocument)

                    file_id = getattr(media, media.media.value).file_id
                    file = await client.download_media(file_id, in_memory=True)
                    input_media_group.append(
                        mtype(
                            media=aiogram.types.BufferedInputFile(file.getbuffer(), file.name),
                            caption=text if is_first else "",
                        )
                    )
                    is_first = False

                await bot.send_media_group(chat_id=client.me.id, media=input_media_group)
            else:
                file_id = getattr(cached_message, cached_message.media.value).file_id
                file = await client.download_media(file_id, in_memory=True)

                if cached_message.sticker:
                    await bot.send_message(chat_id=client.me.id, text=text)
                    await bot.send_sticker(
                        chat_id=client.me.id,
                        sticker=file_id,
                    )
                elif cached_message.video_note:
                    await bot.send_message(chat_id=client.me.id, text=text)
                    await bot.send_video_note(
                        chat_id=client.me.id,
                        video_note=aiogram.types.BufferedInputFile(file.getbuffer(), file.name),
                    )
                else:
                    await bot.send_document(
                        chat_id=client.me.id,
                        document=aiogram.types.BufferedInputFile(file.getbuffer(), file.name),
                        caption=text,
                    )
        else:
            await bot.send_message(
                chat_id=client.me.id,
                text=text,
            )
        await cache.delete(cached_message.id)
    await bot.session.close()


@Client.on_message(command(["dmcfg"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def dmessages_state_handler(client: Client, message: Message):
    args, nargs = get_args(message)

    if not args:
        return await message.edit_text(
            "<b>Current config:</b>\n"
            f'Enabled: <code>{bool(db.get("dmessages", "enabled"))}</code>\n'
            f'Bot token set: <code>{bool(db.get("dmessages", "bot_token"))}</code>\n'
            f'Max to show: <code>{db.get("dmessages", "max_to_show", DEFAULT_MAX_TO_SHOW)}</code>'
        )

    result = ""

    if "-e" in nargs or "--enable" in nargs:
        e = nargs.get("-e") or nargs.get("--enable")
        if e not in ("on", "off"):
            result += "Invalid value for enable. Should be on/off\n"
        else:
            is_enable = e == "on"
            db.set("dmessages", "enabled", is_enable)
            result += f"Deleted messages {is_enable}\n"

    if "-st" in nargs or "--set-token" in nargs:
        st = nargs.get("-st") or nargs.get("--set-token")
        token = re.search(r"(\d+):([A-Za-z0-9_-]+)", st)
        if not token:
            result += "Invalid value for set token.\n"
        else:
            db.set("dmessages", "bot_token", token[0])
            db.set("dmessages", "enabled", True)
            result += "Bot token set and enabled\n"

    if "-max" in nargs or "--max-to-show" in nargs:
        max_to_show = nargs.get("-max") or nargs.get("--max-to-show")
        if not max_to_show.isdigit():
            result += "Invalid value max to show. Should be number.\n"
        else:
            db.set("dmessages", "max_to_show", int(max_to_show))
            result += f"Max messages to show set to: {max_to_show}\n"

    if not result:
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> Invalid arguments</b>"
        )

    return await message.edit_text(result)


module = modules_help.add_module("deleted_messages", __file__)
module.add_command("dmcfg", "Deleted messages config", "-e [on/off]* | -st [token]* | -max [int]*")
