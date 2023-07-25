import shutil
import subprocess
from tempfile import NamedTemporaryFile, TemporaryDirectory

from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import with_reply


@Client.on_message(~filters.scheduled & command(["vnote"]) & filters.me & ~filters.forwarded)
@with_reply
async def vnote(client: Client, message: Message):
    if not shutil.which("ffmpeg"):
        return await message.edit_text("<b>ffmpeg not installed!</b>")

    if message.reply_to_message.media not in (MessageMediaType.VIDEO, MessageMediaType.ANIMATION):
        return await message.edit_text("<b>Only video and gif supported!</b>")

    await message.delete()
    with TemporaryDirectory() as tempdir:
        with NamedTemporaryFile("wb", suffix=".mp4", dir=tempdir) as file:
            data = await message.reply_to_message.download(in_memory=True)

            file.write(data.getbuffer())
            file.seek(0)

            subprocess.run(
                f'ffmpeg -y -i {file.name} -vf "crop=min(iw\,ih):min(iw\,ih),scale=2*trunc(ih/2):2*trunc(ih/2)" {tempdir}/output.mp4',
                shell=True,
            )

            await client.send_video_note(
                chat_id=message.chat.id, video_note=f"{tempdir}/output.mp4"
            )


modules_help["vnote"] = {
    "vnote [reply]": "Make video note from reply video",
}
