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
    (35, "egg",           "egg",       False),
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
    0.5: [90, 10,  0,  0,  0],
    1.5: [68, 26,  5,  1,  0],
    4:   [45, 33, 18,  4,  0],
    6:   [28, 30, 30,  8,  4],   # legendary 4% on 6hr (only if exploration >= 100)
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

def _roll_rarity(duration_hrs: float) -> str:
    weights = SLOT_WEIGHTS.get(duration_hrs, SLOT_WEIGHTS[1.5])
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

# Flat egg drop chance per expedition (OLD: eggs only appeared as uncommon loot table rolls)
EGG_DROP_CHANCE = 0.20  # 20% flat chance regardless of duration

def generate_expedition_loot(duration_hrs: float, pet_element: str, exploration: int) -> list[dict]:
    # 3–8 items depending on duration
    count_ranges = {0.5: (3, 4), 1.5: (4, 5), 4: (5, 7), 6: (6, 8)}
    lo, hi = count_ranges.get(duration_hrs, (3, 5))
    count = random.randint(lo, hi)

    results = []

    # Guaranteed slots by duration
    if duration_hrs >= 1.5:
        results.append(_pick_from(UNCOMMON_LOOT, pet_element))
    if duration_hrs >= 4:
        results.append(_pick_from(RARE_LOOT, pet_element))
    if duration_hrs >= 6:
        results.append(_pick_from(RARE_LOOT, pet_element))  # 2nd guaranteed rare at 6hr

    # Fill remaining slots with random rolls
    for _ in range(count - len(results)):
        rarity = _roll_rarity(duration_hrs)
        # Legendary only with maxed exploration
        if rarity == "legendary" and exploration < 100:
            rarity = "very_rare"
        results.append(_pick_from(TABLE_MAP[rarity], pet_element))

    # Flat 20% egg bonus drop (on top of normal loot)
    if random.random() < EGG_DROP_CHANCE:
        egg_element = random.choice(ELEMENTS)
        results.append({"item_key": "egg", "item_type": "egg", "qty": 1, "element": egg_element})

    return results


def generate_scroll_drop(duration_hrs: float, pet_element: str) -> dict | None:
    """Chance to drop a skill scroll. Element is one the pet's element can learn."""
    from game.skills import SKILL_COMPATIBILITY
    chance = {0.5: 0.05, 1.5: 0.12, 4: 0.28, 6: 0.50}
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


def generate_armor_drop(duration_hrs: float, pet_element: str = None) -> dict | None:
    """Chance to drop one piece of armor from expedition — uses set-based system."""
    chance = {0.5: 0.05, 1.5: 0.15, 4: 0.38, 6: 0.60}
    if random.random() > chance.get(duration_hrs, 0.10):
        return None
    rarity_weights = {
        0.5: {"common": 88, "uncommon": 11, "rare": 1,  "legendary": 0},
        1.5: {"common": 60, "uncommon": 35, "rare": 5,  "legendary": 0},
        4:   {"common": 30, "uncommon": 45, "rare": 23, "legendary": 2},
        6:   {"common": 10, "uncommon": 30, "rare": 45, "legendary": 15},
    }
    w = rarity_weights.get(duration_hrs, rarity_weights[1.5])
    rarity = random.choices(list(w.keys()), weights=list(w.values()), k=1)[0]
    from game.dungeon_loot import generate_armor_piece
    element = pet_element or random.choice(ELEMENTS)
    return generate_armor_piece(element, rarity)


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
    (15, "egg",       "egg",       None),
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
