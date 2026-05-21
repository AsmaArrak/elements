import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import random
from datetime import datetime, timezone

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_EMOJIS, ELEMENT_COLORS, PET_NAMES, STAGE_NAMES,
    BATTLE_WIN_XP, BATTLE_LOSS_XP, BATTLE_WIN_COINS, BATTLE_LOSS_COINS,
    TYPE_ADVANTAGE, RARITY_EMOJIS, get_pet_image
)
from game.stats import effective_stats, hp_bar, calc_physical_damage, calc_magic_damage
from game.skills import SKILLS, DEFAULT_ATTACKS

# In-memory battle states: channel_id -> BattleState
active_battles: dict[int, "BattleState"] = {}


class Combatant:
    def __init__(self, pet: dict):
        self.pet = pet
        stats = effective_stats(pet)
        self.max_hp = stats["hp"]
        self.hp = self.max_hp
        self.stats = stats
        self.element = pet["element"]
        self.name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]

    @property
    def alive(self):
        return self.hp > 0

    def take_damage(self, dmg: int):
        self.hp = max(0, self.hp - dmg)


class BattleState:
    def __init__(self, channel_id: int, challenger_id: int, opponent_id: int,
                 c_pets: list[dict], o_pets: list[dict]):
        self.channel_id = channel_id
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.c_combatants = [Combatant(p) for p in c_pets]
        self.o_combatants = [Combatant(p) for p in o_pets]
        self.c_active = 0
        self.o_active = 0
        self.c_action: dict | None = None
        self.o_action: dict | None = None
        self.turn = 1
        self.log: list[str] = []
        self.message: discord.Message | None = None
        self.c_pet_img_url: str | None = None
        self.o_pet_img_url: str | None = None

    @property
    def c_current(self) -> Combatant:
        return self.c_combatants[self.c_active]

    @property
    def o_current(self) -> Combatant:
        return self.o_combatants[self.o_active]

    @property
    def c_alive_indices(self) -> list[int]:
        return [i for i, c in enumerate(self.c_combatants) if c.alive]

    @property
    def o_alive_indices(self) -> list[int]:
        return [i for i, c in enumerate(self.o_combatants) if c.alive]

    @property
    def c_won(self) -> bool:
        return all(not c.alive for c in self.o_combatants)

    @property
    def o_won(self) -> bool:
        return all(not c.alive for c in self.c_combatants)

    def both_acted(self) -> bool:
        return self.c_action is not None and self.o_action is not None

    def resolve_turn(self) -> list[str]:
        logs = []
        ca = self.c_action
        oa = self.o_action
        self.c_action = None
        self.o_action = None
        self.turn += 1

        # Handle forfeits first
        if ca and ca["type"] == "forfeit":
            logs.append(f"🏳️ **{self.c_current.name}**'s trainer forfeited!")
            for c in self.c_combatants:
                c.hp = 0
            return logs
        if oa and oa["type"] == "forfeit":
            logs.append(f"🏳️ **{self.o_current.name}**'s trainer forfeited!")
            for c in self.o_combatants:
                c.hp = 0
            return logs

        # Handle switches (free action, no damage)
        if ca["type"] == "switch":
            idx = ca["target"]
            if idx in self.c_alive_indices and idx != self.c_active:
                self.c_active = idx
                logs.append(f"🔄 Challenger switched to **{self.c_current.name}**!")

        if oa["type"] == "switch":
            idx = oa["target"]
            if idx in self.o_alive_indices and idx != self.o_active:
                self.o_active = idx
                logs.append(f"🔄 Opponent switched to **{self.o_current.name}**!")

        # Determine turn order by SPD
        c_first = self.c_current.stats["spd"] >= self.o_current.stats["spd"]
        actions = [(ca, self.c_current, self.o_current, "challenger"),
                   (oa, self.o_current, self.c_current, "opponent")]
        if not c_first:
            actions = [actions[1], actions[0]]

        for action, attacker, defender, side in actions:
            if not attacker.alive or not defender.alive:
                continue
            if action["type"] == "switch":
                continue  # already handled above

            if action["type"] == "attack":
                move = action.get("move", "default")

                if move == "default":
                    att_name = action.get("name", "Attack")
                    att_type = action.get("attack_type", "physical")
                    mult = action.get("mult", 1.1)
                    if att_type == "physical":
                        base = calc_physical_damage(attacker.stats, defender.stats)
                    else:
                        base, _ = calc_magic_damage(attacker.pet, defender.pet, attacker.stats, defender.stats)
                    dmg = int(base * mult)
                    if defender.element in TYPE_ADVANTAGE.get(attacker.element, []):
                        dmg = int(dmg * 1.5)
                        se_note = " ✨ *Super effective!*"
                    else:
                        se_note = ""
                    defender.take_damage(dmg)
                    logs.append(f"⚔️ **{attacker.name}** used **{att_name}** on **{defender.name}** for **{dmg}** damage!{se_note}")

                elif move == "skill":
                    skill_key = action.get("skill_key")
                    skill = SKILLS.get(skill_key, {})
                    mult = skill.get("mult", 1.3)
                    skill_elem = skill.get("element", attacker.element)
                    if skill.get("type") == "physical":
                        base = calc_physical_damage(attacker.stats, defender.stats)
                        dmg = int(base * mult)
                    else:
                        base, _ = calc_magic_damage(attacker.pet, defender.pet, attacker.stats, defender.stats)
                        dmg = int(base * mult)
                    if defender.element in TYPE_ADVANTAGE.get(skill_elem, []):
                        dmg = int(dmg * 1.5)
                        se_note = " ✨ *Super effective!*"
                    else:
                        se_note = ""
                    defender.take_damage(dmg)
                    r_emoji = RARITY_EMOJIS.get(skill.get("rarity", ""), "")
                    logs.append(f"{r_emoji} **{attacker.name}** used **{skill.get('name', skill_key)}** on **{defender.name}** for **{dmg}** damage!{se_note}")

                if not defender.alive:
                    logs.append(f"💀 **{defender.name}** fainted!")
                    if side == "challenger":
                        alive = self.o_alive_indices
                        if alive:
                            self.o_active = alive[0]
                            logs.append(f"➡️ Opponent sent out **{self.o_current.name}**!")
                    else:
                        alive = self.c_alive_indices
                        if alive:
                            self.c_active = alive[0]
                            logs.append(f"➡️ Challenger sent out **{self.c_current.name}**!")

        return logs


