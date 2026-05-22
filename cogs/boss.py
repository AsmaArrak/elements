import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import random
from datetime import datetime, timezone, time as dt_time, timedelta
import os

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_EMOJIS, ELEMENT_COLORS, PET_NAMES,
    TYPE_ADVANTAGE, RARITY_EMOJIS, get_pet_image,
)
from game.stats import effective_stats, hp_bar
from game.skills import SKILLS, DEFAULT_ATTACKS
from game.dungeon_loot import generate_armor_piece

# ── In-memory boss sessions: user_id → BossSession ────────────────────────────
active_boss_sessions: dict[int, "BossSession"] = {}

# ── Boss definitions (one per element, rotated weekly by ISO week number) ─────
BOSS_DEFINITIONS = [
    {
        "name": "Pyroclasm Prime", "element": "ember", "emoji": "🔥",
        "description": "An ancient fire titan whose breath melts entire mountain ranges.",
        "base_atk": 180, "base_mgk": 150, "base_def": 80, "base_spd": 50, "base_res": 60,
        "abilities": [
            {"name": "Inferno Sweep", "type": "physical", "mult": 1.8},
            {"name": "Magma Burst",   "type": "magic",    "mult": 2.2},
            {"name": "Flame Crash",   "type": "physical", "mult": 2.0},
        ],
    },
    {
        "name": "Stormreign",      "element": "storm", "emoji": "⚡",
        "description": "A colossal storm dragon commanding lightning from the heavens.",
        "base_atk": 160, "base_mgk": 200, "base_def": 60, "base_spd": 100, "base_res": 70,
        "abilities": [
            {"name": "Thunder Crash", "type": "magic",    "mult": 2.4},
            {"name": "Gale Strike",   "type": "physical", "mult": 1.9},
            {"name": "Storm Surge",   "type": "magic",    "mult": 2.0},
        ],
    },
    {
        "name": "Verdant Colossus", "element": "bloom", "emoji": "🌿",
        "description": "A towering ancient treant that bends the forest to its will.",
        "base_atk": 140, "base_mgk": 160, "base_def": 120, "base_spd": 30, "base_res": 100,
        "abilities": [
            {"name": "Root Crush",    "type": "physical", "mult": 1.7},
            {"name": "Spore Blast",   "type": "magic",    "mult": 2.1},
            {"name": "Thorn Barrage", "type": "physical", "mult": 2.0},
        ],
    },
    {
        "name": "Gemlord Eternal",  "element": "crystal", "emoji": "💎",
        "description": "A crystalline behemoth with walls of gemstone for armor.",
        "base_atk": 130, "base_mgk": 170, "base_def": 160, "base_spd": 25, "base_res": 140,
        "abilities": [
            {"name": "Crystal Shatter", "type": "magic",    "mult": 2.3},
            {"name": "Gem Slam",        "type": "physical", "mult": 1.8},
            {"name": "Prism Beam",      "type": "magic",    "mult": 2.1},
        ],
    },
    {
        "name": "Galaxorn",         "element": "cosmic", "emoji": "✨",
        "description": "A cosmic horror that drifts in from the void between stars.",
        "base_atk": 150, "base_mgk": 210, "base_def": 70, "base_spd": 80, "base_res": 90,
        "abilities": [
            {"name": "Star Collapse", "type": "magic",    "mult": 2.5},
            {"name": "Void Ray",      "type": "magic",    "mult": 2.2},
            {"name": "Meteor Smash",  "type": "physical", "mult": 2.0},
        ],
    },
    {
        "name": "Pestilorn",        "element": "toxin", "emoji": "☠️",
        "description": "A plague-ridden abomination that poisons everything it touches.",
        "base_atk": 145, "base_mgk": 190, "base_def": 75, "base_spd": 70, "base_res": 80,
        "abilities": [
            {"name": "Plague Breath", "type": "magic",    "mult": 2.3},
            {"name": "Venom Strike",  "type": "physical", "mult": 1.9},
            {"name": "Blight Surge",  "type": "magic",    "mult": 2.1},
        ],
    },
    {
        "name": "Titanforge",       "element": "forge", "emoji": "⚙️",
        "description": "A mechanical colossus forged from living, semi-sentient metal.",
        "base_atk": 210, "base_mgk": 120, "base_def": 150, "base_spd": 35, "base_res": 70,
        "abilities": [
            {"name": "Iron Crush",   "type": "physical", "mult": 2.1},
            {"name": "Gear Grind",   "type": "physical", "mult": 2.0},
            {"name": "Steam Cannon", "type": "magic",    "mult": 1.9},
        ],
    },
    {
        "name": "Phantomking",      "element": "phantom", "emoji": "👻",
        "description": "The ruler of spirits who exists between life and death.",
        "base_atk": 155, "base_mgk": 200, "base_def": 55, "base_spd": 110, "base_res": 85,
        "abilities": [
            {"name": "Soul Rend",      "type": "magic",    "mult": 2.4},
            {"name": "Spectral Slash", "type": "physical", "mult": 2.0},
            {"name": "Terror Pulse",   "type": "magic",    "mult": 2.2},
        ],
    },
    {
        "name": "Tidalwarden",      "element": "tide", "emoji": "🌊",
        "description": "An ancient sea leviathan that controls the very tides of fate.",
        "base_atk": 165, "base_mgk": 175, "base_def": 100, "base_spd": 65, "base_res": 110,
        "abilities": [
            {"name": "Tidal Crash",  "type": "physical", "mult": 1.9},
            {"name": "Abyssal Beam", "type": "magic",    "mult": 2.3},
            {"name": "Whirlpool",    "type": "magic",    "mult": 2.0},
        ],
    },
    {
        "name": "Abyssarex",        "element": "void", "emoji": "🌑",
        "description": "A void entity that erases existence from reality itself.",
        "base_atk": 170, "base_mgk": 200, "base_def": 90, "base_spd": 75, "base_res": 95,
        "abilities": [
            {"name": "Void Erasure",     "type": "magic",    "mult": 2.5},
            {"name": "Dark Matter Slam", "type": "physical", "mult": 2.0},
            {"name": "Null Storm",       "type": "magic",    "mult": 2.2},
        ],
    },
]

