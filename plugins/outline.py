import datetime
import json
import typing
from dataclasses import dataclass
from subprocess import PIPE, Popen

import arrow
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from urllib3 import PoolManager

from utils.db import db
from utils.filters import command
from utils.misc import modules_help
from utils.scripts import get_args, get_args_raw, get_full_name

text_template = (
    "<emoji id=5472164874886846699>✨</emoji> Outline конфиг пользователя {0}.\n\n"
    "<b>Ваш ключ доступа:</b> <code>{1}#Kurimuzon%20VPN</code>\n\n"
    "<b><emoji id=5818865088970362886>❕</b></emoji> <b>Инструкция по установке:</b>\n"
    "1. Скачайте и установите на устройство приложение Outline:\n"
    "<a href='https://itunes.apple.com/app/outline-app/id1356177741'>iOS</a> | "
    "<a href='https://itunes.apple.com/app/outline-app/id1356178125'>macOS</a> | "
    "<a href='https://s3.amazonaws.com/outline-releases/client/windows/stable/Outline-Client.exe'>Windows</a> | "
    "<a href='https://s3.amazonaws.com/outline-releases/client/linux/stable/Outline-Client.AppImage'>Linux</a> | "
    "<a href='https://play.google.com/store/apps/details?id=org.outline.android.client'>Android</a> | "
    "<a href='https://s3.amazonaws.com/outline-releases/client/android/stable/Outline-Client.apk'>Дополнительная ссылка для Android (APK)</a>\n\n"
    "2. Скопируйте ключ доступа, который начинается с ss://.\n\n"
    '3. Откройте клиент Outline. Если ваш ключ доступа определился автоматически, нажмите "Подключиться". Если этого не произошло, вставьте ключ в поле и нажмите "Подключиться".\n\n'
    'Теперь у вас есть доступ к свободному интернету. Чтобы убедиться, что вы подключились к серверу, введите в Google Поиске фразу "Какой у меня IP-адрес". IP-адрес, указанный в Google, должен совпадать с IP-адресом в клиенте Outline.'
)


# ! All rights of the block below belong to https://github.com/jadolg/outline-vpn-api
# region
@dataclass
class OutlineKey:
    """
    Describes a key in the Outline server
    """

    key_id: int
    name: str
    password: str
    port: int
    method: str
    access_url: str
    used_bytes: int
    data_limit: typing.Optional[int]


class OutlineServerErrorException(Exception):
    pass


class _FingerprintAdapter(requests.adapters.HTTPAdapter):
    """
    This adapter injected into the requests session will check that the
    fingerprint for the certificate matches for every request
    """

    def __init__(self, fingerprint=None, **kwargs):
        self.fingerprint = str(fingerprint)
        super(_FingerprintAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            assert_fingerprint=self.fingerprint,
        )