def build_battle_embed(state: BattleState, c_user: discord.User, o_user: discord.User,
                        extra_log: list[str] = None, waiting: bool = True) -> discord.Embed:
    cc = state.c_current
    oc = state.o_current
    c_elem = ELEMENT_EMOJIS[cc.element]
    o_elem = ELEMENT_EMOJIS[oc.element]

    embed = discord.Embed(title=f"⚔️ Battle — Turn {state.turn}", color=0xE74C3C)
    embed.add_field(
        name=f"{c_elem} {cc.name} ({c_user.display_name})",
        value=(
            f"HP: `{hp_bar(cc.hp, cc.max_hp, 12)}` {cc.hp}/{cc.max_hp}\n"
            f"SPD: {cc.stats['spd']} | ATK: {cc.stats['atk']} | MGK: {cc.stats['mgk']}"
        ),
        inline=True
    )
    embed.add_field(name="VS", value="​", inline=True)
    embed.add_field(
        name=f"{o_elem} {oc.name} ({o_user.display_name})",
        value=(
            f"HP: `{hp_bar(oc.hp, oc.max_hp, 12)}` {oc.hp}/{oc.max_hp}\n"
            f"SPD: {oc.stats['spd']} | ATK: {oc.stats['atk']} | MGK: {oc.stats['mgk']}"
        ),
        inline=True
    )

    # Team status
    def team_status(combatants, active_idx):
        parts = []
        for i, c in enumerate(combatants):
            if not c.alive:
                parts.append(f"💀 ~~{c.name}~~")
            elif i == active_idx:
                parts.append(f"**► {c.name}**")
            else:
                parts.append(c.name)
        return " · ".join(parts)

    embed.add_field(
        name="Teams",
        value=(
            f"**{c_user.display_name}:** {team_status(state.c_combatants, state.c_active)}\n"
            f"**{o_user.display_name}:** {team_status(state.o_combatants, state.o_active)}"
        ),
        inline=False
    )

    # ⚔️ = chose their move, ⏳ = still deciding
    c_ready = "⚔️ Ready" if state.c_action else "⏳ Deciding..."
    o_ready = "⚔️ Ready" if state.o_action else "⏳ Deciding..."
    embed.add_field(
        name="Actions",
        value=f"{c_ready} — {c_user.display_name}\n{o_ready} — {o_user.display_name}",
        inline=False
    )

    # Recent log
    log_lines = (extra_log or state.log)[-5:]
    if log_lines:
        embed.add_field(name="📜 Battle Log", value="\n".join(log_lines), inline=False)

    if waiting:
        embed.set_footer(text="Both players select a move below.")

    # Pet image (challenger's active pet, stored from battle start)
    if state.c_pet_img_url:
        embed.set_thumbnail(url=state.c_pet_img_url)

    return embed


