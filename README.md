<p align="center">
    <br>
    <b>Kurimuzon-Userbot</b>
    <br>
    <b>Telegram userbot inspired by <a href='https://github.com/Dragon-Userbot/Dragon-Userbot'>Dragon-Userbot</a></b>
    <br>
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge" alt="Code style">
    <img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/KurimuzonAkuma/Kurimuzon-Userbot?style=for-the-badge">
    <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/KurimuzonAkuma/Kurimuzon-Userbot?style=for-the-badge">
</p>

<h1>About</h1>
<p>Kurimuzon-Userbot is a Telegram userbot (in case you didn't know, selfbot/userbot are used to automate user accounts).
So how does it work? It works in a very simple way, using the pyrogram library, a python script connects to your account (creating a new session) and catches your commands.

Using selfbot/userbot is against Telegram's Terms of Service, and you may get banned for using it if you're not careful.

The developers are not responsible for any consequences you may encounter when using Kurimuzon-Userbot. We are also not
responsible for any damage to chat rooms caused by using this userbot.</p>

<h1>Installation</h1>
<h2>Linux and Windows [only wsl]</h2>

```bash
apt-get update && apt install curl && curl -sS https://raw.githubusercontent.com/KurimuzonAkuma/Kurimuzon-Userbot/master/install.sh | sh
```

<h2>Manual</h2>
<ul>
<li>Clone repository from github</li>
<li>Go to folder with userbot and rename .env.example -> .env</li>
<li>Start userbot with python3 main.py</li>
</ul>

Subsequent launch:
<pre><code>cd Kurimuzon-Userbot/</code></pre>
<pre><code>python3 main.py</code></pre>

<h1>Custom modules</h1>

<p>To add your module to the bot, create a pull request or put in manually in plugins folder.</p>

```python3
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.misc import modules_help, prefix


@Client.on_message(filters.command("example_edit", prefix) & filters.me)
async def example_edit(client: Client, message: Message):
    await message.edit("<code>This is an example module</code>")


@Client.on_message(filters.command("example_send", prefix) & filters.me)
async def example_send(client: Client, message: Message):
    await client.send_message(message.chat.id, "<b>This is an example module</b>")


# This adds instructions for your module
modules_help["example"] = {
    "example_send": "example send",
    "example_edit": "example edit",
}

# modules_help["example"] = { "example_send [text]": "example send" }
#                  |            |              |        |
#                  |            |              |        └─ command description
#           module_name         command_name   └─ optional command arguments
#        (only snake_case)   (only snake_case too)
```

<h2>Credits</h2>
<nav>
<li><a href='https://github.com/john-phonk'>john-phonk</a></li>
<li><a href='https://github.com/Taijefx34'>Taijefx34</a></li>
<li><a href='https://github.com/LaciaMemeFrame'>LaciaMemeFrame</a></li>
<li><a href='https://github.com/iamnalinor'>nalinor</a></li>
<li>asphy <a href='https://t.me/LKRinternationalrunetcomphinc'>tg</a> and <a href='https://ru.namemc.com/profile/asphyxiamywife.1'>namemc</a></li>
<li><a href='http://t.me/fuccsoc'>fuccsoc</a></li>
</nav>
<h4>Written on <a href='https://github.com/pyrogram/pyrogram'>Pyrogram❤️</a></h4>
