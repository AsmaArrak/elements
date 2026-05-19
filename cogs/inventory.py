import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_EMOJIS, ELEMENT_COLORS, PET_NAMES, FOOD_ITEMS,
    STAT_ITEMS, get_stone_image
)
from game.evolution import evolve_pet, can_evolve_to


def item_display_name(item_key: str, item_type: str, element: str = None) -> str:
    if item_type == "food":
        return FOOD_ITEMS.get(item_key, {}).get("display", item_key.title())
    if item_type == "stat_item":
        return STAT_ITEMS.get(item_key, {}).get("display", item_key.replace("_", " ").title())
    if item_type == "evo_stone":
        prefix = ELEMENT_DISPLAY.get(element, element.title()) + " " if element else ""
        stone_name = "Uncommon Evo Stone" if item_key == "evo_stone_uncommon" else "Rare Evo Stone"
        return f"{prefix}{stone_name}"
    if item_type == "mega_stone":
        prefix = ELEMENT_DISPLAY.get(element, element.title()) + " " if element else ""
        return f"{prefix}Mega Stone ⭐"
    if item_type == "egg":
        prefix = ELEMENT_DISPLAY.get(element, element.title()) + " " if element else ""
        return f"{prefix}Egg 🥚"
    if item_type == "coins":
        return "Coins 💰"
    return item_key.replace("_", " ").title()


