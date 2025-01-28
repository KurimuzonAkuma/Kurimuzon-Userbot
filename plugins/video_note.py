import contextlib
import os
import shutil
import tempfile

from pyrogram import Client, enums, errors, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import shell_exec


@Client.on_message(
    ~filters.scheduled & command(["vnote"]) & filters.me & ~filters.forwarded
)
async def vnote(_: Client, message: Message):
    msg = message.reply_to_message or message

    if not msg.media:
        return await message.edit_text("<b>Message should contain media!</b>")

    if msg.media not in (
        enums.MessageMediaType.VIDEO,
        enums.MessageMediaType.ANIMATION,
    ):
        return await message.edit_text("<b>Only video and gif supported!</b>")

    media = getattr(msg, msg.media.value)

    width = 480
    height = 480

    with tempfile.TemporaryDirectory() as tempdir:
        input_file_path = os.path.join(tempdir, "input.mp4")
        output_file_path = os.path.join(tempdir, "output.mp4")

        await msg.download(file_name=input_file_path)

        await message.edit_text("<code>Converting video...</code>")

        if message.media:
            await message.delete()

        if media.width == width and media.height == height and media.duration <= 60:
            output_file_path = input_file_path
        else:
            if not shutil.which("ffmpeg"):
                with contextlib.supress(errors.MessageIdInvalid):
                    return await message.edit("<b>ffmpeg not installed!</b>")

            await shell_exec(
                command=f"ffmpeg -y -hwaccel auto -i {input_file_path} "
                "-t 00:01:00 "
                # "-preset superfast -crf 24 "
                "-vcodec libx264 -acodec aac "
                rf'-vf "crop=min(iw\,ih):min(iw\,ih),scale={width}:{height}" '
                f"{output_file_path}",
                executable=db.get("shell", "executable"),
            )

        try:
            await message.reply_video_note(
                video_note=output_file_path,
                quote=False,
            )
        except errors.VoiceMessagesForbidden:
            with contextlib.supress(errors.MessageIdInvalid):
                return await message.edit(
                    "<b>Voice messages forbidden in this chat.</b>"
                )


module = modules_help.add_module("vnote", __file__)
module.add_command("vnote", "Make video note from message or reply media", "[reply]")
