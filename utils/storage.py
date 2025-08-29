import base64
import logging
import struct
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

from cryptography.fernet import Fernet
from pyrogram import Client, raw, utils
from pyrogram.storage import Storage

import aiosqlite

log = logging.getLogger(__name__)


# language=SQLite
SCHEMA = """
CREATE TABLE sessions
(
    dc_id          INTEGER PRIMARY KEY,
    server_address TEXT,
    port           INTEGER,
    api_id         INTEGER,
    test_mode      INTEGER,
    auth_key       BLOB,
    date           INTEGER NOT NULL,
    user_id        INTEGER,
    is_bot         INTEGER
);

CREATE TABLE peers
(
    id             INTEGER PRIMARY KEY,
    access_hash    INTEGER,
    type           INTEGER NOT NULL,
    phone_number   TEXT,
    last_update_on INTEGER NOT NULL DEFAULT (CAST(STRFTIME('%s', 'now') AS INTEGER))
);

CREATE TABLE usernames
(
    id       INTEGER,
    username TEXT,
    FOREIGN KEY (id) REFERENCES peers(id)
);

CREATE TABLE update_state
(
    id   INTEGER PRIMARY KEY,
    pts  INTEGER,
    qts  INTEGER,
    date INTEGER,
    seq  INTEGER
);

CREATE TABLE version
(
    number INTEGER PRIMARY KEY
);

CREATE INDEX idx_peers_id ON peers (id);
CREATE INDEX idx_peers_phone_number ON peers (phone_number);
CREATE INDEX idx_usernames_id ON usernames (id);
CREATE INDEX idx_usernames_username ON usernames (username);

CREATE TRIGGER trg_peers_last_update_on
    AFTER UPDATE
    ON peers
BEGIN
    UPDATE peers
    SET last_update_on = CAST(STRFTIME('%s', 'now') AS INTEGER)
    WHERE id = NEW.id;
END;
"""

USERNAMES_SCHEMA = """
CREATE TABLE usernames
(
    id       INTEGER,
    username TEXT,
    FOREIGN KEY (id) REFERENCES peers(id)
);

CREATE INDEX idx_usernames_username ON usernames (username);
"""

UPDATE_STATE_SCHEMA = """
CREATE TABLE update_state
(
    id   INTEGER PRIMARY KEY,
    pts  INTEGER,
    qts  INTEGER,
    date INTEGER,
    seq  INTEGER
);
"""

PROD = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
    203: "91.105.192.100"
}

def get_input_peer(peer_id: int, access_hash: int, peer_type: str):
    if peer_type in ["user", "bot"]:
        return raw.types.InputPeerUser(
            user_id=peer_id,
            access_hash=access_hash
        )

    if peer_type == "group":
        return raw.types.InputPeerChat(
            chat_id=-peer_id
        )

    if peer_type in ["direct", "channel", "forum", "supergroup"]:
        return raw.types.InputPeerChannel(
            channel_id=utils.get_channel_id(peer_id),
            access_hash=access_hash
        )

    raise ValueError(f"Invalid peer type: {peer_type}")


