import os
import shutil
import tempfile

from pyrogram import Client, enums, errors, filters
from pyrogram.types import Message, ReplyParameters

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import shell_exec, with_reply


@Client.on_message(
    ~filters.scheduled & command(["vnote"]) & filters.me & ~filters.forwarded
)
async def vnote(client: Client, message: Message):
    if not shutil.which("ffmpeg"):
        return await message.edit("<b>ffmpeg not installed!</b>")

    if (
        not message.media
        and message.reply_to_message
        and message.reply_to_message.media
    ):
        msg = message.reply_to_message
    else:
        msg = message

    if not msg.media:
        return await message.edit_text("<b>Message should contain media!</b>")

    if msg.media not in (
        enums.MessageMediaType.VIDEO,
        enums.MessageMediaType.ANIMATION,
    ):
        return await message.edit_text("<b>Only video and gif supported!</b>")

    chat = await client.get_chat(message.chat.id, force_full=True)

    if not chat.can_send_voice_messages:
        return await message.edit_text(
            "<b>Voice messages are forbidden in this chat.</b>"
        )

    if message.media:
        message.empty = bool(await message.delete())

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
            await client.send_video_note(
                message.chat.id,
                video_note=output_file_path,
                reply_parameters=ReplyParameters(
                    message_id=msg.id,
                    chat_id=msg.chat.id
                    if not msg.chat.type == enums.ChatType.PRIVATE
                    else None,
                ),
            )
        except (errors.ReplyMessageIdInvalid, errors.ChannelInvalid):
            await message.reply_video_note(video_note=output_file_path)
        except errors.VoiceMessagesForbidden:
            if not message.empty:
                return await message.edit(
                    "<b>Voice messages are forbidden in this chat.</b>"
                )

    if not message.empty:
        await message.delete()


@Client.on_message(
    ~filters.scheduled & command(["sticker"]) & filters.me & ~filters.forwarded
)
@with_reply
async def sticker_cmd(client: Client, message: Message):
    if not shutil.which("ffmpeg"):
        return await message.edit("<b>ffmpeg not installed!</b>")

    msg = message.reply_to_message

    if not msg.media:
        return await message.edit("<b>Replied message should contain media!</b>")

    if msg.media not in (
        enums.MessageMediaType.VIDEO,
        enums.MessageMediaType.PHOTO,
        enums.MessageMediaType.ANIMATION,
    ):
        return await message.edit("<b>Only video, photo, and gif supported!</b>")

    await message.edit_text("<code>Converting to sticker...</code>")

    with tempfile.TemporaryDirectory() as tempdir:
        input_file_path = os.path.join(tempdir, "input")
        await msg.download(file_name=input_file_path)

        is_video = msg.media in (
            enums.MessageMediaType.VIDEO,
            enums.MessageMediaType.ANIMATION,
        )

        if is_video:
            output_file_path = os.path.join(tempdir, "output.webm")
            # video sticker
            cmd = (
                f'ffmpeg -y -i "{input_file_path}" -t 3 -an -c:v libvpx-vp9 -pix_fmt yuva420p '
                '-vf "fps=30,scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0" '
                f'-b:v 500k "{output_file_path}"'
            )
        else:
            output_file_path = os.path.join(tempdir, "output.webp")
            # static sticker
            cmd = (
                f'ffmpeg -y -i "{input_file_path}" -vf '
                '"scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0" '
                f'-vframes 1 "{output_file_path}"'
            )

        _, _, stderr = await shell_exec(
            command=cmd,
            executable=db.get("shell", "executable"),
        )

        if (
            not os.path.exists(output_file_path)
            or os.path.getsize(output_file_path) == 0
        ):
            err = stderr or "Unknown ffmpeg error"
            return await message.edit(
                f"<b>Failed to convert to sticker.</b>\n\n<b>Error:</b>\n<code>{err}</code>"
            )

        try:
            await client.send_sticker(
                chat_id=message.chat.id,
                sticker=output_file_path,
                reply_parameters=ReplyParameters(
                    message_id=msg.id,
                    chat_id=msg.chat.id
                    if not msg.chat.type == enums.ChatType.PRIVATE
                    else None,
                ),
            )
            await message.delete()
        except (errors.ReplyMessageIdInvalid, errors.ChannelInvalid):
            await message.reply_sticker(sticker=output_file_path)
            await message.delete()
        except Exception as e:
            await message.edit(f"<b>Error sending sticker:</b>\n<code>{e}</code>")


module = modules_help.add_module("vnote", __file__)
module.add_command("vnote", "Make video note from message or reply media", "[reply]")
module.add_command("sticker", "Make sticker from message or reply media", "[reply]")
