import aiosqlite
import os
import json
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "elementals.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                user_id     INTEGER PRIMARY KEY,
                coins       INTEGER DEFAULT 100,
                last_daily  TEXT,
                last_train  TEXT,
                last_fish   TEXT,
                last_dig    TEXT,
                active_pet  INTEGER DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS pets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id    INTEGER NOT NULL,
                element      TEXT NOT NULL,
                variant      INTEGER NOT NULL,
                stage        INTEGER DEFAULT 0,
                level        INTEGER DEFAULT 1,
                xp           INTEGER DEFAULT 0,
                base_hp      INTEGER DEFAULT 0,
                base_atk     INTEGER DEFAULT 0,
                base_def     INTEGER DEFAULT 0,
                base_spd     INTEGER DEFAULT 0,
                base_mgk     INTEGER DEFAULT 0,
                base_res     INTEGER DEFAULT 0,
                bonus_hp     INTEGER DEFAULT 0,
                bonus_atk    INTEGER DEFAULT 0,
                bonus_def    INTEGER DEFAULT 0,
                bonus_spd    INTEGER DEFAULT 0,
                bonus_mgk    INTEGER DEFAULT 0,
                bonus_res    INTEGER DEFAULT 0,
                exploration  INTEGER DEFAULT 0,
                nickname     TEXT,
                first_fed    INTEGER DEFAULT 0,
                FOREIGN KEY (player_id) REFERENCES players(user_id)
            );

            CREATE TABLE IF NOT EXISTS inventory (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id   INTEGER NOT NULL,
                item_key    TEXT NOT NULL,
                item_type   TEXT NOT NULL,
                quantity    INTEGER DEFAULT 1,
                element     TEXT,
                FOREIGN KEY (player_id) REFERENCES players(user_id)
            );

            CREATE TABLE IF NOT EXISTS expeditions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id        INTEGER NOT NULL,
                player_id     INTEGER NOT NULL,
                start_time    TEXT NOT NULL,
                duration_hrs  INTEGER NOT NULL,
                returned      INTEGER DEFAULT 0,
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            CREATE TABLE IF NOT EXISTS battle_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                challenger_id INTEGER NOT NULL,
                opponent_id   INTEGER NOT NULL,
                winner_id     INTEGER,
                timestamp     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trades (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id       INTEGER NOT NULL,
                receiver_id     INTEGER NOT NULL,
                sender_items    TEXT NOT NULL,
                receiver_items  TEXT NOT NULL,
                status          TEXT DEFAULT 'pending',
                created_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id           INTEGER PRIMARY KEY,
                drops_channel_id   INTEGER,
                announce_channel_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS channel_drops (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                message_id  INTEGER,
                item_key    TEXT NOT NULL,
                item_type   TEXT NOT NULL,
                item_element TEXT,
                claimed_by  INTEGER,
                spawn_time  TEXT NOT NULL,
                expires_at  TEXT NOT NULL
            );
        """)
        await db.commit()

# ── helpers ──────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

async def get_player(db: aiosqlite.Connection, user_id: int) -> dict | None:
    async with db.execute("SELECT * FROM players WHERE user_id=?", (user_id,)) as cur:
        row = await cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    return None

async def ensure_player(db: aiosqlite.Connection, user_id: int) -> dict:
    p = await get_player(db, user_id)
    if p is None:
        await db.execute(
            "INSERT INTO players(user_id, coins) VALUES(?,100)", (user_id,)
        )
        await db.commit()
        p = await get_player(db, user_id)
    return p

async def get_pet(db: aiosqlite.Connection, pet_id: int) -> dict | None:
    async with db.execute("SELECT * FROM pets WHERE id=?", (pet_id,)) as cur:
        row = await cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    return None

async def get_active_pet(db: aiosqlite.Connection, user_id: int) -> dict | None:
    p = await get_player(db, user_id)
    if not p or not p["active_pet"]:
        return None
    return await get_pet(db, p["active_pet"])

async def get_player_pets(db: aiosqlite.Connection, user_id: int) -> list[dict]:
    async with db.execute(
        "SELECT * FROM pets WHERE player_id=? ORDER BY id", (user_id,)
    ) as cur:
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

async def add_item(db: aiosqlite.Connection, player_id: int, item_key: str,
                   item_type: str, quantity: int = 1, element: str = None):
    async with db.execute(
        "SELECT id, quantity FROM inventory WHERE player_id=? AND item_key=? AND (element=? OR (element IS NULL AND ? IS NULL))",
        (player_id, item_key, element, element)
    ) as cur:
        row = await cur.fetchone()
    if row:
        await db.execute(
            "UPDATE inventory SET quantity=quantity+? WHERE id=?", (quantity, row[0])
        )
    else:
        await db.execute(
            "INSERT INTO inventory(player_id,item_key,item_type,quantity,element) VALUES(?,?,?,?,?)",
            (player_id, item_key, item_type, quantity, element)
        )

async def remove_item(db: aiosqlite.Connection, player_id: int, item_key: str,
                      quantity: int = 1, element: str = None) -> bool:
    async with db.execute(
        "SELECT id, quantity FROM inventory WHERE player_id=? AND item_key=? AND (element=? OR (element IS NULL AND ? IS NULL))",
        (player_id, item_key, element, element)
    ) as cur:
        row = await cur.fetchone()
    if not row or row[1] < quantity:
        return False
    if row[1] == quantity:
        await db.execute("DELETE FROM inventory WHERE id=?", (row[0],))
    else:
        await db.execute("UPDATE inventory SET quantity=quantity-? WHERE id=?", (quantity, row[0]))
    return True

async def get_inventory(db: aiosqlite.Connection, player_id: int) -> list[dict]:
    async with db.execute(
        "SELECT * FROM inventory WHERE player_id=? ORDER BY item_type, item_key", (player_id,)
    ) as cur:
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

async def has_item(db: aiosqlite.Connection, player_id: int, item_key: str,
                   qty: int = 1, element: str = None) -> bool:
    async with db.execute(
        "SELECT quantity FROM inventory WHERE player_id=? AND item_key=? AND (element=? OR (element IS NULL AND ? IS NULL))",
        (player_id, item_key, element, element)
    ) as cur:
        row = await cur.fetchone()
    return row is not None and row[0] >= qty

async def add_xp(db: aiosqlite.Connection, pet_id: int, amount: int) -> dict:
    """Add XP to a pet, handle level-ups, return updated pet dict."""
    from config import xp_for_next_level
    pet = await get_pet(db, pet_id)
    if not pet or pet["stage"] == 0:
        return pet
    xp = pet["xp"] + amount
    level = pet["level"]
    leveled_up = False
    while level < 100:
        needed = xp_for_next_level(level)
        if xp >= needed:
            xp -= needed
            level += 1
            leveled_up = True
        else:
            break
    await db.execute(
        "UPDATE pets SET xp=?, level=? WHERE id=?", (xp, level, pet_id)
    )
    pet["xp"] = xp
    pet["level"] = level
    pet["leveled_up"] = leveled_up
    return pet

async def get_guild_config(db: aiosqlite.Connection, guild_id: int) -> dict | None:
    async with db.execute("SELECT * FROM guild_config WHERE guild_id=?", (guild_id,)) as cur:
        row = await cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    return None

async def set_guild_config(db: aiosqlite.Connection, guild_id: int, **kwargs):
    cfg = await get_guild_config(db, guild_id)
    if cfg is None:
        await db.execute(
            "INSERT INTO guild_config(guild_id) VALUES(?)", (guild_id,)
        )
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [guild_id]
    await db.execute(f"UPDATE guild_config SET {sets} WHERE guild_id=?", vals)
    await db.commit()

async def get_active_expedition(db: aiosqlite.Connection, player_id: int) -> dict | None:
    async with db.execute(
        "SELECT * FROM expeditions WHERE player_id=? AND returned=0", (player_id,)
    ) as cur:
        row = await cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    return None

async def connect() -> aiosqlite.Connection:
    return await aiosqlite.connect(DB_PATH)
