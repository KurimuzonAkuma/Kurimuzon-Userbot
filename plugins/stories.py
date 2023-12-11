import io
import shutil
from tempfile import TemporaryDirectory

from pyrogram import Client, enums, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args, get_args_raw, paste_neko, shell_exec, with_premium


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
    if media not in (enums.MessageMediaType.VIDEO, enums.MessageMediaType.PHOTO):
        return await message.edit_text("<b>Only photo and video supported!</b>")

    video = message.video or getattr(message.reply_to_message, "video", None)
    photo = message.photo or getattr(message.reply_to_message, "photo", None)

    media = video or photo
    if not media:
        return await message.edit_text("<b>Media not found!</b>")

    args, nargs = get_args(message=message)

    if "-c" in args:
        caption = message.caption or getattr(message.reply_to_message, "caption", None)
    else:
        caption = " ".join(args)

    await message.edit_text("<b>Converting media...</b>")

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

    video_attributes = {}
    if video:
        with TemporaryDirectory() as tempdir:
            with open(f"{tempdir}/input.mp4", "wb") as file:
                file.write(downloaded_media.getbuffer())
                file.seek(0)

            rcode, stdout, stderr = await shell_exec(
                command=f"ffmpeg -y -hwaccel auto -i {tempdir}/input.mp4 "
                "-preset superfast "
                "-crf 24 -vcodec libx264 -acodec aac "
                f"-vf crop={new_width}:{new_height},scale=720:1280 "
                f"{tempdir}/output.mp4",
                executable=db.get("shell", "executable"),
            )

            if rcode != 0:
                return await message.edit_text(
                    f"<b>Failed to convert media.</b>\n\nError: {await paste_neko(stderr)}"
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
            chat_id="me",
            media=downloaded_media,
            caption=caption,
            period=86400 * 2,
            privacy=enums.StoriesPrivacyRules.PUBLIC,
            disallowed_users=db.get("stories", "blacklist"),
            **video_attributes,
        )
    except Exception as e:
        return await message.edit_text(f"<b>Error: {e}</b>")

    await message.edit_text("Story posted!")


@Client.on_message(
    filters.regex("^\+storybl ") & filters.me & ~filters.forwarded & ~filters.scheduled
)
async def stories_add_blacklist_handler(client: Client, message: Message):
    args = get_args_raw(message)

    if not args.lstrip("-").isdigit():
        return await message.edit_text("<b>Chat id should be int</b>")

    args = int(args)

    current_list = db.get("stories", "blacklist", [])

    if args in current_list:
        return await message.edit_text("<b>Chat already added to blacklist</b>")

    current_list.append(args)
    db.set("stories", "blacklist", current_list)
    return await message.edit_text("<b>Chat added to blacklist</b>")


@Client.on_message(
    filters.regex("^\-storybl ") & filters.me & ~filters.forwarded & ~filters.scheduled
)
async def stories_remove_blacklist_handler(client: Client, message: Message):
    args = get_args_raw(message)

    if not args.lstrip("-").isdigit():
        return await message.edit_text("<b>Chat id should be int</b>")

    args = int(args)

    current_list = db.get("stories", "blacklist", [])

    if args not in current_list:
        return await message.edit_text("<b>Chat not in blacklist</b>")

    current_list.remove(args)
    db.set("stories", "blacklist", current_list)
    return await message.edit_text("<b>Chat removed from blacklist</b>")


module = modules_help.add_module("stories", __file__)
module.add_command(
    command="story",
    description="Post story from message or reply. Pass the '-c' argument to take the caption from the media, otherwise the message will be used",
    args="[reply]* [-c] - keep original caption",
)
module.add_command("+storybl", "Add chat id to blacklist", "[chat_id]*")
module.add_command("-storybl", "Remove chat id from blacklist", "[chat_id]*")
