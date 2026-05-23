import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_COLORS, ELEMENT_EMOJIS, PET_NAMES, STAGE_NAMES,
    FOOD_ITEMS, TRAIN_XP, TRAIN_STAT_BOOST, TRAIN_COOLDOWN_HOURS,
    get_pet_image, get_food_image, xp_for_next_level, stat_cap
)
from game.stats import effective_stats, hp_bar, apply_stat_bonus, calc_base_stats
from game.evolution import evolve_pet
from datetime import datetime, timezone, timedelta


def pet_embed(pet: dict, owner: discord.User | discord.Member = None) -> tuple[discord.Embed, discord.File]:
    element = pet["element"]
    variant = pet["variant"]
    stage = pet["stage"]
    level = pet["level"]
    name = pet.get("nickname") or PET_NAMES[element][variant][stage]
    display_element = ELEMENT_DISPLAY[element]
    emoji = ELEMENT_EMOJIS[element]
    color = ELEMENT_COLORS[element]
    stage_name = STAGE_NAMES[stage]

    stats = effective_stats(pet)
    xp = pet["xp"]
    xp_needed = xp_for_next_level(level) if level < 100 else 0
    xp_bar = hp_bar(xp, xp_needed, 12) if xp_needed else "MAX LEVEL"

    embed = discord.Embed(
        title=f"{emoji} {name}",
        description=f"**{display_element} — {stage_name}** | Level {level}",
        color=color
    )
    if owner:
        embed.set_author(name=str(owner), icon_url=owner.display_avatar.url)

    if stage > 0:
        caps = {s: stat_cap(pet[f"base_{s}"], level) for s in ("hp", "atk", "def", "spd", "mgk", "res")}
        embed.add_field(
            name="⚔️ Battle Stats  *(current / cap)*",
            value=(
                f"```\n"
                f"HP : {stats['hp']:>4}/{caps['hp']:<4}  ATK: {stats['atk']:>4}/{caps['atk']:<4}\n"
                f"DEF: {stats['def']:>4}/{caps['def']:<4}  SPD: {stats['spd']:>4}/{caps['spd']:<4}\n"
                f"MGK: {stats['mgk']:>4}/{caps['mgk']:<4}  RES: {stats['res']:>4}/{caps['res']:<4}\n"
                f"```"
            ),
            inline=False
        )
    else:
        feed_count = pet.get("first_fed", 0)
        remaining = 3 - feed_count
        dots = "🟡" * feed_count + "⚪" * remaining
        embed.add_field(
            name="🥚 Egg",
            value=f"Feed it **{remaining} more time(s)** to hatch!\n{dots} ({feed_count}/3 feedings)",
            inline=False
        )

    if level < 100 and stage > 0:
        embed.add_field(name="📈 XP", value=f"`{xp_bar}` {xp}/{xp_needed}", inline=False)
    elif stage > 0:
        embed.add_field(name="📈 Level", value="**MAX LEVEL** ⭐", inline=False)

    if stage > 0:
        expl = pet['exploration']
        embed.add_field(
            name="🧭 Exploration",
            value=f"{expl}/100 {'✅' if expl >= 100 else f'({100 - expl} to Mega)'}",
            inline=True
        )

    image_path = get_pet_image(element, variant, stage)
    file = discord.File(image_path, filename="pet.png")
    embed.set_image(url="attachment://pet.png")
    return embed, file


