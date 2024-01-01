import asyncio
import contextlib
import logging
import os
import platform
import shutil
import subprocess
from time import perf_counter
from traceback import print_exc

import git
from pyrogram import Client, idle
from pyrogram.enums import ParseMode

from utils import config
from utils.db import db
from utils.misc import scheduler, scheduler_jobs, script_path
from utils.scripts import CustomFormatter, restart
from utils.storage import AnyStorage

if script_path != os.getcwd():
    os.chdir(script_path)


async def main():
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(
        CustomFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[stdout_handler],
    )

    app = Client(
        "KurimuzonUserbot",
        api_hash=config.api_hash,
        api_id=config.api_id,
        device_model="HUAWEISTK-LX1",
        system_version="SDK 29",
        app_version="9.0.2 (28089)",
        lang_code="ru",
        hide_password=True,
        plugins=dict(root="plugins"),
        sleep_threshold=30,
        workdir=script_path,
        parse_mode=ParseMode.HTML,
        **config.proxy_settings,
    )

    app.storage = AnyStorage(client=app)

    await app.start()

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

    if updater := db.get("core.updater", "restart_info"):
        try:
            if updater["type"] == "restart":
                logging.info(f"{app.me.username}#{app.me.id} | Userbot succesfully restarted.")
                await app.edit_message_text(
                    chat_id=updater["chat_id"],
                    message_id=updater["message_id"],
                    text=f"<code>Restarted in {perf_counter() - updater['time']:.3f}s...</code>",
                )
            elif updater["type"] == "update":
                current_hash = git.Repo().head.commit.hexsha
                git.Repo().remote("origin").fetch()
                branch = git.Repo().active_branch.name
                upcoming = next(git.Repo().iter_commits(f"origin/{branch}", max_count=1)).hexsha
                upcoming_version = len(list(git.Repo().iter_commits()))
                current_version = upcoming_version - (
                    len(list(git.Repo().iter_commits(f"{current_hash}..{upcoming}")))
                )

                update_text = (
                    f"Userbot succesfully updated from {updater['hash'][:7]} "
                    f"({updater['version']}) to {current_hash[:7]} ({current_version}) version."
                )

                logging.info(f"{app.me.username}#{app.me.id} | {update_text}.")
                await app.edit_message_text(
                    chat_id=updater["chat_id"],
                    message_id=updater["message_id"],
                    text=(
                        f"<code>{update_text}.\n\n"
                        f"Restarted in {perf_counter() - updater['time']:.3f}s...</code>"
                    ),
                )
        except Exception:
            print("Error when updating!")
            print_exc()

        db.remove("core.updater", "restart_info")
    else:
        logging.info(
            f"{app.me.username}#{app.me.id} on {git.Repo().active_branch.name}"
            f"@{git.Repo().head.commit.hexsha[:7]}"
            " | Userbot succesfully started."
        )

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
            logging.error("Windows is not supported!")
            exit()

        if not shutil.which("termux-setup-storage"):
            try:
                import uvloop

                uvloop.install()
            except ImportError:
                subprocess.run("pip install uvloop", shell=True)
                restart()

        if platform.python_version_tuple() >= ("3", "11"):
            with asyncio.Runner() as runner:
                runner.get_loop().run_until_complete(main())
        else:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(main())
