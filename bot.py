import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

import database as db

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID", "").strip()

COGS = [
    "cogs.setup",
    "cogs.help_cmd",
    "cogs.admin",
    "cogs.start",
    "cogs.pet",
    "cogs.inventory",
    "cogs.expedition",
    "cogs.battle",
    "cogs.economy",
    "cogs.drops",
    "cogs.minigames",
    "cogs.party",
    "cogs.armor",
    "cogs.skills_cmd",
    "cogs.dungeon",
    "cogs.boss",
]


class ElementalsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await db.init_db()
        for cog in COGS:
            await self.load_extension(cog)
            print(f"  Loaded: {cog}")

        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"  Slash commands synced to guild {GUILD_ID} (instant)")
        else:
            await self.tree.sync()
            print("  Slash commands synced globally (may take ~1 hour to propagate)")

    async def on_ready(self):
        print(f"\n✅ {self.user} is online!")
        print(f"   Serving {len(self.guilds)} guild(s)")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="pets evolve | /start"
            )
        )

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        msg = "An unexpected error occurred."
        if isinstance(error, discord.app_commands.MissingPermissions):
            msg = "You don't have permission to use this command."
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            msg = f"On cooldown! Try again in {error.retry_after:.1f}s."
        print(f"  Command error [{interaction.command}]: {error}")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


async def main():
    if not TOKEN:
        print("ERROR: BOT_TOKEN not set in .env file!")
        print("Copy .env.example to .env and add your token.")
        return

    bot = ElementalsBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
