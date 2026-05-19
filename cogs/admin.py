import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import random
import os

import database as db
from config import (
    ELEMENTS, ELEMENT_DISPLAY, ELEMENT_EMOJIS, FOOD_ITEMS, STAT_ITEMS,
    get_food_image, get_stone_image
)
from game.loot import generate_channel_drop, CHANNEL_DROPS
from cogs.drops import drop_display_name

# Only these Discord user IDs can use admin commands
# Pulled from env so you don't hardcode your ID in the repo
ADMIN_IDS_ENV = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: set[int] = {int(x.strip()) for x in ADMIN_IDS_ENV.split(",") if x.strip().isdigit()}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    admin = app_commands.Group(name="admin", description="Admin-only game management commands")

    async def _check(self, interaction: discord.Interaction) -> bool:
        if not is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ You don't have permission to use admin commands.", ephemeral=True
            )
            return False
        return True

    # ── /admin drop ──────────────────────────────────────────────────────────

    @admin.command(name="drop", description="Force a random item drop in the drops channel right now")
    async def drop(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return

        async with aiosqlite.connect(db.DB_PATH) as conn:
            cfg = await db.get_guild_config(conn, interaction.guild.id)

        channel_id = cfg.get("drops_channel_id") if cfg else None
        channel = interaction.guild.get_channel(channel_id) if channel_id else interaction.channel

        if not channel:
            await interaction.response.send_message(
                "No drops channel set. Use `/setup drops #channel` first.", ephemeral=True
            )
            return

        # Import and call the drop poster directly
        from cogs.drops import Drops
        drops_cog: Drops = self.bot.get_cog("Drops")
        if drops_cog:
            await drops_cog._post_drop(interaction.guild.id, channel.id)
            await interaction.response.send_message(
                f"✅ Drop posted in {channel.mention}!", ephemeral=True
            )
        else:
            await interaction.response.send_message("Drops cog not loaded.", ephemeral=True)

    # ── /admin give ───────────────────────────────────────────────────────────

    @admin.command(name="give", description="Give a player an item or coins")
    @app_commands.describe(
        target="The player to give to",
        item="Item name (food, stat item, evo_stone_uncommon, etc.) or 'coins'",
        qty="Amount (default 1)",
        element="Element for evo/mega stones or eggs"
    )
    async def give(self, interaction: discord.Interaction,
                   target: discord.Member, item: str,
                   qty: int = 1, element: str = None):
        if not await self._check(interaction):
            return

        item = item.lower().strip()
        if element:
            element = element.lower().strip()

        async with aiosqlite.connect(db.DB_PATH) as conn:
            await db.ensure_player(conn, target.id)

            if item == "coins":
                await conn.execute(
                    "UPDATE players SET coins=coins+? WHERE user_id=?", (qty, target.id)
                )
                await conn.commit()
                await interaction.response.send_message(
                    f"✅ Gave **{qty} coins** to {target.mention}.", ephemeral=True
                )
                return

            # Determine item type
            if item in FOOD_ITEMS:
                item_type = "food"
            elif item in STAT_ITEMS:
                item_type = "stat_item"
            elif item in ("evo_stone_uncommon", "evo_stone_rare"):
                item_type = "evo_stone"
            elif item == "mega_stone":
                item_type = "mega_stone"
            elif item == "egg":
                item_type = "egg"
                if not element:
                    element = random.choice(ELEMENTS)
            else:
                await interaction.response.send_message(
                    f"Unknown item: `{item}`\n"
                    f"Valid: food names, stat item keys, `evo_stone_uncommon`, `evo_stone_rare`, `mega_stone`, `egg`, `coins`",
                    ephemeral=True
                )
                return

            await db.add_item(conn, target.id, item, item_type, qty, element)
            await conn.commit()

        elem_label = f" ({ELEMENT_DISPLAY.get(element, element)})" if element else ""
        await interaction.response.send_message(
            f"✅ Gave {qty}× **{item}{elem_label}** to {target.mention}.", ephemeral=True
        )

    # ── /admin coins ──────────────────────────────────────────────────────────

    @admin.command(name="coins", description="Set or adjust a player's coin balance")
    @app_commands.describe(
        target="The player",
        amount="Amount to add (use negative to remove)",
    )
    async def coins(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        if not await self._check(interaction):
            return
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await db.ensure_player(conn, target.id)
            await conn.execute(
                "UPDATE players SET coins=MAX(0, coins+?) WHERE user_id=?", (amount, target.id)
            )
            await conn.commit()
            p = await db.get_player(conn, target.id)

        sign = "+" if amount >= 0 else ""
        await interaction.response.send_message(
            f"✅ {sign}{amount} coins for {target.mention}. New balance: **{p['coins']}**.",
            ephemeral=True
        )

    # ── /admin xp ─────────────────────────────────────────────────────────────

    @admin.command(name="xp", description="Give XP to a player's active pet")
    @app_commands.describe(target="The player", amount="XP to add")
    async def xp(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        if not await self._check(interaction):
            return
        async with aiosqlite.connect(db.DB_PATH) as conn:
            pet = await db.get_active_pet(conn, target.id)
            if not pet or pet["stage"] == 0:
                await interaction.response.send_message(
                    f"{target.mention} has no hatched pet.", ephemeral=True
                )
                return
            result = await db.add_xp(conn, pet["id"], amount)
            await conn.commit()

        lvl_note = f" → Level **{result['level']}**!" if result.get("leveled_up") else ""
        await interaction.response.send_message(
            f"✅ +{amount} XP for {target.mention}'s pet.{lvl_note}", ephemeral=True
        )

    # ── /admin announce ───────────────────────────────────────────────────────

    @admin.command(name="announce", description="Send a message to the announcements channel")
    @app_commands.describe(message="The announcement text")
    async def announce(self, interaction: discord.Interaction, message: str):
        if not await self._check(interaction):
            return
        async with aiosqlite.connect(db.DB_PATH) as conn:
            cfg = await db.get_guild_config(conn, interaction.guild.id)
        ch_id = cfg.get("announce_channel_id") if cfg else None
        ch = interaction.guild.get_channel(ch_id) if ch_id else None
        if not ch:
            await interaction.response.send_message(
                "No announcements channel set. Use `/setup announcements #channel`.", ephemeral=True
            )
            return
        embed = discord.Embed(description=message, color=0x7B68EE)
        embed.set_author(name="📢 Announcement")
        await ch.send(embed=embed)
        await interaction.response.send_message(f"✅ Announced in {ch.mention}.", ephemeral=True)

    # ── /admin stats ──────────────────────────────────────────────────────────

    @admin.command(name="stats", description="View server game stats")
    async def stats(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute("SELECT COUNT(*) FROM players") as cur:
                total_players = (await cur.fetchone())[0]
            async with conn.execute("SELECT COUNT(*) FROM pets WHERE stage > 0") as cur:
                hatched = (await cur.fetchone())[0]
            async with conn.execute("SELECT COUNT(*) FROM pets WHERE stage = 4") as cur:
                megas = (await cur.fetchone())[0]
            async with conn.execute("SELECT COUNT(*) FROM expeditions WHERE returned=0") as cur:
                active_exps = (await cur.fetchone())[0]
            async with conn.execute("SELECT MAX(level) FROM pets") as cur:
                max_level = (await cur.fetchone())[0] or 0

        embed = discord.Embed(title="📊 Game Stats", color=0x7B68EE)
        embed.add_field(name="Players", value=str(total_players), inline=True)
        embed.add_field(name="Hatched Pets", value=str(hatched), inline=True)
        embed.add_field(name="Mega Evolutions", value=str(megas), inline=True)
        embed.add_field(name="Active Expeditions", value=str(active_exps), inline=True)
        embed.add_field(name="Highest Level Pet", value=str(max_level), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /admin backup ─────────────────────────────────────────────────────────

    @admin.command(name="backup", description="DM yourself the database file for safekeeping")
    async def backup(self, interaction: discord.Interaction):
        if not await self._check(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            file = discord.File(db.DB_PATH, filename="elementals_backup.db")
            await interaction.user.send(
                "📦 **Elementals DB Backup**\nKeep this file safe. Use `/admin restore` with this file after a redeploy.",
                file=file
            )
            await interaction.followup.send("✅ Backup sent to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Couldn't DM you. Enable DMs from server members.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    # ── /admin restore ────────────────────────────────────────────────────────

    @admin.command(name="restore", description="Restore the database from a backup file")
    @app_commands.describe(file="The elementals_backup.db file to restore")
    async def restore(self, interaction: discord.Interaction, file: discord.Attachment):
        if not await self._check(interaction):
            return
        if not file.filename.endswith(".db"):
            await interaction.response.send_message("❌ Please attach a .db file.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            data = await file.read()
            with open(db.DB_PATH, "wb") as f:
                f.write(data)
            await interaction.followup.send(
                f"✅ Database restored! ({len(data):,} bytes)\nRestart the bot for changes to take full effect.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
