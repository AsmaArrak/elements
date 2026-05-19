import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db
from config import PET_NAMES, ELEMENT_EMOJIS, STAGE_NAMES, RARITY_EMOJIS


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


async def setup(bot: commands.Bot):
    await bot.add_cog(Armor(bot))
