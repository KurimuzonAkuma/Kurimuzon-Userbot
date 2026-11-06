import copy
import datetime
import inspect
import logging
import sys
from importlib import import_module
from pathlib import Path
from utils.loader import help_registry, scheduler
from pyrogram import Client
from apscheduler.jobstores.base import JobLookupError
from utils.loader import Plugin

from utils.loader import (
    add_command_help,
    create_command_handler,
)

log = logging.getLogger(__name__)


class CustomClient(Client):
    """Modified Pyrogram Client, the main means for interacting with Telegram.

    Parameters:
        name (``str``):
            A name for the client, e.g.: "my_account".

        api_id (``int`` | ``str``, *optional*):
            The *api_id* part of the Telegram API key, as integer or string.
            E.g.: 12345 or "12345".

        api_hash (``str``, *optional*):
            The *api_hash* part of the Telegram API key, as string.
            E.g.: "0123456789abcdef0123456789abcdef".

        app_version (``str``, *optional*):
            Application version.
            Defaults to "Pyrogram x.y.z".

        device_model (``str``, *optional*):
            Device model.
            Defaults to *platform.python_implementation() + " " + platform.python_version()*.

        system_version (``str``, *optional*):
            Operating System version.
            Defaults to *platform.system() + " " + platform.release()*.

        lang_pack (``str``, *optional*):
            Name of the language pack used on the client.
            Defaults to "" (empty string).

        lang_code (``str``, *optional*):
            Code of the language used on the client, in ISO 639-1 standard.
            Defaults to "en".

        system_lang_code (``str``, *optional*):
            Code of the language used on the system, in ISO 639-1 standard.
            Defaults to "en".

        ipv6 (``bool``, *optional*):
            Pass True to connect to Telegram using IPv6.
            Defaults to False (IPv4).

        proxy (``dict``, *optional*):
            The Proxy settings as dict.
            E.g.: *dict(scheme="socks5", hostname="11.22.33.44", port=1234, username="user", password="pass")*.
            The *username* and *password* can be omitted if the proxy doesn't require authorization.

        test_mode (``bool``, *optional*):
            Enable or disable login to the test servers.
            Only applicable for new sessions and will be ignored in case previously created sessions are loaded.
            Defaults to False.

        bot_token (``str``, *optional*):
            Pass the Bot API token to create a bot session, e.g.: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
            Only applicable for new sessions.

        session_string (``str``, *optional*):
            Pass a session string to load the session in-memory.
            Implies ``in_memory=True``.

        in_memory (``bool``, *optional*):
            Pass True to start an in-memory session that will be discarded as soon as the client stops.
            In order to reconnect again using an in-memory session without having to login again, you can use
            :meth:`~pyrogram.Client.export_session_string` before stopping the client to get a session string you can
            pass to the ``session_string`` parameter.
            Defaults to False.

        phone_number (``str``, *optional*):
            Pass the phone number as string (with the Country Code prefix included) to avoid entering it manually.
            Only applicable for new sessions.

        phone_code (``str``, *optional*):
            Pass the phone code as string (for test numbers only) to avoid entering it manually.
            Only applicable for new sessions.

        password (``str``, *optional*):
            Pass the Two-Step Verification password as string (if required) to avoid entering it manually.
            Only applicable for new sessions.

        workers (``int``, *optional*):
            Number of maximum concurrent workers for handling incoming updates.
            Defaults to ``min(32, os.cpu_count() + 4)``.

        workdir (``str``, *optional*):
            Define a custom working directory.
            The working directory is the location in the filesystem where Pyrogram will store the session files.
            Defaults to the parent directory of the main script.

        plugins (``dict``, *optional*):
            Smart Plugins settings as dict, e.g.: *dict(root="plugins")*.

        parse_mode (:obj:`~pyrogram.enums.ParseMode`, *optional*):
            Set the global parse mode of the client. By default, texts are parsed using both Markdown and HTML styles.
            You can combine both syntaxes together.

        no_updates (``bool``, *optional*):
            Pass True to disable incoming updates.
            When updates are disabled the client can't receive messages or other updates.
            Useful for batch programs that don't need to deal with updates.
            Defaults to False (updates enabled and received).

        skip_updates (``bool``, *optional*):
            Pass True to skip pending updates that arrived while the client was offline.
            Defaults to True.

        takeout (``bool``, *optional*):
            Pass True to let the client use a takeout session instead of a normal one, implies *no_updates=True*.
            Useful for exporting Telegram data. Methods invoked inside a takeout session (such as get_chat_history,
            download_media, ...) are less prone to throw FloodWait exceptions.
            Only available for users, bots will ignore this parameter.
            Defaults to False (normal session).

        sleep_threshold (``int``, *optional*):
            Set a sleep threshold for flood wait exceptions happening globally in this client instance, below which any
            request that raises a flood wait will be automatically invoked again after sleeping for the required amount
            of time. Flood wait exceptions requiring higher waiting times will be raised.
            Defaults to 10 seconds.

        hide_password (``bool``, *optional*):
            Pass True to hide the password when typing it during the login.
            Defaults to False, because ``getpass`` (the library used) is known to be problematic in some
            terminal environments.

        max_concurrent_transmissions (``int``, *optional*):
            Set the maximum amount of concurrent transmissions (uploads & downloads).
            A value that is too high may result in network related issues.
            Defaults to 1.

        max_message_cache_size (``int``, *optional*):
            Set the maximum size of the message cache.
            Defaults to 10000.

        storage_engine (:obj:`~pyrogram.storage.Storage`, *optional*):
            Pass an instance of your own implementation of session storage engine.
            Useful when you want to store your session in databases like Mongo, Redis, etc.

        init_connection_params (:obj:`~pyrogram.raw.base.JSONValue`, *optional*):
            Additional initConnection parameters.
            For now, only the tz_offset field is supported, for specifying timezone offset in seconds.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_instances = {}
        self.plugin_handlers = {}
        self.plugin_loops = []
        self.scheduled_plugin_loop_ids = set()

    def _register_class_plugins(self, module, module_path: str) -> int:

        plugin_classes = [
            (class_name, plugin_class)
            for class_name, plugin_class in vars(module).items()
            if inspect.isclass(plugin_class)
            and plugin_class is not Plugin
            and plugin_class.__module__ == module.__name__
            and issubclass(plugin_class, Plugin)
        ]
        if not plugin_classes:
            return 0

        if module_path in self.plugin_instances:
            raise ValueError(f"Plugin '{module_path}' is already loaded")

        conflicts = self.get_plugin_registration_conflicts(module, module_path)
        if conflicts:
            raise ValueError("\n".join(conflicts))

        plugins = [
            (class_name, plugin_class, plugin_class(self))
            for class_name, plugin_class in plugin_classes
        ]

        count = 0
        for class_name, plugin_class, plugin in plugins:
            self.plugin_instances.setdefault(module_path, []).append(plugin)
            class_registration_count = 0
            plugin_name = Path(module.__file__).stem
            module_help = help_registry.add_module(plugin_name, module.__file__)
            help_registry.add_class_name(module_help, class_name)
            plugin._loader_help_name = plugin_name

            for method_name, method in vars(plugin_class).items():
                bound_method = getattr(plugin, method_name)
                command_metadata = getattr(method, "__loader_command__", None)
                if command_metadata:
                    handler, group = create_command_handler(plugin, bound_method, command_metadata)
                    self.add_handler(handler, group)
                    self.plugin_handlers.setdefault(module_path, []).append((handler, group))
                    add_command_help(module_help, command_metadata)
                    count += 1
                    class_registration_count += 1

                for handler, group in getattr(method, "handlers", []):
                    bound_handler = copy.copy(handler)
                    bound_handler.callback = bound_method
                    self.add_handler(bound_handler, group)
                    self.plugin_handlers.setdefault(module_path, []).append((bound_handler, group))
                    count += 1
                    class_registration_count += 1

                loop_metadata = getattr(method, "__loader_loop__", None)
                if loop_metadata:
                    self.plugin_loops.append(
                        {
                            "func": bound_method,
                            "id": f"{module_path}.{class_name}.{method_name}",
                            **loop_metadata,
                        }
                    )
                    count += 1
                    class_registration_count += 1

            if class_registration_count:
                log.info(
                    '[%s] [LOAD] Loaded plugin "%s" from "%s" (%s registrations)',
                    self.name,
                    plugin_name,
                    module_path,
                    class_registration_count,
                )

        return count

    def get_plugin_registration_conflicts(self, module, module_path: str) -> list[str]:
        plugin_classes = [
            (class_name, plugin_class)
            for class_name, plugin_class in vars(module).items()
            if inspect.isclass(plugin_class)
            and plugin_class is not Plugin
            and plugin_class.__module__ == module.__name__
            and issubclass(plugin_class, Plugin)
        ]
        if not plugin_classes:
            return []

        if module_path in self.plugin_instances:
            return [f"Plugin '{module_path}' is already loaded"]

        plugin_file = Path(module.__file__).resolve()
        registered_names = {}
        conflicts = []

        for module_name, help_module in help_registry.modules.items():
            for registered_command in help_module.commands:
                for name in registered_command.commands:
                    registered_names.setdefault(
                        name.casefold(), (module_name, registered_command.commands[0])
                    )

        candidate_names = {}
        candidate_modules = {}

        for class_name, plugin_class in plugin_classes:
            command_metadata = [
                metadata
                for method in vars(plugin_class).values()
                if (metadata := getattr(method, "__loader_command__", None))
            ]
            if not command_metadata:
                continue

            help_name = plugin_file.stem
            for lookup_name in (plugin_file.stem, class_name):
                lookup_key = lookup_name.casefold()
                previous = candidate_modules.get(lookup_key)
                if previous and previous[1] != str(plugin_file):
                    conflicts.append(f"Plugin name '{lookup_name}' conflicts with '{previous[0]}'")
                candidate_modules[lookup_key] = (lookup_name, str(plugin_file))

                try:
                    existing_module = help_registry.get_module(lookup_name)
                except ValueError:
                    existing_module = None
                if existing_module and Path(existing_module.path).resolve() != plugin_file:
                    conflicts.append(
                        f"Plugin name '{lookup_name}' is already registered by "
                        f"'{existing_module.name}'"
                    )

            for metadata in command_metadata:
                local_names = set()
                for name in metadata["commands"]:
                    key = name.casefold()
                    if key in local_names:
                        conflicts.append(
                            f"Command '{name}' is declared more than once in the uploaded plugin"
                        )
                        continue
                    local_names.add(key)

                    existing = registered_names.get(key)
                    if existing:
                        conflicts.append(
                            f"Command '{name}' is already used by '{existing[0]}.{existing[1]}'"
                        )
                        continue

                    previous = candidate_names.get(key)
                    if previous:
                        conflicts.append(
                            f"Command '{name}' conflicts with '{previous[1]}' in the uploaded plugin"
                        )
                        continue

                    candidate_names[key] = (help_name, name)

        return list(dict.fromkeys(conflicts))

    def register_plugin_loops(self):

        for job in self.plugin_loops:
            if job["id"] in self.scheduled_plugin_loop_ids:
                continue

            scheduler.add_job(
                func=job["func"],
                trigger="interval",
                seconds=job["interval"],
                id=job["id"],
                next_run_time=None if job["wait_before"] else datetime.datetime.now(),
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )
            self.scheduled_plugin_loop_ids.add(job["id"])

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unloads a plugin.

        Parameters:
            plugin_name (``str``):
                The name of the plugin to unload.

        Returns:
            ``bool``: True if the plugin was unloaded successfully, False otherwise.
        """

        if self.plugins:
            root = self.plugins["root"]
        else:
            root = "plugins"

        path = root + "." + plugin_name

        if path not in sys.modules:
            log.warning('[%s] [UNLOAD] Plugin "%s" is not loaded', self.name, path)
            return False

        removed_handlers = self.plugin_handlers.pop(path, [])
        for handler, group in removed_handlers:
            self.remove_handler(handler, group)

        plugins = self.plugin_instances.pop(path, [])
        plugin_names = []
        for plugin in plugins:
            plugin_names.append(Path(sys.modules[path].__file__).stem)
            help_name = getattr(plugin, "_loader_help_name", None)
            if help_name and help_name in help_registry.modules:
                help_registry.delete_module(help_name)

        plugin_loops = []
        removed_loops = 0
        for job in self.plugin_loops:
            if job["id"].startswith(path + "."):
                removed_loops += 1
                try:
                    scheduler.remove_job(job["id"])
                except JobLookupError:
                    pass
                self.scheduled_plugin_loop_ids.discard(job["id"])
            else:
                plugin_loops.append(job)
        self.plugin_loops = plugin_loops

        del sys.modules[path]

        log.info(
            '[%s] [UNLOAD] Unloaded plugin "%s" from "%s" (%s handlers, %s loops)',
            self.name,
            ", ".join(dict.fromkeys(plugin_names)) or plugin_name,
            path,
            len(removed_handlers),
            removed_loops,
        )

        return True

    def load_plugins(self):
        if not self.plugins or not self.plugins.get("enabled", True):
            return

        root = self.plugins["root"]
        count = 0

        for path in sorted(Path(root.replace(".", "/")).rglob("*.py")):
            module_path = ".".join(path.parent.parts + (path.stem,))

            try:
                module = import_module(module_path)
            except Exception as e:
                log.warning(f'[{self.name}] [LOAD] Ignoring module "{module_path}": {e}')
                continue

            try:
                count += self._register_class_plugins(module, module_path)
            except ValueError as e:
                log.warning(
                    '[%s] [LOAD] Skipping plugin "%s" due to a registration conflict: %s',
                    self.name,
                    module_path,
                    e,
                )

        if count:
            log.info(
                '[{}] Successfully loaded {} plugin registration{} from "{}"'.format(
                    self.name, count, "s" if count != 1 else "", root
                )
            )
        else:
            log.warning('[%s] No plugin registrations found in "%s"', self.name, root)