class OutlineVPN:
    """
    An Outline VPN connection
    """

    def __init__(self, api_url: str, cert_sha256: str = None):
        self.api_url = api_url

        if cert_sha256:
            session = requests.Session()
            session.mount("https://", _FingerprintAdapter(cert_sha256))
            self.session = session
        else:
            self.session = requests.Session()

    def get_keys(self):
        """Get all keys in the outline server"""
        response = self.session.get(f"{self.api_url}/access-keys/", verify=False)
        if response.status_code == 200 and "accessKeys" in response.json():
            response_metrics = self.session.get(f"{self.api_url}/metrics/transfer", verify=False)
            if (
                response_metrics.status_code >= 400
                or "bytesTransferredByUserId" not in response_metrics.json()
            ):
                raise OutlineServerErrorException("Unable to get metrics")

            response_json = response.json()
            return [
                OutlineKey(
                    key_id=key.get("id"),
                    name=key.get("name"),
                    password=key.get("password"),
                    port=key.get("port"),
                    method=key.get("method"),
                    access_url=key.get("accessUrl"),
                    data_limit=key.get("dataLimit", {}).get("bytes"),
                    used_bytes=response_metrics.json()
                    .get("bytesTransferredByUserId")
                    .get(key.get("id")),
                )
                for key in response_json.get("accessKeys")
            ]
        raise OutlineServerErrorException("Unable to retrieve keys")

    def create_key(self, key_name=None) -> OutlineKey:
        """Create a new key"""
        response = self.session.post(f"{self.api_url}/access-keys/", verify=False)
        if response.status_code == 201:
            key = response.json()
            outline_key = OutlineKey(
                key_id=key.get("id"),
                name=key.get("name"),
                password=key.get("password"),
                port=key.get("port"),
                method=key.get("method"),
                access_url=key.get("accessUrl"),
                used_bytes=0,
                data_limit=None,
            )
            if key_name and self.rename_key(outline_key.key_id, key_name):
                outline_key.name = key_name
            return outline_key

        raise OutlineServerErrorException("Unable to create key")

    def delete_key(self, key_id: int) -> bool:
        """Delete a key"""
        response = self.session.delete(f"{self.api_url}/access-keys/{key_id}", verify=False)
        return response.status_code == 204

    def rename_key(self, key_id: int, name: str):
        """Rename a key"""
        files = {
            "name": (None, name),
        }

        response = self.session.put(
            f"{self.api_url}/access-keys/{key_id}/name", files=files, verify=False
        )
        return response.status_code == 204

    def add_data_limit(self, key_id: int, limit_bytes: int) -> bool:
        """Set data limit for a key (in bytes)"""
        data = {"limit": {"bytes": limit_bytes}}

        response = self.session.put(
            f"{self.api_url}/access-keys/{key_id}/data-limit", json=data, verify=False
        )
        return response.status_code == 204

    def delete_data_limit(self, key_id: int) -> bool:
        """Removes data limit for a key"""
        response = self.session.delete(
            f"{self.api_url}/access-keys/{key_id}/data-limit", verify=False
        )
        return response.status_code == 204

    def get_transferred_data(self):
        """Gets how much data all keys have used
        {
            "bytesTransferredByUserId": {
                "1":1008040941,
                "2":5958113497,
                "3":752221577
            }
        }"""
        response = self.session.get(f"{self.api_url}/metrics/transfer", verify=False)
        if response.status_code >= 400 or "bytesTransferredByUserId" not in response.json():
            raise OutlineServerErrorException("Unable to get metrics")
        return response.json()

    def get_server_information(self):
        """Get information about the server
        {
            "name":"My Server",
            "serverId":"7fda0079-5317-4e5a-bb41-5a431dddae21",
            "metricsEnabled":true,
            "createdTimestampMs":1536613192052,
            "version":"1.0.0",
            "accessKeyDataLimit":{"bytes":8589934592},
            "portForNewAccessKeys":1234,
            "hostnameForAccessKeys":"example.com"
        }
        """
        response = self.session.get(f"{self.api_url}/server", verify=False)
        if response.status_code != 200:
            raise OutlineServerErrorException("Unable to get information about the server")
        return response.json()

    def set_server_name(self, name: str) -> bool:
        """Renames the server"""
        return self._extracted_from_set_metrics_status_3("name", name, "/name")

    def set_hostname(self, hostname: str) -> bool:
        """Changes the hostname for access keys.
        Must be a valid hostname or IP address."""
        return self._extracted_from_set_metrics_status_3(
            "hostname", hostname, "/server/hostname-for-access-keys"
        )

    def get_metrics_status(self) -> bool:
        """Returns whether metrics is being shared"""
        response = self.session.get(f"{self.api_url}/metrics/enabled", verify=False)
        return response.json().get("metricsEnabled")

    def set_metrics_status(self, status: bool) -> bool:
        """Enables or disables sharing of metrics"""
        return self._extracted_from_set_metrics_status_3(
            "metricsEnabled", status, "/metrics/enabled"
        )

    # TODO Rename this here and in `set_server_name`, `set_hostname` and `set_metrics_status`
    def _extracted_from_set_metrics_status_3(self, arg0, arg1, arg2):
        data = {arg0: arg1}
        response = self.session.put(f"{self.api_url}{arg2}", verify=False, json=data)
        return response.status_code == 204

    def set_port_new_for_access_keys(self, port: int) -> bool:
        """Changes the default port for newly created access keys.
        This can be a port already used for access keys."""
        data = {"port": port}
        response = self.session.put(
            f"{self.api_url}/server/port-for-new-access-keys", verify=False, json=data
        )
        if response.status_code == 400:
            raise OutlineServerErrorException(
                "The requested port wasn't an integer from 1 through 65535, or the request had no port parameter."
            )
        elif response.status_code == 409:
            raise OutlineServerErrorException(
                "The requested port was already in use by another service."
            )
        return response.status_code == 204

    def set_data_limit_for_all_keys(self, limit_bytes: int) -> bool:
        """Sets a data transfer limit for all access keys."""
        data = {"limit": {"bytes": limit_bytes}}
        response = self.session.put(
            f"{self.api_url}/server/access-key-data-limit", verify=False, json=data
        )
        return response.status_code == 204

    def delete_data_limit_for_all_keys(self) -> bool:
        """Removes the access key data limit, lifting data transfer restrictions on all access keys."""
        response = self.session.delete(
            f"{self.api_url}/server/access-key-data-limit", verify=False
        )
        return response.status_code == 204


