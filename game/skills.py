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

# Max scroll-learned skills a pet can know at once
MAX_SKILLS = 4

# ── Default attacks (2 per element, always available — no scroll needed) ───────
DEFAULT_ATTACKS = {
    "void": [
        {"key": "dark_tackle",    "name": "Dark Tackle",    "type": "physical", "mult": 1.1, "desc": "A tackle cloaked in darkness"},
        {"key": "shadow_flare",   "name": "Shadow Flare",   "type": "magic",    "mult": 1.2, "desc": "A weak burst of shadow energy"},
    ],
    "ember": [
        {"key": "scratch",        "name": "Scratch",        "type": "physical", "mult": 1.1, "desc": "A quick claw swipe"},
        {"key": "ember_shot",     "name": "Ember Shot",     "type": "magic",    "mult": 1.2, "desc": "A small fireball"},
    ],
    "storm": [
        {"key": "headbutt",       "name": "Headbutt",       "type": "physical", "mult": 1.1, "desc": "A forceful headbutt"},
        {"key": "spark",          "name": "Spark",          "type": "magic",    "mult": 1.2, "desc": "A tiny electric burst"},
    ],
    "bloom": [
        {"key": "tackle",         "name": "Tackle",         "type": "physical", "mult": 1.1, "desc": "A basic body slam"},
        {"key": "leaf_toss",      "name": "Leaf Toss",      "type": "magic",    "mult": 1.2, "desc": "Hurls sharp leaves"},
    ],
    "crystal": [
        {"key": "crystal_jab",    "name": "Crystal Jab",   "type": "physical", "mult": 1.1, "desc": "A sharp crystalline poke"},
        {"key": "prism_shot",     "name": "Prism Shot",    "type": "magic",    "mult": 1.2, "desc": "A small focused light beam"},
    ],
    "cosmic": [
        {"key": "headbutt",       "name": "Headbutt",       "type": "physical", "mult": 1.1, "desc": "A forceful headbutt"},
        {"key": "star_shot",      "name": "Star Shot",      "type": "magic",    "mult": 1.2, "desc": "Flicks a tiny star"},
    ],
    "toxin": [
        {"key": "bite",           "name": "Bite",           "type": "physical", "mult": 1.1, "desc": "A quick venomous bite"},
        {"key": "acid_drop",      "name": "Acid Drop",      "type": "magic",    "mult": 1.2, "desc": "Drips a drop of corrosive acid"},
    ],
    "forge": [
        {"key": "iron_bash",      "name": "Iron Bash",      "type": "physical", "mult": 1.1, "desc": "A heavy metallic bash"},
        {"key": "cinder_toss",    "name": "Cinder Toss",   "type": "magic",    "mult": 1.2, "desc": "Flicks hot embers"},
    ],
    "phantom": [
        {"key": "spirit_scratch", "name": "Spirit Scratch", "type": "physical", "mult": 1.1, "desc": "A claw from the spirit world"},
        {"key": "wisp",           "name": "Wisp",           "type": "magic",    "mult": 1.2, "desc": "A floating ghost flame"},
    ],
    "tide": [
        {"key": "splash_slap",    "name": "Splash Slap",   "type": "physical", "mult": 1.1, "desc": "A wet slap of water"},
        {"key": "water_drop",     "name": "Water Drop",    "type": "magic",    "mult": 1.2, "desc": "A concentrated droplet"},
    ],
}

# ── Scroll skills (10 per element, learned from scrolls) ──────────────────────
# Rarities: 3 common · 3 uncommon · 2 rare · 2 legendary per element

