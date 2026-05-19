# Elementals — Discord Monster-Raising Bot

A Discord bot where players hatch elemental pets, raise them through four evolution stages, battle each other, and compete on the leaderboard.

---

## What is Elementals?

Players choose an elemental egg, feed and level it up, send it on expeditions for loot, and eventually evolve it all the way to a powerful **Mega** form. Ten elements, two variants each, fully illustrated with custom art.

---

## Elements

| Element | Display | Emoji | Strong Against |
|---------|---------|-------|----------------|
| Void | Void | 🌑 | Phantom, Cosmic |
| Ember | Ember | 🔥 | Bloom, Crystal |
| Storm | Storm | ⚡ | Tide, Forge |
| Bloom | Bloom | 🌿 | Tide, Phantom |
| Crystal | Crystal | 💎 | Storm, Void |
| Cosmic | Cosmic | ✨ | Void, Phantom |
| Toxin | Plague | ☠️ | Bloom, Tide |
| Forge | Forge | ⚙️ | Crystal, Cosmic |
| Phantom | Phantom | 👻 | Forge, Plague |
| Tide | Tide | 🌊 | Ember, Forge |

---

## Evolution Path

```
🥚 Egg  →  Feed 3 times  →  Evo 1
Evo 1   →  Level 35 + Uncommon Evo Stone  →  Evo 2
Evo 2   →  Level 70 + Rare Evo Stone      →  Evo 3
Evo 3   →  Level 100 + Exploration 100/100 + Mega Stone  →  ⭐ MEGA
```

Each element has **2 variants** (same stats, different names and art), assigned randomly on `/start`.

---

## Commands

### Getting Started
| Command | Description |
|---------|-------------|
| `/start` | Browse all eggs and choose your element |
| `/profile [@user]` | View your profile or another player's |
| `/pet` | See full detailed stats and caps |
| `/rename <name>` | Give your active pet a custom name |
| `/activepet` | Switch which of your pets is active |
| `/restart` | Delete everything and start over |

### Feeding & Items
| Command | Description |
|---------|-------------|
| `/feed` | Pick a pet and food from your inventory |
| `/inventory` | View all your items |
| `/use <stone>` | Use an evo stone or stat item on your pet |
| `/claim` | Grab a randomly spawned drop from the channel |
| `/train` | Daily training — boost a random stat + XP (20h cooldown) |

### Expeditions
| Command | Description |
|---------|-------------|
| `/expedition <1/6/12/24>` | Send your pet out for loot (hours) |
| `/expedition status` | Check how long until your pet returns |
| `/collect` | Collect your pet and loot when it returns |

### Battle
| Command | Description |
|---------|-------------|
| `/battle @user` | Challenge someone to PvP |
| `/battlelog` | View your recent battle history |

### Economy
| Command | Description |
|---------|-------------|
| `/shop` | Browse the item shop |
| `/buy <item>` | Purchase an item |
| `/sell <item> [qty]` | Sell items for coins |
| `/balance` | Check your coin balance |
| `/daily` | Claim daily bonus (100 coins + 30 XP) |
| `/give @user <amount>` | Give coins to someone |
| `/trade @user` | Propose an item trade |

### Minigames
| Command | Description |
|---------|-------------|
| `/fish` | Cast a line for coins & items (30min cooldown) |
| `/dig` | Excavate for buried treasure (45min cooldown) |
| `/trivia` | Answer a question to win coins |
| `/leaderboard` | See the top pets on the server |

---

## Setup (Server Admins)

1. Invite the bot to your server
2. Run `/setup drops #channel` to set where item drops appear
3. Run `/setup announcements #channel` to set where Mega Evolution announcements go
4. Run `/setup info` to confirm your configuration

Item drops spawn automatically every 20–60 minutes and expire after 10 minutes if unclaimed.

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
# Fill in your BOT_TOKEN in .env
python bot.py
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Your Discord bot token |
| `GUILD_ID` | Optional | Guild ID for instant slash command sync during development |
| `ADMIN_IDS` | Optional | Comma-separated Discord user IDs for `/admin` commands |

### Admin Commands

Users listed in `ADMIN_IDS` can use:
- `/admin drop` — Force a drop in the drops channel right now
- `/admin give @user <item> [qty]` — Give a player any item
- `/admin coins @user <amount>` — Add or remove coins
- `/admin xp @user <amount>` — Add XP to a player's active pet
- `/admin announce <message>` — Post to the announcements channel
- `/admin stats` — View server-wide game statistics

---

## Hosting on Railway

1. Push this repo to GitHub
2. Create a new project on [Railway](https://railway.app) and connect the repo
3. Add `BOT_TOKEN`, `GUILD_ID`, and `ADMIN_IDS` as environment variables in the Railway dashboard
4. Railway auto-deploys on every push — no server management needed