class EncryptedFernetStorage(Storage):
    VERSION = 7
    USERNAME_TTL = 8 * 60 * 60
    FILE_EXTENSION = ".session"

    def __init__(
        self,
        client: Client,
        key: bytes,
        use_wal: Optional[bool] = False,
    ):
        super().__init__(client.name)

        self.conn = None  # type: aiosqlite.Connection
        self.fernet = Fernet(key)

        self.session_string = client.session_string
        self.in_memory = client.in_memory
        self.use_wal = use_wal

        if self.in_memory:
            self.database = ":memory:"
        else:
            self.database = client.workdir / (client.name + self.FILE_EXTENSION)

    async def update(self):
        version = await self.version()

        if version == 1:
            await self.conn.execute("DELETE FROM peers;")

            version += 1

        if version == 2:
            await self.conn.execute("ALTER TABLE sessions ADD api_id INTEGER;")

            version += 1

        if version == 3:
            await self.conn.executescript(USERNAMES_SCHEMA)

            version += 1

        if version == 4:
            await self.conn.executescript(UPDATE_STATE_SCHEMA)

            version += 1

        if version == 5:
            await self.conn.execute("CREATE INDEX idx_usernames_id ON usernames (id);")

            version += 1

        if version == 6:
            address = PROD[await self.dc_id()]

            await self.conn.execute("ALTER TABLE sessions ADD server_address TEXT;")
            await self.conn.execute("ALTER TABLE sessions ADD port INTEGER;")

            await self.conn.execute("UPDATE sessions SET server_address = ?;", (address,))
            await self.conn.execute("UPDATE sessions SET port = 443;")

            version += 1

        await self.version(version)

        await self.conn.commit()

    async def create(self):
        await self.conn.executescript(SCHEMA)

        await self.conn.execute("INSERT INTO version VALUES (?)", (self.VERSION,))

        await self.conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2, "149.154.167.51", 443, None, None, None, 0, None, None),
        )

        await self.conn.commit()

    async def open(self):
        if self.in_memory:
            self.conn = await aiosqlite.connect(":memory:", timeout=1, check_same_thread=False)
            await self.create()

            if self.session_string:
                # Old format
                if len(self.session_string) in [
                    self.SESSION_STRING_SIZE,
                    self.SESSION_STRING_SIZE_64,
                ]:
                    dc_id, test_mode, auth_key, user_id, is_bot = struct.unpack(
                        (
                            self.OLD_SESSION_STRING_FORMAT
                            if len(self.session_string) == self.SESSION_STRING_SIZE
                            else self.OLD_SESSION_STRING_FORMAT_64
                        ),
                        base64.urlsafe_b64decode(
                            self.session_string + "=" * (-len(self.session_string) % 4)
                        ),
                    )

                    await self.dc_id(dc_id)
                    await self.test_mode(test_mode)
                    await self.auth_key(auth_key)
                    await self.user_id(user_id)
                    await self.is_bot(is_bot)
                    await self.date(0)

                    log.warning(
                        "You are using an old session string format. Use export_session_string to update"
                    )
                    return

                dc_id, api_id, test_mode, auth_key, user_id, is_bot = struct.unpack(
                    self.SESSION_STRING_FORMAT,
                    base64.urlsafe_b64decode(
                        self.session_string + "=" * (-len(self.session_string) % 4)
                    ),
                )

                await self.dc_id(dc_id)
                await self.server_address(PROD[dc_id])
                await self.port(443)
                await self.api_id(api_id)
                await self.test_mode(test_mode)
                await self.auth_key(auth_key)
                await self.user_id(user_id)
                await self.is_bot(is_bot)
                await self.date(0)

            return

        path = self.database
        file_exists = isinstance(path, Path) and path.is_file()

        self.conn = await aiosqlite.connect(str(path), timeout=1, check_same_thread=False)

        if self.use_wal:
            await self.conn.execute("PRAGMA journal_mode=WAL")
        else:
            await self.conn.execute("PRAGMA journal_mode=DELETE")

        if file_exists:
            await self.update()
        else:
            await self.create()

        await self.conn.execute("VACUUM")
        await self.conn.commit()

    async def save(self):
        await self.date(int(time.time()))
        await self.conn.commit()

    async def close(self):
        await self.conn.close()

    async def delete(self):
        if not self.in_memory:
            Path(self.database).unlink()

    async def update_peers(self, peers: List[Tuple[int, int, str, str]]):
        await self.conn.executemany(
            "REPLACE INTO peers (id, access_hash, type, phone_number) VALUES (?, ?, ?, ?)", peers
        )

    async def update_usernames(self, usernames: List[Tuple[int, List[str]]]):
        await self.conn.executemany("DELETE FROM usernames WHERE id = ?", [(id,) for id, _ in usernames])

        await self.conn.executemany(
            "REPLACE INTO usernames (id, username) VALUES (?, ?)",
            [(id, username) for id, usernames in usernames for username in usernames],
        )

    async def update_state(self, value: Tuple[int, int, int, int, int] = object):
        if value is object:
            r = await self.conn.execute(
                "SELECT id, pts, qts, date, seq FROM update_state ORDER BY date ASC"
            )

            return await r.fetchall()
        else:
            if isinstance(value, int):
                await self.conn.execute("DELETE FROM update_state WHERE id = ?", (value,))
            else:
                await self.conn.execute(
                    "REPLACE INTO update_state (id, pts, qts, date, seq) VALUES (?, ?, ?, ?, ?)",
                    value,
                )

    async def get_peer_by_id(self, peer_id: int):
        r = await (await self.conn.execute(
            "SELECT id, access_hash, type FROM peers WHERE id = ?",
            (peer_id,)
        )).fetchone()

        if r is None:
            raise KeyError(f"ID not found: {peer_id}")

        return get_input_peer(*r)

    async def get_peer_by_username(self, username: str):
        r = await (await self.conn.execute(
            "SELECT p.id, p.access_hash, p.type, p.last_update_on FROM peers p "
            "JOIN usernames u ON p.id = u.id "
            "WHERE u.username = ? "
            "ORDER BY p.last_update_on DESC",
            (username,)
        )).fetchone()

        if r is None:
            raise KeyError(f"Username not found: {username}")

        if abs(time.time() - r[3]) > self.USERNAME_TTL:
            raise KeyError(f"Username expired: {username}")

        return get_input_peer(*r[:3])

    async def get_peer_by_phone_number(self, phone_number: str):
        r = await (await self.conn.execute(
            "SELECT id, access_hash, type FROM peers WHERE phone_number = ?",
            (phone_number,)
        )).fetchone()

        if r is None:
            raise KeyError(f"Phone number not found: {phone_number}")

        return get_input_peer(*r)

    async def _get(self, table: str, attr: str):
        r = await self.conn.execute(f"SELECT {attr} FROM {table}")

        return (await r.fetchone())[0]

    async def _set(self, table: str, attr: str, value: Any):
        await self.conn.execute(f"UPDATE {table} SET {attr} = ?", (value,))
        await self.conn.commit()

    async def _accessor(self, table: str, attr: str, value: Any = object):
        return await self._get(table, attr) if value is object else await self._set(table, attr, value)

    async def dc_id(self, value: int = object):
        return await self._accessor("sessions", "dc_id", value)

    async def server_address(self, value: str = object):
        return await self._accessor("sessions", "server_address", value)

    async def port(self, value: int = object):
        return await self._accessor("sessions", "port", value)

    async def api_id(self, value: int = object):
        return await self._accessor("sessions", "api_id", value)

    async def test_mode(self, value: bool = object):
        return await self._accessor("sessions", "test_mode", value)

    async def auth_key(self, value: bytes = object):
        if value is object:
            r = await self._accessor("sessions", "auth_key", value)
            return self.fernet.decrypt(r) if r else None
        else:
            return await self._accessor("sessions", "auth_key", self.fernet.encrypt(value))

    async def date(self, value: int = object):
        return await self._accessor("sessions", "date", value)

    async def user_id(self, value: int = object):
        return await self._accessor("sessions", "user_id", value)

    async def is_bot(self, value: bool = object):
        return await self._accessor("sessions", "is_bot", value)

    async def version(self, value: int = object):
        return await self._accessor("version", "number", value)
