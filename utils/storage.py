import inspect
import os
import sqlite3
import time
from typing import Any, List, Tuple

from cryptography.fernet import Fernet
from pyrogram import Client, raw, utils
from pyrogram.storage import Storage

SCHEMA = """
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
    access_hash    BLOB,
    type           INTEGER NOT NULL,
    phone_number   BLOB,
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


def get_input_peer(peer_id: int, access_hash: int, peer_type: str):
    if peer_type in ["user", "bot"]:
        return raw.types.InputPeerUser(user_id=peer_id, access_hash=access_hash)

    if peer_type == "group":
        return raw.types.InputPeerChat(chat_id=-peer_id)

    if peer_type in ["channel", "supergroup"]:
        return raw.types.InputPeerChannel(
            channel_id=utils.get_channel_id(peer_id), access_hash=access_hash
        )

    raise ValueError(f"Invalid peer type: {peer_type}")


class FernetStorage(Storage):
    FILE_EXTENSION = ".session"
    VERSION = 6
    USERNAME_TTL = 8 * 60 * 60

    def __init__(self, client: Client, key: bytes):
        super().__init__(client.name)

        self.conn = None  # type: sqlite3.Connection
        self.fernet = Fernet(key)

        self.database = client.workdir / (client.name + self.FILE_EXTENSION)

    def update(self):
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
                self.conn.executescript(USERNAMES_SCHEMA)

            version += 1

        if version == 4:
            with self.conn:
                self.conn.executescript(UPDATE_STATE_SCHEMA)

            version += 1

        if version == 5:
            with self.conn:
                self.conn.execute("CREATE INDEX idx_usernames_id ON usernames (id);")

            version += 1

        self.version(version)

    def create(self):
        with self.conn:
            self.conn.executescript(SCHEMA)

            self.conn.execute("INSERT INTO version VALUES (?)", (self.VERSION,))

            self.conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (2, None, None, None, 0, None, None),
            )

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

    async def update_peers(self, peers: List[Tuple[int, int, str, str]]):
        self.conn.executemany(
            "REPLACE INTO peers (id, access_hash, type, phone_number) VALUES (?, ?, ?, ?)",
            peers,
        )

    async def update_usernames(self, usernames: List[Tuple[int, List[str]]]):
        self.conn.executemany("DELETE FROM usernames WHERE id = ?", [(id,) for id, _ in usernames])

        self.conn.executemany(
            "REPLACE INTO usernames (id, username) VALUES (?, ?)",
            [(id, username) for id, usernames in usernames for username in usernames],
        )

    async def update_state(self, value: Tuple[int, int, int, int, int] = object):
        if value is object:
            return self.conn.execute(
                "SELECT id, pts, qts, date, seq FROM update_state ORDER BY date ASC"
            ).fetchall()
        else:
            with self.conn:
                if isinstance(value, int):
                    self.conn.execute("DELETE FROM update_state WHERE id = ?", (value,))
                else:
                    self.conn.execute(
                        "REPLACE INTO update_state (id, pts, qts, date, seq) "
                        "VALUES (?, ?, ?, ?, ?)",
                        value,
                    )

    async def get_peer_by_id(self, peer_id: int):
        r = self.conn.execute(
            "SELECT id, access_hash, type FROM peers WHERE id = ?", (peer_id,)
        ).fetchone()

        if r is None:
            raise KeyError(f"ID not found: {peer_id}")

        return get_input_peer(*r)

    async def get_peer_by_username(self, username: str):
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

        return get_input_peer(*r[:3])

    async def get_peer_by_phone_number(self, phone_number: str):
        r = self.conn.execute(
            "SELECT id, access_hash, type FROM peers WHERE phone_number = ?",
            (phone_number,),
        ).fetchone()

        if r is None:
            raise KeyError(f"Phone number not found: {phone_number}")

        return get_input_peer(*r)

    def _get(self):
        attr = inspect.stack()[2].function
        return self.conn.execute(f"SELECT {attr} FROM sessions").fetchone()[0]

    def _set(self, value: Any):
        attr = inspect.stack()[2].function

        with self.conn:
            self.conn.execute(f"UPDATE sessions SET {attr} = ?", (value,))

    def _accessor(self, value: Any = object):
        return self._get() if value is object else self._set(value)

    async def dc_id(self, value: int = object):
        return self._accessor(value)

    async def api_id(self, value: int = object):
        return self._accessor(value)

    async def test_mode(self, value: bool = object):
        return self._accessor(value)

    async def auth_key(self, value: bytes = object):
        if value is object:
            r = self.conn.execute("SELECT auth_key FROM sessions").fetchone()[0]

            return self.fernet.decrypt(r) if r else None
        else:
            with self.conn:
                self.conn.execute(
                    "UPDATE sessions SET auth_key = ?", (self.fernet.encrypt(value),)
                )

    async def date(self, value: int = object):
        return self._accessor(value)

    async def user_id(self, value: int = object):
        return self._accessor(value)

    async def is_bot(self, value: bool = object):
        return self._accessor(value)

    def version(self, value: int = object):
        if value is object:
            return self.conn.execute("SELECT number FROM version").fetchone()[0]
        else:
            with self.conn:
                self.conn.execute("UPDATE version SET number = ?", (value,))
