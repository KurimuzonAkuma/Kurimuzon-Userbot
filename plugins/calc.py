from pyrogram import Client, filters
from pyrogram.types import Message

from utils import loader
from utils.loader import CommandArg, Plugin
from utils.scripts import get_args_raw


class Calculator(Plugin):
    @loader.command(
        ["calc", "c"],
        description="Evaluate expression and return result",
        args=[CommandArg("expression", "expression to calculate", required=False)],
        filters=~filters.scheduled & filters.me,
    )
    async def calc(self, client: Client, message: Message):
        args = get_args_raw(message)

        if not args:
            return await message.edit("Expression required to calculate")

        try:
            await message.edit(f"<i>{args}</i> = <code>{eval(args)}</code>")
        except Exception as e:
            await message.edit(
                f"Error while evaluating expression: <code>{e.__class__.__name__}: {e}</code>"
            )
