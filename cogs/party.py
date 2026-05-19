import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db
from config import ELEMENT_EMOJIS, PET_NAMES, STAGE_NAMES


class SetPartyView(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict]):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.order = list(pets)
        self.selected_idx = 0
        self._rebuild()

    def _make_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎯 Set Your Battle Party",
            description="Select a pet, then use the arrows to reorder. The first pet starts every battle and shows on your profile.",
            color=0x7B68EE
        )
        lines = []
        for i, p in enumerate(self.order):
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            emoji = ELEMENT_EMOJIS[p["element"]]
            stage = STAGE_NAMES[p["stage"]]
            marker = " ◀" if i == self.selected_idx else ""
            lines.append(f"**{i+1}.** {emoji} **{name}** — {stage}, Lv {p['level']}{marker}")
        embed.add_field(name="Party Order", value="\n".join(lines), inline=False)
        embed.set_footer(text="Click ✅ Save Party when done.")
        return embed

    def _rebuild(self):
        self.clear_items()

        options = []
        for i, p in enumerate(self.order):
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            emoji = ELEMENT_EMOJIS[p["element"]]
            stage = STAGE_NAMES[p["stage"]]
            options.append(discord.SelectOption(
                label=f"{i + 1}. {name}",
                value=str(i),
                description=f"{stage} · Lv {p['level']}",
                emoji=emoji,
                default=(i == self.selected_idx)
            ))

        pet_select = discord.ui.Select(placeholder="Select a pet to move...", options=options, row=0)
        pet_select.callback = self._select_cb
        self.add_item(pet_select)

        up_btn = discord.ui.Button(
            label="⬆ Move Up", style=discord.ButtonStyle.secondary,
            disabled=(self.selected_idx == 0), row=1
        )
        up_btn.callback = self._up_cb
        self.add_item(up_btn)

        down_btn = discord.ui.Button(
            label="⬇ Move Down", style=discord.ButtonStyle.secondary,
            disabled=(self.selected_idx >= len(self.order) - 1), row=1
        )
        down_btn.callback = self._down_cb
        self.add_item(down_btn)

        confirm_btn = discord.ui.Button(
            label="✅ Save Party", style=discord.ButtonStyle.success, row=1
        )
        confirm_btn.callback = self._confirm_cb
        self.add_item(confirm_btn)

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return False
        return True

    async def _select_cb(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        self.selected_idx = int(interaction.data["values"][0])
        self._rebuild()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    async def _up_cb(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        i = self.selected_idx
        self.order[i], self.order[i - 1] = self.order[i - 1], self.order[i]
        self.selected_idx -= 1
        self._rebuild()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    async def _down_cb(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        i = self.selected_idx
        self.order[i], self.order[i + 1] = self.order[i + 1], self.order[i]
        self.selected_idx += 1
        self._rebuild()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    async def _confirm_cb(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        self.stop()
        async with aiosqlite.connect(db.DB_PATH) as conn:
            for slot, pet in enumerate(self.order, start=1):
                await conn.execute(
                    "UPDATE pets SET party_slot=? WHERE id=?", (slot, pet["id"])
                )
            await conn.commit()

        lines = []
        for i, p in enumerate(self.order):
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            emoji = ELEMENT_EMOJIS[p["element"]]
            lines.append(f"**{i + 1}.** {emoji} {name}")

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Party Saved!",
                description="\n".join(lines),
                color=0x2ECC71
            ),
            view=None
        )


class Party(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setparty", description="Set the order of your pets for battle")
    async def setparty(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pets = await db.get_player_pets(conn, interaction.user.id)

        if not pets:
            await interaction.response.send_message("You have no pets yet.", ephemeral=True)
            return

        if len(pets) == 1:
            await interaction.response.send_message(
                "You only have one pet — your party is already set!", ephemeral=True
            )
            return

        view = SetPartyView(interaction.user.id, pets)
        await interaction.response.send_message(embed=view._make_embed(), view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Party(bot))
