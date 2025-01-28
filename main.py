import asyncio
import contextlib
import logging
import os
import pathlib
import platform

import git
from pyrogram import enums, idle

from utils.client import CustomClient
from utils.misc import env, scheduler, scheduler_jobs
from utils.scripts import Formatter, get_proxy, handle_restart
from utils.storage import FernetStorage

os.chdir(pathlib.Path(__file__).parent)


async def main():
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(
        Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[stdout_handler],
    )

    app = CustomClient(
        "KurimuzonUserbot",
        api_id=env.int("API_ID", 6),
        api_hash=env.str("API_HASH", "eb06d4abfb49dc3eeb1aeb98ae0f581e"),
        device_model=env.str("DEVICE_MODEL", "Samsung SM-S931B"),
        system_version=env.str("SYSTEM_VERSION", "15 (35)"),
        app_version=env.str("APP_VERSION", "11.7.0 (56631)"),
        lang_pack=env.str("LANG_PACK", "android"),
        lang_code=env.str("LANG_CODE", "jabka"),
        hide_password=True,
        plugins=dict(root="plugins"),
        sleep_threshold=10,
        workdir=pathlib.Path(__file__).parent,
        parse_mode=enums.ParseMode.HTML,
        skip_updates=False,
        proxy=get_proxy(),
    )

    # For security purposes
    app.storage = FernetStorage(client=app, key=bytes(env.str("FERNET_KEY"), "utf-8"))

    await app.start(use_qr=True)

    async for _ in app.get_dialogs(limit=100):
        pass

    await app.storage.save()

    try:
        git.Repo()
    except git.exc.InvalidGitRepositoryError:
        repo = git.Repo.init()
        origin = repo.create_remote(
            "origin", "https://github.com/KurimuzonAkuma/Kurimuzon-Userbot"
        )
        origin.fetch()
        repo.create_head("master", origin.refs.master)
        repo.heads.master.set_tracking_branch(origin.refs.master)
        repo.heads.master.checkout(True)

    await handle_restart(app)

    for job in scheduler_jobs:
        scheduler.add_job(
            func=job.func,
            trigger=job.trigger,
            args=[app] + job.args,
            kwargs=job.kwargs,
            id=job.id,
        )

    scheduler.start()

    await idle()

    await app.stop()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        if platform.system() == "Windows":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        else:
            try:
                import uvloop

                uvloop.install()
            except ImportError:
                logging.warning("uvloop not installed.")

        if platform.python_version_tuple() >= ("3", "11"):
            with asyncio.Runner() as runner:
                loop = runner.get_loop()
                loop.run_until_complete(main())
        else:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(main())
