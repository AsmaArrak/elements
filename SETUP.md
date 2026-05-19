# Elementals Bot — Setup Guide

## Requirements
- Python 3.11 or newer
- A Discord account with a bot application

---

## Step 1 — Create a Discord Bot

1. Go to https://discord.com/developers/applications
2. Click **New Application** → give it a name (e.g. "Elementals")
3. Go to the **Bot** tab → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - ✅ **Server Members Intent**
5. Click **Reset Token** → copy the token (keep it secret!)

---

## Step 2 — Invite the Bot to Your Server

On the **OAuth2 → URL Generator** page:
- Scopes: `bot` + `applications.commands`
- Bot Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`

Open the generated URL in your browser and invite the bot.

---

## Step 3 — Configure the Bot

In the `evolife` folder (where `bot.py` lives):

```bash
# Copy the example env file
copy .env.example .env
```

Open `.env` and fill in:
```
BOT_TOKEN=your_token_here
GUILD_ID=your_server_id_here   # Right-click your server → Copy Server ID
```

`GUILD_ID` is optional but recommended during setup — it makes slash commands appear instantly.
Without it, global commands can take up to 1 hour to propagate.

---

## Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 5 — Run the Bot

```bash
python bot.py
```

You should see:
```
  Loaded: cogs.setup
  Loaded: cogs.start
  ...
  ✅ Elementals#1234 is online!
```

---

## Step 6 — Configure Your Server

In Discord, use these admin commands to set up channels:

```
/setup drops #game-channel
/setup announcements #general
```

- **Drops channel**: where random items will spawn every 20–60 minutes
- **Announcements**: where Mega Evolution news gets broadcasted

---

## Playing the Game

```
/start          — Choose your element and get your first egg
/feed apple     — Feed it! (first feeding hatches the egg instantly)
/profile        — Check your pet
/daily          — Claim daily bonus (100 coins + 30 XP)
/expedition 6   — Send your pet out for 6 hours to find loot
/collect        — Get your pet and loot back
/shop           — Buy food with coins
/battle @someone — Challenge another player
/setup help     — Full command list
```

---

## Evolution Path

| Stage | Requirement |
|-------|-------------|
| Egg → Evo 1 | **First feeding** (instant!) |
| Evo 1 → Evo 2 | Level 35 + Uncommon Evo Stone for your element |
| Evo 2 → Evo 3 | Level 70 + Rare Evo Stone for your element |
| Evo 3 → Mega | Level 100 + Exploration 100/100 + Mega Stone |

Evo Stones drop from expeditions and channel drops.
Mega Stones **only** drop from expeditions with maxed Exploration.

---

## File Structure

```
evolife/
├── bot.py            ← Start the bot here
├── config.py         ← Game constants (tweak XP, timers, etc.)
├── database.py       ← Database layer
├── requirements.txt
├── .env              ← Your token (DO NOT share)
├── elementals.db     ← Created automatically on first run
├── cogs/             ← Command modules
├── game/             ← Game logic
├── void/             ← Element image assets
├── ember/
├── ... (other elements)
└── food/             ← Food images
```

---

## Tuning the Game

All timing and XP values live in `config.py`:

| Constant | Default | Effect |
|----------|---------|--------|
| `PASSIVE_XP_PER_HOUR` | 5 | XP every pet earns per hour |
| `DROP_INTERVAL_MIN/MAX` | 20–60 min | How often items spawn |
| `xp_for_next_level()` | 100–1800 | XP curve per level range |
| `EXPLORATION_GAIN` | 2–55 | Exploration earned per expedition |
| `FISH_COOLDOWN_MINUTES` | 30 | Fishing cooldown |
| `DIG_COOLDOWN_MINUTES` | 45 | Digging cooldown |
