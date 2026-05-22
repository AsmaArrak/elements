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
                "`/feed` — Pick a pet, food, and quantity to feed (egg needs **3 feedings** to hatch!)\n"
                "`/incubate <element>` — Place an egg from your inventory to start hatching it\n"
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
                "`/expedition 30m` — Quick 30-minute run (light loot)\n"
                "`/expedition 1h30` — 1.5-hour expedition\n"
                "`/expedition 4h` — 4-hour expedition\n"
                "`/expedition 6h` — Best loot, highest rarity chance\n"
                "`/expedition status` — Check all active expeditions\n"
                "`/expedition cancel` — Recall a pet early *(no loot)*\n"
                "`/expedition accelerate` — Use an accelerator to cut expedition time ⏩\n"
                "`/collect` — Collect your pet and loot when it returns"
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
                "`/battlelog` — View your recent battle history\n"
                "*Each pet has 2 default attacks — learn up to 4 more from scrolls*"
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
                "`/buy <item> [qty]` — Purchase an item (add quantity to buy in bulk)\n"
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
                "`/fish` — Cast a line for coins, items & accelerators (10min cooldown)\n"
                "`/dig` — Excavate for buried treasure & accelerators (10min cooldown)\n"
                "`/trivia` — Answer a question to win coins\n"
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
            name="👹 Weekend Boss Raid",
            value=(
                "`/bossbattle` — Join the active weekend boss and deal damage\n"
                "`/bossleaderboard` — See the server damage rankings\n"
                "*Bosses spawn every **Saturday at 10 UTC** and end **Monday midnight***\n"
                "*Deal damage, flee to save progress, come back for more!*\n"
                "🥇 #1: 35,000 coins · 3 Legendary armor · 📜 Legendary scroll\n"
                "🥈 #2: 20,000 coins · 2 Rare armor · 📜 Rare scroll | 🥉 #3: 12,000 coins · 1 Rare armor · 📜 Rare scroll\n"
                "⚔️ #4+: 8,000 coins · 1 Uncommon armor · 📜 Common scroll"
            ),
            inline=False
        )
        embed.add_field(
            name="⚔️ Dungeons",
            value=(
                "`/dungeon <name>` — Farm a dungeon for armor pieces (costs **20 🌙**)\n"
                "`/moonshard` — Check Moon Shards, regen timer & player level\n"
                "`/upgradearmor` — Sacrifice armor pieces to level up another (1→15)\n"
                "*🌙 Moon Shards regen +1 every 2 min · cap 120 (full in 4h) · better loot at higher player level*\n"
                "**5 Dungeons:** Ashen Ruins · Sunken Depths · Verdant Forge · Tempest Hollow · Void Nexus\n"
                "*4-piece armor set bonus = +20% element damage in battle!*"
            ),
            inline=False
        )
        embed.add_field(
            name="🌱 Evolution Path",
            value=(
                "🥚 Egg → Feed **3 times** → Evo 1\n"
                "Evo 1 → Level 20 + Uncommon Evo Stone → Evo 2\n"
                "Evo 2 → Level 50 + Rare Evo Stone → Evo 3\n"
                "Evo 3 → Level 100 + Exploration 100/100 + Mega Stone → **MEGA** ⭐"
            ),
            inline=False
        )
        embed.set_footer(text="Evo Stones drop from expeditions and channel drops. Mega Stones only from 4h+ expeditions with Exploration 100!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
