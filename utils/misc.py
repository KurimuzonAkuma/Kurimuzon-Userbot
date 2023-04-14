import pathlib
from time import perf_counter

from apscheduler.schedulers.asyncio import AsyncIOScheduler

script_path = pathlib.Path(__file__).parent.parent

modules_help = {}
scheduler_jobs = []

scheduler = AsyncIOScheduler()
bot_uptime = perf_counter()
