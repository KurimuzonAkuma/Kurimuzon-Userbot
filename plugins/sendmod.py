import os

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.filters import command
from utils.misc import modules_help
from utils.scripts import format_exc, format_module_help, with_args


@Client.on_message(~filters.scheduled & command(["sendmod", "sm"]) & filters.me)
@with_args("<b>Module name to send is not provided</b>")
async def sendmod(client: Client, message: Message):
    try:
        module_name = message.command[1].lower()
        if module_name in modules_help:
            await message.delete()
            text = format_module_help(module_name)
            if os.path.isfile(f"plugins/{module_name}.py"):
                await client.send_document(
                    message.chat.id, f"plugins/{module_name}.py", caption=text
                )
        else:
            await message.edit(f"<b>Module {module_name} not found!</b>")
    except Exception as e:
        await message.edit(format_exc(e))


modules_help["sendmod"] = {
    "sendmod [module_name]": "Send module to chat",
}