# endregion


@dataclass
class CustomOutlineKey:
    """
    Describes a key in the Outline server
    """

    key_id: int
    user_id: int
    name: str
    password: str
    port: int
    method: str
    access_url: str
    used_bytes: int
    created_at: int
    updated_at: int
    data_limit: typing.Optional[int]


class CustomOutlineVPN(OutlineVPN):
    def __init__(self, api_url: str, cert_sha256: str = None):
        super().__init__(api_url, cert_sha256)

    def get_keys(self) -> typing.List[CustomOutlineKey]:
        """Get all keys in the outline server"""
        response = self.session.get(f"{self.api_url}/access-keys/", verify=False)
        if response.status_code == 200 and "accessKeys" in response.json():
            response_metrics = self.session.get(f"{self.api_url}/metrics/transfer", verify=False)
            if (
                response_metrics.status_code >= 400
                or "bytesTransferredByUserId" not in response_metrics.json()
            ):
                raise OutlineServerErrorException("Unable to get metrics")

            response_json = response.json()
            users = db.get("outline", "users", {})

            return [
                CustomOutlineKey(
                    key_id=key.get("id"),
                    user_id=users.get(key.get("id")).get("user_id"),
                    name=key.get("name"),
                    password=key.get("password"),
                    port=key.get("port"),
                    method=key.get("method"),
                    access_url=f"{key.get('accessUrl')}#Kurimuzon%20VPN",
                    data_limit=key.get("dataLimit", {}).get("bytes"),
                    created_at=datetime.datetime.fromtimestamp(
                        users.get(key.get("id")).get("created_at")
                    ),
                    updated_at=datetime.datetime.fromtimestamp(
                        users.get(key.get("id")).get("updated_at")
                    ),
                    used_bytes=response_metrics.json()
                    .get("bytesTransferredByUserId")
                    .get(key.get("id")),
                )
                for key in response_json.get("accessKeys")
            ]
        raise OutlineServerErrorException("Unable to retrieve keys")

    def get_key(self, user_id: int) -> CustomOutlineKey:
        """Get key in the outline server"""
        for key in self.get_keys():
            if key.user_id == user_id:
                return key

    def create_key(self, user_id: int, key_name: str = None) -> CustomOutlineKey:
        """Create a new key"""

        if self.get_key(user_id):
            raise OutlineServerErrorException("User already exists")

        response = self.session.post(f"{self.api_url}/access-keys/", verify=False)
        if response.status_code == 201:
            key = response.json()
            outline_key = CustomOutlineKey(
                key_id=key.get("id"),
                user_id=user_id,
                name=key.get("name"),
                password=key.get("password"),
                port=key.get("port"),
                method=key.get("method"),
                access_url=key.get("accessUrl"),
                used_bytes=0,
                created_at=int(datetime.datetime.now().timestamp()),
                updated_at=int(datetime.datetime.now().timestamp()),
                data_limit=None,
            )

            users = db.get("outline", "users", {})
            users[outline_key.key_id] = outline_key.__dict__
            db.set("outline", "users", users)

            if key_name and self.rename_key(user_id, key_name):
                outline_key.name = key_name

            return outline_key

        raise OutlineServerErrorException("Unable to create key")

    def delete_key(self, user_id: int) -> bool:
        """Delete a key"""
        key = self.get_key(user_id)

        response = self.session.delete(f"{self.api_url}/access-keys/{key.key_id}", verify=False)
        result = response.status_code == 204
        if not result:
            raise OutlineServerErrorException("Unable to delete key")

        users = db.get("outline", "users", {})
        users.pop(user_id)
        db.set("outline", "users", users)

        return result

    def rename_key(self, user_id: int, name: str):
        """Rename a key"""
        files = {
            "name": (None, name),
        }

        key = self.get_key(user_id)

        response = self.session.put(
            f"{self.api_url}/access-keys/{key.key_id}/name", files=files, verify=False
        )

        users = db.get("outline", "users", {})
        users[key.key_id]["updated_at"] = int(datetime.datetime.now().timestamp())
        db.set("outline", "users", users)

        return response.status_code == 204

    def add_data_limit(self, user_id: int, limit_bytes: int) -> bool:
        """Set data limit for a key (in bytes)"""
        data = {"limit": {"bytes": limit_bytes}}

        key = self.get_key(user_id)

        response = self.session.put(
            f"{self.api_url}/access-keys/{key.key_id}/data-limit", json=data, verify=False
        )

        users = db.get("outline", "users", {})
        users[key.key_id]["updated_at"] = int(datetime.datetime.now().timestamp())
        db.set("outline", "users", users)

        return response.status_code == 204

    def delete_data_limit(self, user_id: int) -> bool:
        """Removes data limit for a key"""
        key = self.get_key(user_id)

        response = self.session.delete(
            f"{self.api_url}/access-keys/{key.key_id}/data-limit", verify=False
        )

        users = db.get("outline", "users", {})
        users[key.key_id]["updated_at"] = int(datetime.datetime.now().timestamp())
        db.set("outline", "users", users)

        return response.status_code == 204


