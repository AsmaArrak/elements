import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_EMOJIS, ELEMENT_COLORS, PET_NAMES, STAGE_NAMES, FOOD_ITEMS,
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


class UseView(discord.ui.View):
    """Pet picker + item picker to use a stat item or evo stone."""

    def __init__(self, user_id: int, pets: list[dict], item_options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pets = pets
        self.selected_pet_id: int | None = pets[0]["id"] if len(pets) == 1 else None

        # Pet picker (only shown if >1 pet)
        if len(pets) > 1:
            pet_opts = []
            for p in pets:
                name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
                pet_opts.append(discord.SelectOption(
                    label=name, value=str(p["id"]),
                    description=f"Level {p['level']} · {STAGE_NAMES[p['stage']]}",
                    emoji=ELEMENT_EMOJIS[p["element"]]
                ))
            pet_sel = discord.ui.Select(placeholder="🐾 Choose a pet...", options=pet_opts, row=0)
            pet_sel.callback = self._pet_cb
            self.add_item(pet_sel)

        item_sel = discord.ui.Select(
            placeholder="🎒 Choose an item to use...",
            options=item_options,
            row=1
        )
        item_sel.callback = self._on_select
        self.add_item(item_sel)

    async def _pet_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.selected_pet_id = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return
        if not self.selected_pet_id:
            await interaction.response.send_message("Pick a pet first!", ephemeral=True)
            return

        self.stop()
        # Value format: "item_key|element"
        raw = interaction.data["values"][0]
        item_key, element = raw.split("|", 1)
        element = element or None

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.edit_message(content="❌ Account not found.", embed=None, view=None)
                return
            pet = await db.get_pet(conn, self.selected_pet_id)
            if not pet:
                await interaction.response.edit_message(content="❌ Pet not found.", embed=None, view=None)
                return

            exp = await db.get_active_expedition(conn, interaction.user.id)
            if exp and exp["pet_id"] == pet["id"]:
                await interaction.response.edit_message(
                    content="❌ Your pet is on an expedition!", embed=None, view=None
                )
                return

            # ── Stat item ──────────────────────────────────────────────────────
            if item_key in STAT_ITEMS:
                if not await db.has_item(conn, interaction.user.id, item_key):
                    await interaction.response.edit_message(
                        content=f"❌ You no longer have **{STAT_ITEMS[item_key]['display']}**.",
                        embed=None, view=None
                    )
                    return
                from game.stats import apply_stat_bonus
                from config import stat_cap
                stat_key = STAT_ITEMS[item_key]["stat"]
                boost = STAT_ITEMS[item_key]["boost"]
                actual, capped = apply_stat_bonus(pet, stat_key, boost)
                if actual > 0:
                    await conn.execute(
                        f"UPDATE pets SET bonus_{stat_key}=bonus_{stat_key}+? WHERE id=?",
                        (actual, pet["id"])
                    )
                await db.remove_item(conn, interaction.user.id, item_key)
                await conn.commit()

                name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
                new_bonus = pet[f"bonus_{stat_key}"] + actual
                new_total = pet[f"base_{stat_key}"] + new_bonus
                cap_val = stat_cap(pet[f"base_{stat_key}"], pet["level"])

                if actual == 0:
                    result_line = f"⛔ {stat_key.upper()} is already at cap! **{new_total}/{cap_val}**"
                elif capped:
                    result_line = f"+{actual} {stat_key.upper()} *(cap reached)* → **{new_total}/{cap_val}**"
                else:
                    result_line = f"+{actual} {stat_key.upper()} → **{new_total}/{cap_val}**"

                embed = discord.Embed(
                    description=f"✅ Used **{STAT_ITEMS[item_key]['display']}** on **{name}**!\n{result_line}",
                    color=0x2ECC71
                )
                await interaction.response.edit_message(embed=embed, view=None)
                return

            # ── Evo / Mega stone ───────────────────────────────────────────────
            evo_stones = {"evo_stone_uncommon": 2, "evo_stone_rare": 3, "mega_stone": 4}
            if item_key in evo_stones:
                from game.evolution import evolve_pet, can_evolve_to
                from config import get_pet_image
                target_stage = evo_stones[item_key]
                req_element = pet["element"]

                if element and element != req_element:
                    await interaction.response.edit_message(
                        content=(
                            f"❌ That stone is for **{ELEMENT_DISPLAY.get(element, element)}** pets, "
                            f"but your pet is **{ELEMENT_DISPLAY[req_element]}**."
                        ),
                        embed=None, view=None
                    )
                    return

                has_it = await db.has_item(conn, interaction.user.id, item_key, element=req_element)
                ok, reason = can_evolve_to(pet, target_stage, has_it, item_key)
                if not ok:
                    await interaction.response.edit_message(content=f"❌ {reason}", embed=None, view=None)
                    return

                await db.remove_item(conn, interaction.user.id, item_key, element=req_element)
                await evolve_pet(conn, pet, target_stage)
                await conn.commit()
                pet = await db.get_pet(conn, pet["id"])

                name = PET_NAMES[pet["element"]][pet["variant"]][target_stage]
                stage_name = ["Egg", "Evo 1", "Evo 2", "Evo 3", "MEGA EVOLUTION"][target_stage]
                emoji = ELEMENT_EMOJIS[pet["element"]]
                color = ELEMENT_COLORS[pet["element"]]

                image_path = get_pet_image(pet["element"], pet["variant"], target_stage)
                pet_file = discord.File(image_path, filename="evo.png")
                stone_file = None
                try:
                    stone_path = get_stone_image(pet["element"], item_key)
                    stone_file = discord.File(stone_path, filename="stone.png")
                except Exception:
                    pass

                evo_embed = discord.Embed(
                    title=f"{'⭐ MEGA ' if target_stage == 4 else '✨ '}EVOLUTION!",
                    description=(
                        f"{emoji} **{name}** has reached **{stage_name}**!\n\n"
                        "All stats have been boosted significantly."
                    ),
                    color=color
                )
                evo_embed.set_image(url="attachment://evo.png")
                if stone_file:
                    evo_embed.set_thumbnail(url="attachment://stone.png")

                # Dismiss the dropdown first, then send evo result as followup
                await interaction.response.edit_message(
                    content="✨ Evolution in progress...", embed=None, view=None
                )
                files = [pet_file] + ([stone_file] if stone_file else [])
                await interaction.followup.send(embed=evo_embed, files=files)

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


class IncubateView(discord.ui.View):
    """Dropdown to pick which egg to incubate."""

    def __init__(self, user_id: int, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        self.user_id = user_id

        sel = discord.ui.Select(
            placeholder="🥚 Choose an egg to incubate...",
            options=options,
            row=0
        )
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return

        element = interaction.data["values"][0]
        self.stop()

        import random
        import os
        from config import ELEMENTS, PET_NAMES, ASSETS_PATH
        from game.stats import calc_base_stats

        async with aiosqlite.connect(db.DB_PATH) as conn:
            # Re-check they still have the egg
            if not await db.has_item(conn, interaction.user.id, "egg", element=element):
                await interaction.response.edit_message(
                    content=f"❌ You no longer have a **{ELEMENT_DISPLAY.get(element, element.title())} Egg**!",
                    embed=None, view=None
                )
                return

            # Remove from inventory
            await db.remove_item(conn, interaction.user.id, "egg", element=element)

            # Variant with pity (alternates between 1 and 2)
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

            # Create egg pet (stage 0)
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
        display = ELEMENT_DISPLAY.get(element, element.title())

        embed = discord.Embed(
            title=f"🥚 {egg_name} is now in your care!",
            description=(
                f"{emoji} Your **{display} Egg** has been placed!\n\n"
                f"Feed it **3 times** with `/feed` to hatch it!"
            ),
            color=color
        )
        try:
            img_path = os.path.join(ASSETS_PATH, element, "egg.png")
            if os.path.exists(img_path):
                file = discord.File(img_path, filename="egg.png")
                embed.set_thumbnail(url="attachment://egg.png")
                await interaction.response.edit_message(embed=embed, view=None, attachments=[file])
                return
        except Exception:
            pass
        await interaction.response.edit_message(embed=embed, view=None)


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

    @app_commands.command(name="use", description="Use a stat item or evolution stone on a pet")
    async def use(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            inventory = await db.get_inventory(conn, interaction.user.id)
            pets = [p for p in await db.get_player_pets(conn, interaction.user.id) if p["stage"] > 0]

        # Filter to only usable item types
        usable_types = {"stat_item", "evo_stone", "mega_stone"}
        usable = [i for i in inventory if i["item_type"] in usable_types and i["quantity"] > 0]

        if not pets:
            await interaction.response.send_message(
                "You need a hatched pet to use items!", ephemeral=True
            )
            return
        if not usable:
            await interaction.response.send_message(
                "You have no usable items!\nStat items drop from expeditions and `/dig`. "
                "Evo stones drop from expeditions.",
                ephemeral=True
            )
            return

        options = []
        for item in usable[:25]:
            key = item["item_key"]
            itype = item["item_type"]
            element = item.get("element") or ""
            qty = item["quantity"]

            if itype == "stat_item":
                info = STAT_ITEMS.get(key, {})
                label = f"{info.get('display', key)} ×{qty}"
                desc = info.get("desc", "")
                emoji_str = "📦"
            elif itype == "evo_stone":
                elem_display = ELEMENT_DISPLAY.get(element, element.title())
                stone_name = "Uncommon Evo Stone" if key == "evo_stone_uncommon" else "Rare Evo Stone"
                label = f"{elem_display} {stone_name} ×{qty}"
                desc = "Evo 1 → 2" if key == "evo_stone_uncommon" else "Evo 2 → 3"
                emoji_str = "💠"
            else:  # mega_stone
                elem_display = ELEMENT_DISPLAY.get(element, element.title())
                label = f"{elem_display} Mega Stone ×{qty}"
                desc = "Evo 3 → MEGA ⭐"
                emoji_str = "⭐"

            options.append(discord.SelectOption(
                label=label[:100],
                value=f"{key}|{element}",
                description=desc[:100],
                emoji=emoji_str
            ))

        view = UseView(interaction.user.id, pets, options)
        desc = "Choose a pet and an item to use." if len(pets) > 1 else "Choose an item to use on your pet."
        embed = discord.Embed(title="🎒 Use an Item", description=desc, color=0x7B68EE)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="incubate", description="Place an egg from your inventory to hatch it")
    async def incubate(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            # Fetch all eggs in inventory
            async with conn.execute(
                "SELECT element, quantity FROM inventory WHERE player_id=? AND item_key='egg' AND quantity>0",
                (interaction.user.id,)
            ) as cur:
                egg_rows = await cur.fetchall()

        if not egg_rows:
            await interaction.response.send_message(
                "🥚 You have no eggs in your inventory!\nFind eggs from expeditions, channel drops, or the `/start` command.",
                ephemeral=True
            )
            return

        # Build dropdown options from owned eggs
        options = []
        for element, qty in egg_rows:
            emoji = ELEMENT_EMOJIS.get(element, "🥚")
            display = ELEMENT_DISPLAY.get(element, element.title())
            options.append(discord.SelectOption(
                label=f"{display} Egg",
                value=element,
                description=f"You have {qty}× · Feed 3 times to hatch",
                emoji=emoji
            ))

        view = IncubateView(interaction.user.id, options)
        embed = discord.Embed(
            title="🥚 Incubate an Egg",
            description="Choose which egg to place. Feed it **3 times** with `/feed` to hatch it!",
            color=0xF1C40F
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Inventory(bot))
