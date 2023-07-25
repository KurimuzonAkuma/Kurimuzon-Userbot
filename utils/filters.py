import re
from typing import List, Union

from pyrogram import Client
from pyrogram.filters import Filter, create
from pyrogram.types import Message

from utils.scripts import get_prefix

reactions_filter = create(lambda _, __, message: bool(message.reactions))


def command(commands: Union[str, List[str]], case_sensitive: bool = False):
    """Filter commands, i.e.: text messages starting with "/" or any other custom prefix.

    Parameters:
        commands (``str`` | ``list``):
            The command or list of commands as string the filter should look for.
            Examples: "start", ["start", "help", "settings"]. When a message text containing
            a command arrives, the command itself and its arguments will be stored in the *command*
            field of the :obj:`~pyrogram.Message`.



        case_sensitive (``bool``, *optional*):
            Pass True if you want your command(s) to be case sensitive. Defaults to False.
            Examples: when True, command="Start" would trigger /Start but not /start.
    """
    command_re = re.compile(r"([\"'])(.*?)(?<!\\)\1|(\S+)")

    async def func(flt, client: Client, message: Message):
        username = client.me.username or ""
        text = message.text or message.caption
        message.command = None

        if not text:
            return False

        for prefix in get_prefix():
            if not text.startswith(prefix):
                continue

            without_prefix = text[len(prefix) :]

            for cmd in flt.commands:
                if not re.match(
                    f"^(?:{cmd}(?:@?{username})?)(?:\s|$)",
                    without_prefix,
                    flags=0 if flt.case_sensitive else re.IGNORECASE,
                ):
                    continue

                without_command = re.sub(
                    f"{cmd}(?:@?{username})?\s?",
                    "",
                    without_prefix,
                    count=1,
                    flags=0 if flt.case_sensitive else re.IGNORECASE,
                )

                # match.groups are 1-indexed, group(1) is the quote, group(2) is the text
                # between the quotes, group(3) is unquoted, whitespace-split text

                # Remove the escape character from the arguments
                message.command = [cmd] + [
                    re.sub(r"\\([\"'])", r"\1", m.group(2) or m.group(3) or "")
                    for m in command_re.finditer(without_command)
                ]

                return True

        return False

    commands = commands if isinstance(commands, list) else [commands]
    commands = {c if case_sensitive else c.lower() for c in commands}

    return create(func, "CommandFilter", commands=commands, case_sensitive=case_sensitive)


class startswith(Filter, set):
    """Filter messages starting with text.

    Parameters:
        ignore_case (``bool``, *optional*):
            Pass True to ignore case sensitivity.
            Defaults to True.
    """

    def __init__(self, text: str, ignore_case: bool = True):
        super().__init__()
        self.text = text
        self.ignore_case = ignore_case

    async def __call__(self, _, message: Message):
        mtext = message.text or message.caption
        if not mtext:
            return False
        if self.ignore_case:
            mtext = mtext.lower()
        return bool(mtext.startswith(self.text))


class viabot(Filter, set):
    """Filter messages coming with via_bot.

    Parameters:
        bots (``int`` | ``str`` | ``list``):
            Pass one or more bot ids/usernames to filter.
            Defaults to None (any bot).
    """

    def __init__(self, bots: Union[int, str, List[Union[int, str]]] = None):
        bots = [] if bots is None else bots if isinstance(bots, list) else [bots]

        super().__init__(bot.lower().strip("@") if isinstance(bot, str) else bot for bot in bots)

    async def __call__(self, _, message: Message):
        return message.via_bot and (
            message.via_bot.id in self
            or (message.via_bot.username and message.via_bot.username.lower() in self)
        )
