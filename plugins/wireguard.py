import datetime
import logging
import os
import shutil
import subprocess
import typing
from io import BytesIO

from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid
from pyrogram.types import Message, User

from utils.misc import modules_help, prefix
from utils.scripts import full_name

# i hope someone will refactor this cringe...


text_template = (
            "<emoji id=5472164874886846699>✨</emoji> Твой сгенерированный конфиг для WireGuard:\n\n"
            "<b><emoji id=5818865088970362886>❕</b></emoji><b> Инструкция по установке:\n"
            "</b>Android/IOS:\n"
            '1. Скачать приложение из <a href="https://play.google.com/store/apps/details?id=com.wireguard.android">Play Market</a> или <a href="https://apps.apple.com/ru/app/wireguard/id1441195209">App Store</a>\n'
            "2. Нажать на плюсик и импортировать файл конфигурации или отсканировать QR код\n"
            "3. Включить VPN\n\n"
            "Windows/MacOS/Linux:\n"
            '1. Скачать приложение с <a href="https://www.wireguard.com/install/">официального сайта</a>\n'
            "2. Импортировать файл конфигурации\n"
            "3. Включить VPN\n\n"
)

def remove_readonly(func, path, _):
    "Clear the readonly bit and reattempt the removal"
    os.chmod(path, 0o0200)
    func(path)


class ConfigParser:
    def __init__(self):
        self.filename = ""
        self.sections = []


    def read(self, filename):
        self.filename = filename
        with open(self.filename, "r") as file:
            for line in file:
                # get rid of the newline
                line = line.strip()
                try:
                    if line:
                        if line.startswith("["):
                            section = line.strip("[]")
                            self.sections.append({section: {}})
                        else:
                            if line.startswith("#"):
                                self.sections[-1][section]["Comments"] = self.sections[-1][
                                    section
                                ].get("Comments", []) + [line.lstrip("#").strip()]
                                continue
                            (key, val) = line.split("=", 1)
                            key = key.strip()
                            val = val.strip()
                            if key not in self.sections[-1][section]:
                                self.sections[-1][section][key] = []
                            self.sections[-1][section][key].append(val.strip())
                except Exception as e:
                    logging.warning(f"WG | {str(e)} - line:{line}")

        return self.sections

    def write(self):
        with open(self.filename, "w") as file:
            for section in self.sections:
                for key, val in section.items():
                    file.write(f"[{key}]\n")
                    for k, v in val.items():
                        if k == "Comments":
                            for comment in v:
                                file.write(f"# {comment}\n")
                        else:
                            for value in v:
                                file.write(f"{k} = {value}\n")
                file.write("\n")

