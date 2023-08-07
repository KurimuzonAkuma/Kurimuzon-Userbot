import io
import shutil
import subprocess
from tempfile import TemporaryDirectory

from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.raw.types import InputPrivacyValueAllowAll
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args, with_premium


@Client.on_message(command(["story"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
@with_premium
async def post_story(client: Client, message: Message):
    if not shutil.which("ffmpeg"):
        return await message.edit_text("<b>ffmpeg not installed!</b>")

    try:
        from PIL import Image
    except ImportError:
        return await message.edit_text("<b>Pillow not installed!</b>")

    media = message.media or getattr(message.reply_to_message, "media", None)
    if media not in (MessageMediaType.VIDEO, MessageMediaType.PHOTO):
        return await message.edit_text("<b>Only photo and video supported!</b>")

    video = message.video or getattr(message.reply_to_message, "video", None)
    video_attributes = {}
    photo = message.photo or getattr(message.reply_to_message, "photo", None)
    media = video or photo
    if not media:
        return await message.edit_text("<b>Media not found!</b>")

    args, nargs = get_args(message=message, use_reply=True)

    if "-d" in nargs:
        period = nargs.pop("-d")
        if not period.isdigit():
            return await message.edit_text("<b>Invalid period! Must be a number</b>")

        period = int(period)
        args.remove("-d")
        if not 1 <= period <= 7:
            return await message.edit_text("<b>Invalid period! Must be from 1 to 7</b>")
    else:
        period = 1

    if "-c" in args:
        caption = message.caption or (
            message.reply_to_message and message.reply_to_message.caption
        )
        args.remove("-c")
    else:
        caption = " ".join(args)

    await message.edit_text("<b>Uploading media...</b>")

    width = media.width
    height = media.height

    if width > height:
        new_width = int(height * 720 / 1280)
        new_height = height
    else:
        new_width = width
        new_height = int(width * 1280 / 720)

    downloaded_media = (
        await message.download(in_memory=True)
        if message.media
        else await message.reply_to_message.download(in_memory=True)
    )

    if video:
        with TemporaryDirectory() as tempdir:
            with open(f"{tempdir}/input.mp4", "wb") as file:
                file.write(downloaded_media.getbuffer())
                file.seek(0)

            subprocess.run(
                f"ffmpeg -y -hwaccel auto -i {tempdir}/input.mp4 "
                "-preset ultrafast "
                "-crf 24 -vcodec libx264 -acodec aac "
                f"-vf crop={new_width}:{new_height},scale=720:1280 "
                f"-v quiet "
                f"{tempdir}/output.mp4",
                shell=True,
            )

            video_attributes = {"duration": video.duration, "width": 720, "height": 1280}

            with open(f"{tempdir}/output.mp4", "rb") as file:
                downloaded_media = io.BytesIO(file.read())
                downloaded_media.name = "output.mp4"
    else:
        image = Image.open(downloaded_media)
        image = image.crop(
            (
                (width - new_width) // 2,
                (height - new_height) // 2,
                (width + new_width) // 2,
                (height + new_height) // 2,
            )
        )
        image = image.resize((1080, 1920), Image.ANTIALIAS)

        downloaded_media = io.BytesIO()
        downloaded_media.name = "output.jpg"

        image.save(downloaded_media, format="JPEG")
        downloaded_media.seek(0)

    try:
        await client.send_story(
            media=downloaded_media,
            caption=caption,
            period=86400 * period,
            **video_attributes,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return await message.edit_text(f"<b>Error: {e}</b>")

    await message.edit_text("Story posted!")


module = modules_help.add_module("stories", __file__)
module.add_command(
    command="story",
    description="Post story from message or reply. Pass the '-c' argument to take the caption from the media, otherwise the message will be used",
    args="[reply] [-c] [-d <days from 1 to 7>]",
)