# ── Reward tiers: (rank_min, rank_max, coins, armor_count, armor_rarity, scroll_rarity)
BOSS_REWARD_TIERS = [
    (1,  1,   35000, 3, "legendary", "legendary"),
    (2,  2,   20000, 2, "rare",      "rare"),
    (3,  3,   12000, 1, "rare",      "rare"),
    (4,  999, 8000,  1, "uncommon",  "common"),
]


def get_current_boss_def() -> dict:
    """Return this week's boss by ISO week number."""
    week = datetime.now(timezone.utc).isocalendar()[1]
    return BOSS_DEFINITIONS[week % len(BOSS_DEFINITIONS)]


def _get_reward_tier(rank: int) -> tuple[int, int, str, str]:
    """Returns (coins, armor_count, armor_rarity, scroll_rarity)."""
    for tier_min, tier_max, coins, armor_count, armor_rarity, scroll_rarity in BOSS_REWARD_TIERS:
        if tier_min <= rank <= tier_max:
            return coins, armor_count, armor_rarity, scroll_rarity
    return 150, 1, "uncommon", "common"


def _pick_random_scroll(scroll_rarity: str) -> str | None:
    """Pick a random skill key of the given rarity."""
    pool = [k for k, v in SKILLS.items() if v.get("rarity") == scroll_rarity]
    return random.choice(pool) if pool else None


# ── Combatant & Session ────────────────────────────────────────────────────────

def _has_full_set(pet: dict) -> bool:
    pieces = pet.get("equipped_pieces", [])
    if len(pieces) < 4:
        return False
    return len({p.get("set_name") for p in pieces}) == 1


class BossCombatant:
    def __init__(self, pet: dict):
        self.pet = pet
        stats = effective_stats(pet)
        self.max_hp = stats["hp"]
        self.hp = self.max_hp
        self.stats = stats
        self.element = pet["element"]
        self.name = (
            pet.get("nickname")
            or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        )
        self.set_bonus_mult = 1.2 if _has_full_set(pet) else 1.0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, dmg: int):
        self.hp = max(0, self.hp - dmg)


class BossSession:
    def __init__(self, player_id: int, boss_id: int, boss_def: dict, pets: list[dict]):
        self.player_id = player_id
        self.boss_id = boss_id
        self.boss_def = boss_def
        self.combatants = [BossCombatant(p) for p in pets]
        self.active_idx = 0
        self.total_damage = 0
        self.turn = 1
        self.log: list[str] = []
        self.message: discord.Message | None = None
        self.pet_img_url: str | None = None

    @property
    def current(self) -> BossCombatant:
        return self.combatants[self.active_idx]

    @property
    def alive_indices(self) -> list[int]:
        return [i for i, c in enumerate(self.combatants) if c.alive]

    @property
    def all_fainted(self) -> bool:
        return all(not c.alive for c in self.combatants)


