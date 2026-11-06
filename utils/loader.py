import html
from dataclasses import dataclass, field
from collections.abc import Callable, Sequence

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import filters as pyrogram_filters
from pyrogram.handlers import MessageHandler
from pyrogram.utils import split_text

from utils.filters import command as command_filter
from utils.scripts import get_prefix


@dataclass
class CommandEntry:
    commands: list[str]
    description: str | None = None
    args: str | None = None
    hidden: bool = False


@dataclass
class HelpPlugin:
    name: str
    path: str
    commands: list[CommandEntry] = field(default_factory=list)
    hidden: bool = False

    def add_command(
        self,
        commands: list[str],
        description: str | None = None,
        args: str | None = None,
        hidden: bool = False,
    ) -> CommandEntry:
        existing_commands = {name.casefold() for entry in self.commands for name in entry.commands}
        duplicate = next((name for name in commands if name.casefold() in existing_commands), None)
        if duplicate:
            raise ValueError(f"Command {duplicate} already exists in module {self.name}")

        entry = CommandEntry(commands, description, _render_args(args), hidden)
        self.commands.append(entry)

        return entry

    def delete_command(self, command: str) -> None:
        entry = next(
            (
                entry
                for entry in self.commands
                if command.casefold() in {name.casefold() for name in entry.commands}
            ),
            None,
        )

        if entry is None:
            raise ValueError(f"Command {command} not found")

        self.commands.remove(entry)

    def set_command_visibility(self, command: str, hidden: bool) -> None:
        entry = next(
            (
                entry
                for entry in self.commands
                if command.casefold() in {name.casefold() for name in entry.commands}
            ),
            None,
        )

        if entry is None:
            raise ValueError(f"Command {command} not found")

        entry.hidden = hidden


class HelpRegistry:
    def __init__(self) -> None:
        self.modules: dict[str, HelpPlugin] = {}
        self.class_names: dict[str, HelpPlugin] = {}

    def add_module(self, name: str, path: str) -> HelpPlugin:
        existing = self._find_module(name)

        if existing:
            if existing.path != path:
                raise ValueError(f"Plugin {name} already exists")
            return existing

        module = HelpPlugin(name, path)
        self.modules[name] = module

        return module

    def delete_module(self, name: str) -> None:
        module = self._find_module(name)
        if module is None:
            raise ValueError(f"Plugin {name} not found")

        del self.modules[module.name]
        self.class_names = {
            class_name: registered_module
            for class_name, registered_module in self.class_names.items()
            if registered_module is not module
        }

    def add_class_name(self, module: HelpPlugin, class_name: str) -> None:
        key = class_name.casefold()
        existing = self.class_names.get(key)
        if existing and existing is not module:
            raise ValueError(f"Plugin class name {class_name} already exists")

        self.class_names[key] = module

    def hide_module(self, name: str) -> None:
        self.get_module(name).hidden = True

    def show_module(self, name: str) -> None:
        self.get_module(name).hidden = False

    def get_module(self, name: str) -> HelpPlugin:
        module = self._find_module(name)

        if module is None:
            raise ValueError(f"Plugin {name} not found")

        return module

    def get_module_by_path(self, path: str) -> HelpPlugin:
        for module in self.modules.values():
            if module.path == path:
                return module

        raise ValueError(f"Plugin with path {path} not found")

    def get_module_by_command(self, command: str) -> HelpPlugin:
        command_key = command.casefold()

        for module in self.modules.values():
            for entry in module.commands:
                if command_key in {name.casefold() for name in entry.commands}:
                    return module

        raise ValueError(f"Plugin with command {command} not found")

    def help(self, max_length: int = 3500) -> list[str]:
        prefix = html.escape(get_prefix())
        lines = [
            f"For more help on how to use a command, type "
            f"<code>{prefix}help [module|command]</code>",
            "",
            "Available Modules:",
        ]

        for module_name, module in sorted(
            self.modules.items(), key=lambda item: item[0].casefold()
        ):
            if module.hidden:
                continue

            visible_commands = [entry for entry in module.commands if not entry.hidden]
            if not visible_commands:
                continue

            module_title = html.escape(module_name.title())
            tokens = [
                f"<code>{prefix}{html.escape(command)}</code>"
                for entry in visible_commands
                for command in entry.commands
            ]
            lines.extend([f"┌{module_title}", "└ " + " ".join(tokens)])

        module_count = self.modules_count
        command_count = self.commands_count
        lines.extend(
            [
                "",
                f"The number of modules in the userbot: {module_count}",
                f"The number of commands in the userbot: {command_count}",
            ]
        )
        return split_text("\n".join(lines), max_length)

    def module_help(self, module_name: str, full: bool = True) -> str:
        module = self.get_module(module_name)
        prefix = html.escape(get_prefix())
        lines = []
        if full:
            lines.extend(
                [
                    f"Plugin <code>{html.escape(module.name)}</code> "
                    f"with {len(module.commands)} commands",
                    "",
                ]
            )

        for index, entry in enumerate(module.commands):
            line = f"<code>{prefix}{html.escape(entry.commands[0])}</code>"
            if entry.description:
                line += f" — <i>{html.escape(entry.description)}</i>"
            lines.append(line)
            if entry.args:
                lines.extend(["Args:", *(html.escape(arg) for arg in entry.args.splitlines())])
            if len(entry.commands) > 1:
                aliases = " ".join(
                    f"<code>{prefix}{html.escape(alias)}</code>" for alias in entry.commands[1:]
                )
                lines.extend(["", f"Aliases: {aliases}"])
            if entry.hidden:
                lines.extend(["", "hidden command"])
            if index < len(module.commands) - 1:
                lines.append("")

        return "\n".join(lines)

    def command_help(self, command: str) -> str:
        command_key = command.casefold()
        for module in self.modules.values():
            for entry in module.commands:
                if command_key in {name.casefold() for name in entry.commands}:
                    return self._command_help(module, entry)
        raise ValueError(f"Command {command} not found")

    def _command_help(self, module: HelpPlugin, entry: CommandEntry) -> str:
        prefix = html.escape(get_prefix())
        command = f"<code>{prefix}{html.escape(entry.commands[0])}</code>"
        lines = [
            f"Plugin: <code>{html.escape(module.name)}</code> · "
            f"<code>{prefix}help {html.escape(module.name)}</code>",
            "",
            command,
        ]
        if entry.description:
            lines[-1] += f" - <i>{html.escape(entry.description)}</i>"
        if entry.args:
            lines.extend(["", "Args:"])
            lines.extend(html.escape(argument) for argument in entry.args.splitlines())
        if len(entry.commands) > 1:
            aliases = " ".join(
                f"<code>{prefix}{html.escape(alias)}</code>" for alias in entry.commands[1:]
            )
            lines.extend(["", f"Aliases: {aliases}"])
        if entry.hidden:
            lines.extend(["", "<i>Hidden command</i>"])
        return "\n".join(lines)

    def _find_module(self, name: str) -> HelpPlugin | None:
        name_key = name.casefold()
        module = next(
            (
                module
                for module_name, module in self.modules.items()
                if module_name.casefold() == name_key
            ),
            None,
        )
        return module or self.class_names.get(name_key)

    @property
    def modules_count(self) -> int:
        return sum(
            1
            for module in self.modules.values()
            if not module.hidden and any(not entry.hidden for entry in module.commands)
        )

    @property
    def commands_count(self) -> int:
        return sum(
            1
            for module in self.modules.values()
            for entry in module.commands
            if not module.hidden and not entry.hidden
        )


