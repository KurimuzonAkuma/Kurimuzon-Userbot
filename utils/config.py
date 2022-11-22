import environs

env = environs.Env()
env.read_env("./.env")

api_id = env.int("API_ID")
api_hash = env.str("API_HASH")

db_name = env.str("DB_NAME")
