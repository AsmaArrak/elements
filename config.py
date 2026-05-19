import os

# Root directory (where the element folders live)
ASSETS_PATH = os.path.dirname(os.path.abspath(__file__))

ELEMENTS = ["void", "ember", "storm", "bloom", "crystal", "cosmic", "toxin", "forge", "phantom", "tide"]

ELEMENT_DISPLAY = {
    "void": "Void", "ember": "Ember", "storm": "Storm", "bloom": "Bloom",
    "crystal": "Crystal", "cosmic": "Cosmic", "toxin": "Plague",
    "forge": "Forge", "phantom": "Phantom", "tide": "Tide",
}

ELEMENT_COLORS = {
    "void": 0x4B0082, "ember": 0xFF4500, "storm": 0x4169E1, "bloom": 0x228B22,
    "crystal": 0x00CED1, "cosmic": 0x191970, "toxin": 0x32CD32,
    "forge": 0x8B4513, "phantom": 0xB0C4DE, "tide": 0x006994,
}

ELEMENT_EMOJIS = {
    "void": "🌑", "ember": "🔥", "storm": "⚡", "bloom": "🌿",
    "crystal": "💎", "cosmic": "✨", "toxin": "☠️",
    "forge": "⚙️", "phantom": "👻", "tide": "🌊",
}

# element -> elements it hits for 1.5x MGK
TYPE_ADVANTAGE = {
    "void":    ["phantom", "cosmic"],
    "ember":   ["bloom", "crystal"],
    "storm":   ["tide", "forge"],
    "bloom":   ["tide", "phantom"],
    "crystal": ["storm", "void"],
    "cosmic":  ["void", "phantom"],
    "toxin":   ["bloom", "tide"],
    "forge":   ["crystal", "cosmic"],
    "phantom": ["forge", "toxin"],
    "tide":    ["ember", "forge"],
}

# Pet names: element -> variant (1|2) -> [egg, evo1, evo2, evo3, mega]
PET_NAMES = {
    "void": {
        1: ["Void Egg", "Dimling", "Veilmaw", "Nullshade", "Abyssarex"],
        2: ["Void Egg", "Shadeling", "Umbravex", "Duskraith", "Voidterror"],
    },
    "ember": {
        1: ["Ember Egg", "Embkit", "Cinderoc", "Blazemane", "Pyroclasm"],
        2: ["Ember Egg", "Sparklet", "Ashclaw", "Infernokin", "Solarwrath"],
    },
    "storm": {
        1: ["Storm Egg", "Zappuff", "Stormfang", "Tempestrix", "Cyclonarch"],
        2: ["Storm Egg", "Voltpup", "Thundermaw", "Galecrest", "Stormreign"],
    },
    "bloom": {
        1: ["Bloom Egg", "Petalop", "Floriven", "Arborath", "Verdantis"],
        2: ["Bloom Egg", "Sproutling", "Vineclaw", "Thornlord", "Naturewarden"],
    },
    "crystal": {
        1: ["Crystal Egg", "Shardling", "Gemlynx", "Crystalith", "Prismarex"],
        2: ["Crystal Egg", "Gemcub", "Prismfox", "Crystalwing", "Gemlord"],
    },
    "cosmic": {
        1: ["Cosmic Egg", "Stellpuff", "Astrova", "Nebulair", "Galaxorn"],
        2: ["Cosmic Egg", "Starpup", "Galaxfox", "Nebulon", "Cosmovern"],
    },
    "toxin": {
        1: ["Plague Egg", "Vexling", "Miasmare", "Corruptis", "Pestilorn"],
        2: ["Plague Egg", "Sporepup", "Venomwing", "Blightfiend", "Plaguewarden"],
    },
    "forge": {
        1: ["Forge Egg", "Ironpup", "Geargrizzle", "Forgeknight", "Titanforge"],
        2: ["Forge Egg", "Scraplet", "Steamclaw", "Anvilknight", "Forgegod"],
    },
    "phantom": {
        1: ["Phantom Egg", "Wispling", "Specryn", "Phantaveil", "Soulvern"],
        2: ["Phantom Egg", "Mistpup", "Veilserpent", "Spectralis", "Phantomking"],
    },
    "tide": {
        1: ["Tide Egg", "Tidepup", "Wavefin", "Thalassyn", "Leviarcus"],
        2: ["Tide Egg", "Coralcub", "Deepfin", "Abyssray", "Tidalwarden"],
    },
}