help_registry = HelpRegistry()
scheduler = AsyncIOScheduler()


@dataclass
class CommandArg:
    name: str
    description: str | None = None
    required: bool = True

    def render(self) -> str:
        suffix = ""

        if self.description:
            suffix = f" - {self.description}"

        if self.required:
            return f"<{self.name}>{suffix}"

        return f"[{self.name}, *optional*]{suffix}"


def _normalize_args(args: str | Sequence[CommandArg] | None):
    if args is None or isinstance(args, str):
        return args
    return list(args)


def _render_args(args: str | Sequence[CommandArg] | None) -> str | None:
    if args is None or isinstance(args, str):
        return args
    return "\n".join(arg.render() for arg in args)


def command(
    commands: str | list[str],
    *,
    description: str | None = None,
    args: str | Sequence[CommandArg] | None = None,
    filters=None,
    group: int = 0,
    hidden: bool = False,
):
    """Register a command handler on a Plugin method."""

    def decorator(function: Callable):
        names = [commands] if isinstance(commands, str) else list(commands)
        if not names:
            raise ValueError("A command must have at least one trigger")

        function.__loader_command__ = {
            "commands": names,
            "description": description,
            "args": _normalize_args(args),
            "filters": filters if filters is not None else pyrogram_filters.me,
            "group": group,
            "hidden": hidden,
        }
        return function

    return decorator


def loop(interval: float = 60, *, wait_before: bool = True):
    """Run a Plugin method periodically after the client has started."""

    def decorator(function: Callable):
        function.__loader_loop__ = {"interval": interval, "wait_before": wait_before}
        return function

    return decorator


class Plugin:
    """Base class for class-based plugins."""

    def __init__(self, client):
        self.client = client


def create_command_handler(instance: Plugin, method: Callable, metadata: dict):
    handler_filter = command_filter(metadata["commands"]) & metadata["filters"]
    return MessageHandler(method, handler_filter), metadata["group"]


def add_command_help(module_help, metadata: dict) -> None:
    module_help.add_command(
        metadata["commands"],
        metadata["description"],
        _render_args(metadata.get("args")),
        hidden=metadata.get("hidden", False),
    )