SKILLS = {
    # ── Void ──────────────────────────────────────────────────────────────────
    "void_slash":          {"name": "Void Slash",          "element": "void",    "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "A slash of dark energy"},
    "dark_bite":           {"name": "Dark Bite",           "element": "void",    "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "Bites with dark-infused fangs"},
    "null_swipe":          {"name": "Null Swipe",          "element": "void",    "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A swipe that erases light"},
    "shadow_pulse":        {"name": "Shadow Pulse",        "element": "void",    "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A burst of pulsing shadow"},
    "dark_wave":           {"name": "Dark Wave",           "element": "void",    "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A wave of crushing darkness"},
    "void_shroud":         {"name": "Void Shroud",         "element": "void",    "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "Wraps the enemy in void energy"},
    "void_collapse":       {"name": "Void Collapse",       "element": "void",    "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Collapses reality on the enemy"},
    "soul_drain":          {"name": "Soul Drain",          "element": "void",    "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Drains the enemy's life force"},
    "abyssal_doom":        {"name": "Abyssal Doom",        "element": "void",    "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The ultimate void strike"},
    "void_annihilation":   {"name": "Void Annihilation",   "element": "void",    "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "Erases the enemy from existence"},

    # ── Ember ─────────────────────────────────────────────────────────────────
    "ember_claw":          {"name": "Ember Claw",          "element": "ember",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A burning claw swipe"},
    "fire_bite":           {"name": "Fire Bite",           "element": "ember",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A bite that ignites on contact"},
    "scorch":              {"name": "Scorch",              "element": "ember",   "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Scorches the enemy with heat"},
    "flame_burst":         {"name": "Flame Burst",         "element": "ember",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "An eruption of flame"},
    "heat_wave":           {"name": "Heat Wave",           "element": "ember",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A wave of searing heat"},
    "ash_cloud":           {"name": "Ash Cloud",           "element": "ember",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "Smothers the enemy in hot ash"},
    "inferno_strike":      {"name": "Inferno Strike",      "element": "ember",   "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "A devastating fire attack"},
    "magma_cannon":        {"name": "Magma Cannon",        "element": "ember",   "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Fires a ball of molten rock"},
    "solar_wrath":         {"name": "Solar Wrath",         "element": "ember",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The fury of the sun"},
    "phoenix_blaze":       {"name": "Phoenix Blaze",       "element": "ember",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "A rebirth of scorching flame"},

    # ── Storm ─────────────────────────────────────────────────────────────────
    "static_jab":          {"name": "Static Jab",          "element": "storm",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A quick electric jab"},
    "thunder_clap":        {"name": "Thunder Clap",        "element": "storm",   "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "A clap that summons thunder"},
    "wind_slash":          {"name": "Wind Slash",          "element": "storm",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A blade of compressed wind"},
    "thunder_bolt":        {"name": "Thunderbolt",         "element": "storm",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A bolt of lightning"},
    "storm_gust":          {"name": "Storm Gust",          "element": "storm",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A fierce gust of storm wind"},
    "lightning_whip":      {"name": "Lightning Whip",      "element": "storm",   "rarity": "uncommon",  "type": "physical", "mult": 1.6, "desc": "A whip made of lightning"},
    "cyclone_slash":       {"name": "Cyclone Slash",       "element": "storm",   "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "A spinning wind blade"},
    "storm_strike":        {"name": "Storm Strike",        "element": "storm",   "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "A strike charged with storm energy"},
    "storm_apocalypse":    {"name": "Storm Apocalypse",    "element": "storm",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The sky tears apart"},
    "sky_splitter":        {"name": "Sky Splitter",        "element": "storm",   "rarity": "legendary", "type": "physical", "mult": 3.0, "desc": "Cleaves the heavens in two"},

    # ── Bloom ─────────────────────────────────────────────────────────────────
    "vine_whip":           {"name": "Vine Whip",           "element": "bloom",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A lashing vine strike"},
    "thorn_jab":           {"name": "Thorn Jab",           "element": "bloom",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "Jabs with a sharp thorn"},
    "seed_bomb":           {"name": "Seed Bomb",           "element": "bloom",   "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Hurls an exploding seed"},
    "petal_storm":         {"name": "Petal Storm",         "element": "bloom",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A storm of razor petals"},
    "spore_burst":         {"name": "Spore Burst",         "element": "bloom",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "Releases an explosive burst of spores"},
    "overgrowth":          {"name": "Overgrowth",          "element": "bloom",   "rarity": "uncommon",  "type": "physical", "mult": 1.6, "desc": "Smothers the enemy with vines"},
    "root_crush":          {"name": "Root Crush",          "element": "bloom",   "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "Roots erupt and crush"},
    "bloom_eruption":      {"name": "Bloom Eruption",      "element": "bloom",   "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "The earth blooms with explosive force"},
    "nature_wrath":        {"name": "Nature's Wrath",      "element": "bloom",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The forest strikes back"},
    "world_tree_wrath":    {"name": "World Tree Wrath",    "element": "bloom",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The ancient world tree awakens"},

    # ── Crystal ───────────────────────────────────────────────────────────────
    "shard_toss":          {"name": "Shard Toss",          "element": "crystal", "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "Hurls a crystal shard"},
    "crystal_bite":        {"name": "Crystal Bite",        "element": "crystal", "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "Bites with crystalline teeth"},
    "ice_shard":           {"name": "Ice Shard",           "element": "crystal", "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Fires a shard of frozen crystal"},
    "prism_beam":          {"name": "Prism Beam",          "element": "crystal", "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A focused light beam"},
    "crystal_rain":        {"name": "Crystal Rain",        "element": "crystal", "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "Rains sharp crystals down"},
    "refraction":          {"name": "Refraction",          "element": "crystal", "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "Bends light into a cutting beam"},
    "crystal_prison":      {"name": "Crystal Prison",      "element": "crystal", "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Encases enemy in crystal"},
    "gemstone_barrage":    {"name": "Gemstone Barrage",    "element": "crystal", "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "Fires a volley of gem shards"},
    "diamond_nova":        {"name": "Diamond Nova",        "element": "crystal", "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "An explosion of pure crystal"},
    "crystal_apocalypse":  {"name": "Crystal Apocalypse",  "element": "crystal", "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The world shatters into crystal"},

    # ── Cosmic ────────────────────────────────────────────────────────────────
    "stardust":            {"name": "Stardust",            "element": "cosmic",  "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Sprinkles cosmic dust"},
    "comet_strike":        {"name": "Comet Strike",        "element": "cosmic",  "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "Strikes like a falling comet"},
    "lunar_jab":           {"name": "Lunar Jab",           "element": "cosmic",  "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A jab powered by moonlight"},
    "nebula_blast":        {"name": "Nebula Blast",        "element": "cosmic",  "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A blast of nebula energy"},
    "cosmic_surge":        {"name": "Cosmic Surge",        "element": "cosmic",  "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A surge of cosmic energy"},
    "astral_wave":         {"name": "Astral Wave",         "element": "cosmic",  "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A wave from the astral plane"},
    "gravity_crush":       {"name": "Gravity Crush",       "element": "cosmic",  "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Crushes with gravity"},
    "black_hole_pull":     {"name": "Black Hole Pull",     "element": "cosmic",  "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Pulls the enemy into a black hole"},
    "big_bang":            {"name": "Big Bang",            "element": "cosmic",  "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "A miniature universe explosion"},
    "universe_collapse":   {"name": "Universe Collapse",   "element": "cosmic",  "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The universe folds in on itself"},

    # ── Toxin ─────────────────────────────────────────────────────────────────
    "acid_spit":           {"name": "Acid Spit",           "element": "toxin",   "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Spits corrosive acid"},
    "poison_bite":         {"name": "Poison Bite",         "element": "toxin",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A bite that injects poison"},
    "spore_cloud":         {"name": "Spore Cloud",         "element": "toxin",   "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Releases a toxic spore cloud"},
    "venom_strike":        {"name": "Venom Strike",        "element": "toxin",   "rarity": "uncommon",  "type": "physical", "mult": 1.6, "desc": "A venomous physical hit"},
    "toxic_spray":         {"name": "Toxic Spray",         "element": "toxin",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "Sprays a stream of toxin"},
    "miasma":              {"name": "Miasma",              "element": "toxin",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "Fills the air with poisonous gas"},
    "plague_cloud":        {"name": "Plague Cloud",        "element": "toxin",   "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "A cloud of plague"},
    "necrotic_burst":      {"name": "Necrotic Burst",      "element": "toxin",   "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "An explosion of decaying energy"},
    "death_bloom":         {"name": "Death Bloom",         "element": "toxin",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "Beautiful and deadly"},
    "pestilence":          {"name": "Pestilence",          "element": "toxin",   "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "A plague that wipes out all life"},

    # ── Forge ─────────────────────────────────────────────────────────────────
    "iron_punch":          {"name": "Iron Punch",          "element": "forge",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A heavy iron fist"},
    "metal_bash":          {"name": "Metal Bash",          "element": "forge",   "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "Bashes with a metal body"},
    "spark_clang":         {"name": "Spark Clang",         "element": "forge",   "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Clangs metal to create sparks"},
    "molten_slam":         {"name": "Molten Slam",         "element": "forge",   "rarity": "uncommon",  "type": "physical", "mult": 1.6, "desc": "Slams with molten metal"},
    "forge_smash":         {"name": "Forge Smash",         "element": "forge",   "rarity": "uncommon",  "type": "physical", "mult": 1.6, "desc": "A smithing hammer blow"},
    "steel_storm":         {"name": "Steel Storm",         "element": "forge",   "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A storm of steel fragments"},
    "forge_cannon":        {"name": "Forge Cannon",        "element": "forge",   "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "Fires a molten cannonball"},
    "magma_burst":         {"name": "Magma Burst",         "element": "forge",   "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "An eruption of magma"},
    "titanbreach":         {"name": "Titanbreach",         "element": "forge",   "rarity": "legendary", "type": "physical", "mult": 3.0, "desc": "The ultimate forge technique"},
    "iron_apocalypse":     {"name": "Iron Apocalypse",     "element": "forge",   "rarity": "legendary", "type": "physical", "mult": 3.0, "desc": "The world is crushed under iron"},

    # ── Phantom ───────────────────────────────────────────────────────────────
    "ghost_claw":          {"name": "Ghost Claw",          "element": "phantom", "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A claw from beyond"},
    "wisp_bolt":           {"name": "Wisp Bolt",           "element": "phantom", "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "A bolt of ghost fire"},
    "spirit_jab":          {"name": "Spirit Jab",          "element": "phantom", "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A jab from the spirit plane"},
    "specter_bolt":        {"name": "Specter Bolt",        "element": "phantom", "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A ghostly projectile"},
    "phantom_rush":        {"name": "Phantom Rush",        "element": "phantom", "rarity": "uncommon",  "type": "physical", "mult": 1.6, "desc": "Rushes through the enemy like a ghost"},
    "haunting_gaze":       {"name": "Haunting Gaze",       "element": "phantom", "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A gaze that chills the soul"},
    "soul_rend":           {"name": "Soul Rend",           "element": "phantom", "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "Tears at the soul"},
    "spectral_storm":      {"name": "Spectral Storm",      "element": "phantom", "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "A storm of ghost energy"},
    "phantom_eclipse":     {"name": "Phantom Eclipse",     "element": "phantom", "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "Blots out reality itself"},
    "eternal_haunting":    {"name": "Eternal Haunting",    "element": "phantom", "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "A curse that never fades"},

    # ── Tide ──────────────────────────────────────────────────────────────────
    "water_jet":           {"name": "Water Jet",           "element": "tide",    "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "A high-pressure water blast"},
    "splash_strike":       {"name": "Splash Strike",       "element": "tide",    "rarity": "common",    "type": "physical", "mult": 1.3, "desc": "Strikes with a crashing wave"},
    "current_hit":         {"name": "Current Hit",         "element": "tide",    "rarity": "common",    "type": "magic",    "mult": 1.3, "desc": "Hits with a sharp underwater current"},
    "tidal_wave":          {"name": "Tidal Wave",          "element": "tide",    "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A crushing wave"},
    "whirlpool":           {"name": "Whirlpool",           "element": "tide",    "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "Pulls the enemy into a whirlpool"},
    "sea_surge":           {"name": "Sea Surge",           "element": "tide",    "rarity": "uncommon",  "type": "magic",    "mult": 1.6, "desc": "A surge of ocean energy"},
    "deep_crush":          {"name": "Deep Crush",          "element": "tide",    "rarity": "rare",      "type": "physical", "mult": 2.1, "desc": "The pressure of the deep sea"},
    "tsunami_slam":        {"name": "Tsunami Slam",        "element": "tide",    "rarity": "rare",      "type": "magic",    "mult": 2.1, "desc": "A tsunami crashes down"},
    "leviathan_surge":     {"name": "Leviathan Surge",     "element": "tide",    "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "A surge from the ancient deep"},
    "ocean_apocalypse":    {"name": "Ocean Apocalypse",    "element": "tide",    "rarity": "legendary", "type": "magic",    "mult": 3.0, "desc": "The oceans swallow the world"},
}

SCROLL_RARITY_WEIGHTS = {
    "common": 50, "uncommon": 30, "rare": 15, "legendary": 5
}

SCROLL_SELL_PRICE = {
    "common": 200, "uncommon": 600, "rare": 1500, "legendary": 5000
}
