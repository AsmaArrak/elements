import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone, timedelta

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_EMOJIS, ELEMENT_COLORS, PET_NAMES, STAGE_NAMES,
    FOOD_ITEMS, STAT_ITEMS, EXPEDITION_XP, EXPLORATION_GAIN, get_pet_image
)
from game.loot import generate_expedition_loot, generate_armor_drop


VALID_DURATIONS = {1, 6, 12, 24}


class ExpeditionPetSelect(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict], duration: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.duration = duration
        self.pets_by_id = {str(p["id"]): p for p in pets}
        options = []
        for p in pets:
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            emoji = ELEMENT_EMOJIS[p["element"]]
            stage_label = STAGE_NAMES[p["stage"]]
            options.append(discord.SelectOption(
                label=name,
                value=str(p["id"]),
                description=f"Level {p['level']} · {stage_label} · Exploration {p['exploration']}/100",
                emoji=emoji
            ))
        select = discord.ui.Select(placeholder="Choose a pet to send...", options=options)
        select.callback = self._callback
        self.add_item(select)

    async def _callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        pet = self.pets_by_id[interaction.data["values"][0]]
        self.stop()
        await interaction.response.defer()

        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute(
                "INSERT INTO expeditions(pet_id, player_id, start_time, duration_hrs) VALUES(?,?,?,?)",
                (pet["id"], interaction.user.id, db.now_iso(), self.duration)
            )
            await conn.commit()

        pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        emoji = ELEMENT_EMOJIS[pet["element"]]
        color = ELEMENT_COLORS[pet["element"]]
        returns_at = datetime.now(timezone.utc) + timedelta(hours=self.duration)
        ts = int(returns_at.timestamp())

        embed = discord.Embed(
            title="🗺️ Expedition Started!",
            description=(
                f"{emoji} **{pet_name}** has set out on a **{self.duration}-hour expedition**!\n\n"
                f"Returns: <t:{ts}:R> (<t:{ts}:t>)\n\n"
                f"Your pet is **locked** from battles until it returns.\n"
                f"Exploration stat: **{pet['exploration']}/100**"
                + (" — Mega Stone eligible! 🌟" if pet["exploration"] >= 100 else "")
            ),
            color=color
        )
        image_path = get_pet_image(pet["element"], pet["variant"], pet["stage"])
        try:
            file = discord.File(image_path, filename="pet.png")
            embed.set_thumbnail(url="attachment://pet.png")
            await interaction.followup.send(embed=embed, file=file)
        except Exception:
            await interaction.followup.send(embed=embed)

        try:
            await interaction.edit_original_response(
                embed=discord.Embed(description=f"✅ {pet_name} sent on expedition!", color=0x2ECC71),
                view=None
            )
        except Exception:
            pass


def item_display_name_simple(item_key: str, item_type: str, element: str = None) -> str:
    if item_type == "food":
        return FOOD_ITEMS.get(item_key, {}).get("display", item_key.title())
    if item_type == "stat_item":
        return STAT_ITEMS.get(item_key, {}).get("display", item_key.replace("_", " ").title())
    if item_type == "evo_stone":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "") + " "
        name = "Uncommon Evo Stone" if item_key == "evo_stone_uncommon" else "Rare Evo Stone"
        return f"{prefix}{name}"
    if item_type == "mega_stone":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "") + " "
        return f"{prefix}Mega Stone ⭐"
    if item_type == "egg":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "") + " "
        return f"{prefix}Egg 🥚"
    return item_key.replace("_", " ").title()


