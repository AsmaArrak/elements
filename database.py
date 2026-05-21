import aiosqlite
import os
import json
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "elementals.db"))

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
        # Migrations
        # Pet learned skills
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pet_skills (
                pet_id    INTEGER NOT NULL,
                skill_key TEXT NOT NULL,
                PRIMARY KEY (pet_id, skill_key)
            )
        """)
        await db.commit()
        # Armor table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS armor_inventory (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id  INTEGER NOT NULL,
                name       TEXT NOT NULL,
                rarity     TEXT NOT NULL,
                bonus_hp   INTEGER DEFAULT 0,
                bonus_atk  INTEGER DEFAULT 0,
                bonus_def  INTEGER DEFAULT 0,
                bonus_spd  INTEGER DEFAULT 0,
                bonus_mgk  INTEGER DEFAULT 0,
                bonus_res  INTEGER DEFAULT 0,
                FOREIGN KEY (player_id) REFERENCES players(user_id)
            )
        """)
        await db.commit()
        # Column migrations
        for col_sql in [
            "ALTER TABLE players ADD COLUMN last_trivia TEXT",
            "ALTER TABLE pets ADD COLUMN equipped_armor INTEGER DEFAULT NULL",
            # 4 dedicated armor slots (one per piece type)
            "ALTER TABLE pets ADD COLUMN slot_crown     INTEGER DEFAULT NULL",
            "ALTER TABLE pets ADD COLUMN slot_plate     INTEGER DEFAULT NULL",
            "ALTER TABLE pets ADD COLUMN slot_gauntlets INTEGER DEFAULT NULL",
            "ALTER TABLE pets ADD COLUMN slot_greaves   INTEGER DEFAULT NULL",
        ]:
            try:
                await db.execute(col_sql)
                await db.commit()
            except Exception:
                pass
        # Migration: add party_slot column if it doesn't exist yet
        try:
            await db.execute("ALTER TABLE pets ADD COLUMN party_slot INTEGER DEFAULT NULL")
            await db.commit()
        except Exception:
            pass
        # Pity table: tracks last variant received per element per player
        await db.execute("""
            CREATE TABLE IF NOT EXISTS element_pity (
                player_id    INTEGER NOT NULL,
                element      TEXT NOT NULL,
                last_variant INTEGER NOT NULL,
                PRIMARY KEY (player_id, element)
            )
        """)
        await db.commit()
        # Migration: add qty column to channel_drops for coins
        try:
            await db.execute("ALTER TABLE channel_drops ADD COLUMN qty INTEGER DEFAULT 1")
            await db.commit()
        except Exception:
            pass
        # Migration: player level, XP, moon shards
        for col_sql in [
            "ALTER TABLE players ADD COLUMN player_level INTEGER DEFAULT 1",
            "ALTER TABLE players ADD COLUMN player_xp    INTEGER DEFAULT 0",
            "ALTER TABLE players ADD COLUMN moon_shards  INTEGER DEFAULT 60",
            "ALTER TABLE players ADD COLUMN last_shard_time TEXT",
        ]:
            try:
                await db.execute(col_sql)
                await db.commit()
            except Exception:
                pass
        # Boss battle tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS boss_battles (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                boss_name    TEXT NOT NULL,
                boss_element TEXT NOT NULL,
                spawn_time   TEXT NOT NULL,
                end_time     TEXT NOT NULL,
                active       INTEGER DEFAULT 1,
                total_damage INTEGER DEFAULT 0,
                rewards_given INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS boss_damage_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                boss_id   INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                damage    INTEGER DEFAULT 0,
                UNIQUE(boss_id, player_id),
                FOREIGN KEY (boss_id) REFERENCES boss_battles(id)
            )
        """)
        await db.commit()
        # Migration: boss channel per guild
        try:
            await db.execute("ALTER TABLE guild_config ADD COLUMN boss_channel_id INTEGER")
            await db.commit()
        except Exception:
            pass
        # Migration: armor upgrade columns
        for col_sql in [
            "ALTER TABLE armor_inventory ADD COLUMN armor_level INTEGER DEFAULT 1",
            "ALTER TABLE armor_inventory ADD COLUMN armor_xp    INTEGER DEFAULT 0",
            "ALTER TABLE armor_inventory ADD COLUMN set_name    TEXT",
            "ALTER TABLE armor_inventory ADD COLUMN piece_type  TEXT",
            "ALTER TABLE armor_inventory ADD COLUMN sub_stats   TEXT DEFAULT '[]'",
        ]:
            try:
                await db.execute(col_sql)
                await db.commit()
            except Exception:
                pass

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

# Mapping from piece_type name → pets table column
ARMOR_SLOT_COLS = {
    "Crown":     "slot_crown",
    "Plate":     "slot_plate",
    "Gauntlets": "slot_gauntlets",
    "Greaves":   "slot_greaves",
}

async def apply_armor_to_pet(db: aiosqlite.Connection, pet: dict) -> dict:
    """Fetch all 4 equipped armor slots, apply level scaling + substats via
    effective_armor_stats(), and store totals in armor_bonus_X keys.
    Also stores full piece rows in pet['equipped_pieces'] for display."""
    from game.dungeon_loot import effective_armor_stats

    pet = dict(pet)  # don't mutate original
    for s in ("hp", "atk", "def", "spd", "mgk", "res"):
        pet[f"armor_bonus_{s}"] = 0
    pet["equipped_pieces"] = []

    fetch_cols = (
        "id", "bonus_hp", "bonus_atk", "bonus_def", "bonus_spd", "bonus_mgk", "bonus_res",
        "name", "rarity", "piece_type", "set_name", "armor_level", "sub_stats"
    )

    for piece_type, col in ARMOR_SLOT_COLS.items():
        armor_id = pet.get(col)
        if not armor_id:
            continue
        async with db.execute(
            f"SELECT {', '.join(fetch_cols)} FROM armor_inventory WHERE id=?", (armor_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            continue
        piece = dict(zip(fetch_cols, row))
        # Apply level multiplier + substats
        scaled = effective_armor_stats(piece)
        for s in ("hp", "atk", "def", "spd", "mgk", "res"):
            pet[f"armor_bonus_{s}"] += scaled.get(f"bonus_{s}", 0)
        # Store piece with its scaled stats for display
        piece["scaled"] = scaled
        pet["equipped_pieces"].append(piece)

    return pet

async def unequip_armor_id(db: aiosqlite.Connection, armor_id: int, player_id: int):
    """Remove an armor piece from whichever pet slot it occupies."""
    for col in ARMOR_SLOT_COLS.values():
        await db.execute(
            f"UPDATE pets SET {col}=NULL WHERE {col}=? AND player_id=?",
            (armor_id, player_id)
        )
    # Legacy single-slot compat
    await db.execute(
        "UPDATE pets SET equipped_armor=NULL WHERE equipped_armor=? AND player_id=?",
        (armor_id, player_id)
    )

async def get_active_pet(db: aiosqlite.Connection, user_id: int) -> dict | None:
    async with db.execute(
        "SELECT * FROM pets WHERE player_id=? ORDER BY COALESCE(party_slot, 9999), id LIMIT 1",
        (user_id,)
    ) as cur:
        row = await cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    return None

async def get_player_pets(db: aiosqlite.Connection, user_id: int) -> list[dict]:
    async with db.execute(
        "SELECT * FROM pets WHERE player_id=? ORDER BY COALESCE(party_slot, 9999), id",
        (user_id,)
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


# ── Player XP / Level ─────────────────────────────────────────────────────────

async def add_player_xp(db: aiosqlite.Connection, user_id: int, amount: int) -> tuple[int, int, bool]:
    """Add player XP and handle level-ups. Returns (new_level, new_xp, leveled_up)."""
    from config import player_xp_for_next_level, PLAYER_LEVEL_CAP
    player = await get_player(db, user_id)
    if not player:
        return 1, 0, False
    level = player.get("player_level") or 1
    xp = (player.get("player_xp") or 0) + amount
    leveled_up = False
    while level < PLAYER_LEVEL_CAP:
        needed = player_xp_for_next_level(level)
        if xp >= needed:
            xp -= needed
            level += 1
            leveled_up = True
        else:
            break
    await db.execute(
        "UPDATE players SET player_level=?, player_xp=? WHERE user_id=?",
        (level, xp, user_id)
    )
    return level, xp, leveled_up


# ── Moon Shards ───────────────────────────────────────────────────────────────

async def sync_moon_shards(db: aiosqlite.Connection, user_id: int) -> int:
    """Compute current moon shards including passive regen. Updates DB and returns current count."""
    from config import MOON_SHARD_REGEN_MINS, MOON_SHARD_CAP
    player = await get_player(db, user_id)
    if not player:
        return 0
    current = player.get("moon_shards") or 0
    last_str = player.get("last_shard_time")
    now = datetime.now(timezone.utc)
    if current < MOON_SHARD_CAP and last_str:
        try:
            last = datetime.fromisoformat(last_str)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed_mins = (now - last).total_seconds() / 60
            gained = int(elapsed_mins / MOON_SHARD_REGEN_MINS)
            if gained > 0:
                current = min(MOON_SHARD_CAP, current + gained)
                await db.execute(
                    "UPDATE players SET moon_shards=?, last_shard_time=? WHERE user_id=?",
                    (current, now.isoformat(), user_id)
                )
                await db.commit()
        except Exception:
            pass
    elif last_str is None:
        # First time — set the clock
        await db.execute(
            "UPDATE players SET last_shard_time=? WHERE user_id=?",
            (now.isoformat(), user_id)
        )
        await db.commit()
    return current


async def spend_moon_shards(db: aiosqlite.Connection, user_id: int, amount: int) -> bool:
    """Spend moon shards. Returns False if insufficient."""
    current = await sync_moon_shards(db, user_id)
    if current < amount:
        return False
    now = datetime.now(timezone.utc)
    await db.execute(
        "UPDATE players SET moon_shards=moon_shards-?, last_shard_time=? WHERE user_id=?",
        (amount, now.isoformat(), user_id)
    )
    await db.commit()
    return True