STAGE_NAMES = ["Egg", "Evo 1", "Evo 2", "Evo 3", "Mega Evolution"]

# Base stats per element (for Evo 1). Same for both variants of an element.
BASE_STATS = {
    "void":    {"hp": 60,  "atk": 15, "def": 10, "spd": 20, "mgk": 30, "res": 10},
    "ember":   {"hp": 65,  "atk": 25, "def": 15, "spd": 18, "mgk": 22, "res": 12},
    "storm":   {"hp": 55,  "atk": 20, "def": 12, "spd": 35, "mgk": 18, "res": 10},
    "bloom":   {"hp": 80,  "atk": 12, "def": 18, "spd": 12, "mgk": 15, "res": 25},
    "crystal": {"hp": 60,  "atk": 15, "def": 30, "spd": 10, "mgk": 18, "res": 28},
    "cosmic":  {"hp": 65,  "atk": 18, "def": 15, "spd": 18, "mgk": 25, "res": 18},
    "toxin":   {"hp": 55,  "atk": 12, "def": 12, "spd": 20, "mgk": 32, "res": 15},
    "forge":   {"hp": 70,  "atk": 28, "def": 25, "spd": 10, "mgk": 12, "res": 18},
    "phantom": {"hp": 50,  "atk": 15, "def": 10, "spd": 30, "mgk": 28, "res": 12},
    "tide":    {"hp": 75,  "atk": 16, "def": 22, "spd": 14, "mgk": 18, "res": 20},
}

# Multiplier applied to base stats at each stage
STAGE_MULTIPLIERS = {0: 0.5, 1: 1.0, 2: 1.6, 3: 2.5, 4: 4.0}

# XP needed to go from level N to N+1
def xp_for_next_level(level: int) -> int:
    if level < 10:
        return 100
    elif level < 35:
        return 350
    elif level < 70:
        return 800
    else:
        return 1800

# Stat cap: base_stat + (level * 2)  — bonus stats cannot push past this
def stat_cap(base_stat: int, level: int) -> int:
    return base_stat + (level * 2)

# Evolution requirements
EVO_REQUIREMENTS = {
    # stage -> (min_level, required_item_type or None)
    1: (1, None),              # Egg -> Evo1: just first feeding
    2: (35, "evo_stone_uncommon"),
    3: (70, "evo_stone_rare"),
    4: (100, "mega_stone"),    # also needs exploration >= 100
}

FOOD_ITEMS = {
    # Common — all 6 stats covered
    "apple":    {"stat": "hp",  "boost": 5,  "rarity": "common",   "xp": 20, "display": "Apple 🍎"},
    "bread":    {"stat": "def", "boost": 4,  "rarity": "common",   "xp": 20, "display": "Bread 🍞"},
    "carrot":   {"stat": "spd", "boost": 5,  "rarity": "common",   "xp": 20, "display": "Carrot 🥕"},
    "cheese":   {"stat": "atk", "boost": 5,  "rarity": "common",   "xp": 20, "display": "Cheese 🧀"},
    "grape":    {"stat": "res", "boost": 5,  "rarity": "common",   "xp": 20, "display": "Grape 🍇"},
    "mushroom": {"stat": "mgk", "boost": 5,  "rarity": "common",   "xp": 20, "display": "Mushroom 🍄"},
    # Uncommon — all 6 stats covered
    "chicken":  {"stat": "atk", "boost": 8,  "rarity": "uncommon", "xp": 35, "display": "Chicken 🍗"},
    "fish":     {"stat": "mgk", "boost": 8,  "rarity": "uncommon", "xp": 35, "display": "Fish 🐟"},
    "berry":    {"stat": "res", "boost": 8,  "rarity": "uncommon", "xp": 35, "display": "Berry 🫐"},
    "steak":    {"stat": "def", "boost": 8,  "rarity": "uncommon", "xp": 35, "display": "Steak 🥩"},
    "noodles":  {"stat": "spd", "boost": 8,  "rarity": "uncommon", "xp": 35, "display": "Noodles 🍜"},
    "potion":   {"stat": "hp",  "boost": 12, "rarity": "uncommon", "xp": 35, "display": "Potion 🧪"},
    # Rare — all 6 stats covered
    "cake":     {"stat": "hp",  "boost": 20, "rarity": "rare",     "xp": 60, "display": "Cake 🎂"},
    "honey":    {"stat": "mgk", "boost": 18, "rarity": "rare",     "xp": 60, "display": "Honey 🍯"},
    "dragonfruit": {"stat": "atk", "boost": 18, "rarity": "rare",  "xp": 60, "display": "Dragonfruit 🐉"},
    "ironbark":    {"stat": "def", "boost": 18, "rarity": "rare",  "xp": 60, "display": "Ironbark 🪵"},
    "windleaf":    {"stat": "spd", "boost": 18, "rarity": "rare",  "xp": 60, "display": "Windleaf 🍃"},
    "starfruit":   {"stat": "res", "boost": 18, "rarity": "rare",  "xp": 60, "display": "Starfruit ⭐"},
}

