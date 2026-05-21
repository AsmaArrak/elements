import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db
from config import (
    DUNGEONS, DUNGEON_SHARD_COST, MOON_SHARD_CAP, MOON_SHARD_REGEN_MINS,
    ARMOR_SETS, RARITY_EMOJIS, ELEMENT_EMOJIS, PLAYER_XP_SOURCES,
    player_xp_for_next_level, PLAYER_LEVEL_CAP,
)
from game.dungeon_loot import generate_dungeon_loot


DUNGEON_CHOICES = [
    app_commands.Choice(name=f"{v['emoji']} {v['name']} ({' & '.join(v['elements'])})", value=k)
    for k, v in DUNGEONS.items()
]


class Dungeon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="dungeon", description="Farm a dungeon for armor pieces")
    @app_commands.describe(dungeon="Which dungeon to farm")
    @app_commands.choices(dungeon=DUNGEON_CHOICES)
    async def dungeon(self, interaction: discord.Interaction, dungeon: app_commands.Choice[str]):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            # Sync and check moon shards
            current_shards = await db.sync_moon_shards(conn, interaction.user.id)
            if current_shards < DUNGEON_SHARD_COST:
                regen_mins = MOON_SHARD_REGEN_MINS
                needed = DUNGEON_SHARD_COST - current_shards
                wait_mins = needed * regen_mins
                await interaction.response.send_message(
                    f"❌ Not enough Moon Shards! You have **{current_shards}/{DUNGEON_SHARD_COST}** 🌙\n"
                    f"You need **{needed}** more — they regen in ~**{wait_mins} minutes**.",
                    ephemeral=True
                )
                return

            # Spend shards
            await db.spend_moon_shards(conn, interaction.user.id, DUNGEON_SHARD_COST)
            player_level = player.get("player_level") or 1

            # Generate loot
            pieces = generate_dungeon_loot(dungeon.value, player_level)

            # Save to DB
            for piece in pieces:
                await conn.execute(
                    """INSERT INTO armor_inventory
                       (player_id, name, rarity, set_name, piece_type, armor_level, armor_xp, sub_stats,
                        bonus_hp, bonus_atk, bonus_def, bonus_spd, bonus_mgk, bonus_res)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (interaction.user.id, piece["name"], piece["rarity"],
                     piece["set_name"], piece["piece_type"], 1, 0, "[]",
                     piece.get("bonus_hp", 0), piece.get("bonus_atk", 0),
                     piece.get("bonus_def", 0), piece.get("bonus_spd", 0),
                     piece.get("bonus_mgk", 0), piece.get("bonus_res", 0))
                )

            # Player XP
            p_xp = PLAYER_XP_SOURCES.get("dungeon", 30)
            new_level, new_xp, leveled_up = await db.add_player_xp(conn, interaction.user.id, p_xp)
            await conn.commit()

            shards_left = current_shards - DUNGEON_SHARD_COST

        dinfo = DUNGEONS[dungeon.value]
        embed = discord.Embed(
            title=f"{dinfo['emoji']} {dinfo['name']}",
            description=f"You spent **{DUNGEON_SHARD_COST} 🌙 Moon Shards** and cleared the dungeon!",
            color=0x9B59B6
        )

        # Loot display
        lines = []
        for piece in pieces:
            r_emoji = RARITY_EMOJIS.get(piece["rarity"], "⚪")
            elem_emoji = ELEMENT_EMOJIS.get(piece["set_name"], "")
            set_display = ARMOR_SETS[piece["set_name"]]["name"]
            stat_parts = []
            for stat in ("hp", "atk", "def", "spd", "mgk", "res"):
                v = piece.get(f"bonus_{stat}", 0)
                if v:
                    stat_parts.append(f"+{v} {stat.upper()}")
            stat_str = " · ".join(stat_parts) if stat_parts else "—"
            lines.append(f"{r_emoji} {elem_emoji} **{piece['name']}** — {stat_str}")

        embed.add_field(name="🎁 Armor Dropped", value="\n".join(lines), inline=False)
        embed.add_field(
            name="🌙 Moon Shards",
            value=f"{shards_left}/{MOON_SHARD_CAP} *(+1 every {MOON_SHARD_REGEN_MINS} min)*",
            inline=True
        )
        embed.add_field(
            name="📈 Player XP",
            value=f"+{p_xp} XP → Level **{new_level}**" + (" ⬆️ **LEVEL UP!**" if leveled_up else ""),
            inline=True
        )
        embed.set_footer(text="Use /upgradearmor to level up your pieces · /armor to view collection")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="moonshard", description="Check your Moon Shard balance and regen")
    async def moonshard(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            current = await db.sync_moon_shards(conn, interaction.user.id)
            player_level = player.get("player_level") or 1
            player_xp = player.get("player_xp") or 0

        if player_level < PLAYER_LEVEL_CAP:
            needed = player_xp_for_next_level(player_level)
            xp_line = f"{player_xp}/{needed} XP to level {player_level + 1}"
        else:
            xp_line = "Max level reached!"

        mins_to_full = (MOON_SHARD_CAP - current) * MOON_SHARD_REGEN_MINS

        embed = discord.Embed(title="🌙 Moon Shards", color=0x9B59B6)
        embed.add_field(name="Current Shards", value=f"**{current}/{MOON_SHARD_CAP}**", inline=True)
        embed.add_field(name="Regen Rate", value=f"+1 every {MOON_SHARD_REGEN_MINS} min", inline=True)
        embed.add_field(
            name="Full in",
            value=f"{mins_to_full} minutes" if current < MOON_SHARD_CAP else "Already full!",
            inline=True
        )
        embed.add_field(name="🧑 Player Level", value=f"**{player_level}** / {PLAYER_LEVEL_CAP}", inline=True)
        embed.add_field(name="Player XP", value=xp_line, inline=True)
        embed.add_field(
            name="Dungeon Cost",
            value=f"{DUNGEON_SHARD_COST} 🌙 per run",
            inline=True
        )

        # Dungeon list
        dungeon_lines = []
        for k, v in DUNGEONS.items():
            elems = " & ".join(f"{ELEMENT_EMOJIS.get(e,'')} {e.title()}" for e in v["elements"])
            dungeon_lines.append(f"{v['emoji']} **{v['name']}** — {elems}")
        embed.add_field(name="⚔️ Available Dungeons", value="\n".join(dungeon_lines), inline=False)
        embed.set_footer(text="Use /dungeon <name> to farm • Better loot at higher player levels")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Dungeon(bot))
