import pathlib
from time import perf_counter

from utils.db import db

script_path = pathlib.Path(__file__).parent.parent

modules_help = {}

bot_uptime = perf_counter()
