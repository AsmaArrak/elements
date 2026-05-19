# Elementals — Discord Monster-Raising Bot

A Discord bot where players hatch elemental pets, raise them through four evolution stages, equip armor, learn skills, battle each other, and compete on the leaderboard. Ten elements, two variants each, fully illustrated with custom art.

---

## Table of Contents

- [What is Elementals?](#what-is-elementals)
- [Elements](#elements)
- [Evolution Path](#evolution-path)
- [Stats](#stats)
- [All Commands](#all-commands)
- [Systems Overview](#systems-overview)
- [Server Setup](#server-setup)
- [Self-Hosting](#self-hosting)
- [Admin Commands](#admin-commands)
- [Hosting on Railway](#hosting-on-railway)

---

## What is Elementals?

Players pick an elemental egg, feed and level it up, send it on expeditions for loot, equip armor, teach it skills from scrolls, and evolve it all the way to a powerful **Mega** form. Everything is driven by slash commands and interactive Discord menus — no prefixes needed.

---

## Elements

| Element | Display | Emoji | Strong Against |
|---------|---------|-------|----------------|
| void | Void | 🌑 | Phantom, Cosmic |
| ember | Ember | 🔥 | Bloom, Crystal |
| storm | Storm | ⚡ | Tide, Forge |
| bloom | Bloom | 🌿 | Tide, Phantom |
| crystal | Crystal | 💎 | Storm, Void |
| cosmic | Cosmic | ✨ | Void, Phantom |
| toxin | Plague | ☠️ | Bloom, Tide |
| forge | Forge | ⚙️ | Crystal, Cosmic |
| phantom | Phantom | 👻 | Forge, Plague |
| tide | Tide | 🌊 | Ember, Forge |

Each element has **2 variants** with different names and art but identical base stats. Assigned randomly on `/start`. A **pity system** guarantees that picking the same element twice in a row gives you the other variant.

---

## Evolution Path

```
🥚 Egg  ──( Feed 3× )──►  Evo 1
Evo 1   ──( Level 35 + Uncommon Evo Stone )──►  Evo 2
Evo 2   ──( Level 70 + Rare Evo Stone )──►  Evo 3
Evo 3   ──( Level 100 + Exploration 100 + Mega Stone )──►  ⭐ MEGA
```

- **Evo Stones** drop from expeditions and occasionally from channel drops
- **Mega Stones** only drop from expeditions when your pet's **Exploration** stat is at 100
- Evolution embeds show the stone's art as a thumbnail alongside the newly evolved pet

---

## Stats

| Stat | Raised By |
|------|-----------|
| HP | Apple 🍎, Potion 🧪, Life Crystal |
| ATK | Carrot 🥕, Chicken 🍗, Ancient Fang 🦷, Dragonfruit 🐉 |
| DEF | Bread 🍞, Steak 🥩, Iron Scrap 🔩, Ironbark 🪵 |
| SPD | Grape 🍇, Noodles 🍜, Swift Feather 🪶, Windleaf 🍃 |
| MGK | Cheese 🧀, Mushroom 🍄, Crystal Shard 🔷, Honey 🍯, Cake 🎂 |
| RES | Fish 🐟, Berry 🫐, Mystic Root 🌱, Starfruit ⭐ |

**Food rarities:** Common (shop 500c) · Uncommon (shop 800c) · Rare (expedition drops only)

**Stat items** give a permanent flat bonus. Each stat has a cap based on base stat and level.

**Exploration** increases with every expedition (3–35 points depending on duration). Reaching 100 unlocks Mega Stone drops from expeditions.

---

## All Commands

### Getting Started
| Command | Description |
|---------|-------------|
| `/start` | Browse all 10 eggs and choose your element |
| `/profile [@user]` | View your or another player's active pet and coins |
| `/pet` | Full stat sheet: base + bonuses, caps, exploration, equipped armor |
| `/rename <name>` | Give your active pet a nickname (leave blank to reset) |
| `/restart` | Delete all your data and start over |

### Feeding & Items
| Command | Description |
|---------|-------------|
| `/feed` | Dropdown menu — pick a pet and a food from your bag |
| `/inventory` | View all items grouped by type with descriptions |
| `/use <item> [element]` | Use an evo stone or stat item on your active pet |
| `/claim` | Grab a randomly spawned drop in the channel |
| `/train` | Daily training — boost a random stat + XP (20h cooldown) |

### Expeditions
| Command | Description |
|---------|-------------|
| `/expedition 30m` | Quick 30-minute run — light loot |
| `/expedition 1h30` | 1.5-hour expedition |
| `/expedition 4h` | 4-hour expedition — guaranteed rare drop |
| `/expedition 6h` | Best loot and highest rarity chances |
| `/expedition status` | Check all active expedition timers |
| `/expedition cancel` | Recall a pet early — **no loot awarded** |
| `/collect` | Collect your returned pet and all loot |

**Loot by duration:**

| Duration | Items | Guaranteed | Scroll chance | Armor chance |
|----------|-------|------------|---------------|--------------|
| 30m | 3–4 | — | 5% | 5% |
| 1h30 | 4–5 | 1 uncommon | 12% | 15% |
| 4h | 5–7 | 1 rare | 28% | 38% |
| 6h | 6–8 | 2 rares | 50% | 60% |

Legendary loot only drops at 6h **and** only if Exploration is 100.

### Armor
| Command | Description |
|---------|-------------|
| `/armor` | View your full armor collection (grouped by rarity) |
| `/equip` | Equip a piece of armor to one of your pets |
| `/sellarmor <id>` | Sell armor for coins (common 150 · uncommon 400 · rare 1000 · legendary 3000) |

Armor adds flat stat bonuses visible in `/pet`. Four rarities: ⚪ Common · 🟢 Uncommon · 🟣 Rare · 🟡 Legendary.

### Skills
| Command | Description |
|---------|-------------|
| `/learn` | Teach your pet a skill from a scroll in your inventory |
| `/skills` | View all your pets' learned skills |
| `/forgetskill <name>` | Remove a skill from a pet to free a slot |
| `/sellscroll <name>` | Sell a scroll for coins |

- Each pet can learn up to **4 skills**
- 40 skills total across all 10 elements, 4 rarities each (common/uncommon/rare/legendary)
- Multipliers: common 1.3× · uncommon 1.6× · rare 2.1× · legendary 3.0×
- Each element can learn from itself and 2 compatible elements (not all elements)
- Skills are used during battle alongside normal attacks

### Battle
| Command | Description |
|---------|-------------|
| `/setparty` | Set your party order — use ⬆⬇ buttons, first pet starts battles |
| `/battle @user` | Challenge someone to PvP turn-based combat |
| `/battlelog` | View your recent battle history |

Battle is turn-based. Each turn you choose: **Attack** · **Skill** (pick from learned skills) · **Defend** · **Item**. Type advantages deal 1.5× damage. Speed determines who goes first.

### Economy
| Command | Description |
|---------|-------------|
| `/shop` | Browse available food and stat items |
| `/buy <item>` | Purchase an item with coins |
| `/sell <item> [qty]` | Sell items back for coins |
| `/balance` | Check your coin balance |
| `/daily` | Daily login bonus — 100 coins + 30 XP (24h cooldown) |
| `/give @user <amount>` | Transfer coins to another player |
| `/trade @user offer:<item> request:<item>` | Propose an item trade |

### Minigames
| Command | Description |
|---------|-------------|
| `/fish` | Cast a line for coins and items (10min cooldown) |
| `/dig` | Excavate for buried treasure (10min cooldown) |
| `/trivia` | Answer a question for coins — 80+ questions, no cooldown |
| `/leaderboard` | Top 10 highest-level pets on the server |

---

## Systems Overview

### Channel Drops
Random items spawn in the configured drops channel every **20–60 minutes** and expire after **12 minutes** if unclaimed. Use `/claim` to grab one. First person to claim wins it.

### Passive XP
All non-egg pets that aren't on expedition earn **passive XP every hour** automatically — no action needed.

### Exploration
Tracked per pet from 0–100. Increases each time the pet returns from an expedition:

| Duration | Exploration Gained |
|----------|--------------------|
| 30m | +3 |
| 1h30 | +8 |
| 4h | +20 |
| 6h | +35 |

Visible in `/pet` with a progress note. At 100/100 Mega Stones become available in expedition loot.

### Variant Pity
When picking a starter egg, if you've chosen the same element before and got variant 1, your next pick of that element is **guaranteed** to be variant 2 (and vice versa). After the pity triggers it resets to 50/50.

---

## Server Setup

Run these once as a server admin:

```
/setup drops #channel        — Set the channel for automatic item drops
/setup announcements #channel — Set the channel for Mega Evolution announcements
/setup info                  — Confirm your current configuration
```

Use `/admin drop` to immediately test that drops are working.

---

## Self-Hosting

### Requirements
- Python 3.11+
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))

### Installation

```bash
git clone https://github.com/AsmaArrak/elements.git
cd elements
pip install -r requirements.txt
cp .env.example .env
# Fill in BOT_TOKEN (and optionally GUILD_ID, ADMIN_IDS) in .env
python bot.py
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Your Discord bot token |
| `DB_PATH` | Optional | Custom path for the SQLite database file |
| `GUILD_ID` | Optional | Guild ID for instant slash command sync during development |
| `ADMIN_IDS` | Optional | Comma-separated Discord user IDs allowed to use `/admin` |

---

## Admin Commands

Users listed in `ADMIN_IDS` can use:

| Command | Description |
|---------|-------------|
| `/admin drop` | Force a drop in the drops channel immediately |
| `/admin give @user <item> [qty] [element]` | Give any item to a player |
| `/admin coins @user <amount>` | Add or remove coins (negative to deduct) |
| `/admin xp @user <amount>` | Add XP to a player's active pet |
| `/admin announce <message>` | Post to the announcements channel |
| `/admin stats` | Server-wide stats (players, hatched pets, megas, expeditions) |
| `/admin backup` | DM yourself the database file |
| `/admin restore <file>` | Overwrite the database from a .db attachment |

> **Tip:** Before every Railway redeploy, run `/admin backup`. After the deploy, run `/admin restore` with the file it DM'd you to restore your data.

---

## Hosting on Railway

1. Push this repo to GitHub
2. Create a new project on [Railway](https://railway.app) and connect the repo
3. Add environment variables in the Railway dashboard: `BOT_TOKEN`, `ADMIN_IDS`, optionally `GUILD_ID`
4. **Turn off auto-deploy** in Railway Settings → Source to prevent accidental data loss on every push
5. To deploy a new version: Settings → Source → "Check for updates"

> ⚠️ Railway's free tier does not include persistent volumes. The database lives on the container's ephemeral filesystem. Always run `/admin backup` before deploying and `/admin restore` after to preserve player data.
