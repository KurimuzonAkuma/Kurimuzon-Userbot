import datetime
import subprocess
import sys
from time import perf_counter

import pyrogram
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.misc import bot_uptime, modules_help, prefix, repo


@Client.on_message(filters.command(["status", "статус"], prefix) & filters.me)
async def status(_, message: Message):
    await message.edit("<code>Getting info...</code>")
    text = "<b>===== Bot status =====</b>\n"
    text += f"<b>Prefix:</b> <code>{prefix}</code>\n"
    text += f"<b>Plugins:</b> <code>{len(modules_help)}</code>\n"
    text += f"<b>Current version:</b> <code>{repo.head.commit.hexsha[:7]}</code>\n"
    text += f"<b>Branch:</b> <code>{repo.active_branch}</code>\n"
    text += f"<b>Uptime:</b> <code>{datetime.timedelta(seconds=perf_counter() - bot_uptime)}</code>\n\n"

    text += "<b>===== System info =====</b>\n"
    text += f"<b>Python:</b> <code>{sys.version}</code>\n"
    text += f"<b>Pyrogram:</b> <code>{pyrogram.__version__}</code>\n"
    text += f"<b>OS:</b> <code>{sys.platform}</code>\n"
    kernel_version = subprocess.run(["uname", "-r"], capture_output=True).stdout.decode().strip()
    text += f"<b>Kernel:</b> <code>{kernel_version}</code>\n"
    system_uptime = subprocess.run(["uptime", "-p"], capture_output=True).stdout.decode().strip()
    text += f"<b>Uptime:</b> <code>{system_uptime}</code>\n\n"
    text += "<a href='https://github.com/KurimuzonAkuma/Kurimuzon-Userbot'>Kurimuzon-Userbot</a>"
    await message.edit(text)


modules_help["status"] = {
    "status": "Get information about the userbot and system",
}
