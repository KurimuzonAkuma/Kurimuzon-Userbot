import re
from typing import Iterable, List, Optional

import aiogram
from aiocache import Cache
from aiocache.serializers import PickleSerializer
from aiogram import Bot
from pyrogram import Client, enums, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args, get_args_raw, get_entity_url, get_full_name, get_message_link

cache = Cache(Cache.MEMORY, ttl=3600, serializer=PickleSerializer())

DEFAULT_MAX_TO_SHOW = 20

deleted_map = {
    ChatType.GROUP: '🗑 <b>Deleted message from chat <a href="{ent_link}">{ent_name}</a></b>\n{text}',
    ChatType.SUPERGROUP: '🗑 <b>Deleted message from chat <a href="{ent_link}">{ent_name}</a></b>\n{text}',
    ChatType.PRIVATE: '🗑 <b>Deleted message from private <a href="{ent_link}">{ent_name}</a></b>\n{text}',
    ChatType.CHANNEL: '🗑 <b>Deleted message from channel <a href="{ent_link}">{ent_name}</a></b>\n{text}',
}

edited_map = {
    ChatType.GROUP: '📝 <b><a href="{ent_link}">{ent_name}</a> edited <a href="{msg_link}">message</a> in chat</b>\n{edit_text}\n<code>Original message</code>\n{orig_text}',
    ChatType.SUPERGROUP: '📝 <b><a href="{ent_link}">{ent_name}</a> edited <a href="{msg_link}">message</a> in chat</b>\n{edit_text}\n<code>Original message</code>\n{orig_text}',
    ChatType.PRIVATE: '📝 <b><a href="{ent_link}">{ent_name}</a> edited <a href="{msg_link}">message</a> in private</b>\n{edit_text}\n<code>Original message</code>\n{orig_text}',
    ChatType.CHANNEL: '📝 <b><a href="{ent_link}">{ent_name}</a> edited <a href="{msg_link}">message</a> in channel</b>\n{edit_text}\n<code>Original message</code>\n{orig_text}',
}


def reactions():
    async def func(flt, _, message: Message):
        old_message = await cache.get(message.id)

        if not old_message:
            return False

        return bool(not old_message.reactions and message.reactions)

    return filters.create(func)


def whitelist():
    async def func(flt, _, message: Message):
        if message.chat.type == ChatType.PRIVATE:
            return True

        whitelist_chats = db.get("history", "whitelist", [])

        return message.chat.id in whitelist_chats

    return filters.create(func)


async def get_cached_media_group(
    media_group_id: int, deleted_messages: List[Message]
) -> List[Message]:
    media_group = []

    for dmessage in deleted_messages:
        cached = await cache.get(dmessage.id)
        if cached and cached.media_group_id == media_group_id:
            media_group.append(cached)

    return media_group


async def get_input_media_group(client: Client, cached_messages: Iterable[Message], text: str):
    processed_media_groups_ids = []
    input_media_group = []

    media_types_map = {
        enums.MessageMediaType.PHOTO: aiogram.types.InputMediaPhoto,
        enums.MessageMediaType.VIDEO: aiogram.types.InputMediaVideo,
        enums.MessageMediaType.AUDIO: aiogram.types.InputMediaAudio,
    }

    for cached_message in cached_messages:
        if cached_message.media_group_id:
            if cached_message.media_group_id in processed_media_groups_ids:
                continue

            processed_media_groups_ids.append(cached_message.media_group_id)
            media_group = await get_cached_media_group(
                cached_message.media_group_id, cached_messages
            )

            is_first = True
            for media_message in media_group:
                if not media_message.media:
                    continue

                media = getattr(media_message, media_message.media.value, None)

                file_bytes = await client.download_media(media.file_id, in_memory=True)

                media_type = media_types_map.get(
                    media_message.media, aiogram.types.InputMediaDocument
                )
                input_media_group.append(
                    media_type(
                        media=aiogram.types.BufferedInputFile(
                            file_bytes.getbuffer(), file_bytes.name
                        ),
                        caption=text if is_first else "",
                    )
                )
                is_first = False

    return input_media_group