class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="inventory", description="View everything in your inventory")
    async def inventory(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            items = await db.get_inventory(conn, interaction.user.id)

        if not items:
            await interaction.response.send_message(
                "Your inventory is empty! Claim drops with `/claim` or go on `/expedition`.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🎒 {interaction.user.display_name}'s Inventory",
            color=0x7B68EE
        )

        # Group by type
        groups: dict[str, list[str]] = {}
        type_order = ["food", "stat_item", "evo_stone", "mega_stone", "egg", "coins"]
        type_labels = {
            "food": "🍖 Food",
            "stat_item": "📦 Stat Items",
            "evo_stone": "💠 Evolution Stones",
            "mega_stone": "⭐ Mega Stones",
            "egg": "🥚 Eggs",
            "coins": "💰 Coins",
        }

        for item in items:
            t = item["item_type"]
            if t not in groups:
                groups[t] = []
            name = item_display_name(item["item_key"], item["item_type"], item["element"])
            groups[t].append(f"**{name}** ×{item['quantity']}")

        for t in type_order:
            if t in groups:
                embed.add_field(
                    name=type_labels.get(t, t.title()),
                    value="\n".join(groups[t]),
                    inline=False
                )

        embed.set_footer(text=f"💰 {player['coins']} coins")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="use", description="Use an evolution stone or stat item on your active pet")
    @app_commands.describe(
        item="Item to use: evo_stone_uncommon, evo_stone_rare, mega_stone, or a stat item name",
        element="Element of the stone (required for evo/mega stones)"
    )
    async def use(self, interaction: discord.Interaction, item: str, element: str = None):
        item = item.lower().strip()
        if element:
            element = element.lower().strip()

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pet = await db.get_active_pet(conn, interaction.user.id)
            if not pet:
                await interaction.response.send_message("No active pet.", ephemeral=True)
                return

            exp = await db.get_active_expedition(conn, interaction.user.id)
            if exp and exp["pet_id"] == pet["id"]:
                await interaction.response.send_message(
                    "Your pet is on an expedition!", ephemeral=True
                )
                return

            # Stat items
            if item in STAT_ITEMS:
                if not await db.has_item(conn, interaction.user.id, item):
                    await interaction.response.send_message(
                        f"You don't have a **{STAT_ITEMS[item]['display']}**.", ephemeral=True
                    )
                    return
                from game.stats import apply_stat_bonus
                stat_key = STAT_ITEMS[item]["stat"]
                boost = STAT_ITEMS[item]["boost"]
                actual, capped = apply_stat_bonus(pet, stat_key, boost)
                if actual > 0:
                    await conn.execute(
                        f"UPDATE pets SET bonus_{stat_key}=bonus_{stat_key}+? WHERE id=?",
                        (actual, pet["id"])
                    )
                await db.remove_item(conn, interaction.user.id, item)
                await conn.commit()

                name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
                cap_note = " *(stat is at cap)*" if capped and actual == 0 else ""
                await interaction.response.send_message(
                    f"Used **{STAT_ITEMS[item]['display']}** on **{name}**!\n"
                    f"+{actual} **{stat_key.upper()}**{cap_note}"
                )
                return

            # Evolution stones
            evo_stones = {"evo_stone_uncommon": 2, "evo_stone_rare": 3, "mega_stone": 4}
            if item in evo_stones:
                target_stage = evo_stones[item]
                req_element = pet["element"]

                if not element:
                    await interaction.response.send_message(
                        f"Specify the element of your stone: `/use {item} element:{req_element}`",
                        ephemeral=True
                    )
                    return

                if element != req_element:
                    await interaction.response.send_message(
                        f"That stone is for **{ELEMENT_DISPLAY.get(element, element)}** pets, "
                        f"but your pet is **{ELEMENT_DISPLAY[req_element]}**.",
                        ephemeral=True
                    )
                    return

                has_it = await db.has_item(conn, interaction.user.id, item, element=req_element)
                ok, reason = can_evolve_to(pet, target_stage, has_it, item)
                if not ok:
                    await interaction.response.send_message(reason, ephemeral=True)
                    return

                await db.remove_item(conn, interaction.user.id, item, element=req_element)
                await evolve_pet(conn, pet, target_stage)
                await conn.commit()
                pet = await db.get_pet(conn, pet["id"])

                name = PET_NAMES[pet["element"]][pet["variant"]][target_stage]
                stage_name = ["Egg", "Evo 1", "Evo 2", "Evo 3", "MEGA EVOLUTION"][target_stage]
                emoji = ELEMENT_EMOJIS[pet["element"]]
                color = ELEMENT_COLORS[pet["element"]]

                from config import get_pet_image
                image_path = get_pet_image(pet["element"], pet["variant"], target_stage)
                file = discord.File(image_path, filename="evo.png")

                embed = discord.Embed(
                    title=f"{'⭐ MEGA ' if target_stage == 4 else '✨ '}EVOLUTION!",
                    description=(
                        f"{emoji} **{name}** has reached **{stage_name}**!\n\n"
                        "All stats have been boosted significantly."
                    ),
                    color=color
                )
                embed.set_image(url="attachment://evo.png")
                await interaction.response.send_message(embed=embed, file=file)

                # Mega announcement
                if target_stage == 4 and interaction.guild:
                    async with aiosqlite.connect(db.DB_PATH) as cfg_conn:
                        cfg = await db.get_guild_config(cfg_conn, interaction.guild.id)
                    ch_id = cfg.get("announce_channel_id") if cfg else None
                    ch = interaction.guild.get_channel(ch_id) if ch_id else interaction.channel
                    if ch:
                        try:
                            ann_file = discord.File(image_path, filename="mega.png")
                            ann_embed = discord.Embed(
                                title="⚡ LEGENDARY EVOLUTION ⚡",
                                description=(
                                    f"{interaction.user.mention}'s **{name}** has achieved "
                                    f"**MEGA EVOLUTION**!\n{emoji} The server trembles..."
                                ),
                                color=color
                            )
                            ann_embed.set_image(url="attachment://mega.png")
                            await ch.send(embed=ann_embed, file=ann_file)
                        except Exception:
                            await ch.send(
                                f"⚡ **MEGA EVOLUTION!** ⚡\n"
                                f"{interaction.user.mention}'s **{name}** {emoji} has gone Mega!"
                            )
                return

            await interaction.response.send_message(
                f"Unknown item: **{item}**.\nValid evo stones: `evo_stone_uncommon`, `evo_stone_rare`, `mega_stone`\n"
                f"Stat items: " + ", ".join(STAT_ITEMS.keys()),
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Inventory(bot))
