import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import json

import database as db
from config import (
    PET_NAMES, ELEMENT_EMOJIS, STAGE_NAMES, RARITY_EMOJIS,
    ARMOR_SETS, ARMOR_LEVEL_XP, ARMOR_UPGRADE_COINS, ARMOR_FODDER_XP,
    ARMOR_SUBSTAT_UNLOCK_LEVELS, ARMOR_LEVEL_MULT,
)
from game.dungeon_loot import effective_armor_stats, roll_substat, xp_to_next_armor_level


def armor_bonus_line(row: dict) -> str:
    bonuses = []
    for stat in ("hp", "atk", "def", "spd", "mgk", "res"):
        val = row.get(f"bonus_{stat}", 0)
        if val:
            bonuses.append(f"+{val} {stat.upper()}")
    return " · ".join(bonuses) if bonuses else "no bonuses"


def armor_sell_price(rarity: str) -> int:
    return {"common": 150, "uncommon": 400, "rare": 1000, "legendary": 3000}.get(rarity, 150)


class EquipView(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict], armor_list: list[dict]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.selected_pet = pets[0] if len(pets) == 1 else None
        self.selected_armor_id = None
        self.pets = pets
        self.armor_list = armor_list

        if len(pets) > 1:
            pet_opts = []
            for p in pets:
                name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
                pet_opts.append(discord.SelectOption(
                    label=name, value=str(p["id"]),
                    description=f"Level {p['level']} · {STAGE_NAMES[p['stage']]}",
                    emoji=ELEMENT_EMOJIS[p["element"]]
                ))
            pet_sel = discord.ui.Select(placeholder="Choose a pet...", options=pet_opts, row=0)
            pet_sel.callback = self._pet_cb
            self.add_item(pet_sel)

        armor_opts = []
        for ar in armor_list[:25]:
            r_emoji = RARITY_EMOJIS.get(ar["rarity"], "⚪")
            armor_opts.append(discord.SelectOption(
                label=ar["name"], value=str(ar["id"]),
                description=f"{ar['rarity'].title()} · {armor_bonus_line(ar)[:50]}",
                emoji=r_emoji
            ))
        armor_sel = discord.ui.Select(placeholder="Choose armor to equip...", options=armor_opts, row=1)
        armor_sel.callback = self._armor_cb
        self.add_item(armor_sel)

        confirm = discord.ui.Button(label="✅ Equip", style=discord.ButtonStyle.success, row=2)
        confirm.callback = self._confirm_cb
        self.add_item(confirm)

    async def _pet_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        pid = int(interaction.data["values"][0])
        self.selected_pet = next(p for p in self.pets if p["id"] == pid)
        await interaction.response.defer()

    async def _armor_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.selected_armor_id = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def _confirm_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        if not self.selected_pet:
            await interaction.response.send_message("Select a pet first.", ephemeral=True)
            return
        if not self.selected_armor_id:
            await interaction.response.send_message("Select armor first.", ephemeral=True)
            return
        self.stop()
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute(
                "UPDATE pets SET equipped_armor=? WHERE id=?",
                (self.selected_armor_id, self.selected_pet["id"])
            )
            await conn.commit()
            async with conn.execute(
                "SELECT name, rarity FROM armor_inventory WHERE id=?", (self.selected_armor_id,)
            ) as cur:
                ar = await cur.fetchone()
        pet_name = self.selected_pet.get("nickname") or PET_NAMES[self.selected_pet["element"]][self.selected_pet["variant"]][self.selected_pet["stage"]]
        r_emoji = RARITY_EMOJIS.get(ar[1], "")
        await interaction.response.edit_message(
            embed=discord.Embed(
                description=f"✅ **{pet_name}** is now wearing {r_emoji} **{ar[0]}**!",
                color=0x2ECC71
            ),
            view=None
        )


