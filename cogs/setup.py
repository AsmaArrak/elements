import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    setup_group = app_commands.Group(name="setup", description="Configure Elementals for this server")

    @setup_group.command(name="drops", description="Set the channel where items will randomly spawn")
    @app_commands.describe(channel="The text channel for item drops")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_drops(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await db.set_guild_config(conn, interaction.guild.id, drops_channel_id=channel.id)
        await interaction.response.send_message(
            f"✅ Item drops will now appear in {channel.mention}!\n"
            f"Items will spawn every {20}–{60} minutes. Make sure I have permission to send messages there."
        )

    @setup_group.command(name="announcements", description="Set the channel for Mega Evolution announcements")
    @app_commands.describe(channel="The text channel for server-wide announcements")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_announce(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await db.set_guild_config(conn, interaction.guild.id, announce_channel_id=channel.id)
        await interaction.response.send_message(
            f"✅ Mega Evolution and legendary drop announcements will go to {channel.mention}!"
        )

    @setup_group.command(name="info", description="View current Elementals configuration")
    async def setup_info(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            cfg = await db.get_guild_config(conn, interaction.guild.id)

        if not cfg:
            await interaction.response.send_message(
                "No configuration set yet. Use `/setup drops #channel` to get started!",
                ephemeral=True
            )
            return

        drops_ch = interaction.guild.get_channel(cfg.get("drops_channel_id") or 0)
        ann_ch = interaction.guild.get_channel(cfg.get("announce_channel_id") or 0)

        embed = discord.Embed(title="⚙️ Elementals Configuration", color=0x7B68EE)
        embed.add_field(
            name="Drops Channel",
            value=drops_ch.mention if drops_ch else "Not set",
            inline=True
        )
        embed.add_field(
            name="Announcements Channel",
            value=ann_ch.mention if ann_ch else "Not set",
            inline=True
        )
        await interaction.response.send_message(embed=embed)

    @setup_group.command(name="help", description="Show all game commands and how to play")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🐾 Elementals — How to Play",
            description="A Discord monster-raising game. Hatch, feed, and evolve your pet!",
            color=0x7B68EE
        )
        embed.add_field(
            name="🚀 Getting Started",
            value="`/start` — Choose your element and hatch an egg\n"
                  "`/profile` — View your active pet\n"
                  "`/pet` — See full stats\n"
                  "`/feed <item>` — Feed your pet (first feed hatches it!)",
            inline=False
        )
        embed.add_field(
            name="🌱 Items",
            value="`/inventory` — View all your items\n"
                  "`/use <stone> <element>` — Use an evolution stone\n"
                  "`/claim` — Claim a channel drop\n"
                  "`/shop` · `/buy` · `/sell` — Shop system",
            inline=False
        )
        embed.add_field(
            name="🗺️ Expeditions",
            value="`/expedition <1/6/12/24>` — Send pet on expedition\n"
                  "`/expedition status` — Check expedition timer\n"
                  "`/collect` — Collect returned pet + loot",
            inline=False
        )
        embed.add_field(
            name="⚔️ Battle",
            value="`/battle @user` — Challenge someone to PvP\n"
                  "`/battlelog` — View recent battles",
            inline=False
        )
        embed.add_field(
            name="🎮 Minigames & Daily",
            value="`/daily` — Daily login bonus\n"
                  "`/train` — Daily stat training\n"
                  "`/fish` · `/dig` · `/trivia` — Minigames for coins & items",
            inline=False
        )
        embed.add_field(
            name="🤝 Social",
            value="`/trade @user offer:item request:item` — Trade items\n"
                  "`/give @user <amount>` — Give coins\n"
                  "`/leaderboard` — Server top pets\n"
                  "`/nickname <name>` — Name your pet",
            inline=False
        )
        embed.set_footer(text="Evolution: Egg→Evo1 (first feed) → Evo2 (Lv35+Uncommon Stone) → Evo3 (Lv70+Rare Stone) → Mega (Lv100+Exploration 100+Mega Stone)")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