# ── Damage calculation ─────────────────────────────────────────────────────────

def calc_player_damage_to_boss(
    attacker: BossCombatant, boss_def: dict, move_info: dict
) -> tuple[int, str]:
    """Player pet attacks the boss. Returns (damage, log_line)."""
    move_type = move_info.get("move", "default")
    boss_def_val = boss_def["base_def"]
    boss_res_val = boss_def["base_res"]
    boss_element = boss_def["element"]

    if move_type == "default":
        att_type = move_info.get("attack_type", "physical")
        mult = move_info.get("mult", 1.1)
        name = move_info.get("name", "Attack")
        skill_element = attacker.element
        if att_type == "physical":
            base = max(1, attacker.stats["atk"] - boss_def_val // 2)
        else:
            base = max(1, attacker.stats["mgk"] - boss_res_val // 2)
    else:
        skill_key = move_info.get("skill_key", "")
        skill = SKILLS.get(skill_key, {})
        mult = skill.get("mult", 1.3)
        name = skill.get("name", skill_key)
        att_type = skill.get("type", "physical")
        skill_element = skill.get("element", attacker.element)
        if att_type == "physical":
            base = max(1, attacker.stats["atk"] - boss_def_val // 2)
        else:
            base = max(1, attacker.stats["mgk"] - boss_res_val // 2)

    se = ""
    if boss_element in TYPE_ADVANTAGE.get(skill_element, []):
        base = int(base * 1.5)
        se = " ✨ *Super effective!*"

    # Apply 4-piece armor set bonus (+20% magic DMG) if applicable
    is_magic = (move_type == "default" and move_info.get("attack_type") != "physical") or \
               (move_type != "default" and SKILLS.get(move_info.get("skill_key",""), {}).get("type") != "physical")
    set_mult = attacker.set_bonus_mult if is_magic else 1.0
    set_note = " 🛡️✨" if set_mult > 1.0 else ""

    dmg = max(1, int(base * mult * set_mult * random.uniform(0.88, 1.12)))
    log_line = f"⚔️ **{attacker.name}** used **{name}** for **{dmg}** damage!{se}{set_note}"
    return dmg, log_line


def calc_boss_damage_to_pet(
    boss_def: dict, defender: BossCombatant
) -> tuple[int, str]:
    """Boss attacks player pet. Returns (damage, log_line). Also applies damage."""
    ability = random.choice(boss_def["abilities"])
    boss_element = boss_def["element"]

    if ability["type"] == "physical":
        base = max(1, boss_def["base_atk"] - defender.stats["def"] // 2)
    else:
        base = max(1, boss_def["base_mgk"] - defender.stats["res"] // 2)

    se = ""
    if defender.element in TYPE_ADVANTAGE.get(boss_element, []):
        base = int(base * 1.5)
        se = " ✨ *Super effective!*"

    dmg = max(1, int(base * ability["mult"] * random.uniform(0.88, 1.12)))
    defender.take_damage(dmg)
    log_line = f"💥 **{boss_def['name']}** used **{ability['name']}** for **{dmg}** damage!{se}"
    return dmg, log_line


async def _fetch_server_total(boss_id: int) -> int:
    try:
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT SUM(damage) FROM boss_damage_log WHERE boss_id=?", (boss_id,)
            ) as cur:
                row = await cur.fetchone()
                return row[0] or 0
    except Exception:
        return 0


async def end_boss_session(session: BossSession):
    """Save session damage to DB and remove from active_boss_sessions."""
    from config import PLAYER_XP_SOURCES
    active_boss_sessions.pop(session.player_id, None)
    if session.total_damage <= 0:
        return
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute(
            """INSERT INTO boss_damage_log(boss_id, player_id, damage) VALUES(?,?,?)
               ON CONFLICT(boss_id, player_id) DO UPDATE SET damage = damage + excluded.damage""",
            (session.boss_id, session.player_id, session.total_damage),
        )
        await conn.execute(
            "UPDATE boss_battles SET total_damage = total_damage + ? WHERE id = ?",
            (session.total_damage, session.boss_id),
        )
        # Award player XP for participating in this session
        session_xp = PLAYER_XP_SOURCES.get("boss_session", 40)
        await db.add_player_xp(conn, session.player_id, session_xp)
        await conn.commit()


# ── Embed builder ──────────────────────────────────────────────────────────────

def build_boss_embed(session: BossSession, server_total: int = 0) -> discord.Embed:
    boss = session.boss_def
    color = ELEMENT_COLORS.get(boss["element"], 0xE74C3C)
    pet = session.current

    embed = discord.Embed(
        title=f"{boss['emoji']} BOSS RAID — {boss['name']}",
        description=(
            f"*{boss['description']}*\n"
            f"⚠️ **This boss cannot be defeated** — deal as much damage as you can!"
        ),
        color=color,
    )

    elem_display = ELEMENT_DISPLAY.get(boss["element"], boss["element"].title())
    embed.add_field(
        name=f"{boss['emoji']} {boss['name']}",
        value=f"Element: **{elem_display}**\n🛡️ **Unkillable Raid Boss**",
        inline=True,
    )

    embed.add_field(
        name=f"🐾 {pet.name}",
        value=(
            f"HP: `{hp_bar(pet.hp, pet.max_hp, 12)}` {pet.hp}/{pet.max_hp}\n"
            f"ATK {pet.stats['atk']} · MGK {pet.stats['mgk']} · SPD {pet.stats['spd']}"
        ),
        inline=True,
    )

    party_parts = []
    for i, c in enumerate(session.combatants):
        if not c.alive:
            party_parts.append(f"💀 ~~{c.name}~~")
        elif i == session.active_idx:
            party_parts.append(f"**► {c.name}**")
        else:
            party_parts.append(c.name)
    embed.add_field(name="🐾 Party", value=" · ".join(party_parts), inline=False)

    embed.add_field(name="💥 Your Damage", value=f"**{session.total_damage:,}**", inline=True)
    embed.add_field(name="🌍 Server Total", value=f"**{server_total:,}**", inline=True)
    embed.add_field(name="⏱️ Turn", value=str(session.turn), inline=True)

    log_lines = session.log[-5:]
    if log_lines:
        embed.add_field(name="📜 Battle Log", value="\n".join(log_lines), inline=False)

    if session.pet_img_url:
        embed.set_thumbnail(url=session.pet_img_url)

    embed.set_footer(text="Turn " + str(session.turn) + " · Use 🏃 Flee to save progress anytime!")
    return embed


# ── Boss Battle View ───────────────────────────────────────────────────────────

class BossBattleView(discord.ui.View):
    def __init__(self, session: BossSession):
        super().__init__(timeout=120)
        self.session = session

    async def _execute_turn(self, action: dict):
        """Process one full turn: player attacks, boss retaliates. Updates main message."""
        session = self.session
        logs = []

        # Player attacks boss
        p_dmg, p_log = calc_player_damage_to_boss(session.current, session.boss_def, action)
        session.total_damage += p_dmg
        logs.append(p_log)

        # Boss retaliates
        _b_dmg, b_log = calc_boss_damage_to_pet(session.boss_def, session.current)
        logs.append(b_log)

        session.log.extend(logs)

        # Handle pet fainting
        if not session.current.alive:
            fainted_name = session.current.name
            session.log.append(f"💀 **{fainted_name}** fainted!")
            alive = session.alive_indices
            if alive:
                session.active_idx = alive[0]
                session.log.append(f"➡️ **{session.current.name}** entered the battle!")

        session.turn += 1

        server_total = await _fetch_server_total(session.boss_id)

        if session.all_fainted:
            await end_boss_session(session)
            embed = build_boss_embed(session, server_total)
            embed.color = 0x888888
            embed.add_field(
                name="💀 All Pets Fainted!",
                value=(
                    f"Your raid session is over!\n"
                    f"Total damage dealt: **{session.total_damage:,}**\n"
                    f"*Rewards distributed at the end of the weekend!*"
                ),
                inline=False,
            )
            if session.message:
                await session.message.edit(embed=embed, view=None)
            return

        embed = build_boss_embed(session, server_total)
        new_view = BossBattleView(session)
        if session.message:
            await session.message.edit(embed=embed, view=new_view)

    @discord.ui.button(label="⚔️ Moves", style=discord.ButtonStyle.danger, row=0)
    async def moves_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.player_id:
            await interaction.response.send_message("This isn't your battle!", ephemeral=True)
            return

        session = self.session
        current = session.current

        options = []
        move_map: dict[str, tuple] = {}

        for atk in DEFAULT_ATTACKS.get(current.element, []):
            val = f"default:{atk['key']}"
            options.append(discord.SelectOption(
                label=atk["name"], value=val,
                description=f"{'ATK' if atk['type'] == 'physical' else 'MGK'} · {atk['mult']}x · {atk.get('desc', '')}",
                emoji="⚔️" if atk["type"] == "physical" else "✨",
            ))
            move_map[val] = ("default", atk)

        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT skill_key FROM pet_skills WHERE pet_id=?", (current.pet["id"],)
            ) as cur:
                learned = [r[0] for r in await cur.fetchall()]

        for sk_key in learned:
            s = SKILLS.get(sk_key, {})
            r_emoji = RARITY_EMOJIS.get(s.get("rarity", ""), "⚪")
            val = f"skill:{sk_key}"
            options.append(discord.SelectOption(
                label=s.get("name", sk_key), value=val,
                description=f"{s.get('mult', 1.0)}x {s.get('type', 'physical').upper()} · {s.get('rarity', '').title()}",
                emoji=r_emoji,
            ))
            move_map[val] = ("skill", s, sk_key)

        if not options:
            await interaction.response.send_message("No moves available!", ephemeral=True)
            return

        move_select = discord.ui.Select(placeholder="Choose a move...", options=options)

        async def move_callback(inter: discord.Interaction):
            if inter.user.id != interaction.user.id:
                await inter.response.send_message("Not your menu!", ephemeral=True)
                return
            val = move_select.values[0]
            entry = move_map[val]
            if entry[0] == "default":
                atk = entry[1]
                action = {
                    "move": "default",
                    "name": atk["name"],
                    "attack_type": atk["type"],
                    "mult": atk["mult"],
                }
                label = atk["name"]
            else:
                _, s, sk_key = entry
                action = {"move": "skill", "skill_key": sk_key}
                label = s.get("name", sk_key)
            await inter.response.send_message(f"⚔️ **{label}** — GO!", ephemeral=True)
            await self._execute_turn(action)

        move_select.callback = move_callback
        sv = discord.ui.View(timeout=30)
        sv.add_item(move_select)
        await interaction.response.send_message("Choose a move:", view=sv, ephemeral=True)

    @discord.ui.button(label="🔄 Switch", style=discord.ButtonStyle.secondary, row=0)
    async def switch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.player_id:
            await interaction.response.send_message("This isn't your battle!", ephemeral=True)
            return
        session = self.session
        other_alive = [i for i in session.alive_indices if i != session.active_idx]
        if not other_alive:
            await interaction.response.send_message("No other alive pets to switch to!", ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=session.combatants[i].name,
                value=str(i),
                description=f"HP: {session.combatants[i].hp}/{session.combatants[i].max_hp}",
            )
            for i in other_alive
        ]

        switch_select = discord.ui.Select(placeholder="Switch to...", options=options)

        async def switch_callback(inter: discord.Interaction):
            if inter.user.id != interaction.user.id:
                await inter.response.send_message("Not your menu!", ephemeral=True)
                return
            idx = int(switch_select.values[0])
            session.active_idx = idx
            session.log.append(f"🔄 Switched to **{session.current.name}**!")
            await inter.response.send_message(
                f"🔄 Switched to **{session.current.name}**!", ephemeral=True
            )
            server_total = await _fetch_server_total(session.boss_id)
            embed = build_boss_embed(session, server_total)
            new_view = BossBattleView(session)
            if session.message:
                await session.message.edit(embed=embed, view=new_view)

        switch_select.callback = switch_callback
        sv = discord.ui.View(timeout=30)
        sv.add_item(switch_select)
        await interaction.response.send_message("Switch to:", view=sv, ephemeral=True)

    @discord.ui.button(label="🏃 Flee", style=discord.ButtonStyle.secondary, row=0)
    async def flee_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.player_id:
            await interaction.response.send_message("This isn't your battle!", ephemeral=True)
            return
        session = self.session
        total = session.total_damage
        await end_boss_session(session)
        embed = discord.Embed(
            title="🏃 Fled from the Boss!",
            description=(
                f"You retreated from **{session.boss_def['name']}**!\n"
                f"Total damage dealt: **{total:,}**\n"
                f"*Progress saved! Rewards distributed at the weekend's end.*"
            ),
            color=0x888888,
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_timeout(self):
        session = self.session
        await end_boss_session(session)
        if session.message:
            try:
                embed = build_boss_embed(session)
                embed.set_footer(text="⏰ Session timed out — damage saved!")
                await session.message.edit(embed=embed, view=None)
            except Exception:
                pass


# ── Boss Cog ───────────────────────────────────────────────────────────────────

class Boss(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.boss_spawn_task.start()
        self.boss_end_task.start()

    def cog_unload(self):
        self.boss_spawn_task.cancel()
        self.boss_end_task.cancel()

    # ── Scheduled tasks ────────────────────────────────────────────────────────

    @tasks.loop(time=dt_time(hour=10, minute=0, tzinfo=timezone.utc))
    async def boss_spawn_task(self):
        """Fires daily at 10:00 UTC — only acts on Saturdays."""
        if datetime.now(timezone.utc).weekday() != 5:
            return
        await self._spawn_boss_all_guilds()

    @tasks.loop(time=dt_time(hour=0, minute=1, tzinfo=timezone.utc))
    async def boss_end_task(self):
        """Fires daily at 00:01 UTC — only acts on Mondays."""
        if datetime.now(timezone.utc).weekday() != 0:
            return
        await self._end_boss_all_guilds()

    @boss_spawn_task.before_loop
    async def before_spawn(self):
        await self.bot.wait_until_ready()

    @boss_end_task.before_loop
    async def before_end(self):
        await self.bot.wait_until_ready()

    # ── Spawn logic ────────────────────────────────────────────────────────────

    async def _spawn_boss_all_guilds(self):
        boss_def = get_current_boss_def()
        now = datetime.now(timezone.utc)
        # End time = next Monday 00:00 UTC
        days_to_monday = (7 - now.weekday()) % 7 or 7
        end_time = (now + timedelta(days=days_to_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute("UPDATE boss_battles SET active=0 WHERE active=1")
            cur = await conn.execute(
                """INSERT INTO boss_battles(boss_name, boss_element, spawn_time, end_time, active)
                   VALUES(?,?,?,?,1)""",
                (boss_def["name"], boss_def["element"], now.isoformat(), end_time.isoformat()),
            )
            await conn.commit()

        color = ELEMENT_COLORS.get(boss_def["element"], 0xFF0000)
        embed = discord.Embed(
            title="⚔️ WEEKEND BOSS HAS APPEARED! ⚔️",
            description=(
                f"{boss_def['emoji']} **{boss_def['name']}** has emerged!\n\n"
                f"*{boss_def['description']}*\n\n"
                f"Deal as much damage as you can before Monday!\n"
                f"Use `/bossbattle` to join the raid!\n\n"
                f"🏆 **Top damage dealers earn legendary rewards!**\n"
                f"⏰ Boss disappears **Monday at midnight UTC**"
            ),
            color=color,
        )
        embed.add_field(
            name="🎁 Reward Tiers",
            value=(
                "🥇 **#1 —** 35,000 coins · 3 Legendary armor pieces · 📜 Legendary scroll\n"
                "🥈 **#2 —** 20,000 coins · 2 Rare armor pieces · 📜 Rare scroll\n"
                "🥉 **#3 —** 12,000 coins · 1 Rare armor piece · 📜 Rare scroll\n"
                "⚔️ **#4+ —** 8,000 coins · 1 Uncommon armor piece · 📜 Common scroll"
            ),
            inline=False,
        )

        for guild in self.bot.guilds:
            try:
                async with aiosqlite.connect(db.DB_PATH) as conn:
                    cfg = await db.get_guild_config(conn, guild.id)
                ch_id = (cfg.get("boss_channel_id") or cfg.get("announce_channel_id")) if cfg else None
                ch = guild.get_channel(ch_id) if ch_id else None
                if ch is None:
                    ch = next(
                        (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
                        None,
                    )
                if ch:
                    await ch.send(content="@everyone", embed=embed)
            except Exception as e:
                print(f"[Boss] Failed to announce spawn in guild {guild.id}: {e}")

    # ── End / reward logic ─────────────────────────────────────────────────────

    async def _end_boss_all_guilds(self):
        # Flush all active in-memory sessions first (save any unsaved damage)
        for user_id, session in list(active_boss_sessions.items()):
            try:
                await end_boss_session(session)
            except Exception:
                pass

        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT id, boss_name, boss_element, rewards_given FROM boss_battles WHERE active=1"
            ) as cur:
                boss_row = await cur.fetchone()
            if not boss_row:
                return
            boss_id, boss_name, boss_element, rewards_given = boss_row
            if rewards_given:
                return

            async with conn.execute(
                "SELECT player_id, damage FROM boss_damage_log WHERE boss_id=? ORDER BY damage DESC",
                (boss_id,),
            ) as cur:
                rankings = await cur.fetchall()

            # Distribute rewards
            from config import PLAYER_XP_SOURCES
            for rank_idx, (player_id, _damage) in enumerate(rankings):
                rank = rank_idx + 1
                coins, armor_count, armor_rarity, scroll_rarity = _get_reward_tier(rank)
                # Rank-based player XP
                if rank == 1:
                    rank_xp = PLAYER_XP_SOURCES.get("boss_rank_1", 200)
                elif rank <= 3:
                    rank_xp = PLAYER_XP_SOURCES.get("boss_rank_2" if rank == 2 else "boss_rank_3", 100)
                else:
                    rank_xp = PLAYER_XP_SOURCES.get("boss_rank_other", 50)
                await db.add_player_xp(conn, player_id, rank_xp)
                await conn.execute(
                    "UPDATE players SET coins=coins+? WHERE user_id=?", (coins, player_id)
                )
                for _ in range(armor_count):
                    piece = generate_armor_piece(boss_element, armor_rarity)
                    await conn.execute(
                        """INSERT INTO armor_inventory(
                               player_id, name, rarity,
                               bonus_hp, bonus_atk, bonus_def, bonus_spd, bonus_mgk, bonus_res,
                               set_name, piece_type, armor_level, armor_xp, sub_stats
                           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,0,'[]')""",
                        (
                            player_id, piece["name"], piece["rarity"],
                            piece["bonus_hp"], piece["bonus_atk"], piece["bonus_def"],
                            piece["bonus_spd"], piece["bonus_mgk"], piece["bonus_res"],
                            piece["set_name"], piece["piece_type"],
                        ),
                    )
                # Give a random scroll of the appropriate rarity
                scroll_key = _pick_random_scroll(scroll_rarity)
                if scroll_key:
                    await db.add_item(conn, player_id, scroll_key, "scroll", 1)

            await conn.execute(
                "UPDATE boss_battles SET active=0, rewards_given=1 WHERE id=?", (boss_id,)
            )
            await conn.commit()

        # Build result announcement
        color = ELEMENT_COLORS.get(boss_element, 0xFFD700)
        embed = discord.Embed(
            title=f"🏆 Boss Raid Over — {boss_name}",
            description="The weekend raid has ended! Rewards have been distributed.",
            color=color,
        )
        if rankings:
            medals = ["🥇", "🥈", "🥉"] + ["⚔️"] * 200
            lines = []
            for rank_idx, (player_id, damage) in enumerate(rankings[:10]):
                rank = rank_idx + 1
                coins, armor_count, armor_rarity, scroll_rarity = _get_reward_tier(rank)
                lines.append(
                    f"{medals[rank_idx]} **#{rank}** <@{player_id}> · "
                    f"**{damage:,}** dmg → {coins} coins, "
                    f"{armor_count}×{armor_rarity} armor, 📜 {scroll_rarity} scroll"
                )
            if len(rankings) > 10:
                lines.append(f"*…and {len(rankings) - 10} more participants received rewards!*")
            embed.add_field(name="Top Damage Dealers", value="\n".join(lines), inline=False)
        else:
            embed.description += "\n\nNo one fought the boss this weekend."

        for guild in self.bot.guilds:
            try:
                async with aiosqlite.connect(db.DB_PATH) as conn:
                    cfg = await db.get_guild_config(conn, guild.id)
                ch_id = (cfg.get("boss_channel_id") or cfg.get("announce_channel_id")) if cfg else None
                ch = guild.get_channel(ch_id) if ch_id else None
                if ch is None:
                    ch = next(
                        (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
                        None,
                    )
                if ch:
                    await ch.send(embed=embed)
            except Exception as e:
                print(f"[Boss] Failed to announce end in guild {guild.id}: {e}")

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="bossbattle", description="Join the weekend boss raid!")
    async def bossbattle(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT id, boss_name, boss_element FROM boss_battles WHERE active=1"
            ) as cur:
                boss_row = await cur.fetchone()

        if not boss_row:
            await interaction.response.send_message(
                "❌ No boss is active right now! Bosses spawn every **Saturday at 10:00 UTC**.",
                ephemeral=True,
            )
            return

        boss_id, boss_name, boss_element = boss_row

        if interaction.user.id in active_boss_sessions:
            await interaction.response.send_message(
                "You're already in a boss battle session! Finish or flee your current session first.",
                ephemeral=True,
            )
            return

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pets = await db.get_player_pets(conn, interaction.user.id)
            exp = await db.get_active_expedition(conn, interaction.user.id)
            # Merge armor bonuses into each pet dict
            pets = [await db.apply_armor_to_pet(conn, p) for p in pets]

        exp_pet_id = exp["pet_id"] if exp else None
        battle_pets = [p for p in pets if p["stage"] > 0 and p["id"] != exp_pet_id][:5]

        if not battle_pets:
            await interaction.response.send_message(
                "You need at least one evolved pet to fight the boss! (Eggs can't battle)",
                ephemeral=True,
            )
            return

        # Find boss definition
        boss_def = next(
            (b for b in BOSS_DEFINITIONS if b["element"] == boss_element),
            get_current_boss_def(),
        )

        session = BossSession(interaction.user.id, boss_id, boss_def, battle_pets)
        active_boss_sessions[interaction.user.id] = session

        # Pet image
        files = []
        lead = battle_pets[0]
        try:
            img = get_pet_image(lead["element"], lead["variant"], lead["stage"])
            if img and os.path.exists(img):
                files.append(discord.File(img, filename="boss_pet.png"))
        except Exception:
            pass

        server_total = await _fetch_server_total(boss_id)
        embed = build_boss_embed(session, server_total)
        if files:
            embed.set_thumbnail(url="attachment://boss_pet.png")

        view = BossBattleView(session)
        await interaction.response.send_message(
            embed=embed,
            view=view,
            files=files if files else discord.utils.MISSING,
        )
        session.message = await interaction.original_response()
        if session.message.attachments:
            session.pet_img_url = session.message.attachments[0].url

    @app_commands.command(name="bossleaderboard", description="See the current boss raid leaderboard")
    async def bossleaderboard(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT id, boss_name, boss_element, total_damage FROM boss_battles WHERE active=1"
            ) as cur:
                boss_row = await cur.fetchone()

            if not boss_row:
                await interaction.response.send_message(
                    "No active boss right now. Bosses spawn every Saturday at 10:00 UTC!",
                    ephemeral=True,
                )
                return

            boss_id, boss_name, boss_element, total_dmg = boss_row

            async with conn.execute(
                """SELECT player_id, damage FROM boss_damage_log
                   WHERE boss_id=? ORDER BY damage DESC LIMIT 15""",
                (boss_id,),
            ) as cur:
                rows = await cur.fetchall()

        color = ELEMENT_COLORS.get(boss_element, 0xFFD700)
        elem_emoji = ELEMENT_EMOJIS.get(boss_element, "⚔️")
        embed = discord.Embed(
            title=f"{elem_emoji} Boss Raid Leaderboard — {boss_name}",
            description=f"🌍 **Total Server Damage:** {total_dmg:,}",
            color=color,
        )

        if not rows:
            embed.description += (
                "\n\nNo one has fought the boss yet! Use `/bossbattle` to be first!"
            )
        else:
            medals = ["🥇", "🥈", "🥉"] + ["⚔️"] * 100
            lines = []
            for i, (player_id, damage) in enumerate(rows):
                member = interaction.guild.get_member(player_id) if interaction.guild else None
                name = member.display_name if member else f"User {player_id}"
                you = " *(you)*" if player_id == interaction.user.id else ""
                lines.append(f"{medals[i]} **#{i + 1}** {name} — **{damage:,}** dmg{you}")
            embed.add_field(name="Top Damage Dealers", value="\n".join(lines), inline=False)

        embed.set_footer(text="Rewards distributed Monday at midnight UTC!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="spawnboss", description="[Admin] Manually spawn the weekend boss")
    @app_commands.default_permissions(administrator=True)
    async def spawnboss(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._spawn_boss_all_guilds()
        await interaction.followup.send("✅ Boss spawned and announced!", ephemeral=True)

    @app_commands.command(name="endboss", description="[Admin] Manually end the boss and distribute rewards")
    @app_commands.default_permissions(administrator=True)
    async def endboss(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._end_boss_all_guilds()
        await interaction.followup.send("✅ Boss ended and rewards distributed!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Boss(bot))