class Armor(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="equip", description="Equip armor to one of your pets")
    async def equip(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pets = await db.get_player_pets(conn, interaction.user.id)
            pets = [p for p in pets if p["stage"] > 0]
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE player_id=? ORDER BY rarity DESC, name",
                (interaction.user.id,)
            ) as cur:
                cols = [d[0] for d in cur.description]
                armor_list = [dict(zip(cols, r)) for r in await cur.fetchall()]

        if not pets:
            await interaction.response.send_message("You need a hatched pet to equip armor.", ephemeral=True)
            return
        if not armor_list:
            await interaction.response.send_message(
                "You have no armor! Go on expeditions to find some.", ephemeral=True
            )
            return

        view = EquipView(interaction.user.id, pets, armor_list)
        await interaction.response.send_message(
            "Choose a pet and armor piece to equip:", view=view, ephemeral=True
        )

    @app_commands.command(name="armor", description="View your armor collection")
    async def armor_cmd(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE player_id=? ORDER BY rarity DESC, name",
                (interaction.user.id,)
            ) as cur:
                cols = [d[0] for d in cur.description]
                armor_list = [dict(zip(cols, r)) for r in await cur.fetchall()]

        if not armor_list:
            await interaction.response.send_message(
                "You have no armor yet. Go on expeditions to find some!", ephemeral=True
            )
            return

        embed = discord.Embed(title="🛡️ Your Armor Collection", color=0x7B68EE)
        by_rarity = {"legendary": [], "rare": [], "uncommon": [], "common": []}
        for ar in armor_list:
            by_rarity[ar["rarity"]].append(ar)

        for rarity in ("legendary", "rare", "uncommon", "common"):
            pieces = by_rarity[rarity]
            if not pieces:
                continue
            r_emoji = RARITY_EMOJIS.get(rarity, "")
            lines = []
            for ar in pieces:
                sell = armor_sell_price(rarity)
                lines.append(f"{r_emoji} **{ar['name']}** (ID:{ar['id']}) — {armor_bonus_line(ar)} | sell: {sell}🪙")
            embed.add_field(name=rarity.title(), value="\n".join(lines), inline=False)

        embed.set_footer(text="Use /equip to equip armor · /sellarmor <id> to sell")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="sellarmor", description="Sell a piece of armor for coins")
    @app_commands.describe(armor_id="The armor ID shown in /armor")
    async def sellarmor(self, interaction: discord.Interaction, armor_id: int):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE id=? AND player_id=?",
                (armor_id, interaction.user.id)
            ) as cur:
                cols = [d[0] for d in cur.description]
                row = await cur.fetchone()

            if not row:
                await interaction.response.send_message("Armor not found in your collection.", ephemeral=True)
                return
            ar = dict(zip(cols, row))

            # Unequip from any pet first
            await conn.execute(
                "UPDATE pets SET equipped_armor=NULL WHERE equipped_armor=? AND player_id=?",
                (armor_id, interaction.user.id)
            )
            await conn.execute("DELETE FROM armor_inventory WHERE id=?", (armor_id,))
            price = armor_sell_price(ar["rarity"])
            await conn.execute(
                "UPDATE players SET coins=coins+? WHERE user_id=?", (price, interaction.user.id)
            )
            await conn.commit()

        r_emoji = RARITY_EMOJIS.get(ar["rarity"], "")
        await interaction.response.send_message(
            f"Sold {r_emoji} **{ar['name']}** for **{price} coins**! 💰"
        )


    @app_commands.command(name="upgradearmor", description="Use armor pieces as fodder to upgrade another piece")
    async def upgradearmor(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE player_id=? ORDER BY rarity DESC, armor_level DESC",
                (interaction.user.id,)
            ) as cur:
                cols = [d[0] for d in cur.description]
                armor_list = [dict(zip(cols, r)) for r in await cur.fetchall()]

        upgradeable = [a for a in armor_list if (a.get("armor_level") or 1) < 15 and a.get("set_name")]
        fodder_pool = [a for a in armor_list if a.get("set_name")]  # any set armor can be fodder

        if not upgradeable:
            await interaction.response.send_message(
                "No upgradeable armor! Farm dungeons or go on expeditions to get set armor pieces.",
                ephemeral=True
            )
            return
        if len(fodder_pool) < 2:
            await interaction.response.send_message(
                "You need at least 2 armor pieces — one to upgrade and one as fodder.",
                ephemeral=True
            )
            return

        view = UpgradeArmorView(interaction.user.id, upgradeable, fodder_pool)
        await interaction.response.send_message(
            "**🔨 Armor Upgrade**\nSelect the piece to upgrade, then the pieces to sacrifice as fodder:",
            view=view, ephemeral=True
        )


