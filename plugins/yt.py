from io import BytesIO
from os import remove

from aiohttp import ClientSession
from pyrogram import Client, enums, filters
from pyrogram.types import Message
from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic

from utils.filters import command
from utils.misc import modules_help

yt_music = YTMusic()


@Client.on_message(~filters.scheduled & command(["ytm"]) & filters.me & ~filters.forwarded)
async def ytm(_, message: Message):
    if len(message.command) == 1 and message.command[0] != "ytm":
        return await message.edit_text("<b>Query to search isn't provided</b>")

    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Searching...</b>")
    query = message.text.split(maxsplit=1)[1]
    results = yt_music.search(query, filter="songs", limit=1)
    if not results:
        return await message.edit_text("<b>No results for: {}</b>".format(query[:35]))

    album = yt_music.get_album(results[0]["album"]["id"])
    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Downloading...</b>")
    thumb_url = album["thumbnails"][-1]["url"]
    thumb_file = BytesIO()
    async with ClientSession() as session:
        thumb_file.write(await (await session.get(thumb_url)).read())
    thumb_file.name = results[0]["videoId"] + ".jpg"
    with YoutubeDL({"format": "bestaudio[ext=m4a]"}) as yt:
        info_dict = yt.extract_info(
            "https://music.youtube.com/watch?v=" + results[0]["videoId"], download=True
        )
        audio_path = yt.prepare_filename(info_dict)

    await message.edit_text("<b><emoji id=5821116867309210830>🔃</emoji> Uploading...</b>")

    msg = await message.reply_audio(
        audio=audio_path,
        quote=True,
        title=results[0]["title"],
        performer=results[0]["artists"][-1]["name"],
        thumb=thumb_file,
        duration=results[0]["duration_seconds"],
    )

    await message.edit_text(
        (
            "<b>- Downloaded successfully !\n"
            "- Title : {title}\n"
            "- Artist: {artist}\n"
            "- Album: {album}\n"
            "- Is explict: {explict}\n"
            "- Message link: {link}</b>"
        ).format(
            title=results[0]["title"],
            artist=results[0]["artists"][-1]["name"],
            album=results[0]["album"]["name"],
            explict=results[0]["isExplicit"],
            link=msg.link if message.chat.type != enums.ChatType.PRIVATE else "👇",
        ),
        disable_web_page_preview=True,
    )

    return remove(audio_path)


module = modules_help.add_module("ytm", __file__)
module.add_command("ytm", "Download a song from music.youtube.com")
