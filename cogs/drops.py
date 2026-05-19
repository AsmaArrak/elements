import discord
from discord.ext import commands, tasks
import aiosqlite
import random
from datetime import datetime, timezone, timedelta

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_EMOJIS, FOOD_ITEMS, STAT_ITEMS,
    DROP_INTERVAL_MIN, DROP_INTERVAL_MAX, DROP_EXPIRY_MINUTES,
    PASSIVE_XP_PER_HOUR
)
from game.loot import generate_channel_drop


def drop_display_name(item_key: str, item_type: str, element: str = None) -> str:
    if item_type == "food":
        return FOOD_ITEMS.get(item_key, {}).get("display", item_key.title())
    if item_type == "stat_item":
        return STAT_ITEMS.get(item_key, {}).get("display", item_key.replace("_", " ").title())
    if item_type == "evo_stone":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "") + " "
        name = "Uncommon Evo Stone" if item_key == "evo_stone_uncommon" else "Rare Evo Stone"
        return f"{prefix}{name}"
    if item_type == "mega_stone":
        return f"{ELEMENT_DISPLAY.get(element, '')} Mega Stone ⭐"
    if item_type == "egg":
        return f"{ELEMENT_DISPLAY.get(element, element.title() if element else '')} Egg 🥚"
    if item_type == "coins":
        return "Coins 💰"
    return item_key.replace("_", " ").title()


# Track when the next drop is due per guild
next_drop_times: dict[int, datetime] = {}