SHOP_ITEMS = {
    # Common food
    "apple":    {"price": 500,  "type": "food", "description": "Boosts HP by 5"},
    "bread":    {"price": 500,  "type": "food", "description": "Boosts DEF by 4"},
    "carrot":   {"price": 500,  "type": "food", "description": "Boosts SPD by 5"},
    "cheese":   {"price": 500,  "type": "food", "description": "Boosts ATK by 5"},
    "grape":    {"price": 500,  "type": "food", "description": "Boosts RES by 5"},
    "mushroom": {"price": 500,  "type": "food", "description": "Boosts MGK by 5"},
    # Uncommon food
    "chicken":  {"price": 800,  "type": "food", "description": "Boosts ATK by 8"},
    "fish":     {"price": 800,  "type": "food", "description": "Boosts MGK by 8"},
    "berry":    {"price": 800,  "type": "food", "description": "Boosts RES by 8"},
    "steak":    {"price": 800,  "type": "food", "description": "Boosts DEF by 8"},
    "noodles":  {"price": 800,  "type": "food", "description": "Boosts SPD by 8"},
    "potion":   {"price": 800,  "type": "food", "description": "Boosts HP by 12"},
}
# Rare foods (cake, honey, dragonfruit, ironbark, windleaf, starfruit) are drops only
# Cake and honey are NOT sold in the shop — rare drops only

STAT_ITEMS = {
    "crystal_shard":  {"stat": "mgk", "boost": 10, "display": "Crystal Shard 🔷",  "desc": "Permanently +10 MGK"},
    "iron_scrap":     {"stat": "def", "boost": 10, "display": "Iron Scrap 🪙",      "desc": "Permanently +10 DEF"},
    "swift_feather":  {"stat": "spd", "boost": 10, "display": "Swift Feather 🪶",   "desc": "Permanently +10 SPD"},
    "ancient_fang":   {"stat": "atk", "boost": 12, "display": "Ancient Fang 🦷",    "desc": "Permanently +12 ATK"},
    "mystic_root":    {"stat": "res", "boost": 10, "display": "Mystic Root 🌱",     "desc": "Permanently +10 RES"},
    "life_crystal":   {"stat": "hp",  "boost": 20, "display": "Life Crystal 💠",    "desc": "Permanently +20 HP"},
}

