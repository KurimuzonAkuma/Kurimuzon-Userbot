import base64
from io import BytesIO
from sqlite3 import OperationalError

from pyrogram import Client, enums, filters, types
from pyrogram.types import Message

from utils import loader
from utils.db import db
from utils.loader import CommandArg, Plugin
from utils.scripts import get_prefix


class Notes(Plugin):
    def get_media_file_name(self, obj) -> str:
        if hasattr(obj, "file_name") and obj.file_name:
            return obj.file_name

        if isinstance(obj, types.Sticker):
            return (
                "sticker.tgs"
                if obj.is_animated
                else "sticker.webm"
                if obj.is_video
                else "sticker.webp"
            )
        elif isinstance(obj, types.Voice):
            return "voice.ogg"
        elif isinstance(obj, types.Document):
            return "document.zip"
        elif isinstance(obj, types.Photo):
            return "photo.jpg"
        elif isinstance(obj, (types.Video, types.VideoNote, types.Animation)):
            return "video.mp4"

        return "document"

    @loader.command(
        "snote",
        description="Save a note",
        args=[CommandArg("name", "note name", required=True)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def snote(self, client: Client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.edit(
                f"<b>Example: <code>{get_prefix()}{message.command[0] if message.command else 'snote'} note_name</code></b>"
            )

        note_name = args[1]
        medias = []
        if (
            message.reply_to_message
            and message.reply_to_message.media
            and message.reply_to_message.media
            in [
                enums.MessageMediaType.AUDIO,
                enums.MessageMediaType.DOCUMENT,
                enums.MessageMediaType.PHOTO,
                enums.MessageMediaType.STICKER,
                enums.MessageMediaType.VIDEO,
                enums.MessageMediaType.ANIMATION,
                enums.MessageMediaType.VOICE,
                enums.MessageMediaType.VIDEO_NOTE,
            ]
        ):
            if message.reply_to_message.media_group_id:
                for i in await message.reply_to_message.get_media_group():
                    file_bytes = await i.download(in_memory=True)
                    media_obj = getattr(i, i.media.value, None)
                    medias.append(
                        {
                            "type": i.media.value,
                            "caption": i.content.html,
                            "base64": base64.b64encode(file_bytes.getvalue()).decode("utf-8"),
                            "file_name": self.get_media_file_name(media_obj),
                        }
                    )
            else:
                file_bytes = await message.reply_to_message.download(in_memory=True)
                media_obj = getattr(
                    message.reply_to_message,
                    message.reply_to_message.media.value,
                    None,
                )
                medias.append(
                    {
                        "type": message.reply_to_message.media.value,
                        "caption": message.reply_to_message.content.html,
                        "base64": base64.b64encode(file_bytes.getvalue()).decode("utf-8"),
                        "file_name": self.get_media_file_name(media_obj),
                    }
                )

        note = {
            "is_media_group": bool(
                message.reply_to_message and message.reply_to_message.media_group_id
            ),
            "is_media": bool(message.reply_to_message and message.reply_to_message.media),
            "content": message.reply_to_message.content.html if message.reply_to_message else "",
            "medias": medias,
        }

        db.set("core.notes", f"note_{note_name}", note)
        await message.edit(f"<b>Successfully saved note:</b> <code>{note_name}</code>")

    @loader.command(
        "note",
        description="Retrieve a saved note",
        args=[CommandArg("name", "note name", required=True)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def note(self, client: Client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.edit(
                f"<b>Example: <code>{get_prefix()}{message.command[0] if message.command else 'note'} note_name</code></b>"
            )

        note_name = args[1]
        note = db.get("core.notes", f"note_{note_name}")
        if not note:
            return await message.edit(f"<b>No note with name:</b> <code>{note_name}</code>")

        input_media_group = []
        await message.delete()

        if note["is_media_group"]:
            for media in note["medias"]:
                content_type = enums.MessageMediaType(media["type"])
                content_bytes = BytesIO(base64.b64decode(media["base64"]))
                content_bytes.name = media["file_name"]
                if content_type == enums.MessageMediaType.PHOTO:
                    input_media_group.append(types.InputMediaPhoto(content_bytes, media["caption"]))
                elif content_type == enums.MessageMediaType.VIDEO:
                    input_media_group.append(types.InputMediaVideo(content_bytes, media["caption"]))
                elif content_type == enums.MessageMediaType.DOCUMENT:
                    input_media_group.append(
                        types.InputMediaDocument(content_bytes, media["caption"])
                    )
                elif content_type == enums.MessageMediaType.AUDIO:
                    input_media_group.append(types.InputMediaAudio(content_bytes, media["caption"]))

                return await message.reply_media_group(
                    media=input_media_group,
                )
        elif note["is_media"]:
            media = note["medias"][0]
            content_type = enums.MessageMediaType(media["type"])
            content_bytes = BytesIO(base64.b64decode(media["base64"]))
            content_bytes.name = media["file_name"]

            if content_type == enums.MessageMediaType.STICKER:
                return await message.reply_sticker(content_bytes)
            elif content_type == enums.MessageMediaType.VIDEO_NOTE:
                return await message.reply_video_note(content_bytes)
            elif content_type == enums.MessageMediaType.VOICE:
                return await message.reply_voice(
                    content_bytes,
                    caption=media["caption"],
                )
            elif content_type == enums.MessageMediaType.ANIMATION:
                return await message.reply_animation(
                    content_bytes,
                    caption=media["caption"],
                )
            elif content_type == enums.MessageMediaType.DOCUMENT:
                return await message.reply_document(
                    content_bytes,
                    caption=media["caption"],
                    file_name=media["file_name"],
                )
            elif content_type == enums.MessageMediaType.AUDIO:
                return await message.reply_audio(
                    content_bytes,
                    caption=media["caption"],
                )
            elif content_type == enums.MessageMediaType.PHOTO:
                return await message.reply_photo(
                    content_bytes,
                    caption=media["caption"],
                )
            elif content_type == enums.MessageMediaType.VIDEO:
                return await message.reply_video(
                    content_bytes,
                    caption=media["caption"],
                )

        await message.reply(note["content"])

    @loader.command(
        "dnote",
        description="Delete a saved note",
        args=[CommandArg("name", "note name", required=True)],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def dnote(self, client: Client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.edit(
                f"<b>Example: <code>{get_prefix()}{message.command[0] if message.command else 'dnote'} note_name</code></b>"
            )

        note_name = args[1]
        if db.get("core.notes", f"note_{note_name}"):
            db.remove("core.notes", f"note_{note_name}")
            await message.edit(f"<b>Successfully deleted note:</b> <code>{note_name}</code>")
        else:
            await message.edit(f"<b>No note with name:</b> <code>{note_name}</code>")

    @loader.command(
        "notes",
        description="List saved notes",
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def notes(self, _, message: Message):
        with db._lock:
            try:
                notes = db._cursor.execute("SELECT * FROM 'core.notes'").fetchall()
            except OperationalError as e:
                if "no such table" in str(e):
                    return await message.edit("<b>No saved notes</b>")

        if not notes:
            return await message.edit("<b>No saved notes</b>")

        res = "Available notes:\n"
        for row in notes:
            res += f"<code>{row['var'].split('_', maxsplit=1)[1]}</code>\n"
        await message.edit(res)