async def send_cached_message(
    client: Client,
    cached_message: Message,
    text: str = "",
    media_group: Optional[List[aiogram.types.InputMedia]] = None,
):
    bot = Bot(db.get("history", "bot_token"), parse_mode="HTML")

    if media_group:
        await bot.send_media_group(client.me.id, media_group)
    elif cached_message.media:
        media = getattr(cached_message, cached_message.media.value, None)
        file_bytes = await client.download_media(media.file_id, in_memory=True)

        if cached_message.sticker:
            await bot.send_message(chat_id=client.me.id, text=text)
            await bot.send_sticker(
                chat_id=client.me.id,
                sticker=media.file_id,
            )
        elif cached_message.video_note:
            await bot.send_message(chat_id=client.me.id, text=text)
            await bot.send_video_note(
                chat_id=client.me.id,
                video_note=aiogram.types.BufferedInputFile(
                    file_bytes.getbuffer(), file_bytes.name
                ),
            )
        else:
            await bot.send_document(
                chat_id=client.me.id,
                document=aiogram.types.BufferedInputFile(file_bytes.getbuffer(), file_bytes.name),
                caption=text,
            )
    else:
        await bot.send_message(
            chat_id=client.me.id,
            text=text,
        )

    await bot.session.close()


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


@Client.on_message(~filters.me & ~filters.bot, group=-1000)
async def history_log_message_handler(client: Client, message: Message):
    if message.chat.type == ChatType.BOT:
        return

    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] and not db.get(
        "history", "is_chats_enabled"
    ):
        return

    if message.chat.type == ChatType.CHANNEL and not db.get("history", "is_channels_enabled"):
        return

    await cache.set(message.id, message)


@Client.on_edited_message(~filters.me & ~reactions() & whitelist(), group=-1000)
async def history_on_edited_handler(client: Client, message: Message):
    if not db.get("history", "enabled"):
        return

    if not db.get("history", "bot_token"):
        return

    cached_message: Message = await cache.get(message.id)

    if not cached_message:
        return

    edit_text = message.text or message.caption
    orig_text = cached_message.text or cached_message.caption
    sender = cached_message.from_user or cached_message.sender_chat

    text = edited_map[cached_message.chat.type].format(
        ent_link=get_entity_url(sender, openmessage=True),
        ent_name=get_full_name(sender),
        msg_link=get_message_link(cached_message, cached_message.chat),
        edit_text=convert_tags(edit_text.html) if edit_text else "",
        orig_text=convert_tags(orig_text.html) if orig_text else "",
    )

    await send_cached_message(client=client, cached_message=cached_message, text=text)
    await cache.set(message.id, message)


@Client.on_deleted_messages(group=-1000)
async def history_on_deleted_handler(client: Client, messages: List[Message]):
    if not db.get("history", "enabled"):
        return

    if not db.get("history", "bot_token"):
        return

    cached_messages: List[Message] = list(
        filter(
            None,
            [await cache.get(message.id) for message in messages][
                : db.get("history", "max_to_show", DEFAULT_MAX_TO_SHOW)
            ],
        )
    )

    if not cached_messages:
        return

    whitelist_chats = db.get("history", "whitelist", [])

    is_media_group_sent = False

    for cached_message in cached_messages:
        if (
            cached_message.chat.id not in whitelist_chats
            and cached_message.chat.type != ChatType.PRIVATE
        ):
            continue
        text = cached_message.text or cached_message.caption
        obj = cached_message.from_user or cached_message.sender_chat

        text = deleted_map[cached_message.chat.type].format(
            msg_link=get_message_link(cached_message, cached_message.chat),
            ent_link=get_entity_url(obj, True),
            ent_name=get_full_name(obj),
            text=convert_tags(text.html) if text else "",
        )

        if cached_message.media and cached_message.media_group_id:
            if not is_media_group_sent:
                input_media_group = await get_input_media_group(client, cached_messages, text)
                await send_cached_message(
                    client=client, cached_message=cached_message, media_group=input_media_group
                )
                is_media_group_sent = True
        else:
            await send_cached_message(client=client, cached_message=cached_message, text=text)

        await cache.delete(cached_message.id)


