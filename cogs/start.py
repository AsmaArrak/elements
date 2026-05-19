import discord
from discord import app_commands
from discord.ext import commands
import random
import aiosqlite

import database as db
from config import (ELEMENTS, ELEMENT_DISPLAY, ELEMENT_EMOJIS, ELEMENT_COLORS,
                    PET_NAMES, get_pet_image, FOOD_ITEMS)
from game.stats import calc_base_stats

ELEMENT_DESCRIPTIONS = {
    "void":    "Darkness consuming light\n⭐ High MGK · Low DEF",
    "ember":   "Eternal spirit fire\n⭐ High ATK & MGK",
    "storm":   "Thunder made flesh\n⭐ Fastest of all elements",
    "bloom":   "Ancient life, wild growth\n⭐ High HP & RES",
    "crystal": "Prismatic hard brilliance\n⭐ Highest DEF & RES",
    "cosmic":  "Born from dying stars\n⭐ Balanced & mystical",
    "toxin":   "Beautiful decay\n⭐ Devastating magic power",
    "forge":   "Iron and fire, built not born\n⭐ Heavy ATK & DEF",
    "phantom": "Between worlds\n⭐ High SPD & MGK",
    "tide":    "Deep ocean patience\n⭐ Tanky & resilient",
}


class EggBrowserView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.current_idx = 0

    def current_element(self) -> str:
        return ELEMENTS[self.current_idx]

    def build_embed(self) -> discord.Embed:
        element = self.current_element()
        display = ELEMENT_DISPLAY[element]
        emoji = ELEMENT_EMOJIS[element]
        color = ELEMENT_COLORS[element]
        desc = ELEMENT_DESCRIPTIONS[element]
        embed = discord.Embed(
            title=f"{emoji} {display} Egg",
            description=(
                f"{desc}\n\n"
                f"*Browse with ◀ ▶ then click **Choose** to pick this egg.*\n\n"
                f"**{self.current_idx + 1} / {len(ELEMENTS)}**"
            ),
            color=color
        )
        embed.set_image(url="attachment://egg.png")
        embed.set_footer(text="Your element is permanent — choose wisely!")
        return embed

    def get_file(self) -> discord.File:
        path = get_pet_image(self.current_element(), 1, 0)
        return discord.File(path, filename="egg.png")

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your selection!", ephemeral=True)
            return
        self.current_idx = (self.current_idx - 1) % len(ELEMENTS)
        await interaction.response.edit_message(
            embed=self.build_embed(), attachments=[self.get_file()], view=self
        )

    @discord.ui.button(label="✅ Choose this egg", style=discord.ButtonStyle.success, row=0)
    async def choose_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your selection!", ephemeral=True)
            return
        await interaction.response.defer()
        await self.on_element_chosen(interaction, self.current_element())

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your selection!", ephemeral=True)
            return
        self.current_idx = (self.current_idx + 1) % len(ELEMENTS)
        await interaction.response.edit_message(
            embed=self.build_embed(), attachments=[self.get_file()], view=self
        )

    async def on_element_chosen(self, interaction: discord.Interaction, element: str):
        self.stop()
        variant = random.randint(1, 2)

        async with aiosqlite.connect(db.DB_PATH) as conn:
            await db.ensure_player(conn, interaction.user.id)
            bases = calc_base_stats(element, 0)
            await conn.execute(
                """INSERT INTO pets
                   (player_id, element, variant, stage, level, xp,
                    base_hp, base_atk, base_def, base_spd, base_mgk, base_res)
                   VALUES (?,?,?,0,1,0,?,?,?,?,?,?)""",
                (interaction.user.id, element, variant,
                 bases["hp"], bases["atk"], bases["def"],
                 bases["spd"], bases["mgk"], bases["res"])
            )
            await conn.commit()
            async with conn.execute("SELECT last_insert_rowid()") as cur:
                pet_id = (await cur.fetchone())[0]
            await conn.execute(
                "UPDATE players SET active_pet=? WHERE user_id=?",
                (pet_id, interaction.user.id)
            )
            # Give 1 starting food item
            starting_food = random.choice(["apple", "bread", "carrot", "cheese", "grape"])
            await db.add_item(conn, interaction.user.id, starting_food, "food", 1)
            await conn.commit()

        egg_name = PET_NAMES[element][variant][0]
        color = ELEMENT_COLORS[element]
        emoji = ELEMENT_EMOJIS[element]
        display = ELEMENT_DISPLAY[element]
        food_display = FOOD_ITEMS[starting_food]["display"]

        file = discord.File(get_pet_image(element, variant, 0), filename="egg.png")
        embed = discord.Embed(
            title=f"{emoji} Your {display} Egg has appeared!",
            description=(
                f"**{egg_name}** is waiting for you.\n\n"
                f"🎁 You received a **{food_display}** to get started!\n\n"
                f"🥚 Feed your egg **3 times** with `/feed` to hatch it!\n"
                f"Each feeding brings it closer to life."
            ),
            color=color
        )
        embed.set_image(url="attachment://egg.png")
        embed.set_footer(text=f"Element: {display} | Use /feed to begin!")

        await interaction.followup.edit_message(
            interaction.message.id,
            content=None,
            embed=embed,
            attachments=[file],
            view=None
        )


class Start(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="start", description="Begin your Elementals journey and choose your egg!")
    async def start(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await db.ensure_player(conn, interaction.user.id)
            pets = await db.get_player_pets(conn, interaction.user.id)

        if pets:
            await interaction.response.send_message(
                "You already have a pet! Use `/profile` to check it out.", ephemeral=True
            )
            return

        view = EggBrowserView(interaction.user.id)
        file = view.get_file()
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, file=file)


async def setup(bot: commands.Bot):
    await bot.add_cog(Start(bot))