async def do_feed(pet: dict, item_key: str, user_id: int, channel) -> tuple[discord.Embed, discord.File | None]:
    """Core feeding logic. Returns (embed, optional file)."""
    async with aiosqlite.connect(db.DB_PATH) as conn:
        # Re-fetch fresh pet state
        pet = await db.get_pet(conn, pet["id"])
        food = FOOD_ITEMS[item_key]
        stat_key = food["stat"]
        boost = food["boost"]
        xp_gain = food["xp"]
        feed_count = pet["first_fed"]

        await db.remove_item(conn, user_id, item_key)

        actual_boost, was_capped = apply_stat_bonus(pet, stat_key, boost)
        if actual_boost > 0:
            await conn.execute(
                f"UPDATE pets SET bonus_{stat_key}=bonus_{stat_key}+? WHERE id=?",
                (actual_boost, pet["id"])
            )

        evolved = False
        evo_message = ""
        new_feed_count = feed_count + 1

        if pet["stage"] == 0:
            await conn.execute(
                "UPDATE pets SET first_fed=? WHERE id=?", (new_feed_count, pet["id"])
            )
            if new_feed_count >= 3:
                await evolve_pet(conn, pet, 1)
                evolved = True
                evo_name = PET_NAMES[pet["element"]][pet["variant"]][1]
                evo_message = (
                    f"🌟 **HATCHED!** Your egg burst open and **{evo_name}** emerged!\n"
                    "Your journey has truly begun!"
                )
                pet = await db.get_pet(conn, pet["id"])
            await db.add_xp(conn, pet["id"], xp_gain)
        else:
            await db.add_xp(conn, pet["id"], xp_gain)

        await conn.commit()
        pet = await db.get_pet(conn, pet["id"])

    food_display = food["display"]
    stat_display = stat_key.upper()
    element = pet["element"]
    variant = pet["variant"]
    stage = pet["stage"]
    name = pet.get("nickname") or PET_NAMES[element][variant][stage]
    color = ELEMENT_COLORS[element]

    # Compute new stat value and cap for display
    current_stat = pet[f"base_{stat_key}"] + pet[f"bonus_{stat_key}"]
    cap_val = stat_cap(pet[f"base_{stat_key}"], pet["level"])
    if actual_boost > 0:
        stat_line = f"+{actual_boost} {stat_display}  →  **{current_stat}/{cap_val}**"
    else:
        stat_line = f"⛔ {stat_display} at cap!  **{current_stat}/{cap_val}**"
    partial_note = f" *(only +{actual_boost} applied, cap reached)*" if was_capped and actual_boost > 0 else ""

    embed = discord.Embed(color=color)
    file = None

    if evolved:
        embed.title = f"🌟 {name} hatched!"
        embed.description = evo_message
        try:
            file = discord.File(get_pet_image(element, variant, stage), filename="img.png")
            embed.set_image(url="attachment://img.png")
        except FileNotFoundError:
            pass
        if channel:
            evo_name = PET_NAMES[element][variant][1]
            emoji = ELEMENT_EMOJIS[element]
            await channel.send(
                f"🎉 <@{user_id}>'s egg just hatched! Say hello to **{evo_name}** {emoji}!"
            )
    elif pet["stage"] == 0:
        remaining = 3 - new_feed_count
        dots = "🟡" * new_feed_count + "⚪" * remaining
        embed.title = "🥚 Your egg enjoyed the meal!"
        embed.description = f"{dots} **{new_feed_count}/3 feedings** — {remaining} more to hatch!"
        try:
            file = discord.File(get_food_image(item_key), filename="img.png")
            embed.set_thumbnail(url="attachment://img.png")
        except FileNotFoundError:
            pass
    else:
        embed.title = f"🍽️ {name} ate {food_display}!"
        try:
            file = discord.File(get_food_image(item_key), filename="img.png")
            embed.set_thumbnail(url="attachment://img.png")
        except FileNotFoundError:
            pass

    embed.add_field(name="Stat Boost", value=f"{stat_line}{partial_note}", inline=False)
    embed.add_field(name="XP Gained", value=f"+{xp_gain} XP", inline=True)
    if pet["stage"] > 0:
        embed.add_field(
            name="Level",
            value=f"Level {pet['level']} | {pet['xp']}/{xp_for_next_level(pet['level'])} XP",
            inline=True
        )
    return embed, file, stat_key, actual_boost, xp_gain


# Tracks the currently open FeedView per user so duplicate sessions are killed
_active_feed_views: dict[int, "FeedView"] = {}


