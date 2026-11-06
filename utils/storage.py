import base64
import logging
import secrets
import struct
import time
from pathlib import Path
from typing import Any
from collections.abc import Iterable

import aiosqlite
from Cryptodome.Cipher import AES
from Cryptodome.Hash import SHA512
from Cryptodome.Protocol.KDF import PBKDF2
from pyrogram import Client, raw, utils
from pyrogram.storage import Storage, UpdateState

log = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 1_000_000

SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32


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

TEST = {1: "149.154.175.10", 2: "149.154.167.40", 3: "149.154.175.117"}

PROD = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
    203: "91.105.192.100",
}


def get_input_peer(peer_id: int, access_hash: int):
    peer_type = utils.get_peer_type(peer_id)

    if peer_type == "user":
        return raw.types.InputPeerUser(user_id=peer_id, access_hash=access_hash)

    if peer_type == "chat":
        return raw.types.InputPeerChat(chat_id=-peer_id)

    if peer_type in {"channel", "monoforum"}:
        return raw.types.InputPeerChannel(
            channel_id=utils.get_channel_id(peer_id), access_hash=access_hash
        )

    raise ValueError(f"Peer id invalid: {peer_id}")


def _derive_key(password: str, salt: bytes) -> bytes:
    return PBKDF2(
        password.encode("utf-8"),
        salt,
        dkLen=KEY_SIZE,
        count=PBKDF2_ITERATIONS,
        hmac_hash_module=SHA512,
    )


def encrypt(data: bytes, password: str) -> bytes:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")

    salt = secrets.token_bytes(SALT_SIZE)
    nonce = secrets.token_bytes(NONCE_SIZE)

    key = _derive_key(password, salt)
    ciphertext, tag = AES.new(key, AES.MODE_GCM, nonce=nonce).encrypt_and_digest(data)

    return salt + nonce + tag + ciphertext


def decrypt(data: bytes, password: str) -> bytes:
    minimum_size = SALT_SIZE + NONCE_SIZE + TAG_SIZE

    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError(
            f"Invalid auth_key storage type: {type(data).__name__} "
            "(session is not encrypted or is corrupted; delete the .session file and re-login)"
        )

    data = bytes(data)

    if len(data) < minimum_size:
        raise ValueError("Invalid encrypted auth_key")

    salt = data[:SALT_SIZE]
    nonce = data[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    tag = data[SALT_SIZE + NONCE_SIZE : SALT_SIZE + NONCE_SIZE + TAG_SIZE]
    ciphertext = data[SALT_SIZE + NONCE_SIZE + TAG_SIZE :]

    key = _derive_key(password, salt)

    try:
        return AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ciphertext, tag)
    except ValueError as e:
        raise ValueError("Invalid password or corrupted auth_key") from e


