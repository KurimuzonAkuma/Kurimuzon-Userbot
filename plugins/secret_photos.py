from pyrogram import Client, filters
from pyrogram.types import Message

from utils.db import db
from utils.misc import modules_help, prefix
from utils.scripts import full_name, with_args


def _secret_media(_, __, message: Message) -> bool:
    media = message.photo or message.video
    return bool(media and media.ttl_seconds)


secret_media = filters.create(_secret_media)


@Client.on_message(filters.private & ~filters.me & secret_media)
async def secret_media(client: Client, message: Message):
    if not db.get("secret_media", "enabled", True):
        return
    media = await message.download(in_memory=True)
    await client.send_document(
        chat_id="me",
        document=media,
        caption=f"Secret {message.media.name.lower()} from {full_name(message.from_user)}",
        force_document=True,
    )


@Client.on_message(filters.command(["secret"], prefix) & filters.me)
@with_args("<b>Argument on/off required!</b>")
async def secret_toggle(_: Client, message: Message):
    if message.command[1] == "on":
        db.set("secret_media", "enabled", True)
        await message.edit_text("Secret media grabber enabled.")
    elif message.command[1] == "off":
        db.set("secret_media", "enabled", False)
        await message.edit_text("Secret media grabber disabled.")


modules_help["secret"] = {
    "secret [on/off]": "On/Off secret media grabber",
}
