import os
import shutil
import tempfile

from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import VoiceMessagesForbidden
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import shell_exec


@Client.on_message(~filters.scheduled & command(["vnote"]) & filters.me & ~filters.forwarded)
async def vnote(_: Client, message: Message):
    if not shutil.which("ffmpeg"):
        return await message.edit_text("<b>ffmpeg not installed!</b>")

    msg = message.reply_to_message or message

    if not msg.media:
        return await message.edit_text("<b>Message should contain media!</b>")

    if msg.media not in (
        MessageMediaType.VIDEO,
        MessageMediaType.ANIMATION,
    ):
        return await message.edit_text("<b>Only video and gif supported!</b>")

    media = getattr(msg, msg.media.value)

    with tempfile.TemporaryDirectory() as tempdir:
        input_file_path = os.path.join(tempdir, "input.mp4")
        output_file_path = os.path.join(tempdir, "output.mp4")

        await msg.download(file_name=input_file_path)

        await message.edit_text("<code>Converting video...</code>")

        if media.width == 360 and media.height == 360 and media.duration <= 60:
            output_file_path = input_file_path
        else:
            await shell_exec(
                command=f"ffmpeg -y -hwaccel auto -i {input_file_path} "
                "-t 00:01:00 "
                "-preset superfast "
                "-crf 24 -vcodec libx264 -acodec aac "
                f'-vf "crop=min(iw\,ih):min(iw\,ih),scale=2*trunc(ih/2):2*trunc(ih/2),scale=360:360" '
                f"{output_file_path}",
                executable=db.get("shell", "executable"),
            )

        try:
            await message.reply_video_note(
                video_note=output_file_path,
                quote=False,
            )
        except VoiceMessagesForbidden:
            return await message.edit_text("<b>Voice messages forbidden in this chat.</b>")


module = modules_help.add_module("vnote", __file__)
module.add_command("vnote", "Make video note from reply video", "[reply]")