class Drops(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.drop_task.start()
        self.passive_xp_task.start()
        self.expire_drops_task.start()

    def cog_unload(self):
        self.drop_task.cancel()
        self.passive_xp_task.cancel()
        self.expire_drops_task.cancel()

    @tasks.loop(minutes=5)
    async def drop_task(self):
        """Check if any guild is due for a drop and post one."""
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute("SELECT * FROM guild_config WHERE drops_channel_id IS NOT NULL") as cur:
                guild_configs = await cur.fetchall()
                cols = [d[0] for d in cur.description]
                configs = [dict(zip(cols, r)) for r in guild_configs]

        for cfg in configs:
            guild_id = cfg["guild_id"]
            channel_id = cfg["drops_channel_id"]

            if guild_id not in next_drop_times:
                # Schedule first drop
                delay = random.randint(DROP_INTERVAL_MIN, DROP_INTERVAL_MAX)
                next_drop_times[guild_id] = now + timedelta(minutes=delay)
                continue

            if now >= next_drop_times[guild_id]:
                await self._post_drop(guild_id, channel_id)
                delay = random.randint(DROP_INTERVAL_MIN, DROP_INTERVAL_MAX)
                next_drop_times[guild_id] = now + timedelta(minutes=delay)

    async def _post_drop(self, guild_id: int, channel_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        drop = generate_channel_drop()
        item_key = drop["item_key"]
        item_type = drop["item_type"]
        element = drop.get("element")
        qty = drop["qty"]

        display = drop_display_name(item_key, item_type, element)
        expires = datetime.now(timezone.utc) + timedelta(minutes=DROP_EXPIRY_MINUTES)
        exp_ts = int(expires.timestamp())

        # Rarity color
        rarity_colors = {
            "food": 0x2ECC71,
            "stat_item": 0x3498DB,
            "evo_stone": 0x9B59B6,
            "egg": 0xF39C12,
            "coins": 0xF1C40F,
        }
        color = rarity_colors.get(item_type, 0x95A5A6)

        # Rarity label
        rarity_labels = {
            "food": "Common", "stat_item": "Uncommon",
            "evo_stone": "Rare", "egg": "Very Rare", "coins": "Common"
        }
        rarity = rarity_labels.get(item_type, "Common")

        embed = discord.Embed(
            title=f"✨ A wild item appeared!",
            description=(
                f"**{display}**" + (f" ×{qty}" if qty > 1 else "") + "\n\n"
                f"Use `/claim` to grab it!\n"
                f"Expires <t:{exp_ts}:R>"
            ),
            color=color
        )
        embed.set_footer(text=f"Rarity: {rarity} | First to /claim wins!")

        # Try to attach an image
        from config import get_food_image, get_stone_image, ASSETS_PATH
        import os
        img_path = None
        if item_type == "food":
            img_path = get_food_image(item_key)
        elif item_type == "evo_stone" and element:
            img_path = get_stone_image(element, item_key)
        if img_path and os.path.exists(img_path):
            try:
                file = discord.File(img_path, filename="drop.png")
                embed.set_thumbnail(url="attachment://drop.png")
                msg = await channel.send(embed=embed, file=file)
            except Exception:
                msg = await channel.send(embed=embed)
        else:
            msg = await channel.send(embed=embed)

        # Record in DB
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute(
                """INSERT INTO channel_drops
                   (guild_id, channel_id, message_id, item_key, item_type, item_element, spawn_time, expires_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (guild_id, channel_id, msg.id, item_key, item_type, element,
                 db.now_iso(), expires.isoformat())
            )
            await conn.commit()

    @tasks.loop(minutes=60)
    async def passive_xp_task(self):
        """Give passive XP to all non-egg pets that aren't on expedition."""
        async with aiosqlite.connect(db.DB_PATH) as conn:
            # Get all active expedition pet IDs
            async with conn.execute(
                "SELECT pet_id FROM expeditions WHERE returned=0"
            ) as cur:
                exp_pet_ids = {r[0] for r in await cur.fetchall()}

            # Get all pets that qualify (stage > 0, level < 100, not on expedition)
            async with conn.execute(
                "SELECT id FROM pets WHERE stage > 0 AND level < 100"
            ) as cur:
                pet_ids = [r[0] for r in await cur.fetchall()]

            for pet_id in pet_ids:
                if pet_id not in exp_pet_ids:
                    await db.add_xp(conn, pet_id, PASSIVE_XP_PER_HOUR)

            await conn.commit()

    @tasks.loop(minutes=5)
    async def expire_drops_task(self):
        """Remove expired unclaimed drops."""
        now = db.now_iso()
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute(
                "DELETE FROM channel_drops WHERE claimed_by IS NULL AND expires_at < ?", (now,)
            )
            await conn.commit()

    @drop_task.before_loop
    @passive_xp_task.before_loop
    @expire_drops_task.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()


# Claim command registered as a top-level cog for clean access
class Claim(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="claim", description="Claim the most recent unclaimed channel drop")
    async def claim(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Claims only work in a server.", ephemeral=True)
            return

        now = db.now_iso()
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.ensure_player(conn, interaction.user.id)

            # Find the most recent unclaimed, unexpired drop in this channel
            async with conn.execute(
                """SELECT * FROM channel_drops
                   WHERE guild_id=? AND channel_id=? AND claimed_by IS NULL AND expires_at > ?
                   ORDER BY spawn_time DESC LIMIT 1""",
                (interaction.guild.id, interaction.channel_id, now)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    await interaction.response.send_message(
                        "No unclaimed drop here right now! Watch for the next one.",
                        ephemeral=True
                    )
                    return
                cols = [d[0] for d in cur.description]
                drop = dict(zip(cols, row))

            # Mark as claimed
            await conn.execute(
                "UPDATE channel_drops SET claimed_by=? WHERE id=?",
                (interaction.user.id, drop["id"])
            )

            # Award item
            item_key = drop["item_key"]
            item_type = drop["item_type"]
            element = drop["item_element"]

            if item_key == "coins":
                # qty stored differently - let's check
                qty = 50  # default if not stored; in practice stored as item_key "coins" means a fixed amount
                await conn.execute(
                    "UPDATE players SET coins=coins+? WHERE user_id=?",
                    (qty, interaction.user.id)
                )
            else:
                await db.add_item(conn, interaction.user.id, item_key, item_type, 1, element)

            await conn.commit()

        display = drop_display_name(item_key, item_type, element)
        qty_text = ""
        if item_key == "coins":
            qty_text = " (50 coins added)"

        await interaction.response.send_message(
            f"🎉 {interaction.user.mention} claimed **{display}**!{qty_text}\n"
            f"Check your `/inventory` to see it."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Drops(bot))
    await bot.add_cog(Claim(bot))
