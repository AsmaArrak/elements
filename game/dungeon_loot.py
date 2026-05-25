import random
import json
from config import (
    ARMOR_SETS, ARMOR_PIECES, ARMOR_PIECE_MAIN_STATS, ARMOR_BASE_VALUES,
    ARMOR_SUBSTAT_RANGES, DUNGEON_RARITY_WEIGHTS, DUNGEONS,
    ARMOR_LEVEL_XP, ARMOR_LEVEL_MULT, ARMOR_SUBSTAT_UNLOCK_LEVELS,
)


def get_player_tier(player_level: int) -> str:
    if player_level <= 20:
        return "tier1"
    elif player_level <= 40:
        return "tier2"
    return "tier3"


def roll_rarity(tier: str) -> str:
    weights = DUNGEON_RARITY_WEIGHTS[tier]
    return random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]


def generate_armor_piece(element: str, rarity: str) -> dict:
    """Generate a single armor piece dict ready for DB insertion."""
    piece_type = random.choice(ARMOR_PIECES)
    main_stat  = random.choice(ARMOR_PIECE_MAIN_STATS[piece_type])
    base_val   = ARMOR_BASE_VALUES[rarity][main_stat]
    set_name   = ARMOR_SETS[element]["name"]

    piece = {
        "name":      f"{set_name} {piece_type}",
        "rarity":    rarity,
        "set_name":  element,
        "piece_type": piece_type,
        "armor_level": 1,
        "armor_xp":   0,
        "sub_stats":  "[]",
        "bonus_hp":   base_val if main_stat == "hp"  else 0,
        "bonus_atk":  base_val if main_stat == "atk" else 0,
        "bonus_def":  base_val if main_stat == "def" else 0,
        "bonus_spd":  base_val if main_stat == "spd" else 0,
        "bonus_mgk":  base_val if main_stat == "mgk" else 0,
        "bonus_res":  base_val if main_stat == "res" else 0,
    }
    return piece


EGG_DROP_CHANCE = 0.04  # 4% chance per dungeon run (was raised to 15%)

def generate_dungeon_loot(dungeon_key: str, player_level: int) -> tuple[list[dict], str | None]:
    """Generate 3–4 armor pieces for a dungeon run.
    Returns (pieces, egg_element) where egg_element is set on a 4% chance."""
    dungeon = DUNGEONS[dungeon_key]
    tier    = get_player_tier(player_level)
    count   = 3 + (1 if random.random() < 0.6 else 0)
    pieces  = []
    for _ in range(count):
        element = random.choice(dungeon["elements"])
        rarity  = roll_rarity(tier)
        pieces.append(generate_armor_piece(element, rarity))

    egg_element = random.choice(dungeon["elements"]) if random.random() < EGG_DROP_CHANCE else None
    return pieces, egg_element


# ── Armor upgrade helpers ──────────────────────────────────────────────────────

def effective_armor_stats(armor: dict) -> dict:
    """Return the scaled stats for an armor piece at its current level."""
    level = armor.get("armor_level") or 1
    mult  = ARMOR_LEVEL_MULT.get(level, 1.0)
    stats = {}
    for stat in ("hp", "atk", "def", "spd", "mgk", "res"):
        base = armor.get(f"bonus_{stat}", 0)
        stats[f"bonus_{stat}"] = int(base * mult)
    # Add substats
    try:
        substats = json.loads(armor.get("sub_stats") or "[]")
    except Exception:
        substats = []
    for ss in substats:
        key = f"bonus_{ss['stat']}"
        stats[key] = stats.get(key, 0) + ss["value"]
    return stats


def roll_substat(armor: dict) -> dict | None:
    """Roll a new random substat for the armor piece. Returns None if all slots filled."""
    rarity = armor.get("rarity", "common")
    try:
        existing = json.loads(armor.get("sub_stats") or "[]")
    except Exception:
        existing = []
    taken = {s["stat"] for s in existing}
    # Also exclude the main stat (the one with a non-zero base)
    for stat in ("hp", "atk", "def", "spd", "mgk", "res"):
        if armor.get(f"bonus_{stat}", 0) > 0:
            taken.add(stat)
            break
    available = [s for s in ("hp", "atk", "def", "spd", "mgk", "res") if s not in taken]
    if not available:
        return None
    stat = random.choice(available)
    lo, hi = ARMOR_SUBSTAT_RANGES[rarity][stat]
    return {"stat": stat, "value": random.randint(lo, hi)}


def xp_to_next_armor_level(current_level: int) -> int | None:
    """XP needed to go from current_level to current_level+1. None if at max."""
    return ARMOR_LEVEL_XP.get(current_level)