class Expedition(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="expedition", description="Send your active pet on an expedition")
    @app_commands.describe(
        duration="Duration: 1, 6, 12, or 24 hours",
        status="Use 'status' instead of a number to check your current expedition"
    )
    async def expedition(
        self,
        interaction: discord.Interaction,
        duration: int = 0,
        status: str = ""
    ):
        # /expedition status
        if status.lower() == "status" or duration == 0:
            await self._status(interaction)
            return

        if duration not in VALID_DURATIONS:
            await interaction.response.send_message(
                "Choose a duration: **1**, **6**, **12**, or **24** hours.", ephemeral=True
            )
            return

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            all_pets = await db.get_player_pets(conn, interaction.user.id)
            # Find which pets are already on expedition
            async with conn.execute(
                "SELECT pet_id FROM expeditions WHERE player_id=? AND returned=0",
                (interaction.user.id,)
            ) as cur:
                on_exp_ids = {row[0] for row in await cur.fetchall()}

            eligible = [
                p for p in all_pets
                if p["stage"] > 0 and p["id"] not in on_exp_ids
            ]

        if not eligible:
            if any(p["stage"] == 0 for p in all_pets):
                await interaction.response.send_message(
                    "Your egg can't go on expeditions! Feed it first.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "All your pets are already on expedition! Use `/expedition status` to check.",
                    ephemeral=True
                )
            return

        if len(eligible) == 1:
            pet = eligible[0]
            async with aiosqlite.connect(db.DB_PATH) as conn:
                await conn.execute(
                    "INSERT INTO expeditions(pet_id, player_id, start_time, duration_hrs) VALUES(?,?,?,?)",
                    (pet["id"], interaction.user.id, db.now_iso(), duration)
                )
                await conn.commit()

            pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
            emoji = ELEMENT_EMOJIS[pet["element"]]
            color = ELEMENT_COLORS[pet["element"]]
            returns_at = datetime.now(timezone.utc) + timedelta(hours=duration)
            ts = int(returns_at.timestamp())

            embed = discord.Embed(
                title="🗺️ Expedition Started!",
                description=(
                    f"{emoji} **{pet_name}** has set out on a **{duration}-hour expedition**!\n\n"
                    f"Returns: <t:{ts}:R> (<t:{ts}:t>)\n\n"
                    f"Your pet is **locked** from battles until it returns.\n"
                    f"Exploration stat: **{pet['exploration']}/100**"
                    + (" — Mega Stone eligible! 🌟" if pet["exploration"] >= 100 else "")
                ),
                color=color
            )
            image_path = get_pet_image(pet["element"], pet["variant"], pet["stage"])
            try:
                file = discord.File(image_path, filename="pet.png")
                embed.set_thumbnail(url="attachment://pet.png")
                await interaction.response.send_message(embed=embed, file=file)
            except Exception:
                await interaction.response.send_message(embed=embed)
        else:
            view = ExpeditionPetSelect(interaction.user.id, eligible, duration)
            await interaction.response.send_message(
                f"Which pet do you want to send on a **{duration}-hour expedition**?",
                view=view, ephemeral=True
            )

    async def _status(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            exp = await db.get_active_expedition(conn, interaction.user.id)
            if not exp:
                await interaction.response.send_message(
                    "No active expedition. Start one with `/expedition 6` (or 1/12/24).",
                    ephemeral=True
                )
                return
            pet = await db.get_pet(conn, exp["pet_id"])

        start = datetime.fromisoformat(exp["start_time"])
        duration = exp["duration_hrs"]
        end = start + timedelta(hours=duration)
        now = datetime.now(timezone.utc)
        remaining = end - now

        pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        emoji = ELEMENT_EMOJIS[pet["element"]]
        color = ELEMENT_COLORS[pet["element"]]
        ts = int(end.timestamp())

        if remaining.total_seconds() <= 0:
            embed = discord.Embed(
                title=f"📦 Expedition Complete!",
                description=f"{emoji} **{pet_name}** has returned! Use `/collect` to get your loot.",
                color=color
            )
        else:
            hrs = int(remaining.total_seconds() // 3600)
            mins = int((remaining.total_seconds() % 3600) // 60)
            embed = discord.Embed(
                title=f"🗺️ {pet_name} is exploring...",
                description=f"Returns <t:{ts}:R> | **{hrs}h {mins}m** remaining",
                color=color
            )
        embed.add_field(name="Duration", value=f"{duration}h expedition", inline=True)
        embed.add_field(name="Exploration", value=f"{pet['exploration']}/100", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="collect", description="Collect your pet and loot after an expedition")
    async def collect(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            exp = await db.get_active_expedition(conn, interaction.user.id)
            if not exp:
                await interaction.response.send_message(
                    "You don't have an active expedition.", ephemeral=True
                )
                return

            start = datetime.fromisoformat(exp["start_time"])
            end = start + timedelta(hours=exp["duration_hrs"])
            if datetime.now(timezone.utc) < end:
                remaining = end - datetime.now(timezone.utc)
                hrs = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                await interaction.response.send_message(
                    f"Your pet isn't back yet! **{hrs}h {mins}m** remaining.", ephemeral=True
                )
                return

            pet = await db.get_pet(conn, exp["pet_id"])

            # Generate loot
            loot = generate_expedition_loot(exp["duration_hrs"], pet["element"], pet["exploration"])

            # Award loot
            coin_total = 0
            loot_items = []
            for drop in loot:
                if drop["item_type"] == "coins":
                    coin_total += drop["qty"]
                else:
                    await db.add_item(
                        conn, interaction.user.id,
                        drop["item_key"], drop["item_type"],
                        drop["qty"], drop.get("element")
                    )
                    loot_items.append(drop)

            if coin_total:
                await conn.execute(
                    "UPDATE players SET coins=coins+? WHERE user_id=?",
                    (coin_total, interaction.user.id)
                )

            # XP for pet
            xp_gain = EXPEDITION_XP[exp["duration_hrs"]]
            await db.add_xp(conn, pet["id"], xp_gain)

            # Exploration gain
            exp_gain = EXPLORATION_GAIN[exp["duration_hrs"]]
            new_exploration = min(100, pet["exploration"] + exp_gain)
            await conn.execute(
                "UPDATE pets SET exploration=? WHERE id=?", (new_exploration, pet["id"])
            )

            # Armor drop
            armor_drop = generate_armor_drop(exp["duration_hrs"])
            if armor_drop:
                await conn.execute(
                    """INSERT INTO armor_inventory
                       (player_id, name, rarity, bonus_hp, bonus_atk, bonus_def, bonus_spd, bonus_mgk, bonus_res)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (interaction.user.id, armor_drop["name"], armor_drop["rarity"],
                     armor_drop.get("bonus_hp", 0), armor_drop.get("bonus_atk", 0),
                     armor_drop.get("bonus_def", 0), armor_drop.get("bonus_spd", 0),
                     armor_drop.get("bonus_mgk", 0), armor_drop.get("bonus_res", 0))
                )

            # Mark expedition returned
            await conn.execute(
                "UPDATE expeditions SET returned=1 WHERE id=?", (exp["id"],)
            )
            await conn.commit()
            pet = await db.get_pet(conn, pet["id"])

        pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        emoji = ELEMENT_EMOJIS[pet["element"]]
        color = ELEMENT_COLORS[pet["element"]]

        embed = discord.Embed(
            title=f"📦 {pet_name} returned from expedition!",
            description=f"{emoji} **{exp['duration_hrs']}-hour expedition** complete!",
            color=color
        )

        # Loot display
        loot_lines = []
        mega_found = False
        for drop in loot_items:
            name = item_display_name_simple(drop["item_key"], drop["item_type"], drop.get("element"))
            qty = drop["qty"]
            loot_lines.append(f"• **{name}**" + (f" ×{qty}" if qty > 1 else ""))
            if drop["item_type"] == "mega_stone":
                mega_found = True
        if coin_total:
            loot_lines.append(f"• **{coin_total} coins** 💰")
        if armor_drop:
            from config import RARITY_EMOJIS
            r_emoji = RARITY_EMOJIS.get(armor_drop["rarity"], "")
            loot_lines.append(f"• {r_emoji} **{armor_drop['name']}** *(armor)*")

        embed.add_field(
            name="🎒 Loot Found",
            value="\n".join(loot_lines) if loot_lines else "Nothing this time...",
            inline=False
        )
        embed.add_field(name="XP Gained", value=f"+{xp_gain} XP", inline=True)
        embed.add_field(
            name="Exploration",
            value=f"{pet['exploration']}/100 (+{exp_gain})",
            inline=True
        )

        await interaction.response.send_message(embed=embed)

        # Mega stone server announcement
        if mega_found and interaction.guild:
            async with aiosqlite.connect(db.DB_PATH) as cfg_conn:
                cfg = await db.get_guild_config(cfg_conn, interaction.guild.id)
            ch_id = cfg.get("announce_channel_id") if cfg else None
            ch = interaction.guild.get_channel(ch_id) if ch_id else interaction.channel
            if ch:
                await ch.send(
                    f"⚡ **LEGENDARY DROP** ⚡\n"
                    f"{interaction.user.mention}'s **{pet_name}** discovered a "
                    f"**{ELEMENT_DISPLAY[pet['element']]} Mega Stone** during exploration! {emoji}"
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(Expedition(bot))
