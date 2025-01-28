import datetime
import pathlib

import environs
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.scripts import ModuleHelp

script_path = pathlib.Path(__file__).parent.parent

modules_help = ModuleHelp()
scheduler_jobs = []

scheduler = AsyncIOScheduler()
uptime = datetime.datetime.now()

env = environs.Env()
env.read_env("./.env")
