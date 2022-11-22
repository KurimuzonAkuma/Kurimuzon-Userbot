import pathlib
from time import perf_counter

import git

from utils.db import db

script_path = pathlib.Path(__file__).parent.parent

modules_help = {}

bot_uptime = perf_counter()
prefix = db.get("core.main", "prefix", default=".")

repo = git.Repo(script_path)
