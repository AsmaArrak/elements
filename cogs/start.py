import discord
from discord import app_commands
from discord.ext import commands
import random
import aiosqlite

import database as db
from config import (ELEMENTS, ELEMENT_DISPLAY, ELEMENT_EMOJIS, ELEMENT_COLORS,
                    BASE_STATS, STAGE_MULTIPLIERS, PET_NAMES, get_pet_image)
from game.stats import calc_base_stats


class ElementSelect(discord.ui.Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        options = [
            discord.SelectOption(
                label=f"{ELEMENT_EMOJIS[e]} {ELEMENT_DISPLAY[e]}",
                value=e,
                description={
                    "void": "Darkness consuming light — high magic",
                    "ember": "Eternal spirit fire — high attack & magic",
                    "storm": "Thunder made flesh — fastest of all",
                    "bloom": "Ancient life — high HP & resistance",
                    "crystal": "Prismatic brilliance — high defense",
                    "cosmic": "Born from dying stars — balanced & mystical",
                    "toxin": "Beautiful decay — devastating magic",
                    "forge": "Iron and fire — heavy hitter, iron defense",
                    "phantom": "Between worlds — fast & magical",
                    "tide": "Deep ocean patience — tanky & resilient",
                }[e]
            )
            for e in ELEMENTS
        ]
        super().__init__(placeholder="Choose your element...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your selection!", ephemeral=True)
            return
        await interaction.response.defer()
        element = self.values[0]
        await self.view.on_element_chosen(interaction, element)


class StartView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.add_item(ElementSelect(user_id))

    async def on_element_chosen(self, interaction: discord.Interaction, element: str):
        self.stop()
        variant = random.randint(1, 2)

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)

            bases = calc_base_stats(element, 0)  # egg stats
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

            async with conn.execute(
                "SELECT last_insert_rowid()"
            ) as cur:
                pet_id = (await cur.fetchone())[0]

            await conn.execute(
                "UPDATE players SET active_pet=? WHERE user_id=?",
                (pet_id, interaction.user.id)
            )
            await conn.commit()

        egg_name = PET_NAMES[element][variant][0]
        color = ELEMENT_COLORS[element]
        emoji = ELEMENT_EMOJIS[element]
        display = ELEMENT_DISPLAY[element]

        image_path = get_pet_image(element, variant, 0)
        file = discord.File(image_path, filename="pet.png")

        embed = discord.Embed(
            title=f"{emoji} Your {display} Egg has appeared!",
            description=(
                f"**{egg_name}** is waiting for you.\n\n"
                "🥚 Give it its **first meal** with `/feed` to hatch it!\n"
                "The moment you feed it for the first time, it will evolve into its first form."
            ),
            color=color
        )
        embed.set_image(url="attachment://pet.png")
        embed.set_footer(text=f"Element: {display} | Variant: {variant}")

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
            player = await db.ensure_player(conn, interaction.user.id)
            pets = await db.get_player_pets(conn, interaction.user.id)

        if pets:
            await interaction.response.send_message(
                "You already have a pet! Use `/profile` to check it out.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="✨ Welcome to Elementals!",
            description=(
                "Choose your element below. Your egg's element is **permanent** — choose wisely!\n\n"
                "Each element has unique strengths and a different evolution path.\n"
                "Both variants you might receive are the **same element** — just different creatures."
            ),
            color=0x7B68EE
        )
        embed.set_thumbnail(url="attachment://logo.png")

        try:
            logo_file = discord.File("logo.png", filename="logo.png")
            view = StartView(interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view, file=logo_file)
        except FileNotFoundError:
            view = StartView(interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Start(bot))
