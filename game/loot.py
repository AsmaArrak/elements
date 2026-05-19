import random
from config import ELEMENTS, ARMOR_BY_RARITY, ARMOR_POOL
from game.skills import SKILLS, SCROLL_RARITY_WEIGHTS

# ── Loot tables ───────────────────────────────────────────────────────────────

COMMON_LOOT = [
    (30, "apple",     "food",  False),
    (25, "bread",     "food",  False),
    (25, "carrot",    "food",  False),
    (25, "cheese",    "food",  False),
    (20, "grape",     "food",  False),
    (20, "mushroom",  "food",  False),
    (40, "coins_small", "coins", False),   # 50–200 coins
]

UNCOMMON_LOOT = [
    (35, "coins_medium",  "coins",     False),  # 150–400
    (25, "chicken",       "food",      False),
    (25, "fish",          "food",      False),
    (25, "berry",         "food",      False),
    (25, "steak",         "food",      False),
    (25, "noodles",       "food",      False),
    (25, "potion",        "food",      False),
    (20, "crystal_shard", "stat_item", False),
    (20, "iron_scrap",    "stat_item", False),
    (20, "swift_feather", "stat_item", False),
    (15, "ancient_fang",  "stat_item", False),
    (15, "mystic_root",   "stat_item", False),
    (15, "life_crystal",  "stat_item", False),
    (10, "egg",           "egg",       False),
]

RARE_LOOT = [
    (40, "evo_stone_uncommon", "evo_stone", True),
    (25, "cake",               "food",      False),
    (25, "honey",              "food",      False),
    (20, "dragonfruit",        "food",      False),
    (20, "ironbark",           "food",      False),
    (20, "windleaf",           "food",      False),
    (20, "starfruit",          "food",      False),
    (15, "coins_large",        "coins",     False),  # 400–800
]

VERY_RARE_LOOT = [
    (60, "evo_stone_rare", "evo_stone", True),
    (20, "coins_xlarge",   "coins",     False),  # 800–1500
]

LEGENDARY_LOOT = [
    (100, "mega_stone", "mega_stone", True),
]

# ── Rarity weights per slot (non-guaranteed rolls) ────────────────────────────
#   [common, uncommon, rare, very_rare, legendary]
SLOT_WEIGHTS = {
    1:  [85, 15,  0,  0,  0],
    6:  [60, 32,  7,  1,  0],
    12: [45, 30, 20,  5,  0],
    24: [30, 25, 35,  0, 10],   # legendary 10% on 24hr
}

TABLE_MAP = {
    "common":    COMMON_LOOT,
    "uncommon":  UNCOMMON_LOOT,
    "rare":      RARE_LOOT,
    "very_rare": VERY_RARE_LOOT,
    "legendary": LEGENDARY_LOOT,
}

RARITIES = ["common", "uncommon", "rare", "very_rare", "legendary"]

