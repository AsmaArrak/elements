import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_EMOJIS, ELEMENT_COLORS, PET_NAMES, FOOD_ITEMS,
    STAT_ITEMS, ACCELERATORS, get_stone_image
)
from game.evolution import evolve_pet, can_evolve_to


def item_display_name(item_key: str, item_type: str, element: str = None) -> str:
    if item_type == "food":
        return FOOD_ITEMS.get(item_key, {}).get("display", item_key.title())
    if item_type == "stat_item":
        return STAT_ITEMS.get(item_key, {}).get("display", item_key.replace("_", " ").title())
    if item_type == "accelerator":
        return ACCELERATORS.get(item_key, {}).get("display", item_key.replace("_", " ").title())
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
        type_order = ["food", "stat_item", "accelerator", "evo_stone", "mega_stone", "egg", "scroll", "coins"]
        type_labels = {
            "food":        "🍖 Food",
            "stat_item":   "📦 Stat Items",
            "accelerator": "⏩ Expedition Accelerators",
            "evo_stone":   "💠 Evolution Stones",
            "mega_stone":  "⭐ Mega Stones",
            "egg":         "🥚 Eggs",
            "scroll":      "📜 Skill Scrolls",
            "coins":       "💰 Coins",
        }

        from config import RARITY_EMOJIS
        from game.skills import SKILLS

        for item in items:
            t = item["item_type"]
            if t not in groups:
                groups[t] = []
            name = item_display_name(item["item_key"], item["item_type"], item["element"])

            if t == "stat_item":
                desc = STAT_ITEMS.get(item["item_key"], {}).get("desc", "")
                groups[t].append(f"**{name}** ×{item['quantity']} — *{desc}*")
            elif t == "food":
                food = FOOD_ITEMS.get(item["item_key"], {})
                stat = food.get("stat", "?").upper()
                boost = food.get("boost", 0)
                rarity = food.get("rarity", "common")
                r_emoji = RARITY_EMOJIS.get(rarity, "⚪")
                groups[t].append(f"{r_emoji} **{name}** ×{item['quantity']} — *+{boost} {stat}*")
            elif t == "scroll":
                skill = SKILLS.get(item["item_key"], {})
                rarity = skill.get("rarity", "common")
                r_emoji = RARITY_EMOJIS.get(rarity, "⚪")
                elem = skill.get("element", "").title()
                groups[t].append(f"{r_emoji} **{skill.get('name', name)} Scroll** ×{item['quantity']} — *{elem} · {skill.get('desc', '')}*")
            elif t == "accelerator":
                acc = ACCELERATORS.get(item["item_key"], {})
                desc = acc.get("desc", "")
                groups[t].append(f"**{name}** ×{item['quantity']} — *{desc}*")
            elif t == "evo_stone":
                stone_name = "Uncommon Evo Stone (Evo 1→2)" if item["item_key"] == "evo_stone_uncommon" else "Rare Evo Stone (Evo 2→3)"
                elem = ELEMENT_DISPLAY.get(item["element"], "") if item["element"] else ""
                groups[t].append(f"**{elem} {stone_name}** ×{item['quantity']}")
            elif t == "mega_stone":
                elem = ELEMENT_DISPLAY.get(item["element"], "") if item["element"] else ""
                groups[t].append(f"**{elem} Mega Stone** ×{item['quantity']} — *Evo 3→Mega (need Exploration 100)*")
            else:
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

    async def use_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = []
        # Stat items
        for key, info in STAT_ITEMS.items():
            label = f"{info['display']} — {info['desc']}"
            if current.lower() in key.lower() or current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label[:100], value=key))
        # Evo stones
        for key, label in [
            ("evo_stone_uncommon", "Uncommon Evo Stone — evolves Evo 1 → Evo 2"),
            ("evo_stone_rare",     "Rare Evo Stone — evolves Evo 2 → Evo 3"),
            ("mega_stone",         "Mega Stone ⭐ — evolves Evo 3 → Mega"),
        ]:
            if current.lower() in key.lower() or current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label[:100], value=key))
        return choices[:25]

    @app_commands.command(name="use", description="Use a stat item or evolution stone on your active pet")
    @app_commands.describe(
        item="Pick a stat item or evo stone from the list",
        element="Element of the stone (required for evo/mega stones)"
    )
    @app_commands.autocomplete(item=use_autocomplete)
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
                from config import stat_cap
                new_bonus = pet[f"bonus_{stat_key}"] + actual
                new_total = pet[f"base_{stat_key}"] + new_bonus
                cap_val = stat_cap(pet[f"base_{stat_key}"], pet["level"])
                if actual == 0:
                    result_line = f"⛔ {stat_key.upper()} is already at cap! **{new_total}/{cap_val}**"
                elif capped:
                    result_line = f"+{actual} {stat_key.upper()} *(cap reached)* → **{new_total}/{cap_val}**"
                else:
                    result_line = f"+{actual} {stat_key.upper()} → **{new_total}/{cap_val}**"
                await interaction.response.send_message(
                    f"✅ Used **{STAT_ITEMS[item]['display']}** on **{name}**!\n{result_line}"
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
                pet_file = discord.File(image_path, filename="evo.png")

                # Show the stone art as thumbnail
                stone_file = None
                try:
                    stone_path = get_stone_image(pet["element"], item)
                    stone_file = discord.File(stone_path, filename="stone.png")
                except Exception:
                    pass

                embed = discord.Embed(
                    title=f"{'⭐ MEGA ' if target_stage == 4 else '✨ '}EVOLUTION!",
                    description=(
                        f"{emoji} **{name}** has reached **{stage_name}**!\n\n"
                        "All stats have been boosted significantly."
                    ),
                    color=color
                )
                embed.set_image(url="attachment://evo.png")
                if stone_file:
                    embed.set_thumbnail(url="attachment://stone.png")

                files = [pet_file] + ([stone_file] if stone_file else [])
                await interaction.response.send_message(embed=embed, files=files)

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

    @app_commands.command(name="incubate", description="Place an egg from your inventory to hatch it")
    @app_commands.describe(element="Element of the egg to incubate (e.g. ember, tide, void)")
    async def incubate(self, interaction: discord.Interaction, element: str):
        element = element.lower().strip()
        from config import ELEMENTS, PET_NAMES, get_pet_image
        if element not in ELEMENTS:
            await interaction.response.send_message(
                f"Unknown element `{element}`. Valid: {', '.join(ELEMENTS)}", ephemeral=True
            )
            return

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            # Check they have that egg in inventory
            if not await db.has_item(conn, interaction.user.id, "egg", element=element):
                await interaction.response.send_message(
                    f"You don't have a **{ELEMENT_DISPLAY.get(element, element.title())} Egg** 🥚 in your inventory!",
                    ephemeral=True
                )
                return

            # Remove from inventory
            await db.remove_item(conn, interaction.user.id, "egg", element=element)

            # Pick a random variant (1 or 2) with pity system
            import random
            async with conn.execute(
                "SELECT last_variant FROM element_pity WHERE player_id=? AND element=?",
                (interaction.user.id, element)
            ) as cur:
                pity_row = await cur.fetchone()
            last_variant = pity_row[0] if pity_row else None
            if last_variant == 1:
                variant = 2
            elif last_variant == 2:
                variant = 1
            else:
                variant = random.choice([1, 2])
            await conn.execute(
                """INSERT INTO element_pity(player_id, element, last_variant)
                   VALUES(?,?,?) ON CONFLICT(player_id, element) DO UPDATE SET last_variant=?""",
                (interaction.user.id, element, variant, variant)
            )

            # Create the pet (stage 0 = egg)
            from game.stats import calc_base_stats
            base = calc_base_stats(element, 0)
            await conn.execute(
                """INSERT INTO pets (player_id, element, variant, stage, level, xp,
                   base_hp, base_atk, base_def, base_spd, base_mgk, base_res)
                   VALUES (?,?,?,0,1,0,?,?,?,?,?,?)""",
                (interaction.user.id, element, variant,
                 base["hp"], base["atk"], base["def"],
                 base["spd"], base["mgk"], base["res"])
            )
            await conn.commit()

        egg_name = PET_NAMES[element][variant][0]
        emoji = ELEMENT_EMOJIS[element]
        color = ELEMENT_COLORS[element]

        embed = discord.Embed(
            title=f"🥚 {egg_name} is now in your care!",
            description=(
                f"{emoji} Your **{ELEMENT_DISPLAY.get(element, element.title())} Egg** has been placed!\n\n"
                f"Feed it **3 times** with `/feed` to hatch it!"
            ),
            color=color
        )
        try:
            import os
            from config import get_pet_image, ASSETS_PATH
            img_path = os.path.join(ASSETS_PATH, element, "egg.png")
            if os.path.exists(img_path):
                file = discord.File(img_path, filename="egg.png")
                embed.set_thumbnail(url="attachment://egg.png")
                await interaction.response.send_message(embed=embed, file=file)
                return
        except Exception:
            pass
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Inventory(bot))