class FeedView(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict], food_inv: list[dict],
                 original_interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pets = pets
        self.food_inv = food_inv
        self.original_interaction = original_interaction
        self.selected_pet: dict | None = pets[0] if len(pets) == 1 else None
        self.selected_food: str | None = None
        self.selected_qty: int = 1
        self._food_max: dict[str, int] = {i["item_key"]: i["quantity"] for i in food_inv}

        # Pet select (only show if more than 1 pet)
        if len(pets) > 1:
            self.add_item(PetSelect(pets))

        # Food select
        self.add_item(FoodSelect(food_inv))

        # Quantity select
        self.add_item(QuantitySelect(row=2))

    @discord.ui.button(label="🍽️ Feed!", style=discord.ButtonStyle.success, row=3)
    async def feed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        if not self.selected_pet:
            await interaction.response.send_message("Please select a pet first.", ephemeral=True)
            return
        if not self.selected_food:
            await interaction.response.send_message("Please select a food item first.", ephemeral=True)
            return

        # Check live inventory from DB — prevents duplicate sessions using the same item
        async with aiosqlite.connect(db.DB_PATH) as conn:
            inventory = await db.get_inventory(conn, self.user_id)
        live_qty = next(
            (i["quantity"] for i in inventory if i["item_key"] == self.selected_food and i["item_type"] == "food"),
            0
        )
        qty = self.selected_qty
        if live_qty <= 0:
            await interaction.response.send_message(
                "❌ You don't have that food anymore!", ephemeral=True
            )
            return
        if qty > live_qty:
            await interaction.response.send_message(
                f"❌ You only have **{live_qty}×** of that food now.", ephemeral=True
            )
            return

        # Invalidate any other open feed session for this user
        _active_feed_views.pop(self.user_id, None)
        self.stop()
        await interaction.response.defer()

        # Feed multiple times, accumulate results
        last_embed, last_file = None, None
        total_xp = 0
        total_stat_boost = 0
        total_stat_key = None
        evolved = False

        for _ in range(qty):
            embed, file, stat_key, boost, xp_gain = await do_feed(
                self.selected_pet, self.selected_food,
                self.user_id, interaction.channel
            )
            last_embed, last_file = embed, file
            total_xp += xp_gain
            total_stat_boost += boost
            total_stat_key = stat_key
            # Refresh pet state for next iteration
            async with aiosqlite.connect(db.DB_PATH) as conn:
                self.selected_pet = await db.get_pet(conn, self.selected_pet["id"])
            if self.selected_pet is None:
                break

        # For bulk feeds, update the embed to show TOTAL stats/XP
        if qty > 1 and last_embed:
            last_embed.clear_fields()
            stat_display = total_stat_key.upper() if total_stat_key else "STAT"
            if self.selected_pet and total_stat_key:
                final_val = self.selected_pet[f"base_{total_stat_key}"] + self.selected_pet[f"bonus_{total_stat_key}"]
                cap_val = stat_cap(self.selected_pet[f"base_{total_stat_key}"], self.selected_pet["level"])
                stat_val_str = f"  →  **{final_val}/{cap_val}**"
            else:
                stat_val_str = ""
            if total_stat_boost > 0:
                boost_text = f"+{total_stat_boost} {stat_display}{stat_val_str}"
            else:
                boost_text = f"⛔ {stat_display} was already at cap!{stat_val_str}"
            last_embed.add_field(name="Total Stat Boost", value=boost_text, inline=False)
            last_embed.add_field(name="Total XP Gained", value=f"+{total_xp} XP", inline=True)
            if self.selected_pet and self.selected_pet["stage"] > 0:
                last_embed.add_field(
                    name="Level",
                    value=f"Level {self.selected_pet['level']} | {self.selected_pet['xp']}/{xp_for_next_level(self.selected_pet['level'])} XP",
                    inline=True
                )
            last_embed.set_footer(text=f"Fed ×{qty}")

        if last_file:
            await interaction.followup.send(embed=last_embed, file=last_file)
        elif last_embed:
            await interaction.followup.send(embed=last_embed)

        try:
            await self.original_interaction.edit_original_response(
                embed=discord.Embed(description=f"✅ Fed ×{qty}!", color=0x2ECC71), view=None
            )
        except Exception:
            pass


class PetSelect(discord.ui.Select):
    def __init__(self, pets: list[dict]):
        options = []
        for p in pets:
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            emoji = ELEMENT_EMOJIS[p["element"]]
            stage_label = STAGE_NAMES[p["stage"]]
            options.append(discord.SelectOption(
                label=name,
                value=str(p["id"]),
                description=f"Level {p['level']} · {stage_label}",
                emoji=emoji
            ))
        super().__init__(placeholder="Choose a pet to feed...", options=options, row=0)
        self.pets_by_id = {str(p["id"]): p for p in pets}

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_pet = self.pets_by_id[self.values[0]]
        await interaction.response.defer()


