import datetime
import pathlib

import environs

script_path = pathlib.Path(__file__).parent.parent

uptime = datetime.datetime.now()

env = environs.Env()
env.read_env("./.env")