class WireGuard:
    def __init__(self):
        self.config_parser = ConfigParser()
        if os.path.exists("/etc/wireguard/wg0.conf"):
            self.config_parser.read("/etc/wireguard/wg0.conf")

        self.server_public_key = subprocess.run(
            "cat /etc/wireguard/publickey", shell=True, capture_output=True, text=True
        ).stdout.strip()
        self.server_private_key = subprocess.run(
            "cat /etc/wireguard/privatekey", shell=True, capture_output=True, text=True
        ).stdout.strip()

    def restart_service(self) -> None:
        subprocess.run(
            "systemctl restart wg-quick@wg0.service",
            shell=True,
        )

    def get_server_public_key(self) -> str:
        return self.server_public_key

    def get_server_private_key(self) -> str:
        return self.server_private_key

    def get_all_peers(self) -> typing.List[dict]:
        peers = []
        for section in self.config_parser.sections:
            peers.extend(section for key, val in section.items() if key == "Peer")
        return peers


    def create_client_config(self, peer_id: int, private_key: str, address: str, shared_key: str):
        server_ip = subprocess.run(
            "hostname -I | awk '{print $1}'",
            shell=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        template = (
            "[Interface]\n"
            f"PrivateKey = {private_key}\n"
            f"Address = {address}\n"
            "DNS = 1.1.1.1, 1.0.0.1\n"
            "\n"
            "[Peer]\n"
            f"PublicKey = {self.get_server_public_key()}\n"
            f"PresharedKey = {shared_key}\n"
            f"Endpoint = {server_ip}:51820\n"
            "AllowedIPs = 0.0.0.0/0, ::0/0"
        )
        with open(f"/etc/wireguard/clients/peer{peer_id}/vpn.conf", "w") as f:
            f.write(template)
        subprocess.run(
            f"qrencode -o /etc/wireguard/clients/peer{peer_id}/qrcode.jpg -r /etc/wireguard/clients/peer{peer_id}/vpn.conf",
            shell=True,
        )

    def add_peer(self, user_id: int, comments: list = None) -> None:
        if self.get_peer(user_id):
            raise ValueError(f"Peer with {user_id=} already exists")

        if len(self.config_parser.sections) < 2:
            allowed_ips = "10.13.13.2/32"
        else:
            last_peer = self.config_parser.sections[-1]
            for key, val in last_peer.items():
                if key == "Peer":
                    for k, v in val.items():
                        if k == "AllowedIPs":
                            allowed_ips = v[0].split("/", 1)[0].split(".")[-1]
                            allowed_ips = f"10.13.13.{int(allowed_ips) + 1}/32"
                            break

        if not os.path.exists(f"/etc/wireguard/clients/peer{user_id}"):
            os.mkdir(f"/etc/wireguard/clients/peer{user_id}")
        subprocess.run(
            f"wg genkey | tee /etc/wireguard/clients/peer{user_id}/privatekey | wg pubkey | tee /etc/wireguard/clients/peer{user_id}/publickey; wg genpsk | tee /etc/wireguard/clients/peer{user_id}/sharedkey",
            shell=True,
        )
        client_private_key = subprocess.run(
            f"cat /etc/wireguard/clients/peer{user_id}/privatekey",
            shell=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        client_public_key = subprocess.run(
            f"cat /etc/wireguard/clients/peer{user_id}/publickey",
            shell=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        client_shared_key = subprocess.run(
            f"cat /etc/wireguard/clients/peer{user_id}/sharedkey",
            shell=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.create_client_config(user_id, client_private_key, allowed_ips, client_shared_key)

        if not comments or not isinstance(comments, list) or f"Id: {user_id}" not in comments:
            comments = [f"Id: {user_id}"]

        self.config_parser.sections.append(
            {
                "Peer": {
                    "Comments": comments,
                    "PublicKey": [client_public_key],
                    "AllowedIPs": [allowed_ips],
                    "PresharedKey": [client_shared_key],
                }
            }
        )
        self.config_parser.write()
        self.restart_service()


    def remove_peer(self, peer_id: int):
        if not self.get_peer(peer_id):
            raise ValueError(f"Peer with {peer_id=} does not exist")

        while self.get_peer(peer_id):
            for section in self.config_parser.sections:
                for key, val in section.items():
                    if key == "Peer":
                        for k, v in val.items():
                            if k == "Comments":
                                for comment in v:
                                    if comment == f"Id: {peer_id}":
                                        self.config_parser.sections.remove(section)
                                        break
        if os.path.exists(f"/etc/wireguard/clients/peer{peer_id}"):
            shutil.rmtree(f"/etc/wireguard/clients/peer{peer_id}", onerror=remove_readonly)
        self.config_parser.write()
        self.restart_service()

    def get_peer_config(self, peer_id: int) -> BytesIO:
        with open(f"/etc/wireguard/clients/peer{peer_id}/vpn.conf", "rb") as file:
            return BytesIO(file.read())

    def get_peer_qr(self, peer_id: int) -> BytesIO:
        with open(f"/etc/wireguard/clients/peer{peer_id}/qrcode.jpg", "rb") as file:
            return BytesIO(file.read())


    def get_peer(self, peer_id: int) -> typing.Union[dict, None]:
        for section in self.config_parser.sections:
            for key, val in section.items():
                if key == "Peer":
                    for k, v in val.items():
                        if k == "Comments":
                            for comment in v:
                                if comment == f"Id: {peer_id}":
                                    return True


    def install(self) -> None:
        subprocess.run(
            "apt update",
            shell=True,
        )
        if not shutil.which("wg"):
            subprocess.run(
                "apt install wireguard -y",
                shell=True,
            )
        if not shutil.which("qrencode"):
            subprocess.run(
                "apt install qrencode -y",
                shell=True,
            )

        if not os.path.exists("/etc/wireguard"):
            os.mkdir("/etc/wireguard")
        if os.path.exists("/etc/wireguard/clients"):
            shutil.rmtree("/etc/wireguard/clients", onerror=remove_readonly)
        os.mkdir("/etc/wireguard/clients")

        subprocess.run(
            "wg genkey | tee /etc/wireguard/privatekey | "
            "wg pubkey | tee /etc/wireguard/publickey",
            shell=True
        )
        os.chmod("/etc/wireguard/privatekey", 0o600)

        self.server_private_key = subprocess.run(
            "cat /etc/wireguard/privatekey",
            shell=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.server_public_key = subprocess.run(
            "cat /etc/wireguard/publickey",
            shell=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        with open("/etc/wireguard/wg0.conf", "w") as f:
            f.write(
                "[Interface]\n"
                "Address = 10.13.13.1\n"
                "ListenPort = 51820\n"
                f"PrivateKey = {self.server_private_key}\n"
                "PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth+ -j MASQUERADE\n"
                "PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth+ -j MASQUERADE\n"
            )

        subprocess.run(
            "systemctl enable wg-quick@wg0.service",
            shell=True,
        )
        subprocess.run(
            "systemctl start wg-quick@wg0.service",
            shell=True,
        )

    def uninstall(self) -> None:
        subprocess.run(
            "systemctl stop wg-quick@wg0.service; systemctl disable wg-quick@wg0.service",
            shell=True,
        )
        subprocess.run(
            "rm -rf /etc/wireguard",
            shell=True,
        )
        subprocess.run(
            "apt remove wireguard -y",
            shell=True,
        )


@Client.on_message(filters.command(["wgi"], prefix) & filters.me)
async def wg_install(_: Client, message: Message):
    if os.geteuid() != 0:
        await message.edit("<b>This command must be run as root!</b>")
        return
    wg = WireGuard()

    if len(message.command) > 1 and message.command[1] in ["-y", "--yes"] or not shutil.which("wg"):
        await message.edit_text("<b>Installing WireGuard...</b>")
        wg.install()
        await message.edit_text("<b>✨ WireGuard installed!</b>")
    else:
        await message.edit_text(
            "<b>Are you sure you want to install WireGuard?</b>\n"
            "<b>It will delete all your current VPN configurations!</b>\n"
            f"<b>Use</b> <code>{prefix}{message.command[0]} -y</code> <b>to confirm</b>"
        )


@Client.on_message(filters.command(["wgu"], prefix) & filters.me)
async def wg_uninstall(_: Client, message: Message):
    if os.geteuid() != 0:
        await message.edit("<b>This command must be run as root!</b>")
        return

    if not shutil.which("wg"):
        await message.edit_text(
            "<b>WireGuard is not installed!</b>\n"
            f"<b>Use</b> <code>{prefix}wgi</code> <b>to install</b>"
        )
        return

    wg = WireGuard()

    if len(message.command) > 1 and message.command[1] in ["-y", "--yes"]:
        await message.edit_text("Uninstalling WireGuard...")
        wg.uninstall()
        await message.edit_text("✨ WireGuard successfully uninstalled")
    else:
        await message.edit_text(
            "<b>Are you sure you want to uninstall WireGuard?</b>\n"
            "<b>It will delete all your current VPN configurations!</b>\n"
            f"<b>Use</b> <code>{prefix}wgu -y</code> <b>to confirm</b>"
        )

@Client.on_message(filters.command(["wga"], prefix) & filters.me)
async def wg_add(client: Client, message: Message):
    if os.geteuid() != 0:
        await message.edit("<b>This command must be run as root!</b>")
        return

    if not shutil.which("wg"):
        await message.edit_text(
            "<b>WireGuard is not installed!</b>\n"
            f"<b>Use</b> <code>{prefix}wgi</code> <b>to install</b>"
        )
        return

    wg = WireGuard()

    user_id = message.chat.id
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1 and message.command[1].isdigit():
        user_id = int(message.command[1])

    if wg.get_peer(user_id):
        await message.edit_text("<b>User already exists</b>")
        return

    try:
        peer = await client.get_users(user_id)
    except PeerIdInvalid:
        peer = User(
            id=user_id,
            first_name="None",
            username="None",
        )

    note = message.text.split(" ", 2)[2] if len(message.command) > 2 else "None"

    wg.add_peer(user_id=user_id, comments=[
        f"Id: {user_id}",
        f"Name: {full_name(peer)}",
        f"Username: {peer.username}",
        f"Reg_date: {datetime.datetime.now().timestamp()}",
        f"Note: {note}"
    ])
    await client.send_document(message.chat.id, wg.get_peer_config(user_id), file_name="vpn.conf")
    await client.send_photo(
        message.chat.id,
        wg.get_peer_qr(user_id),
        caption=text_template,
    )


@Client.on_message(filters.command(["wgr"], prefix) & filters.me)
async def wg_remove(_: Client, message: Message):
    if os.geteuid() != 0:
        await message.edit("<b>This command must be run as root!</b>")
        return

    if not shutil.which("wg"):
        await message.edit_text(
            "<b>WireGuard is not installed!</b>\n"
            f"<b>Use</b> <code>{prefix}wgi</code> <b>to install</b>"
        )
        return

    wg = WireGuard()

    user_id = message.chat.id
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1 and message.command[1].isdigit():
        user_id = int(message.command[1])

    if not wg.get_peer(user_id):
        await message.edit_text("<b>User does not exist</b>")
        return
    wg.remove_peer(user_id)
    await message.edit_text(f"<b>User ID: {user_id} removed from WireGuard</b>")

@Client.on_message(filters.command(["wgs"], prefix) & filters.me)
async def wg_show(client: Client, message: Message):
    if os.geteuid() != 0:
        await message.edit("<b>This command must be run as root!</b>")
        return

    if not shutil.which("wg"):
        await message.edit_text(
            "<b>WireGuard is not installed!</b>\n"
            f"<b>Use</b> <code>{prefix}wgi</code> <b>to install</b>"
        )
        return

    wg = WireGuard()

    user_id = message.chat.id
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1 and message.command[1].isdigit():
        user_id = int(message.command[1])

    if not wg.get_peer(user_id):
        await message.edit_text("<b>User does not exist</b>")
        return

    await client.send_document(message.chat.id, wg.get_peer_config(user_id), file_name="vpn.conf")
    await client.send_photo(
        message.chat.id,
        wg.get_peer_qr(user_id),
        caption=text_template,
    )

@Client.on_message(filters.command(["wgl"], prefix) & filters.me)
async def wg_list(_: Client, message: Message):
    if os.geteuid() != 0:
        await message.edit("<b>This command must be run as root!</b>")
        return

    if not shutil.which("wg"):
        await message.edit_text(
            "<b>WireGuard is not installed!</b>\n"
            f"<b>Use</b> <code>{prefix}wgi</code> <b>to install</b>"
        )
        return

    wg = WireGuard()

    peers = wg.get_all_peers()
    if not peers:
        await message.edit_text("<b>No users found</b>")
        return
    text = "<b>===== Users =====</b>\n"
    for peer in peers:
        for comment in peer["Peer"]["Comments"]:
            key, value = comment.split(": ", 1)
            if key == "Reg_date" and value != "None":
                value = datetime.datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S")
                text += f"<b>{key}:</b> <code>{value}</code>\n" if value != "None" else ""
            elif key == "Username" and value != "None":
                text += f"<b>{key}:</b> <spoiler>@{value}</spoiler>\n" if value != "None" else ""
            else:
                text += f"<b>{key}:</b> <code>{value}</code>\n" if value != "None" else ""
        text += "\n"
    await message.edit_text(text)

modules_help["wireguard"] = {
    "wgi": "Install WireGuard",
    "wgu": "Uninstall WireGuard",
    "wga [user_id|reply]": "Add user to WireGuard and send config",
    "wgr [user_id|reply]": "Remove user from WireGuard",
    "wgs [user_id|reply]": "Show WireGuard config",
    "wgl": "Show all users in WireGuard",
}
