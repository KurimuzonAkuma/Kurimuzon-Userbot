import inspect
import logging
import os
import sqlite3
import time
from typing import Any, List, Tuple

from pyrogram import Client, raw, utils
from pyrogram.storage import Storage

log = logging.getLogger(__name__)

# language=SQLite
TELETHON_SCHEMA = """
CREATE TABLE sessions
(
    dc_id           INTEGER PRIMARY KEY,
    server_address  TEXT,
    port            INTEGER,
    auth_key        BLOB,
    takeout_id      INTEGER
);

CREATE TABLE entities
(
    id             INTEGER PRIMARY KEY,
    hash           INTEGER NOT NULL,
    username       TEXT,
    phone          INTEGER,
    name           TEXT,
    date           INTEGER
);

CREATE TABLE sent_files
(
    md5_digest  BLOB,
    file_size   INTEGER,
    type        INTEGER,
    id          INTEGER,
    hash        INTEGER,
    PRIMARY KEY(md5_digest, file_size, type)
);

CREATE TABLE update_state
(
    id      INTEGER PRIMARY KEY,
    pts     INTEGER,
    qts     INTEGER,
    date    INTEGER,
    seq     INTEGER
);

CREATE TABLE version
(
    version INTEGER PRIMARY KEY
);
"""