class UpgradeArmorView(discord.ui.View):
    def __init__(self, user_id: int, upgradeable: list[dict], all_armor: list[dict]):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.upgradeable = upgradeable
        self.all_armor = all_armor
        self.target_id: int | None = None
        self.fodder_ids: list[int] = []

        # Target select
        target_opts = []
        for a in upgradeable[:25]:
            r_emoji = RARITY_EMOJIS.get(a["rarity"], "⚪")
            lv = a.get("armor_level") or 1
            elem = ELEMENT_EMOJIS.get(a.get("set_name", ""), "")
            target_opts.append(discord.SelectOption(
                label=f"{a['name']} (Lv {lv})",
                value=str(a["id"]),
                description=f"{a['rarity'].title()} · {armor_bonus_line(a)[:40]}",
                emoji=r_emoji
            ))
        target_sel = discord.ui.Select(placeholder="Piece to UPGRADE...", options=target_opts, row=0)
        target_sel.callback = self._target_cb
        self.add_item(target_sel)

        # Fodder select (multi, up to 4)
        fodder_opts = []
        for a in all_armor[:25]:
            r_emoji = RARITY_EMOJIS.get(a["rarity"], "⚪")
            lv = a.get("armor_level") or 1
            xp_val = ARMOR_FODDER_XP.get(a["rarity"], 100)
            fodder_opts.append(discord.SelectOption(
                label=f"{a['name']} (Lv {lv})",
                value=str(a["id"]),
                description=f"Gives {xp_val} upgrade XP · {a['rarity'].title()}",
                emoji=r_emoji
            ))
        fodder_sel = discord.ui.Select(
            placeholder="Fodder pieces to SACRIFICE (up to 4)...",
            options=fodder_opts, row=1, min_values=1, max_values=min(4, len(fodder_opts))
        )
        fodder_sel.callback = self._fodder_cb
        self.add_item(fodder_sel)

        btn = discord.ui.Button(label="🔨 Upgrade", style=discord.ButtonStyle.success, row=2)
        btn.callback = self._upgrade_cb
        self.add_item(btn)

    async def _target_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.target_id = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def _fodder_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.fodder_ids = [int(v) for v in interaction.data["values"]]
        await interaction.response.defer()

    async def _upgrade_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        if not self.target_id:
            await interaction.response.send_message("Select a piece to upgrade first.", ephemeral=True)
            return
        if not self.fodder_ids:
            await interaction.response.send_message("Select at least one fodder piece.", ephemeral=True)
            return
        if self.target_id in self.fodder_ids:
            await interaction.response.send_message(
                "You can't use the upgrade target as fodder!", ephemeral=True
            )
            return

        self.stop()
        async with aiosqlite.connect(db.DB_PATH) as conn:
            # Fetch target
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE id=? AND player_id=?",
                (self.target_id, self.user_id)
            ) as cur:
                cols = [d[0] for d in cur.description]
                row = await cur.fetchone()
            if not row:
                await interaction.response.send_message("Target armor not found.", ephemeral=True)
                return
            target = dict(zip(cols, row))
            current_level = target.get("armor_level") or 1
            if current_level >= 15:
                await interaction.response.send_message("This piece is already at max level (15)!", ephemeral=True)
                return

            # Fetch fodder and calculate XP + coin cost
            total_xp = 0
            total_coins = 0
            for fid in self.fodder_ids:
                async with conn.execute(
                    "SELECT rarity, armor_level FROM armor_inventory WHERE id=? AND player_id=?",
                    (fid, self.user_id)
                ) as cur:
                    frow = await cur.fetchone()
                if frow:
                    base_xp = ARMOR_FODDER_XP.get(frow[0], 100)
                    # Fodder at higher levels gives more XP
                    fodder_lv = frow[1] or 1
                    total_xp += int(base_xp * (1 + (fodder_lv - 1) * 0.1))

            # Check player coins
            player = await db.get_player(conn, self.user_id)
            current_armor_xp = target.get("armor_xp") or 0
            armor_xp = current_armor_xp + total_xp

            # Process level-ups
            new_level = current_level
            sub_stats = json.loads(target.get("sub_stats") or "[]")
            new_substats_gained = []

            while new_level < 15:
                needed = xp_to_next_armor_level(new_level)
                if needed is None or armor_xp < needed:
                    break
                # Calculate coin cost for this level-up
                coin_cost = ARMOR_UPGRADE_COINS.get(new_level, 500)
                total_coins += coin_cost
                if (player.get("coins") or 0) < total_coins:
                    break
                armor_xp -= needed
                new_level += 1
                # Unlock substat if at unlock level
                if new_level in ARMOR_SUBSTAT_UNLOCK_LEVELS:
                    new_ss = roll_substat({**target, "sub_stats": json.dumps(sub_stats)})
                    if new_ss:
                        sub_stats.append(new_ss)
                        new_substats_gained.append(new_ss)

            if new_level == current_level and total_coins == 0:
                # No level up happened — just store the XP
                await conn.execute(
                    "UPDATE armor_inventory SET armor_xp=? WHERE id=?",
                    (armor_xp, self.target_id)
                )
                await conn.execute(
                    "UPDATE players SET coins=coins-? WHERE user_id=?",
                    (0, self.user_id)
                )
            else:
                # Deduct coins
                await conn.execute(
                    "UPDATE players SET coins=coins-? WHERE user_id=?",
                    (total_coins, self.user_id)
                )
                # Update armor
                await conn.execute(
                    "UPDATE armor_inventory SET armor_level=?, armor_xp=?, sub_stats=? WHERE id=?",
                    (new_level, armor_xp, json.dumps(sub_stats), self.target_id)
                )

            # Delete fodder pieces
            for fid in self.fodder_ids:
                # Unequip from any pet first
                await conn.execute(
                    "UPDATE pets SET equipped_armor=NULL WHERE equipped_armor=? AND player_id=?",
                    (fid, self.user_id)
                )
                await conn.execute(
                    "DELETE FROM armor_inventory WHERE id=? AND player_id=?",
                    (fid, self.user_id)
                )
            await conn.commit()

        r_emoji = RARITY_EMOJIS.get(target["rarity"], "⚪")
        embed = discord.Embed(
            title="🔨 Armor Upgraded!",
            color=0xF39C12
        )
        embed.add_field(
            name=f"{r_emoji} {target['name']}",
            value=f"Level **{current_level}** → **{new_level}**" if new_level > current_level
                  else f"Level **{current_level}** — XP stored (+{total_xp} XP toward next level)",
            inline=False
        )
        if new_substats_gained:
            ss_lines = [f"✨ **+{ss['value']} {ss['stat'].upper()}** unlocked!" for ss in new_substats_gained]
            embed.add_field(name="New Substats!", value="\n".join(ss_lines), inline=False)
        if total_coins:
            embed.add_field(name="Coins Spent", value=f"{total_coins:,} 🪙", inline=True)
        embed.add_field(name="Fodder Used", value=f"{len(self.fodder_ids)} piece(s)", inline=True)
        embed.set_footer(text="Substats unlock at levels 3, 6, 9, 12 · Max level 15")

        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Armor(bot))