COIN_RANGES = {
    "coins_small":  (50,   200),
    "coins_medium": (150,  400),
    "coins_large":  (400,  800),
    "coins_xlarge": (800, 1500),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _roll_rarity(duration_hrs: int) -> str:
    weights = SLOT_WEIGHTS.get(duration_hrs, SLOT_WEIGHTS[6])
    return random.choices(RARITIES, weights=weights, k=1)[0]


def _pick_from(table: list, pet_element: str) -> dict:
    weights = [r[0] for r in table]
    chosen = random.choices(table, weights=weights, k=1)[0]
    _, item_key, item_type, element_specific = chosen

    if item_type == "coins":
        lo, hi = COIN_RANGES.get(item_key, (50, 200))
        return {"item_key": "coins", "item_type": "coins", "qty": random.randint(lo, hi), "element": None}

    element = None
    if element_specific:
        element = pet_element
    if item_type == "egg":
        element = random.choice(ELEMENTS)

    return {"item_key": item_key, "item_type": item_type, "qty": 1, "element": element}


# ── Main generator ────────────────────────────────────────────────────────────

def generate_expedition_loot(duration_hrs: int, pet_element: str, exploration: int) -> list[dict]:
    # 5–10 items depending on duration
    count_ranges = {1: (5, 7), 6: (6, 8), 12: (7, 9), 24: (8, 10)}
    lo, hi = count_ranges.get(duration_hrs, (5, 7))
    count = random.randint(lo, hi)

    results = []

    # Guaranteed slots by duration
    if duration_hrs >= 6:
        results.append(_pick_from(UNCOMMON_LOOT, pet_element))
    if duration_hrs >= 12:
        results.append(_pick_from(RARE_LOOT, pet_element))
    if duration_hrs >= 24:
        results.append(_pick_from(RARE_LOOT, pet_element))  # 2nd guaranteed rare at 24hr

    # Fill remaining slots with random rolls
    for _ in range(count - len(results)):
        rarity = _roll_rarity(duration_hrs)
        # Legendary only with maxed exploration
        if rarity == "legendary" and exploration < 100:
            rarity = "very_rare"
        results.append(_pick_from(TABLE_MAP[rarity], pet_element))

    return results


def generate_scroll_drop(duration_hrs: int, pet_element: str) -> dict | None:
    """Chance to drop a skill scroll. Element is one the pet's element can learn."""
    from game.skills import SKILL_COMPATIBILITY
    chance = {1: 0.08, 6: 0.20, 12: 0.38, 24: 0.60}
    if random.random() > chance.get(duration_hrs, 0.08):
        return None
    rarity = random.choices(
        list(SCROLL_RARITY_WEIGHTS.keys()),
        weights=list(SCROLL_RARITY_WEIGHTS.values()), k=1
    )[0]
    compatible_elements = SKILL_COMPATIBILITY.get(pet_element, [pet_element])
    compatible_skills = [
        k for k, v in SKILLS.items()
        if v["rarity"] == rarity and v["element"] in compatible_elements
    ]
    if not compatible_skills:
        compatible_skills = [k for k, v in SKILLS.items() if v["rarity"] == rarity]
    skill_key = random.choice(compatible_skills)
    skill = SKILLS[skill_key]
    return {"skill_key": skill_key, "rarity": rarity, "name": skill["name"], "element": skill["element"]}


def generate_armor_drop(duration_hrs: int) -> dict | None:
    """Chance to drop one piece of armor based on expedition duration."""
    chance = {1: 0.10, 6: 0.25, 12: 0.45, 24: 0.70}
    if random.random() > chance.get(duration_hrs, 0.10):
        return None
    # Pick rarity weighted by duration
    rarity_weights = {
        1:  {"common": 80, "uncommon": 18, "rare": 2,  "legendary": 0},
        6:  {"common": 55, "uncommon": 35, "rare": 9,  "legendary": 1},
        12: {"common": 30, "uncommon": 40, "rare": 25, "legendary": 5},
        24: {"common": 10, "uncommon": 30, "rare": 45, "legendary": 15},
    }
    w = rarity_weights.get(duration_hrs, rarity_weights[6])
    rarity = random.choices(list(w.keys()), weights=list(w.values()), k=1)[0]
    pool = ARMOR_BY_RARITY.get(rarity, ARMOR_BY_RARITY["common"])
    name = random.choice(pool)
    return {"name": name, "rarity": rarity, **{k: v for k, v in ARMOR_POOL[name].items() if k != "rarity"}}


# ── Channel drops ─────────────────────────────────────────────────────────────

CHANNEL_DROPS = [
    (50, "apple",     "food",      None),
    (45, "bread",     "food",      None),
    (45, "carrot",    "food",      None),
    (45, "cheese",    "food",      None),
    (40, "grape",     "food",      None),
    (40, "mushroom",  "food",      None),
    (25, "chicken",   "food",      None),
    (25, "fish",      "food",      None),
    (20, "berry",     "food",      None),
    (20, "steak",     "food",      None),
    (20, "noodles",   "food",      None),
    (20, "potion",    "food",      None),
    (30, "coins_drop", "coins",    None),   # 30–150 coins
    (10, "crystal_shard", "stat_item", None),
    (10, "iron_scrap",    "stat_item", None),
    (10, "swift_feather", "stat_item", None),
    (3,  "evo_stone_uncommon", "evo_stone", None),
    (1,  "egg",       "egg",       None),
]


def generate_channel_drop() -> dict:
    weights = [r[0] for r in CHANNEL_DROPS]
    chosen = random.choices(CHANNEL_DROPS, weights=weights, k=1)[0]
    _, item_key, item_type, element = chosen
    if item_key == "coins_drop":
        return {"item_key": "coins", "item_type": "coins", "qty": random.randint(30, 150), "element": None}
    if item_type in ("evo_stone", "egg"):
        element = random.choice(ELEMENTS)
    return {"item_key": item_key, "item_type": item_type, "qty": 1, "element": element}