# ── Armor ─────────────────────────────────────────────────────────────────────
# name → {rarity, stat bonuses}
ARMOR_POOL = {
    # Common
    "Leather Helm":     {"rarity": "common",    "bonus_def": 5,  "bonus_hp": 8},
    "Cloth Vest":       {"rarity": "common",    "bonus_hp": 12,  "bonus_res": 3},
    "Light Greaves":    {"rarity": "common",    "bonus_spd": 5,  "bonus_def": 3},
    "Wooden Shield":    {"rarity": "common",    "bonus_def": 8,  "bonus_res": 4},
    # Uncommon
    "Iron Helm":        {"rarity": "uncommon",  "bonus_def": 12, "bonus_hp": 15},
    "Chain Vest":       {"rarity": "uncommon",  "bonus_hp": 20,  "bonus_def": 8},
    "Swift Boots":      {"rarity": "uncommon",  "bonus_spd": 12, "bonus_atk": 5},
    "Battle Gauntlets": {"rarity": "uncommon",  "bonus_atk": 12, "bonus_def": 6},
    "Mystic Robe":      {"rarity": "uncommon",  "bonus_mgk": 12, "bonus_res": 6},
    "Runic Bracers":    {"rarity": "uncommon",  "bonus_mgk": 10, "bonus_spd": 5},
    # Rare
    "Dragon Helm":      {"rarity": "rare",      "bonus_def": 22, "bonus_hp": 25, "bonus_res": 8},
    "Titan Plate":      {"rarity": "rare",      "bonus_hp": 35,  "bonus_def": 18, "bonus_atk": 8},
    "Phantom Cloak":    {"rarity": "rare",      "bonus_spd": 20, "bonus_mgk": 12, "bonus_res": 10},
    "Arcane Mantle":    {"rarity": "rare",      "bonus_mgk": 22, "bonus_res": 15, "bonus_hp": 15},
    "Warlord Armor":    {"rarity": "rare",      "bonus_atk": 22, "bonus_def": 15, "bonus_spd": 8},
    # Legendary
    "Celestial Crown":  {"rarity": "legendary", "bonus_hp": 40,  "bonus_mgk": 25, "bonus_res": 20, "bonus_def": 15},
    "Void Aegis":       {"rarity": "legendary", "bonus_def": 35, "bonus_hp": 30,  "bonus_res": 25, "bonus_spd": 10},
    "Storm Regalia":    {"rarity": "legendary", "bonus_atk": 30, "bonus_mgk": 25, "bonus_spd": 20, "bonus_hp": 20},
    "Bloom Sanctuary":  {"rarity": "legendary", "bonus_hp": 50,  "bonus_res": 30, "bonus_def": 20, "bonus_mgk": 15},
}

ARMOR_BY_RARITY = {
    "common":    [k for k, v in ARMOR_POOL.items() if v["rarity"] == "common"],
    "uncommon":  [k for k, v in ARMOR_POOL.items() if v["rarity"] == "uncommon"],
    "rare":      [k for k, v in ARMOR_POOL.items() if v["rarity"] == "rare"],
    "legendary": [k for k, v in ARMOR_POOL.items() if v["rarity"] == "legendary"],
}

RARITY_EMOJIS = {
    "common": "⚪", "uncommon": "🟢", "rare": "🟣", "legendary": "🟡"
}

# Passive XP per hour (background task)
PASSIVE_XP_PER_HOUR = 5

BATTLE_WIN_XP = 50
BATTLE_LOSS_XP = 15
BATTLE_WIN_COINS = 80
BATTLE_LOSS_COINS = 20

EXPEDITION_XP = {0.5: 20, 1.5: 45, 4: 90, 6: 150}
EXPLORATION_GAIN = {0.5: 3, 1.5: 8, 4: 20, 6: 35}

DAILY_LOGIN_XP = 30
DAILY_LOGIN_COINS = 100

TRAIN_XP = 20
TRAIN_STAT_BOOST = 3
TRAIN_COOLDOWN_HOURS = 20

FISH_COOLDOWN_MINUTES = 10
DIG_COOLDOWN_MINUTES = 10
TRIVIA_COOLDOWN_MINUTES = 2

DROP_INTERVAL_MIN = 20   # minutes between channel drops
DROP_INTERVAL_MAX = 60
DROP_EXPIRY_MINUTES = 12

def get_pet_image(element: str, variant: int, stage: int) -> str:
    stage_files = {1: "evo 1.png", 2: "evo 2.png", 3: "evo 3.png", 4: "mega evo.png"}
    if stage == 0:
        return os.path.join(ASSETS_PATH, element, "egg.png")
    return os.path.join(ASSETS_PATH, element, str(variant), stage_files[stage])

def get_stone_image(element: str, stone_type: str) -> str:
    stone_files = {
        "evo_stone_uncommon": "1 to 2.png",
        "evo_stone_rare": "2 to 3.png",
        "mega_stone": "mega.png",
    }
    return os.path.join(ASSETS_PATH, element, stone_files[stone_type])

def get_food_image(food_name: str) -> str:
    return os.path.join(ASSETS_PATH, "food", f"{food_name}.png")
