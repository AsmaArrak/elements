"""
Skill definitions and compatibility rules.
Each element can only learn skills from compatible elements (including its own).
"""

# element → elements whose scrolls this pet can use
SKILL_COMPATIBILITY = {
    "void":    ["void", "phantom", "cosmic"],
    "ember":   ["ember", "forge", "storm"],
    "storm":   ["storm", "ember", "cosmic"],
    "bloom":   ["bloom", "tide", "phantom"],
    "crystal": ["crystal", "tide", "toxin"],
    "cosmic":  ["cosmic", "void", "phantom"],
    "toxin":   ["toxin", "bloom", "phantom"],
    "forge":   ["forge", "ember", "crystal"],
    "phantom": ["phantom", "void", "cosmic"],
    "tide":    ["tide", "bloom", "forge"],
}

# Max skills a pet can know at once
MAX_SKILLS = 4

# skill_key → data
SKILLS = {
    # ── Void ──────────────────────────────────────────────────────────────────
    "void_slash":      {"name": "Void Slash",       "element": "void",    "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "A slash of dark energy"},
    "shadow_pulse":    {"name": "Shadow Pulse",      "element": "void",    "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A burst of shadow"},
    "void_collapse":   {"name": "Void Collapse",     "element": "void",    "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Collapses reality on the enemy"},
    "abyssal_doom":    {"name": "Abyssal Doom",      "element": "void",    "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The ultimate void strike"},
    # ── Ember ─────────────────────────────────────────────────────────────────
    "ember_claw":      {"name": "Ember Claw",        "element": "ember",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A burning claw swipe"},
    "flame_burst":     {"name": "Flame Burst",       "element": "ember",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "An eruption of flame"},
    "inferno_strike":  {"name": "Inferno Strike",    "element": "ember",   "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "A devastating fire attack"},
    "solar_wrath":     {"name": "Solar Wrath",       "element": "ember",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The fury of the sun"},
    # ── Storm ─────────────────────────────────────────────────────────────────
    "static_jab":      {"name": "Static Jab",        "element": "storm",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A quick electric jab"},
    "thunder_bolt":    {"name": "Thunderbolt",        "element": "storm",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A bolt of lightning"},
    "cyclone_slash":   {"name": "Cyclone Slash",      "element": "storm",   "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "A spinning wind blade"},
    "storm_apocalypse":{"name": "Storm Apocalypse",  "element": "storm",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The sky tears apart"},
    # ── Bloom ─────────────────────────────────────────────────────────────────
    "vine_whip":       {"name": "Vine Whip",          "element": "bloom",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A lashing vine strike"},
    "petal_storm":     {"name": "Petal Storm",        "element": "bloom",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A storm of razor petals"},
    "root_crush":      {"name": "Root Crush",         "element": "bloom",   "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "Roots erupt and crush"},
    "nature_wrath":    {"name": "Nature's Wrath",     "element": "bloom",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The forest strikes back"},
    # ── Crystal ───────────────────────────────────────────────────────────────
    "shard_toss":      {"name": "Shard Toss",         "element": "crystal", "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "Hurls a crystal shard"},
    "prism_beam":      {"name": "Prism Beam",         "element": "crystal", "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A focused light beam"},
    "crystal_prison":  {"name": "Crystal Prison",     "element": "crystal", "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Encases enemy in crystal"},
    "diamond_nova":    {"name": "Diamond Nova",       "element": "crystal", "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "An explosion of pure crystal"},
    # ── Cosmic ────────────────────────────────────────────────────────────────
    "stardust":        {"name": "Stardust",           "element": "cosmic",  "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Sprinkles cosmic dust"},
    "nebula_blast":    {"name": "Nebula Blast",       "element": "cosmic",  "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A blast of nebula energy"},
    "gravity_crush":   {"name": "Gravity Crush",      "element": "cosmic",  "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Crushes with gravity"},
    "big_bang":        {"name": "Big Bang",           "element": "cosmic",  "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "A miniature universe explosion"},
    # ── Toxin ─────────────────────────────────────────────────────────────────
    "acid_spit":       {"name": "Acid Spit",          "element": "toxin",   "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Spits corrosive acid"},
    "venom_strike":    {"name": "Venom Strike",       "element": "toxin",   "rarity": "uncommon",  "type": "physical", "mult": 1.6, "desc": "A venomous physical hit"},
    "plague_cloud":    {"name": "Plague Cloud",       "element": "toxin",   "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "A cloud of plague"},
    "death_bloom":     {"name": "Death Bloom",        "element": "toxin",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "Beautiful and deadly"},
    # ── Forge ─────────────────────────────────────────────────────────────────
    "iron_punch":      {"name": "Iron Punch",         "element": "forge",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A heavy iron fist"},
    "molten_slam":     {"name": "Molten Slam",        "element": "forge",   "rarity": "uncommon",  "type": "physical", "mult": 1.6, "desc": "Slams with molten metal"},
    "forge_cannon":    {"name": "Forge Cannon",       "element": "forge",   "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "Fires a molten cannonball"},
    "titanbreach":     {"name": "Titanbreach",        "element": "forge",   "rarity": "legendary", "type": "physical", "mult": 3.0, "desc": "The ultimate forge technique"},
    # ── Phantom ───────────────────────────────────────────────────────────────
    "ghost_claw":      {"name": "Ghost Claw",         "element": "phantom", "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A claw from beyond"},
    "specter_bolt":    {"name": "Specter Bolt",       "element": "phantom", "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A ghostly projectile"},
    "soul_rend":       {"name": "Soul Rend",          "element": "phantom", "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Tears at the soul"},
    "phantom_eclipse": {"name": "Phantom Eclipse",   "element": "phantom", "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "Blots out reality itself"},
    # ── Tide ──────────────────────────────────────────────────────────────────
    "water_jet":       {"name": "Water Jet",          "element": "tide",    "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A high-pressure water blast"},
    "tidal_wave":      {"name": "Tidal Wave",         "element": "tide",    "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A crushing wave"},
    "deep_crush":      {"name": "Deep Crush",         "element": "tide",    "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "The pressure of the deep sea"},
    "leviathan_surge": {"name": "Leviathan Surge",   "element": "tide",    "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "A surge from the ancient deep"},
}

SCROLL_RARITY_WEIGHTS = {
    "common": 50, "uncommon": 30, "rare": 15, "legendary": 5
}

SCROLL_SELL_PRICE = {
    "common": 200, "uncommon": 600, "rare": 1500, "legendary": 5000
}