# language=SQLite
PYROGRAM_SCHEMA = """
CREATE TABLE sessions
(
    dc_id     INTEGER PRIMARY KEY,
    api_id    INTEGER,
    test_mode INTEGER,
    auth_key  BLOB,
    date      INTEGER NOT NULL,
    user_id   INTEGER,
    is_bot    INTEGER
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

CREATE TABLE version
(
    number INTEGER PRIMARY KEY
);

CREATE INDEX idx_peers_id ON peers (id);
CREATE INDEX idx_peers_phone_number ON peers (phone_number);
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


def telethon_get_input_peer(peer_id: int, access_hash: int):
    if peer_id >= 0:
        return raw.types.InputPeerUser(user_id=peer_id, access_hash=access_hash)

    if peer_id <= -1000000000000:
        return raw.types.InputPeerChannel(
            channel_id=utils.get_channel_id(peer_id), access_hash=access_hash
        )

    if peer_id < 0:
        return raw.types.InputPeerChat(chat_id=-peer_id)

    raise ValueError("Invalid peer type")


def pyrogram_get_input_peer(peer_id: int, access_hash: int, peer_type: str):
    if peer_type in ["user", "bot"]:
        return raw.types.InputPeerUser(user_id=peer_id, access_hash=access_hash)

    if peer_type == "group":
        return raw.types.InputPeerChat(chat_id=-peer_id)

    if peer_type in ["channel", "supergroup"]:
        return raw.types.InputPeerChannel(
            channel_id=utils.get_channel_id(peer_id), access_hash=access_hash
        )

    raise ValueError(f"Invalid peer type: {peer_type}")


class AnyStorage(Storage):
    FILE_EXTENSION = ".session"
    VERSION = 4
    USERNAME_TTL = 8 * 60 * 60

    def __init__(self, *, client: Client, is_bot: bool = False):
        super().__init__(client.name)

        self._api_id = client.api_id
        self._test_mode = client.test_mode
        self._is_bot = is_bot

        self.conn = None  # type: sqlite3.Connection
        self.is_telethon = None

        self.database = client.workdir / (client.name + self.FILE_EXTENSION)

    def create(self):
        with self.conn:
            self.conn.executescript(PYROGRAM_SCHEMA)

            self.conn.execute("INSERT INTO version VALUES (?)", (self.VERSION,))

            self.conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (2, None, None, None, 0, None, None),
            )

    def update(self):
        try:
            with self.conn:
                self.conn.execute("SELECT version FROM version")
            self.is_telethon = True
            return
        except sqlite3.OperationalError as e:
            if str(e).startswith("no such table"):
                self.is_telethon = False

        version = self.version()

        if version == 1:
            with self.conn:
                self.conn.execute("DELETE FROM peers")

            version += 1

        if version == 2:
            with self.conn:
                self.conn.execute("ALTER TABLE sessions ADD api_id INTEGER")

            version += 1

        if version == 3:
            with self.conn:
                self.conn.executescript(PYROGRAM_SCHEMA)

            version += 1

        self.version(version)

    async def open(self):
        path = self.database
        file_exists = path.is_file()

        self.conn = sqlite3.connect(str(path), timeout=1, check_same_thread=False)

        if not file_exists:
            self.create()
        else:
            self.update()

        with self.conn:
            self.conn.execute("VACUUM")

    async def save(self):
        await self.date(int(time.time()))
        self.conn.commit()

    async def close(self):
        self.conn.close()

    async def delete(self):
        os.remove(self.database)

    async def update_peers(self, peers: List[Tuple[int, int, str, List[str], str]]):
        values = []

        if self.is_telethon:
            for peer_data in peers:
                id, hash, type, usernames, phone = peer_data
                values.append(
                    (id, hash, usernames[0] if usernames else None, phone, None, int(time.time()))
                )

            self.conn.executemany(
                "REPLACE INTO entities (id, hash, username, phone, name, date)"
                "VALUES (?, ?, ?, ?, ?, ?)",
                values,
            )
        else:
            for peer_data in peers:
                id, access_hash, type, usernames, phone_number = peer_data

                self.conn.execute(
                    "REPLACE INTO peers (id, access_hash, type, phone_number)"
                    "VALUES (?, ?, ?, ?)",
                    (id, access_hash, type, phone_number),
                )

                self.conn.execute("DELETE FROM usernames WHERE id = ?", (id,))

                self.conn.executemany(
                    "REPLACE INTO usernames (id, username) VALUES (?, ?)",
                    [(id, username) for username in usernames] if usernames else [(id, None)],
                )

    async def get_peer_by_id(self, peer_id: int):
        if self.is_telethon:
            r = self.conn.execute(
                "SELECT id, hash FROM entities WHERE id = ?", (peer_id,)
            ).fetchone()
        else:
            r = self.conn.execute(
                "SELECT id, access_hash, type FROM peers WHERE id = ?", (peer_id,)
            ).fetchone()

        if r is None:
            raise KeyError(f"ID not found: {peer_id}")

        return telethon_get_input_peer(*r) if self.is_telethon else pyrogram_get_input_peer(*r)

    async def get_peer_by_username(self, username: str):
        if self.is_telethon:
            r = self.conn.execute(
                "SELECT id, hash, date FROM entities WHERE username = ?" "ORDER BY date DESC",
                (username,),
            ).fetchone()

            if r is None:
                raise KeyError(f"Username not found: {username}")

            if abs(time.time() - r[2]) > self.USERNAME_TTL:
                raise KeyError(f"Username expired: {username}")
        else:
            r = self.conn.execute(
                "SELECT p.id, p.access_hash, p.type, p.last_update_on FROM peers p "
                "JOIN usernames u ON p.id = u.id "
                "WHERE u.username = ? "
                "ORDER BY p.last_update_on DESC",
                (username,),
            ).fetchone()

            if r is None:
                raise KeyError(f"Username not found: {username}")

            if abs(time.time() - r[3]) > self.USERNAME_TTL:
                raise KeyError(f"Username expired: {username}")

        return (
            telethon_get_input_peer(*r[:2])
            if self.is_telethon
            else pyrogram_get_input_peer(*r[:3])
        )

    async def get_peer_by_phone_number(self, phone_number: str):
        if self.is_telethon:
            r = self.conn.execute(
                "SELECT id, hash FROM entities WHERE phone = ?", (phone_number,)
            ).fetchone()
        else:
            r = self.conn.execute(
                "SELECT id, access_hash, type FROM peers WHERE phone_number = ?", (phone_number,)
            ).fetchone()

        if r is None:
            raise KeyError(f"Phone number not found: {phone_number}")

        return telethon_get_input_peer(*r) if self.is_telethon else pyrogram_get_input_peer(*r)

    def _get(self):
        attr = inspect.stack()[2].function

        return self.conn.execute(f"SELECT {attr} FROM sessions").fetchone()[0]

    def _set(self, value: Any):
        attr = inspect.stack()[2].function

        with self.conn:
            self.conn.execute(f"UPDATE sessions SET {attr} = ?", (value,))

    def _accessor(self, value: Any = object):
        return self._get() if value == object else self._set(value)

    async def dc_id(self, value: int = object):
        return self._accessor(value)

    async def api_id(self, value: int = object):
        if self.is_telethon:
            if value != object:
                self._api_id = value

            return self._api_id
        else:
            return self._accessor(value)

    async def test_mode(self, value: bool = object):
        if self.is_telethon:
            if value != object:
                self._test_mode = value

            return self._test_mode
        else:
            return self._accessor(value)

    async def auth_key(self, value: bytes = object):
        return self._accessor(value)

    async def date(self, value: int = object):
        if self.is_telethon:
            if value == object:
                cur = self.conn.execute("SELECT date FROM entities WHERE id=0")

                res = cur.fetchone()

                return None if res is None else res[0]
            else:
                with self.conn:
                    self.conn.execute("UPDATE entities SET date = ? WHERE id=0", (value,))
        else:
            return self._accessor(value)

    async def user_id(self, value: int = object):
        if self.is_telethon:
            if value == object:
                cur = self.conn.execute("SELECT hash FROM entities WHERE id=0")

                res = cur.fetchone()

                if await self.auth_key() and res is None:
                    return 1

                return res[0]
            else:
                if value is None:
                    return

                with self.conn:
                    self.conn.execute(
                        "REPLACE INTO entities VALUES (?, ?, ?, ?, ?, ?)",
                        (0, value, None, None, None, int(time.time())),
                    )
        else:
            return self._accessor(value)

    async def is_bot(self, value: bool = object):
        if self.is_telethon:
            if value != object:
                self._is_bot = value

            return self._is_bot
        else:
            return self._accessor(value)

    def version(self, value: int = object):
        if self.is_telethon:
            if value == object:
                return self.conn.execute("SELECT version FROM version").fetchone()[0]
            else:
                with self.conn:
                    self.conn.execute("UPDATE version SET version = ?", (value,))
        else:
            if value == object:
                return self.conn.execute("SELECT number FROM version").fetchone()[0]
            else:
                with self.conn:
                    self.conn.execute("UPDATE version SET number = ?", (value,))