class FoodSelect(discord.ui.Select):
    def __init__(self, food_inv: list[dict]):
        options = []
        for item in food_inv:
            key = item["item_key"]
            food_data = FOOD_ITEMS.get(key, {})
            display = food_data.get("display", key.title())
            stat = food_data.get("stat", "?").upper()
            boost = food_data.get("boost", 0)
            qty = item["quantity"]
            options.append(discord.SelectOption(
                label=display,
                value=key,
                description=f"×{qty} in bag · +{boost} {stat}",
            ))
        super().__init__(placeholder="Choose a food to feed...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_food = self.values[0]
        # Reset qty to 1 when food changes
        self.view.selected_qty = 1
        await interaction.response.defer()


class QuantitySelect(discord.ui.Select):
    def __init__(self, row: int = 2):
        options = [
            discord.SelectOption(label=f"Feed ×{n}", value=str(n), default=(n == 1))
            for n in [1, 2, 3, 5, 10]
        ]
        super().__init__(placeholder="How many to feed? (default 1)", options=options, row=row)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_qty = int(self.values[0])
        await interaction.response.defer()


class PetViewSelect(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pets_by_id = {str(p["id"]): p for p in pets}
        options = []
        for p in pets:
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            emoji = ELEMENT_EMOJIS[p["element"]]
            stage_label = STAGE_NAMES[p["stage"]]
            options.append(discord.SelectOption(
                label=name,
                value=str(p["id"]),
                description=f"Level {p['level']} · {stage_label}",
                emoji=emoji
            ))
        select = discord.ui.Select(placeholder="Choose a pet to inspect...", options=options)
        select.callback = self._callback
        self.add_item(select)

    async def _callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        pet = self.pets_by_id[interaction.data["values"][0]]
        self.stop()
        await interaction.response.defer()
        pet_cog = interaction.client.get_cog("Pet")
        await pet_cog._send_pet_stats(interaction, pet, followup=True)


class RenameModal(discord.ui.Modal, title="Rename your pet"):
    new_name = discord.ui.TextInput(
        label="New name (leave blank to reset)",
        placeholder="e.g. Blaze  — max 24 chars",
        required=False,
        max_length=24,
    )

    def __init__(self, pet: dict):
        super().__init__()
        self.pet = pet

    async def on_submit(self, interaction: discord.Interaction):
        nick = self.new_name.value.strip() or None
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute("UPDATE pets SET nickname=? WHERE id=?", (nick, self.pet["id"]))
            await conn.commit()
        if nick:
            await interaction.response.send_message(f"✅ Your pet is now known as **{nick}**! 🎀")
        else:
            default = PET_NAMES[self.pet["element"]][self.pet["variant"]][self.pet["stage"]]
            await interaction.response.send_message(f"✅ Nickname cleared. Back to **{default}**.")


class RenamePetPickerView(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pets = {p["id"]: p for p in pets}

        opts = []
        for p in pets:
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            opts.append(discord.SelectOption(
                label=name, value=str(p["id"]),
                description=f"Level {p['level']} · {STAGE_NAMES[p['stage']]}",
                emoji=ELEMENT_EMOJIS[p["element"]]
            ))
        sel = discord.ui.Select(placeholder="🐾 Choose a pet to rename...", options=opts)
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.stop()
        pet = self.pets[int(interaction.data["values"][0])]
        await interaction.response.send_modal(RenameModal(pet))


class TrainPetPickerView(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict], train_fn):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pets = {p["id"]: p for p in pets}
        self.train_fn = train_fn

        opts = []
        for p in pets:
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            opts.append(discord.SelectOption(
                label=name, value=str(p["id"]),
                description=f"Level {p['level']} · {STAGE_NAMES[p['stage']]}",
                emoji=ELEMENT_EMOJIS[p["element"]]
            ))
        sel = discord.ui.Select(placeholder="🐾 Choose a pet to train...", options=opts)
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.stop()
        pet = self.pets[int(interaction.data["values"][0])]
        await self.train_fn(interaction, pet)


class Pet(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your profile or another player's profile")
    @app_commands.describe(player="Another player to look up (leave empty for your own profile)")
    async def profile(self, interaction: discord.Interaction, player: discord.Member = None):
        target = player or interaction.user
        is_self = target.id == interaction.user.id

        async with aiosqlite.connect(db.DB_PATH) as conn:
            p = await db.get_player(conn, target.id)
            if not p:
                msg = "You haven't started yet! Use `/start` to begin." if is_self else f"**{target.display_name}** hasn't started yet."
                await interaction.response.send_message(msg, ephemeral=True)
                return
            moon_shards = await db.sync_moon_shards(conn, target.id)
            p = await db.get_player(conn, target.id)
            all_pets = await db.get_player_pets(conn, target.id)

        from config import player_xp_for_next_level, PLAYER_LEVEL_CAP, MOON_SHARD_CAP
        player_level = p.get("player_level") or 1
        p_xp = p.get("player_xp") or 0

        embed = discord.Embed(
            title=f"👤 {target.display_name}",
            color=0x7B68EE
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        # Player level + XP
        if player_level >= PLAYER_LEVEL_CAP:
            xp_line = f"**Level {player_level} / {PLAYER_LEVEL_CAP}** ⭐ MAX"
        else:
            p_xp_needed = player_xp_for_next_level(player_level)
            p_bar = hp_bar(p_xp, p_xp_needed, 12)
            xp_line = f"**Level {player_level} / {PLAYER_LEVEL_CAP}**\n`{p_bar}` {p_xp:,} / {p_xp_needed:,} XP"
        embed.add_field(name="🏅 Player Level", value=xp_line, inline=False)

        # Resources
        embed.add_field(name="💰 Coins", value=f"**{p['coins']:,}**", inline=True)
        embed.add_field(name="🌙 Moon Shards", value=f"**{moon_shards} / {MOON_SHARD_CAP}**", inline=True)

        # Pet roster
        if all_pets:
            lines = []
            for pet in all_pets[:10]:
                stage_name = STAGE_NAMES[pet["stage"]]
                elem_emoji = ELEMENT_EMOJIS[pet["element"]]
                name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
                lines.append(f"{elem_emoji} **{name}** · {stage_name} · Lv {pet['level']}")
            if len(all_pets) > 10:
                lines.append(f"*...and {len(all_pets) - 10} more*")
            embed.add_field(name=f"🐾 Pets ({len(all_pets)})", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="🐾 Pets", value="*No pets yet — use `/start`*", inline=False)

        embed.set_footer(text="Use /pet to see full stats for a specific pet")
        await interaction.response.send_message(embed=embed, ephemeral=is_self)

    @app_commands.command(name="pet", description="Detailed view of your active pet's stats and bonuses")
    async def pet_cmd(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pets = await db.get_player_pets(conn, interaction.user.id)
            hatched = [p for p in pets if p["stage"] > 0]

        if not pets:
            await interaction.response.send_message("No active pet found.", ephemeral=True)
            return

        if len(pets) > 1:
            view = PetViewSelect(interaction.user.id, pets)
            await interaction.response.send_message(
                "Which pet would you like to inspect?", view=view, ephemeral=True
            )
            return

        await self._send_pet_stats(interaction, pets[0])

    async def _send_pet_stats(self, interaction: discord.Interaction, pet: dict, followup: bool = False):
        from config import stat_cap
        element = pet["element"]
        variant = pet["variant"]
        stage = pet["stage"]
        level = pet["level"]
        name = pet.get("nickname") or PET_NAMES[element][variant][stage]
        color = ELEMENT_COLORS[element]
        emoji = ELEMENT_EMOJIS[element]

        # Apply equipped armor bonuses before computing stats
        async with aiosqlite.connect(db.DB_PATH) as conn:
            pet = await db.apply_armor_to_pet(conn, pet)

        stats = effective_stats(pet)

        embed = discord.Embed(title=f"{emoji} {name} — Full Stats", color=color)

        def stat_line(s):
            base = pet[f"base_{s}"]
            food = pet[f"bonus_{s}"]
            armor = pet.get(f"armor_bonus_{s}", 0)
            total = stats[s]
            parts = f"{base}+{food}" + (f"+{armor}🛡️" if armor else "")
            return f"{s.upper()}: {parts} = **{total}**"

        embed.add_field(
            name="Base Stats  *(base+food+armor)*",
            value="\n".join(stat_line(s) for s in ("hp", "atk", "def")),
            inline=True
        )
        embed.add_field(
            name="​",
            value="\n".join(stat_line(s) for s in ("spd", "mgk", "res")),
            inline=True
        )
        embed.add_field(name="​", value="​", inline=False)
        embed.add_field(name="Stage", value=STAGE_NAMES[stage], inline=True)
        embed.add_field(name="Level", value=f"{level}/100", inline=True)

        # XP progress
        if level < 100 and stage > 0:
            xp_needed = xp_for_next_level(level)
            xp_bar_str = hp_bar(pet["xp"], xp_needed, 12)
            embed.add_field(
                name="📈 XP",
                value=f"`{xp_bar_str}` {pet['xp']:,} / {xp_needed:,}",
                inline=False
            )
        elif stage > 0:
            embed.add_field(name="📈 XP", value="**MAX LEVEL** ⭐", inline=False)
        # Stat caps — all 6 stats, current / cap
        def fmt(s):
            cur = pet[f"base_{s}"] + pet[f"bonus_{s}"]
            cap = stat_cap(pet[f"base_{s}"], level)
            bar = "🟩" if cur < cap else "🟥"
            return f"{bar} **{s.upper()}** {cur}/{cap}"

        embed.add_field(
            name=f"📊 Stat Caps  *(level {level})*",
            value=(
                f"{fmt('hp')}   {fmt('spd')}\n"
                f"{fmt('atk')}   {fmt('mgk')}\n"
                f"{fmt('def')}   {fmt('res')}\n"
                f"*🟩 = room to grow · 🟥 = capped*"
            ),
            inline=False
        )

        # Exploration
        expl_val = pet['exploration']
        if expl_val >= 100:
            expl_desc = f"**{expl_val}/100** ✅\n*Mega Stone drops **unlocked**! You can now find them on expeditions.*"
        else:
            expl_desc = f"**{expl_val}/100**\n*Increases by going on expeditions. Reach **100** to unlock Mega Stone drops!*"
        embed.add_field(name="🧭 Exploration", value=expl_desc, inline=False)

        # Equipped armor — all 4 slots (stats shown are fully scaled: level mult + substats)
        from config import RARITY_EMOJIS, ELEMENT_EMOJIS as ELEM_EMOJIS
        import json as _json
        SLOT_ORDER = ["Crown", "Plate", "Gauntlets", "Greaves"]
        pieces = pet.get("equipped_pieces", [])
        if pieces:
            armor_lines = []
            for p in sorted(pieces, key=lambda x: SLOT_ORDER.index(x["piece_type"]) if x.get("piece_type") in SLOT_ORDER else 99):
                r_emoji = RARITY_EMOJIS.get(p["rarity"], "⚪")
                elem_e = ELEM_EMOJIS.get(p.get("set_name", ""), "")
                lv = p.get("armor_level", 1)
                scaled = p.get("scaled", {})
                # Show scaled total per stat (main stat multiplied by level + substats added)
                stat_parts = []
                for s in ("hp", "atk", "def", "spd", "mgk", "res"):
                    v = scaled.get(f"bonus_{s}", 0)
                    if v:
                        stat_parts.append(f"+{v} {s.upper()}")
                stat_str = " · ".join(stat_parts) if stat_parts else "—"
                line = f"{r_emoji}{elem_e} **{p['name']}** Lv{lv} — {stat_str}"
                armor_lines.append(line)
            embed.add_field(
                name="🛡️ Equipped Armor  *(scaled stats)*",
                value="\n".join(armor_lines),
                inline=False
            )
        else:
            embed.add_field(
                name="🛡️ Equipped Armor",
                value="*None — use `/equip` to equip armor*\n*(Slots: Crown · Plate · Gauntlets · Greaves — each equips independently)*",
                inline=False
            )

        image_path = get_pet_image(element, variant, stage)
        file = discord.File(image_path, filename="pet.png")
        embed.set_thumbnail(url="attachment://pet.png")
        if followup:
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="feed", description="Choose a pet and food item to feed from your inventory")
    async def feed(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            all_pets = await db.get_player_pets(conn, interaction.user.id)
            exp = await db.get_active_expedition(conn, interaction.user.id)
            exp_pet_id = exp["pet_id"] if exp else None

            # Pets that can be fed (not on expedition)
            feedable = [p for p in all_pets if p["id"] != exp_pet_id]
            if not feedable:
                await interaction.response.send_message(
                    "All your pets are on expedition!", ephemeral=True
                )
                return

            # Food items in inventory
            inventory = await db.get_inventory(conn, interaction.user.id)
            food_inv = [i for i in inventory if i["item_type"] == "food"]
            if not food_inv:
                await interaction.response.send_message(
                    "You have no food! Buy some with `/shop` or claim a drop with `/claim`.",
                    ephemeral=True
                )
                return

        # Kill any existing open feed session for this user
        old_view = _active_feed_views.get(interaction.user.id)
        if old_view:
            old_view.stop()

        view = FeedView(interaction.user.id, feedable, food_inv, interaction)
        _active_feed_views[interaction.user.id] = view
        embed = discord.Embed(
            title="🍽️ Feed a pet",
            description="Select a pet and a food item below, then click **Feed**.",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="train", description="Daily training — boost a random stat and gain XP")
    async def train(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            # Cooldown check first
            if player["last_train"]:
                last = datetime.fromisoformat(player["last_train"])
                if (datetime.now(timezone.utc) - last) < timedelta(hours=TRAIN_COOLDOWN_HOURS):
                    remaining = (last + timedelta(hours=TRAIN_COOLDOWN_HOURS)) - datetime.now(timezone.utc)
                    hrs = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)
                    await interaction.response.send_message(
                        f"You already trained today! Come back in **{hrs}h {mins}m**.", ephemeral=True
                    )
                    return

            pets = [p for p in await db.get_player_pets(conn, interaction.user.id) if p["stage"] > 0]

        if not pets:
            await interaction.response.send_message(
                "Your pet needs to hatch first! Feed it with `/feed`.", ephemeral=True
            )
            return

        if len(pets) == 1:
            await self._do_train(interaction, pets[0])
            return

        view = TrainPetPickerView(interaction.user.id, pets, self._do_train)
        embed = discord.Embed(
            title="💪 Train a Pet",
            description="Choose which pet to train today:",
            color=0xF1C40F
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _do_train(self, interaction: discord.Interaction, pet: dict):
        import random
        async with aiosqlite.connect(db.DB_PATH) as conn:
            stats = ["hp", "atk", "def", "spd", "mgk", "res"]
            chosen_stat = random.choice(stats)
            actual, capped = apply_stat_bonus(pet, chosen_stat, TRAIN_STAT_BOOST)
            if actual > 0:
                await conn.execute(
                    f"UPDATE pets SET bonus_{chosen_stat}=bonus_{chosen_stat}+? WHERE id=?",
                    (actual, pet["id"])
                )
            await db.add_xp(conn, pet["id"], TRAIN_XP)
            await conn.execute(
                "UPDATE players SET last_train=? WHERE user_id=?",
                (db.now_iso(), interaction.user.id)
            )
            await conn.commit()
            pet = await db.get_pet(conn, pet["id"])

        name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        color = ELEMENT_COLORS[pet["element"]]
        cap_note = " *(capped)*" if capped and actual == 0 else ""
        embed = discord.Embed(
            title=f"💪 {name} trained hard!",
            description=(
                f"+{actual} **{chosen_stat.upper()}**{cap_note}\n"
                f"+{TRAIN_XP} **XP**\n\n"
                f"Level {pet['level']} | {pet['xp']}/{xp_for_next_level(pet['level'])} XP"
            ),
            color=color
        )
        embed.set_footer(text="Training resets every 20 hours.")
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rename", description="Give one of your pets a custom name")
    async def rename(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pets = [p for p in await db.get_player_pets(conn, interaction.user.id) if p["stage"] > 0]

        if not pets:
            await interaction.response.send_message("You have no hatched pets to rename.", ephemeral=True)
            return

        # If only one pet, skip straight to the rename modal
        if len(pets) == 1:
            await interaction.response.send_modal(RenameModal(pets[0]))
            return

        view = RenamePetPickerView(interaction.user.id, pets)
        embed = discord.Embed(
            title="🎀 Rename a Pet",
            description="Choose which pet to rename:",
            color=0xF1C40F
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



async def setup(bot: commands.Bot):
    await bot.add_cog(Pet(bot))