@Client.on_message(command(["hcfg"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def history_config_handler(client: Client, message: Message):
    args, nargs = get_args(message)

    if not args:
        return await message.edit_text(
            "<b>Current config:</b>\n"
            f'Enabled: <code>{bool(db.get("history", "enabled"))}</code>\n'
            f'Bot token set: <code>{bool(db.get("history", "bot_token"))}</code>\n'
            f'Max to show: <code>{db.get("history", "max_to_show", DEFAULT_MAX_TO_SHOW)}</code>\n'
            f'Chat logging: <code>{bool(db.get("history", "is_chats_enabled"))}</code>\n'
            f'Channels logging: <code>{bool(db.get("history", "is_channels_enabled"))}</code>'
        )

    result = ""

    if "-e" in nargs or "--enable" in nargs:
        e = nargs.get("-e") or nargs.get("--enable")
        if e not in ("on", "off"):
            result += "Invalid value for enable. Should be on/off\n"
        else:
            is_enable = e == "on"
            db.set("history", "enabled", is_enable)
            result += f"Deleted messages {is_enable}\n"

    if "-st" in nargs or "--set-token" in nargs:
        st = nargs.get("-st") or nargs.get("--set-token")
        token = re.search(r"(\d+):([A-Za-z0-9_-]+)", st)
        if not token:
            result += "Invalid value for set token.\n"
        else:
            db.set("history", "bot_token", token[0])
            db.set("history", "enabled", True)
            result += "Bot token set and enabled\n"

    if "-max" in nargs or "--max-to-show" in nargs:
        max_to_show = nargs.get("-max") or nargs.get("--max-to-show")
        if not max_to_show.isdigit():
            result += "Invalid value max to show. Should be number.\n"
        else:
            db.set("history", "max_to_show", int(max_to_show))
            result += f"Max messages to show set to: {max_to_show}\n"

    if "-chats" in nargs:
        c = nargs.get("-chats")
        if c not in ("on", "off"):
            result += "Invalid value for enable. Should be on/off\n"
        else:
            is_enable = c == "on"
            db.set("history", "is_chats_enabled", is_enable)
            result += f"Chat logging {is_enable}\n"

    if "-channels" in nargs:
        c = nargs.get("-channels")
        if c not in ("on", "off"):
            result += "Invalid value for enable. Should be on/off\n"
        else:
            is_enable = c == "on"
            db.set("history", "is_channels_enabled", is_enable)
            result += f"Channels logging {is_enable}\n"

    if not result:
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> Invalid arguments</b>"
        )

    return await message.edit_text(result)


@Client.on_message(filters.regex("^\+hwl ") & filters.me & ~filters.forwarded & ~filters.scheduled)
async def history_add_whitelist_handler(client: Client, message: Message):
    args = get_args_raw(message)

    if not args.lstrip("-").isdigit():
        return await message.edit_text("<b>Chat id should be int</b>")

    args = int(args)

    current_list = db.get("history", "whitelist", [])

    if args in current_list:
        return await message.edit_text("<b>Chat already added to whitelist</b>")

    current_list.append(args)
    db.set("history", "whitelist", current_list)
    return await message.edit_text("<b>Chat added to whitelist</b>")


@Client.on_message(filters.regex("^\-hwl ") & filters.me & ~filters.forwarded & ~filters.scheduled)
async def history_remove_whitelist_handler(client: Client, message: Message):
    args = get_args_raw(message)

    if not args.lstrip("-").isdigit():
        return await message.edit_text("<b>Chat id should be int</b>")

    args = int(args)

    current_list = db.get("history", "whitelist", [])

    if args not in current_list:
        return await message.edit_text("<b>Chat not in whitelist</b>")

    current_list.remove(args)
    db.set("history", "whitelist", current_list)
    return await message.edit_text("<b>Chat removed from whitelist</b>")


module = modules_help.add_module("history", __file__)
module.add_command(
    "hcfg",
    "History config. Example usage: '.hcfg -e on' - Enable history logging",
    "-e [on/off]* | -st [token]* | -max [int]* | -chats [on/off] | -channels [on/off]",
)
module.add_command("+hwl", "Add chat id to whitelist", "[chat_id]*")
module.add_command("-hwl", "Remove chat id from whitelist", "[chat_id]*")
