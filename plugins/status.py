import datetime
import subprocess
import sys
from time import perf_counter

import pyrogram
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import bot_uptime, modules_help
from utils.scripts import get_commits, get_prefix


@Client.on_message(
    ~filters.scheduled & command(["status", "статус"]) & filters.me & ~filters.forwarded
)
async def status(_, message: Message):
    await message.edit("<code>Getting info...</code>")

    prefix = get_prefix()
    commits = get_commits()

    text = "<b>===== Bot status =====</b>\n"
    text += f"<b>Prefix:</b> <code>{prefix}</code>\n"
    text += f"<b>Plugins:</b> <code>{len(modules_help)}</code>\n"
    text += "<b>Current version:</b> "
    text += f"<code>{commits.get('current_hash')[:7]} ({commits.get('current')})</code>\n"
    text += f"<b>Latest version:</b> <code>{commits.get('latest_hash')[:7]}"
    text += f" ({commits.get('latest')})</code>\n"
    text += f"<b>Branch:</b> <code>{commits.get('branch')}</code>\n"
    text += f"<b>Uptime:</b> <code>{datetime.timedelta(seconds=perf_counter() - bot_uptime)}</code>\n\n"

    text += "<b>===== System info =====</b>\n"
    text += f"<b>Python:</b> <code>{sys.version}</code>\n"
    text += f"<b>Pyrogram:</b> <code>{pyrogram.__version__}</code>\n"
    text += f"<b>OS:</b> <code>{sys.platform}</code>\n"
    kernel_version = subprocess.run(["uname", "-a"], capture_output=True).stdout.decode().strip()
    text += f"<b>Kernel:</b> <code>{kernel_version}</code>\n"
    system_uptime = subprocess.run(["uptime", "-p"], capture_output=True).stdout.decode().strip()
    text += f"<b>Uptime:</b> <code>{system_uptime}</code>\n\n"
    text += "<a href='https://github.com/KurimuzonAkuma/Kurimuzon-Userbot'>Kurimuzon-Userbot</a>"
    await message.edit(text, disable_web_page_preview=True)


modules_help["status"] = {
    "status": "Get information about the userbot and system",
}