class EncryptedStorage(Storage):
    VERSION = 8
    USERNAME_TTL = 8 * 60 * 60
    FILE_EXTENSION = ".session"

    def __init__(
        self,
        client: Client,
        password: str,
        use_wal: bool | None = False,
    ):
        self.conn = None  # type: aiosqlite.Connection
        self.password = password

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

        elif version == 2:
            await self.conn.execute("ALTER TABLE sessions ADD api_id INTEGER;")

            version += 1

        elif version == 3:
            await self.conn.executescript(USERNAMES_SCHEMA)

            version += 1

        elif version == 4:
            await self.conn.executescript(UPDATE_STATE_SCHEMA)

            version += 1

        elif version == 5:
            await self.conn.execute("CREATE INDEX idx_usernames_id ON usernames (id);")

            version += 1

        elif version == 6:
            if await self.test_mode():
                address = TEST[await self.dc_id()]
                port = 80
            else:
                address = PROD[await self.dc_id()]
                port = 443

            await self.conn.execute("ALTER TABLE sessions ADD server_address TEXT;")
            await self.conn.execute("ALTER TABLE sessions ADD port INTEGER;")

            await self.conn.execute("UPDATE sessions SET server_address = ?;", (address,))
            await self.conn.execute("UPDATE sessions SET port = ?;", (port,))

            version += 1

        elif version == 7:
            await self.conn.execute("ALTER TABLE peers DROP COLUMN type;")

            version += 1

        await self.version(version)

        await self.save()

    async def create(self):
        await self.conn.executescript(SCHEMA)

        await self.conn.execute("INSERT INTO version VALUES (?)", (self.VERSION,))

        await self.conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2, "149.154.167.51", 443, None, None, None, 0, None, None),
        )

        await self.save()

    async def open(self):
        if self.in_memory:
            self.conn = await aiosqlite.connect(":memory:", timeout=1, check_same_thread=False)
            await self.create()

            if self.session_string:
                dc_id, api_id, test_mode, auth_key, user_id, is_bot = struct.unpack(
                    self.SESSION_STRING_FORMAT,
                    base64.urlsafe_b64decode(
                        self.session_string + "=" * (-len(self.session_string) % 4)
                    ),
                )

                if test_mode:
                    await self.server_address(TEST[dc_id])
                    await self.port(80)
                else:
                    await self.server_address(PROD[dc_id])
                    await self.port(443)

                await self.dc_id(dc_id)
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
            await self.conn.execute("PRAGMA synchronous=NORMAL")
        else:
            await self.conn.execute("PRAGMA journal_mode=DELETE")

        await self.conn.execute("PRAGMA temp_store=MEMORY")
        await self.conn.execute("PRAGMA cache_size=-8000")

        if file_exists:
            await self.update()
        else:
            await self.create()

    async def save(self):
        await self.conn.execute(
            "UPDATE sessions SET date = ?",
            (int(time.time()),),
        )
        await self.conn.commit()

    async def close(self):
        await self.save()
        await self.conn.execute("VACUUM")
        await self.conn.close()
        self.conn = None

    async def delete(self):
        if self.in_memory:
            return

        if self.conn is not None:
            await self.close()

        for suffix in ("", "-shm", "-wal"):
            Path(str(self.database) + suffix).unlink(missing_ok=True)

    async def update_peers(self, peers: list[tuple[int, int, str, str]]):
        peers = [(peer_id, access_hash, phone) for peer_id, access_hash, _, phone in peers]

        await self.conn.executemany(
            "REPLACE INTO peers (id, access_hash, phone_number) VALUES (?, ?, ?)", peers
        )

    async def update_usernames(self, usernames: Iterable[tuple[int, list[str | None]]]):
        usernames = list(usernames)

        if not usernames:
            return

        ids = [id_ for id_, _ in usernames]
        placeholders = ", ".join("?" for _ in ids)

        await self.conn.execute(
            f"DELETE FROM usernames WHERE id IN ({placeholders})",
            ids,
        )

        await self.conn.executemany(
            "REPLACE INTO usernames (id, username) VALUES (?, ?)",
            [
                (id_, username)
                for id_, names in usernames
                for username in names
                if username is not None
            ],
        )

    async def get_update_states(self, ids: int | Iterable[int] | None = None):
        query = "SELECT id, pts, qts, date, seq FROM update_state"

        if ids is not None:
            state_ids = (ids,) if isinstance(ids, int) else tuple(ids)

            if not state_ids:
                return []

            placeholders = ", ".join("?" for _ in state_ids)
            query += f" WHERE id IN ({placeholders})"
        else:
            state_ids = ()

        r = await self.conn.execute(query + " ORDER BY date ASC", state_ids)
        rows = await r.fetchall()
        return [UpdateState(*row) for row in rows]

    async def set_update_state(self, update_state: UpdateState | Iterable[UpdateState]):
        states = [update_state] if isinstance(update_state, UpdateState) else update_state

        await self.conn.executemany(
            "INSERT INTO update_state (id, pts, qts, date, seq) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "pts = COALESCE(excluded.pts, update_state.pts), "
            "qts = COALESCE(excluded.qts, update_state.qts), "
            "date = COALESCE(excluded.date, update_state.date), "
            "seq = COALESCE(excluded.seq, update_state.seq)",
            [(state.id, state.pts, state.qts, state.date, state.seq) for state in states],
        )

    async def delete_update_state(self, state_id):
        if isinstance(state_id, int):
            await self.conn.execute(
                "DELETE FROM update_state WHERE id = ?",
                (state_id,),
            )
            return

        state_ids = tuple(state_id)

        if not state_ids:
            return

        placeholders = ", ".join("?" for _ in state_ids)

        await self.conn.execute(
            f"DELETE FROM update_state WHERE id IN ({placeholders})",
            state_ids,
        )

    async def get_peer_by_id(self, peer_id: int):
        r = await (
            await self.conn.execute("SELECT id, access_hash FROM peers WHERE id = ?", (peer_id,))
        ).fetchone()

        if r is None:
            raise KeyError(f"ID not found: {peer_id}")

        return get_input_peer(*r)

    async def get_peer_by_username(self, username: str):
        r = await (
            await self.conn.execute(
                "SELECT p.id, p.access_hash, p.last_update_on FROM peers p "
                "JOIN usernames u ON p.id = u.id "
                "WHERE u.username = ? "
                "ORDER BY p.last_update_on DESC "
                "LIMIT 1",
                (username,),
            )
        ).fetchone()

        if r is None:
            raise KeyError(f"Username not found: {username}")

        if abs(time.time() - r[2]) > self.USERNAME_TTL:
            raise KeyError(f"Username expired: {username}")

        return get_input_peer(*r[:2])

    async def get_peer_by_phone_number(self, phone_number: str):
        r = await (
            await self.conn.execute(
                "SELECT id, access_hash FROM peers WHERE phone_number = ?",
                (phone_number,),
            )
        ).fetchone()

        if r is None:
            raise KeyError(f"Phone number not found: {phone_number}")

        return get_input_peer(*r)

    async def _get(self, table: str, attr: str):
        r = await self.conn.execute(f"SELECT {attr} FROM {table}")

        return (await r.fetchone())[0]

    async def _set(self, table: str, attr: str, value: Any):
        await self.conn.execute(f"UPDATE {table} SET {attr} = ?", (value,))
        await self.save()

    async def _accessor(self, table: str, attr: str, value: Any = object):
        return (
            await self._get(table, attr) if value is object else await self._set(table, attr, value)
        )

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
            return decrypt(r, self.password) if r else None
        else:
            return await self._accessor("sessions", "auth_key", encrypt(value, self.password))

    async def date(self, value: int = object):
        return await self._accessor("sessions", "date", value)

    async def user_id(self, value: int = object):
        return await self._accessor("sessions", "user_id", value)

    async def is_bot(self, value: bool = object):
        return await self._accessor("sessions", "is_bot", value)

    async def version(self, value: int = object):
        return await self._accessor("version", "number", value)
