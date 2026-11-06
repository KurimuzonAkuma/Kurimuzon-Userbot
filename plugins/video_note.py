import os
import shutil
import tempfile

from pyrogram import Client, enums, errors, filters, types

from utils import loader
from utils.db import db
from utils.loader import Plugin
from utils.scripts import shell_exec


class VideoNote(Plugin):
    @loader.command(
        "vnote",
        description="Make a video note from a message or replied media",
        args=[
            loader.CommandArg(
                "reply",
                "media or message to convert",
                required=False,
            )
        ],
        filters=~filters.scheduled & filters.me & ~filters.forwarded,
    )
    async def vnote(self, _: Client, message: types.Message):
        if not shutil.which("ffmpeg"):
            return await message.edit("<b>ffmpeg not installed!</b>")

        if message.media:
            message.empty = bool(await message.delete())

        if not message.media and message.reply_to_message and message.reply_to_message.media:
            msg = message.reply_to_message
        else:
            msg = message

        if msg.media is None:
            if not message.empty:
                await message.edit_text("<b>Message should contain media!</b>")
            return

        if msg.media not in (
            enums.MessageMediaType.VIDEO,
            enums.MessageMediaType.ANIMATION,
        ):
            if not message.empty:
                return await message.edit_text("<b>Only video and GIFs are supported!</b>")

        if not message.empty:
            await message.edit_text("<code>Converting video...</code>")

        media = getattr(msg, msg.media.value)
        width = 480
        height = 480

        with tempfile.TemporaryDirectory() as tempdir:
            input_file_path = os.path.join(tempdir, "input.mp4")
            output_file_path = os.path.join(tempdir, "output.mp4")

            await msg.download(file_name=input_file_path)

            if media.width == media.height:
                video_filter = f"scale={width}:{height}"
            else:
                video_filter = rf"crop=min(iw\,ih):min(iw\,ih),scale={width}:{height}"

            await shell_exec(
                command=f"ffmpeg -y -hwaccel auto -i {input_file_path} "
                "-t 00:01:00 -vcodec libx264 -crf 23 -b:v 1.2M -acodec aac "
                f'-vf "{video_filter}" '
                f"{output_file_path}",
                executable=db.get("shell", "executable"),
            )

            try:
                await msg.reply_video_note(video_note=output_file_path)
            except errors.VoiceMessagesForbidden:
                if not message.empty:
                    return await message.edit("<b>Voice messages are forbidden in this chat.</b>")
