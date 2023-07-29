from dotenv import dotenv_values

env = dotenv_values("./.env")


def get_env_value(key: str, to_type, default=None):
    value = env.get(key)
    if value is None:
        return default

    try:
        return to_type(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid value for {key}: {value}") from e


api_id = get_env_value("API_ID", int)
api_hash = get_env_value("API_HASH", str)

db_name = get_env_value("DB_NAME", str)

proxy_scheme = get_env_value("PROXY_SCHEME", str)
proxy_hostname = get_env_value("PROXY_HOSTNAME", str)
proxy_port = get_env_value("PROXY_PORT", int)
proxy_username = get_env_value("PROXY_USERNAME", str)
proxy_password = get_env_value("PROXY_PASSWORD", str)
proxy_ipv6 = get_env_value("PROXY_IPV6", bool)

proxy_settings = (
    {
        "proxy": {
            "scheme": proxy_scheme,
            "hostname": proxy_hostname,
            "port": proxy_port,
            "username": proxy_username,
            "password": proxy_password,
        },
        "ipv6": proxy_ipv6,
    }
    if all((proxy_scheme, proxy_hostname, proxy_port, proxy_username, proxy_password, proxy_ipv6))
    else {}
)
