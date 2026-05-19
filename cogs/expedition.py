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
from game.loot import generate_expedition_loot


VALID_DURATIONS = {1, 6, 12, 24}


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

            # Check if already on expedition
            existing = await db.get_active_expedition(conn, interaction.user.id)
            if existing:
                pet_on_exp = await db.get_pet(conn, existing["pet_id"])
                pet_name = PET_NAMES[pet_on_exp["element"]][pet_on_exp["variant"]][pet_on_exp["stage"]]
                await interaction.response.send_message(
                    f"**{pet_name}** is already on an expedition! Use `/expedition status` to check.",
                    ephemeral=True
                )
                return

            pet = await db.get_active_pet(conn, interaction.user.id)
            if not pet:
                await interaction.response.send_message("No active pet.", ephemeral=True)
                return
            if pet["stage"] == 0:
                await interaction.response.send_message(
                    "Your egg can't go on expeditions! Feed it first.", ephemeral=True
                )
                return

            start = db.now_iso()
            await conn.execute(
                "INSERT INTO expeditions(pet_id, player_id, start_time, duration_hrs) VALUES(?,?,?,?)",
                (pet["id"], interaction.user.id, start, duration)
            )
            await conn.commit()

        pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        emoji = ELEMENT_EMOJIS[pet["element"]]
        color = ELEMENT_COLORS[pet["element"]]

        returns_at = datetime.now(timezone.utc) + timedelta(hours=duration)
        ts = int(returns_at.timestamp())

        embed = discord.Embed(
            title=f"🗺️ Expedition Started!",
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
