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
    if not shutil.which("ffmpeg"):
        return await message.edit("<b>ffmpeg not installed!</b>")

    if message.media:
        message.empty = bool(await message.delete())

    if not message.media and message.reply_to_message and message.reply_to_message.media:
        msg = message.reply_to_message
    else:
        msg = message

    if not msg.media:
        if not message.empty:
            return await message.edit_text("<b>Message should contain media!</b>")

    if msg.media not in (
        enums.MessageMediaType.VIDEO,
        enums.MessageMediaType.ANIMATION,
    ):
        if not message.empty:
            return await message.edit_text("<b>Only video and gif supported!</b>")

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
            filters = f"scale={width}:{height}"
        else:
            filters = rf"crop=min(iw\,ih):min(iw\,ih),scale={width}:{height}"

        await shell_exec(
            command=f"ffmpeg -y -hwaccel auto -i {input_file_path} "
            "-t 00:01:00 -vcodec libx264 -acodec aac "
            f'-vf "{filters}" '
            f"{output_file_path}",
            executable=db.get("shell", "executable"),
        )

        try:
            await msg.reply_video_note(
                video_note=output_file_path,
                quote=True,
            )
        except errors.VoiceMessagesForbidden:
            if not message.empty:
                return await message.edit("<b>Voice messages forbidden in this chat.</b>")


module = modules_help.add_module("vnote", __file__)
module.add_command(
    "vnote", "Make video note from message or reply media", "[reply]"
)