class SwitchSelect(discord.ui.Select):
    def __init__(self, state: BattleState, user_id: int, is_challenger: bool):
        self.state = state
        self.user_id = user_id
        self.is_challenger = is_challenger
        combatants = state.c_combatants if is_challenger else state.o_combatants
        active = state.c_active if is_challenger else state.o_active
        options = [
            discord.SelectOption(
                label=c.name,
                value=str(i),
                description=f"HP: {c.hp}/{c.max_hp}" + (" (current)" if i == active else ""),
                default=(i == active)
            )
            for i, c in enumerate(combatants) if c.alive
        ]
        super().__init__(placeholder="Choose a pet to switch to...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("That's not your switch!", ephemeral=True)
            return
        idx = int(self.values[0])
        action = {"type": "switch", "target": idx}
        if self.is_challenger:
            self.state.c_action = action
        else:
            self.state.o_action = action
        await interaction.response.send_message("Switch queued!", ephemeral=True)
        self.view.stop()
        await maybe_resolve(self.state, interaction)


class BattleView(discord.ui.View):
    def __init__(self, state: BattleState, c_user: discord.User, o_user: discord.User):
        super().__init__(timeout=120)
        self.state = state
        self.c_user = c_user
        self.o_user = o_user

    def _is_participant(self, user: discord.User) -> bool:
        return user.id in (self.state.challenger_id, self.state.opponent_id)

    def _is_challenger(self, user: discord.User) -> bool:
        return user.id == self.state.challenger_id

    async def _queue_and_update(self, interaction: discord.Interaction, action: dict, is_c: bool):
        """Record action, update the shared embed to show ⚔️, then check if turn resolves."""
        state = self.state
        if is_c:
            state.c_action = action
        else:
            state.o_action = action

        # Update the main battle embed so the other player sees ⚔️ Ready immediately
        if state.message and not state.both_acted():
            try:
                updated = build_battle_embed(state, self.c_user, self.o_user, waiting=True)
                await state.message.edit(embed=updated)
            except Exception:
                pass

        await maybe_resolve(state, interaction)

    @discord.ui.button(label="⚔️ Moves", style=discord.ButtonStyle.danger, row=0)
    async def moves_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_participant(interaction.user):
            await interaction.response.send_message("You're not in this battle!", ephemeral=True)
            return
        is_c = self._is_challenger(interaction.user)
        state = self.state
        if (is_c and state.c_action) or (not is_c and state.o_action):
            await interaction.response.send_message("You already chose a move this turn!", ephemeral=True)
            return

        current = state.c_current if is_c else state.o_current

        # Build unified move list: default attacks + learned skills
        options = []
        move_map = {}

        defaults = DEFAULT_ATTACKS.get(current.element, [])
        for atk in defaults:
            val = f"default:{atk['key']}"
            options.append(discord.SelectOption(
                label=atk["name"],
                value=val,
                description=f"{'ATK' if atk['type'] == 'physical' else 'MGK'} · {atk['mult']}x · {atk['desc']}",
                emoji="⚔️" if atk["type"] == "physical" else "✨"
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
                label=s.get("name", sk_key),
                value=val,
                description=f"{s.get('mult', 1.0)}x {'ATK' if s.get('type') == 'physical' else 'MGK'} · {s.get('rarity', '').title()}",
                emoji=r_emoji
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
                    "type": "attack", "move": "default",
                    "name": atk["name"], "attack_type": atk["type"], "mult": atk["mult"]
                }
                label = atk["name"]
            else:
                _, s, sk_key = entry
                action = {"type": "attack", "move": "skill", "skill_key": sk_key}
                label = s.get("name", sk_key)
            await inter.response.send_message(f"⚔️ **{label}** queued!", ephemeral=True)
            await self._queue_and_update(inter, action, is_c)

        move_select.callback = move_callback
        sv = discord.ui.View(timeout=30)
        sv.add_item(move_select)
        await interaction.response.send_message("Choose a move:", view=sv, ephemeral=True)

    @discord.ui.button(label="🔄 Switch", style=discord.ButtonStyle.secondary, row=0)
    async def switch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_participant(interaction.user):
            await interaction.response.send_message("You're not in this battle!", ephemeral=True)
            return
        is_c = self._is_challenger(interaction.user)
        combatants = self.state.c_combatants if is_c else self.state.o_combatants
        alive = [c for c in combatants if c.alive]
        if len(alive) <= 1:
            await interaction.response.send_message("No other pets to switch to!", ephemeral=True)
            return
        view = discord.ui.View(timeout=30)
        view.add_item(SwitchSelect(self.state, interaction.user.id, is_c))
        await interaction.response.send_message("Choose a pet to switch to:", view=view, ephemeral=True)

    @discord.ui.button(label="🏳️ Forfeit", style=discord.ButtonStyle.secondary, row=0)
    async def forfeit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_participant(interaction.user):
            await interaction.response.send_message("You're not in this battle!", ephemeral=True)
            return
        is_c = self._is_challenger(interaction.user)
        state = self.state
        if (is_c and state.c_action) or (not is_c and state.o_action):
            await interaction.response.send_message("You already chose an action!", ephemeral=True)
            return
        await interaction.response.send_message("You forfeited!", ephemeral=True)
        await self._queue_and_update(interaction, {"type": "forfeit"}, is_c)

    async def on_timeout(self):
        state = self.state
        def _default_action(element: str) -> dict:
            atk = DEFAULT_ATTACKS.get(element, [{"name": "Tackle", "type": "physical", "mult": 1.1}])[0]
            return {"type": "attack", "move": "default", "name": atk["name"], "attack_type": atk["type"], "mult": atk["mult"]}
        if not state.c_action:
            state.c_action = _default_action(state.c_current.element)
        if not state.o_action:
            state.o_action = _default_action(state.o_current.element)
        try:
            channel = self.c_user.guild.get_channel(state.channel_id) if hasattr(self.c_user, "guild") else None
            if channel:
                await maybe_resolve_force(state, channel, self.c_user, self.o_user)
        except Exception:
            pass


async def maybe_resolve(state: BattleState, interaction: discord.Interaction):
    if not state.both_acted():
        return
    channel = interaction.channel
    c_user = interaction.guild.get_member(state.challenger_id) if interaction.guild else None
    o_user = interaction.guild.get_member(state.opponent_id) if interaction.guild else None
    if c_user is None or o_user is None:
        return
    await resolve_and_update(state, channel, c_user, o_user)


async def maybe_resolve_force(state, channel, c_user, o_user):
    await resolve_and_update(state, channel, c_user, o_user)


async def resolve_and_update(state: BattleState, channel, c_user, o_user):
    new_logs = state.resolve_turn()
    state.log.extend(new_logs)

    if state.c_won or state.o_won:
        winner = c_user if state.c_won else o_user
        loser = o_user if state.c_won else c_user
        winner_id = winner.id
        loser_id = loser.id

        async with aiosqlite.connect(db.DB_PATH) as conn:
            winner_pet = await db.get_active_pet(conn, winner_id)
            loser_pet = await db.get_active_pet(conn, loser_id)
            if winner_pet:
                await db.add_xp(conn, winner_pet["id"], BATTLE_WIN_XP)
            if loser_pet:
                await db.add_xp(conn, loser_pet["id"], BATTLE_LOSS_XP)
            await conn.execute(
                "UPDATE players SET coins=coins+? WHERE user_id=?", (BATTLE_WIN_COINS, winner_id)
            )
            await conn.execute(
                "UPDATE players SET coins=coins+? WHERE user_id=?", (BATTLE_LOSS_COINS, loser_id)
            )
            await conn.execute(
                "INSERT INTO battle_log(challenger_id, opponent_id, winner_id, timestamp) VALUES(?,?,?,?)",
                (state.challenger_id, state.opponent_id, winner_id, db.now_iso())
            )
            await conn.commit()

        embed = build_battle_embed(state, c_user, o_user, extra_log=new_logs, waiting=False)
        embed.color = 0xFFD700
        embed.add_field(
            name="🏆 Battle Over!",
            value=(
                f"**{winner.display_name}** wins! 🎉\n"
                f"+{BATTLE_WIN_XP} XP, +{BATTLE_WIN_COINS} coins for {winner.display_name}\n"
                f"+{BATTLE_LOSS_XP} XP, +{BATTLE_LOSS_COINS} coins for {loser.display_name}"
            ),
            inline=False
        )
        if state.message:
            await state.message.edit(embed=embed, view=None)
        else:
            await channel.send(embed=embed)

        active_battles.pop(channel.id, None)
        return

    # Continue battle — new turn
    embed = build_battle_embed(state, c_user, o_user, extra_log=new_logs, waiting=True)
    view = BattleView(state, c_user, o_user)
    if state.message:
        await state.message.edit(embed=embed, view=view)


class AcceptView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member,
                 c_pets: list[dict], o_pets: list[dict], channel_id: int):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.c_pets = c_pets
        self.o_pets = o_pets
        self.channel_id = channel_id

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        self.stop()

        state = BattleState(
            self.channel_id,
            self.challenger.id, self.opponent.id,
            self.c_pets, self.o_pets
        )
        active_battles[self.channel_id] = state

        # Load pet images for challenger and opponent's active pets
        files = []
        c_pet = self.c_pets[0] if self.c_pets else None
        o_pet = self.o_pets[0] if self.o_pets else None
        if c_pet:
            img = get_pet_image(c_pet["element"], c_pet["variant"], c_pet["stage"])
            if img and os.path.exists(img):
                files.append(discord.File(img, filename="challenger_pet.png"))
        if o_pet:
            img = get_pet_image(o_pet["element"], o_pet["variant"], o_pet["stage"])
            if img and os.path.exists(img):
                files.append(discord.File(img, filename="opponent_pet.png"))

        embed = build_battle_embed(state, self.challenger, self.opponent, waiting=True)
        if files:
            embed.set_thumbnail(url="attachment://challenger_pet.png")

        view = BattleView(state, self.challenger, self.opponent)
        await interaction.response.send_message(
            embed=embed, view=view,
            files=files if files else discord.utils.MISSING
        )
        state.message = await interaction.original_response()

        # Store CDN attachment URLs so we can reference them in future embed edits
        if state.message.attachments:
            state.c_pet_img_url = state.message.attachments[0].url
            if len(state.message.attachments) > 1:
                state.o_pet_img_url = state.message.attachments[1].url

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.opponent.id, self.challenger.id):
            await interaction.response.send_message("Not your challenge!", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(
            content=f"❌ {self.opponent.display_name} declined the challenge.",
            embed=None, view=None
        )


class Battle(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="battle", description="Challenge another player to a PvP battle")
    @app_commands.describe(opponent="The player to challenge")
    async def battle(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot or opponent.id == interaction.user.id:
            await interaction.response.send_message("Invalid opponent.", ephemeral=True)
            return
        if interaction.channel_id in active_battles:
            await interaction.response.send_message(
                "There's already an active battle in this channel!", ephemeral=True
            )
            return

        async with aiosqlite.connect(db.DB_PATH) as conn:
            c_player = await db.get_player(conn, interaction.user.id)
            o_player = await db.get_player(conn, opponent.id)
            if not c_player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            if not o_player:
                await interaction.response.send_message(
                    f"{opponent.display_name} hasn't started yet!", ephemeral=True
                )
                return

            c_exp = await db.get_active_expedition(conn, interaction.user.id)
            o_exp = await db.get_active_expedition(conn, opponent.id)

            c_all_pets = await db.get_player_pets(conn, interaction.user.id)
            o_all_pets = await db.get_player_pets(conn, opponent.id)
            # Merge armor bonuses into each pet dict
            c_all_pets = [await db.apply_armor_to_pet(conn, p) for p in c_all_pets]
            o_all_pets = [await db.apply_armor_to_pet(conn, p) for p in o_all_pets]

        c_exp_pet_id = c_exp["pet_id"] if c_exp else None
        o_exp_pet_id = o_exp["pet_id"] if o_exp else None

        c_pets = [p for p in c_all_pets if p["stage"] > 0 and p["id"] != c_exp_pet_id]
        o_pets = [p for p in o_all_pets if p["stage"] > 0 and p["id"] != o_exp_pet_id]

        if not c_pets:
            await interaction.response.send_message(
                "You have no battle-ready pets! Your pets need to hatch first.", ephemeral=True
            )
            return
        if not o_pets:
            await interaction.response.send_message(
                f"{opponent.display_name} has no battle-ready pets.", ephemeral=True
            )
            return

        c_pets = sorted(c_pets, key=lambda p: p["level"], reverse=True)[:5]
        o_pets = sorted(o_pets, key=lambda p: p["level"], reverse=True)[:5]

        embed = discord.Embed(
            title="⚔️ Battle Challenge!",
            description=(
                f"{interaction.user.mention} challenges {opponent.mention} to battle!\n\n"
                f"**{interaction.user.display_name}:** {len(c_pets)} pet(s)\n"
                f"**{opponent.display_name}:** {len(o_pets)} pet(s)"
            ),
            color=0xE74C3C
        )
        embed.set_footer(text="Challenge expires in 60 seconds.")
        view = AcceptView(interaction.user, opponent, c_pets, o_pets, interaction.channel_id)
        await interaction.response.send_message(
            content=opponent.mention, embed=embed, view=view
        )

    @app_commands.command(name="battlelog", description="View recent battle history")
    async def battlelog(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                """SELECT b.challenger_id, b.opponent_id, b.winner_id, b.timestamp
                   FROM battle_log b
                   WHERE b.challenger_id=? OR b.opponent_id=?
                   ORDER BY b.timestamp DESC LIMIT 10""",
                (interaction.user.id, interaction.user.id)
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message("No battles yet!", ephemeral=True)
            return

        embed = discord.Embed(title="📜 Battle History", color=0xE74C3C)
        lines = []
        for row in rows:
            c_id, o_id, w_id, ts = row
            result = "🏆 Won" if w_id == interaction.user.id else "💀 Lost"
            other_id = o_id if c_id == interaction.user.id else c_id
            other = interaction.guild.get_member(other_id) if interaction.guild else None
            other_name = other.display_name if other else f"User {other_id}"
            lines.append(f"{result} vs **{other_name}**")
        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Battle(bot))
