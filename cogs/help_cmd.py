import discord
from discord import app_commands
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all Elementals commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🐾 Elementals — All Commands",
            description="A Discord monster-raising game. Hatch, feed, evolve, and battle!",
            color=0x7B68EE
        )
        embed.add_field(
            name="🚀 Getting Started",
            value=(
                "`/start` — Browse all eggs and choose your element\n"
                "`/profile [@user]` — View your profile or another player's\n"
                "`/pet` — See full detailed stats and caps\n"
                "`/rename <name>` — Give your active pet a custom name\n"
                "`/restart` — Delete everything and start over"
            ),
            inline=False
        )
        embed.add_field(
            name="🍖 Feeding & Items",
            value=(
                "`/feed` — Pick a pet and food from your inventory (egg needs **3 feedings** to hatch!)\n"
                "`/inventory` — View all your items\n"
                "`/use <stone> <element>` — Use an evo stone to evolve\n"
                "`/claim` — Grab a randomly spawned item from the channel\n"
                "`/train` — Daily stat boost + XP (20h cooldown)"
            ),
            inline=False
        )
        embed.add_field(
            name="🗺️ Expeditions",
            value=(
                "`/expedition <1/6/12/24>` — Send your pet out for loot\n"
                "`/expedition status` — Check how long until return\n"
                "`/collect` — Collect your pet and loot when it returns\n"
                "*Longer expeditions = more items + better rarity (up to 10 items on 24hr)*"
            ),
            inline=False
        )
        embed.add_field(
            name="🛡️ Armor",
            value=(
                "`/armor` — View your armor collection\n"
                "`/equip` — Equip armor to a pet (shown in `/pet`)\n"
                "`/sellarmor <id>` — Sell a piece of armor for coins"
            ),
            inline=False
        )
        embed.add_field(
            name="⚔️ Battle",
            value=(
                "`/setparty` — Set your battle party order\n"
                "`/battle @user` — Challenge someone to PvP\n"
                "`/battlelog` — View your recent battle history"
            ),
            inline=False
        )
        embed.add_field(
            name="📜 Skills",
            value=(
                "`/learn` — Teach your pet a skill from a scroll\n"
                "`/skills` — View your pets' learned skills\n"
                "`/forgetskill <name>` — Forget a skill to free a slot\n"
                "`/sellscroll <name>` — Sell a scroll for coins\n"
                "*Scrolls drop from expeditions. Each pet learns up to 4 skills.*"
            ),
            inline=False
        )
        embed.add_field(
            name="🛒 Economy",
            value=(
                "`/shop` — Browse the item shop\n"
                "`/buy <item>` — Purchase an item\n"
                "`/sell <item> [qty]` — Sell items for coins\n"
                "`/balance` — Check your coin balance\n"
                "`/daily` — Claim daily bonus (100 coins + 30 XP)\n"
                "`/give @user <amount>` — Give coins to someone\n"
                "`/trade @user offer:<item> request:<item>` — Trade items"
            ),
            inline=False
        )
        embed.add_field(
            name="🎮 Minigames",
            value=(
                "`/fish` — Cast a line for coins & items (10min cooldown)\n"
                "`/dig` — Excavate for buried treasure (10min cooldown)\n"
                "`/trivia` — Answer a question to win coins (2min cooldown)\n"
                "`/leaderboard` — See the top pets on the server"
            ),
            inline=False
        )
        embed.add_field(
            name="🎯 Party",
            value="`/setparty` — Set your battle party order (first pet starts battles)",
            inline=False
        )
        embed.add_field(
            name="🌱 Evolution Path",
            value=(
                "🥚 Egg → Feed **3 times** → Evo 1\n"
                "Evo 1 → Level 35 + Uncommon Evo Stone → Evo 2\n"
                "Evo 2 → Level 70 + Rare Evo Stone → Evo 3\n"
                "Evo 3 → Level 100 + Exploration 100/100 + Mega Stone → **MEGA** ⭐"
            ),
            inline=False
        )
        embed.set_footer(text="Evo Stones drop from expeditions and channel drops. Mega Stones only from expeditions!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
