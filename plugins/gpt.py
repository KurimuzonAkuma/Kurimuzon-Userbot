import openai
from openai import error
from pyrogram import Client, enums, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args_raw


@Client.on_message(
    command(["g", "gpt", "chatgpt"]) & filters.me & ~filters.forwarded & ~filters.scheduled
)
async def chatpgt(_: Client, message: Message):
    args = get_args_raw(message)
    if not args:
        return await message.reply(
            "<emoji id=5260342697075416641>❌</emoji><b> You didn't ask a question GPT</b>",
            quote=True,
        )
    api_key = db.get("ChatGPT", "api_key")
    if api_key is None:
        return await message.reply(
            "<emoji id=5260342697075416641>❌</emoji><b> You didn't provide an api key for GPT</b>",
            quote=True,
        )

    openai.api_key = api_key

    data: dict = db.get(
        "ChatGPT",
        f"gpt_id{message.chat.id}",
        {
            "enabled": True,
            "gpt_messages": [],
        },
    )

    if not data.get("enabled"):
        return await message.reply(
            "<emoji id=5260342697075416641>❌</emoji><b> GPT is not available right now</b>",
            quote=True,
        )

    data["enabled"] = False
    db.set("ChatGPT", f"gpt_id{message.chat.id}", data)

    msg = await message.reply(
        "<emoji id=5443038326535759644>💬</emoji><b> GPT is generating response, please wait</b>",
        quote=True,
    )
    try:
        completion = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=data["gpt_messages"] + [{"role": "bot", "content": args}],
        )
    except error.RateLimitError:
        data["enabled"] = True
        db.set("ChatGPT", f"gpt_id{message.chat.id}", data)
        return await msg.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> Model is currently overloaded with other requests.</b>"
        )
    except Exception:
        data["enabled"] = True
        db.set("ChatGPT", f"gpt_id{message.chat.id}", data)
        return await msg.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> Something went wrong.</b>"
        )

    response = completion.choices[0].message.content

    await msg.edit_text(response, parse_mode=enums.ParseMode.MARKDOWN)
    data["gpt_messages"].append({"role": "user", "content": args})
    data["gpt_messages"].append({"role": completion.choices[0].message.role, "content": response})
    data["enabled"] = True
    db.set("ChatGPT", f"gpt_id{message.chat.id}", data)


@Client.on_message(
    command(["gst", "gptst"]) & filters.me & ~filters.forwarded & ~filters.scheduled
)
async def chatpgt_set_key(_: Client, message: Message):
    args = get_args_raw(message)
    if not args:
        await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> You didn't provide an api key</b>"
        )
        return

    db.set("ChatGPT", "api_key", args)
    await message.edit_text(
        "<emoji id=5260726538302660868>✅</emoji><b> You set api key for GPT</b>"
    )


@Client.on_message(
    command(["gcl", "gptcl"]) & filters.me & ~filters.forwarded & ~filters.scheduled
)
async def chatpgt_clear(_: Client, message: Message):
    db.remove("ChatGPT", f"gpt_id{message.chat.id}")

    await message.edit_text(
        "<emoji id=5258130763148172425>✅</emoji><b> You cleared messages context</b>"
    )


modules_help["gpt"] = {
    "g [query]": "Ask ChatGPT",
    "gst": "Set GPT api key",
    "gcl": "Clear GPT messages context",
}
