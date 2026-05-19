import random
from config import ELEMENTS

# Expedition loot tables — (weight, item_key, item_type, element_specific)
COMMON_LOOT = [
    (30, "apple",   "food",  False),
    (25, "bread",   "food",  False),
    (25, "carrot",  "food",  False),
    (25, "cheese",  "food",  False),
    (20, "grape",   "food",  False),
    (15, "chicken", "food",  False),
    (15, "fish",    "food",  False),
    (40, "coins_small", "coins", False),  # 50-200 coins
]

UNCOMMON_LOOT = [
    (40, "coins_medium",   "coins",        False),  # 150-400
    (30, "crystal_shard",  "stat_item",    False),
    (30, "iron_scrap",     "stat_item",    False),
    (30, "swift_feather",  "stat_item",    False),
    (20, "ancient_fang",   "stat_item",    False),
    (20, "mystic_root",    "stat_item",    False),
    (20, "life_crystal",   "stat_item",    False),
    (15, "egg",            "egg",          False),   # random element egg
]

RARE_LOOT = [
    (50, "evo_stone_uncommon", "evo_stone", True),   # element-specific
    (30, "cake",               "food",      False),
    (30, "honey",              "food",      False),
    (20, "coins_large",        "coins",     False),  # 400-800
]

VERY_RARE_LOOT = [
    (60, "evo_stone_rare", "evo_stone", True),
]

LEGENDARY_LOOT = [
    (100, "mega_stone", "mega_stone", True),  # only if exploration >= 100
]

# Duration -> loot roll counts
LOOT_ROLLS = {1: 2, 6: 4, 12: 6, 24: 9}

def roll_rarity(duration_hrs: int) -> str:
    # Longer expeditions shift probability toward rare+
    base = {1: [70, 20, 8, 2, 0], 6: [55, 28, 12, 4, 1], 12: [45, 30, 16, 7, 2], 24: [35, 32, 20, 10, 3]}
    weights = base.get(duration_hrs, base[6])
    return random.choices(["common", "uncommon", "rare", "very_rare", "legendary"], weights=weights, k=1)[0]

def _pick(table):
    keys, weights = zip(*[(item, w) for w, *item in [(r[0], r[1:]) for r in table]])
    chosen = random.choices(keys, weights=weights, k=1)[0]
    return chosen

def generate_expedition_loot(duration_hrs: int, pet_element: str, exploration: int) -> list[dict]:
    rolls = LOOT_ROLLS.get(duration_hrs, 4)
    results = []
    for _ in range(rolls):
        rarity = roll_rarity(duration_hrs)
        # Legendary only with maxed exploration
        if rarity == "legendary" and exploration < 100:
            rarity = "very_rare"

        table_map = {
            "common": COMMON_LOOT,
            "uncommon": UNCOMMON_LOOT,
            "rare": RARE_LOOT,
            "very_rare": VERY_RARE_LOOT,
            "legendary": LEGENDARY_LOOT,
        }
        table = table_map[rarity]
        weights = [r[0] for r in table]
        chosen = random.choices(table, weights=weights, k=1)[0]
        _, item_key, item_type, element_specific = chosen

        element = None
        qty = 1

        if item_type == "coins":
            coin_ranges = {
                "coins_small": (50, 200),
                "coins_medium": (150, 400),
                "coins_large": (400, 800),
            }
            lo, hi = coin_ranges.get(item_key, (50, 200))
            qty = random.randint(lo, hi)
            results.append({"item_key": "coins", "item_type": "coins", "qty": qty, "element": None})
            continue

        if element_specific:
            if item_key == "mega_stone":
                element = pet_element  # mega stone matches pet's element
            else:
                element = pet_element  # evo stones match pet's element

        if item_type == "egg":
            element = random.choice(ELEMENTS)

        results.append({"item_key": item_key, "item_type": item_type, "qty": qty, "element": element})
    return results

# Channel drop pool
CHANNEL_DROPS = [
    # (weight, item_key, item_type, element)
    (50, "apple",   "food",  None),
    (45, "bread",   "food",  None),
    (45, "carrot",  "food",  None),
    (45, "cheese",  "food",  None),
    (40, "grape",   "food",  None),
    (25, "chicken", "food",  None),
    (25, "fish",    "food",  None),
    (30, "coins_drop", "coins", None),  # 30-100 coins
    (10, "crystal_shard", "stat_item", None),
    (10, "iron_scrap",    "stat_item", None),
    (10, "swift_feather", "stat_item", None),
    (3,  "evo_stone_uncommon", "evo_stone", None),  # random element
    (1,  "egg",      "egg",  None),  # random element
]

def generate_channel_drop() -> dict:
    weights = [r[0] for r in CHANNEL_DROPS]
    chosen = random.choices(CHANNEL_DROPS, weights=weights, k=1)[0]
    _, item_key, item_type, element = chosen
    qty = 1
    if item_key == "coins_drop":
        qty = random.randint(30, 100)
        return {"item_key": "coins", "item_type": "coins", "qty": qty, "element": None}
    if item_type in ("evo_stone", "egg"):
        element = random.choice(ELEMENTS)
    return {"item_key": item_key, "item_type": item_type, "qty": qty, "element": element}