# Format the bytes to human readable format
def format_bytes(bytes) -> str:
    units = ["B", "KB", "MB", "GB"]
    i = 0
    while bytes >= 1024 and i < len(units) - 1:
        bytes /= 1024.0
        i += 1
    return "{:.2f}{}".format(bytes, units[i])


@Client.on_message(command(["olst"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def outline_set_token(_: Client, message: Message):
    args = get_args_raw(message)

    try:
        token = json.loads(args)
    except json.JSONDecodeError:
        return await message.edit_text("<b>Invalid token</b>")

    if not isinstance(token, dict) and not token.get("apiUrl") and not token.get("certSha256"):
        return await message.edit_text("<b>Invalid token</b>")

    outline_client = CustomOutlineVPN(api_url=token["apiUrl"], cert_sha256=token["certSha256"])

    try:
        outline_client.get_keys()
    except OutlineServerErrorException:
        return await message.edit_text("<b>Invalid token</b>")

    db.set("outline", "token", token)

    return await message.edit_text("<b>Token set successfully!</b>")


@Client.on_message(command(["olau"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def ol_add(client: Client, message: Message):
    token = db.get("outline", "token")
    if not token:
        return await message.edit_text("<b>Token not set</b>")

    args, nargs = get_args(message)

    if (
        len(nargs) == 2
        and "-id" in nargs
        and nargs["-id"].lstrip("-").isdigit()
        and "-name" in nargs
    ):
        user_id = int(nargs["-id"])
        name = nargs["-name"]
    else:
        user_id = message.chat.id
        name = get_full_name(message.chat)

    outline_client = CustomOutlineVPN(api_url=token["apiUrl"], cert_sha256=token["certSha256"])

    try:
        key = outline_client.create_key(user_id=user_id, key_name=name)
    except OutlineServerErrorException:
        return await message.edit_text("<b>Unable to create key</b>")

    await message.edit_text(
        text_template.format(
            name,
            key.access_url,
        ),
        disable_web_page_preview=True,
    )


@Client.on_message(command(["olru"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def ol_remove(_: Client, message: Message):
    token = db.get("outline", "token")
    if not token:
        return await message.edit_text("<b>Token not set</b>")

    args, nargs = get_args(message)

    if (
        len(nargs) == 2
        and "-id" in nargs
        and nargs["-id"].lstrip("-").isdigit()
        and "-name" in nargs
    ):
        user_id = int(nargs["-id"])
    else:
        user_id = message.chat.id

    outline_client = CustomOutlineVPN(api_url=token["apiUrl"], cert_sha256=token["certSha256"])

    user = outline_client.get_key(user_id)
    if not user:
        return await message.edit_text("<b>User not found</b>")

    outline_client.delete_key(user_id)

    return await message.edit_text("<b>Key deleted successfully!</b>")


@Client.on_message(command(["ole"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def ol_enable(_: Client, message: Message):
    token = db.get("outline", "token")
    if not token:
        return await message.edit_text("<b>Token not set</b>")

    args, nargs = get_args(message)

    if (
        len(nargs) == 2
        and "-id" in nargs
        and nargs["-id"].lstrip("-").isdigit()
        and "-name" in nargs
    ):
        user_id = int(nargs["-id"])
    else:
        user_id = message.chat.id

    outline_client = CustomOutlineVPN(api_url=token["apiUrl"], cert_sha256=token["certSha256"])

    user = outline_client.get_key(user_id)
    if not user:
        return await message.edit_text("<b>User not found</b>")

    outline_client.delete_data_limit(user_id)

    await message.edit_text(f"<b>Key enabled successfully for {user.name}</b>\n\n")


@Client.on_message(command(["old"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def ol_disable(_: Client, message: Message):
    token = db.get("outline", "token")
    if not token:
        return await message.edit_text("<b>Token not set</b>")

    args, nargs = get_args(message)

    if (
        len(nargs) == 2
        and "-id" in nargs
        and nargs["-id"].lstrip("-").isdigit()
        and "-name" in nargs
    ):
        user_id = int(nargs["-id"])
    else:
        user_id = message.chat.id

    outline_client = CustomOutlineVPN(api_url=token["apiUrl"], cert_sha256=token["certSha256"])

    user = outline_client.get_key(user_id)
    if not user:
        return await message.edit_text("<b>User not found</b>")

    outline_client.add_data_limit(user_id, 1000)

    await message.edit_text(f"<b>Key disabled successfully for {user.name}</b>\n\n")


@Client.on_message(command(["oln"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def ol_update_user(_: Client, message: Message):
    token = db.get("outline", "token")
    if not token:
        return await message.edit_text("<b>Token not set</b>")

    args, nargs = get_args(message)

    if (
        len(nargs) == 2
        and "-id" in nargs
        and nargs["-id"].lstrip("-").isdigit()
        and "-name" in nargs
    ):
        user_id = int(nargs["-id"])
        name = nargs["-name"]
    else:
        user_id = message.chat.id
        name = get_full_name(message.chat)

    outline_client = CustomOutlineVPN(api_url=token["apiUrl"], cert_sha256=token["certSha256"])

    user = outline_client.get_key(user_id)
    if not user:
        return await message.edit_text("<b>User not found</b>")

    outline_client.rename_key(user_id, name)

    await message.edit_text(f"<b>User name updated successfully for {user.name}</b>\n\n")


@Client.on_message(command(["oll"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def ol_list(client: Client, message: Message):
    token = db.get("outline", "token")
    if not token:
        return await message.edit_text("<b>Token not set</b>")

    args, nargs = get_args(message)

    outline_client = CustomOutlineVPN(api_url=token["apiUrl"], cert_sha256=token["certSha256"])

    try:
        keys = outline_client.get_keys()
    except OutlineServerErrorException:
        return await message.edit_text("<b>Unable to get keys</b>")

    if not keys:
        return await message.edit_text("<b>No users found</b>")

    if args and args[0].lstrip("-").isdigit():
        user = outline_client.get_key(int(args[0]))
        if not user:
            return await message.edit_text("<b>User not found</b>")

        is_enabled = user.data_limit is None or not user.data_limit <= 1024 * 1024 * 10  # 10 MB

        result = (
            f"<b>Information about user: {user.name}</b> (<code>{user.user_id}</code>)\n"
            f"<b>Enabled:</b> {'🟢' if is_enabled else '🔴'}\n"
            f"<b>Created at:</b> {user.created_at} ({arrow.get(user.created_at.timestamp()).humanize()})\n"
            f"<b>Updated at:</b> {user.updated_at} ({arrow.get(user.updated_at.timestamp()).humanize()})\n"
        )

        if user.used_bytes:
            result += f"<b>Data transferred:</b> 📥📤{format_bytes(user.used_bytes)}"

        return await message.edit_text(result)
    elif "-all" in args:
        header = "🗓️ <b>Information about all users:</b>\n"
        result = ""
        footer = f"\n<b>Total users:</b> {len(keys)}"

        for key in keys:
            is_enabled = key.data_limit is None or not key.data_limit <= 1024 * 1024 * 10  # 10 MB

            if client.me.is_premium:
                if is_enabled:
                    result += (
                        "<emoji id=5206448940639067043>⬜️</emoji>"
                        "<emoji id=5208594229558779394>🔳</emoji>"
                    )
                else:
                    result += (
                        "<emoji id=5208676628506353769>🔲</emoji>"
                        "<emoji id=5208885192118247387>⬛️</emoji>"
                    )
            else:
                result += f"{'🟢' if is_enabled else '🔴'} "

            result += f"<code>{key.user_id}</code>"

            if key.used_bytes:
                result += f" <b>📥📤 {format_bytes(key.used_bytes)}</b>"

            result += "\n"

        return await message.edit_text(header + result + footer)
    else:
        return await message.edit_text("<b>Invalid arguments</b>")


@Client.on_message(command(["olc"]) & filters.me & ~filters.forwarded & ~filters.scheduled)
async def ol_(client: Client, message: Message):
    token = db.get("outline", "token")
    if not token:
        return await message.edit_text("<b>Token not set</b>")

    args, nargs = get_args(message)

    if (
        len(nargs) == 2
        and "-id" in nargs
        and nargs["-id"].lstrip("-").isdigit()
        and "-name" in nargs
    ):
        user_id = int(nargs["-id"])
        name = nargs["-name"]
    else:
        user_id = message.chat.id
        name = get_full_name(message.chat)

    outline_client = CustomOutlineVPN(api_url=token["apiUrl"], cert_sha256=token["certSha256"])

    user = outline_client.get_key(user_id)

    await message.edit_text(
        text_template.format(
            user.name,
            user.access_url,
        ),
        disable_web_page_preview=True,
    )

    db.remove("outline", "users")


module = modules_help.add_module("outline", __file__)
module.add_command("olst", "Set Outline API token", "[token]")
module.add_command("olau", "Add user to Outline and send config", "[-id int] [-name str]")
module.add_command("olru", "Remove user from Outline", "[user_id]")
module.add_command("oln", "Update Outline user name", "[user_id] [name]")
module.add_command("ole", "Enable/Disable Outline for user", "[user_id] [on|off]")
module.add_command("oll", "Show info about user", "[user_id] [-all]")
module.add_command("olc", "Send Outline config", "[user_id]")
