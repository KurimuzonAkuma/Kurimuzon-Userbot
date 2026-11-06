import asyncio
import contextlib
import logging
import os
import pathlib

import git
from pyrogram import enums, idle, raw
from pyrogram.connection.transport import TCPIntermediatePadded

from utils.client import CustomClient
from utils.loader import scheduler
from utils.misc import env
from utils.scripts import (
    Formatter,
    get_init_connection_params,
    get_proxy,
    handle_restart,
)
from utils.storage import EncryptedStorage

log = logging.getLogger(__name__)

os.chdir(pathlib.Path(__file__).parent)


async def main():
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[stdout_handler],
    )
    logging.getLogger("apscheduler.executors").setLevel(logging.WARNING)

    app = CustomClient(
        "KurimuzonUserbot",
        api_id=env.int("API_ID", None) or 6,
        api_hash=env.str("API_HASH", None) or "eb06d4abfb49dc3eeb1aeb98ae0f581e",
        device_model=env.str("DEVICE_MODEL", None) or "Samsung SM-F966B",
        system_version=env.str("SYSTEM_VERSION", None) or "16 (36)",
        app_version=env.str("APP_VERSION", None) or "12.3.1 (63852)",
        lang_pack=env.str("LANG_PACK", None) or "android",
        lang_code=env.str("LANG_CODE", None) or "jabka",
        client_platform=enums.ClientPlatform.ANDROID,
        hide_password=True,
        plugins={"root": "plugins"},
        sleep_threshold=10,
        workdir=pathlib.Path(__file__).parent,
        parse_mode=enums.ParseMode.HTML,
        skip_updates=True,
        proxy=get_proxy(),
        protocol_factory=TCPIntermediatePadded,
        init_connection_params=get_init_connection_params(),
    )

    # For security purposes
    app.storage = EncryptedStorage(client=app, password=env.str("ENCRYPTION_KEY"), use_wal=True)

    delattr(raw.functions.account, "DeleteAccount")

    await app.start(use_qr=True)

    await app.set_dc()

    async for _ in app.get_dialogs(limit=100):
        pass

    await app.storage.save()

    try:
        git.Repo()
    except git.exc.InvalidGitRepositoryError:
        repo = git.Repo.init()
        origin = repo.create_remote("origin", "https://github.com/KurimuzonAkuma/Kurimuzon-Userbot")
        origin.fetch()
        repo.create_head("master", origin.refs.master)
        repo.heads.master.set_tracking_branch(origin.refs.master)
        repo.heads.master.checkout(True)

    await handle_restart(app)

    app.register_plugin_loops()

    scheduler.start()

    # Preload media sessions
    # for dc_id in [1, 2, 4, 5]:
    #     await app.get_session(dc_id=dc_id, is_media=True)

    log.info(
        f"{app.me.username}#{app.me.id} on {git.Repo().active_branch.name}"
        f"@{git.Repo().head.commit.hexsha[:7]}"
        " | Userbot succesfully started."
    )

    await idle()

    await app.stop()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        try:
            import uvloop

            uvloop.install()
        except ImportError:
            log.warning("uvloop not installed.")

        asyncio.run(main())
