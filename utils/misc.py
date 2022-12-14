import pathlib
from time import perf_counter

import git

from utils.db import db

script_path = pathlib.Path(__file__).parent.parent

modules_help = {}

bot_uptime = perf_counter()
prefix = db.get("core.main", "prefix", default=".")

repo = git.Repo(script_path)
# 05c3cfe is the first commit of the fork
commits = {
    "latest": (
        len(
            list(
                repo.iter_commits(f"05c3cfe..{repo.remotes.origin.refs.master.commit.hexsha[:7]}")
            )
        )
        + 1
    ),
    "current": len(list(repo.iter_commits(f"05c3cfe..{repo.head.commit.hexsha[:7]}"))) + 1,
}
