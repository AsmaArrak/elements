import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_COLORS, ELEMENT_EMOJIS, PET_NAMES, STAGE_NAMES,
    FOOD_ITEMS, TRAIN_XP, TRAIN_STAT_BOOST, TRAIN_COOLDOWN_HOURS,
    get_pet_image, get_food_image, xp_for_next_level
)
from game.stats import effective_stats, hp_bar, apply_stat_bonus, calc_base_stats
from game.evolution import evolve_pet
from datetime import datetime, timezone, timedelta


def pet_embed(pet: dict, owner: discord.User | discord.Member = None) -> tuple[discord.Embed, discord.File]:
    element = pet["element"]
    variant = pet["variant"]
    stage = pet["stage"]
    level = pet["level"]
    name = pet.get("nickname") or PET_NAMES[element][variant][stage]
    display_element = ELEMENT_DISPLAY[element]
    emoji = ELEMENT_EMOJIS[element]
    color = ELEMENT_COLORS[element]
    stage_name = STAGE_NAMES[stage]

    stats = effective_stats(pet)
    xp = pet["xp"]
    xp_needed = xp_for_next_level(level) if level < 100 else 0
    xp_bar = hp_bar(xp, xp_needed, 12) if xp_needed else "MAX LEVEL"

    embed = discord.Embed(
        title=f"{emoji} {name}",
        description=f"**{display_element} — {stage_name}** | Level {level}",
        color=color
    )
    if owner:
        embed.set_author(name=str(owner), icon_url=owner.display_avatar.url)

    if stage > 0:
        embed.add_field(
            name="⚔️ Battle Stats",
            value=(
                f"```\n"
                f"HP : {stats['hp']:>4}   ATK: {stats['atk']:>4}\n"
                f"DEF: {stats['def']:>4}   SPD: {stats['spd']:>4}\n"
                f"MGK: {stats['mgk']:>4}   RES: {stats['res']:>4}\n"
                f"```"
            ),
            inline=False
        )
    else:
        feed_count = pet.get("first_fed", 0)
        remaining = 3 - feed_count
        dots = "🟡" * feed_count + "⚪" * remaining
        embed.add_field(
            name="🥚 Egg",
            value=f"Feed it **{remaining} more time(s)** to hatch!\n{dots} ({feed_count}/3 feedings)",
            inline=False
        )

    if level < 100 and stage > 0:
        embed.add_field(name="📈 XP", value=f"`{xp_bar}` {xp}/{xp_needed}", inline=False)
    elif stage > 0:
        embed.add_field(name="📈 Level", value="**MAX LEVEL** ⭐", inline=False)

    embed.add_field(name="🧭 Exploration", value=f"{pet['exploration']}/100", inline=True)

    image_path = get_pet_image(element, variant, stage)
    file = discord.File(image_path, filename="pet.png")
    embed.set_image(url="attachment://pet.png")
    return embed, file


class Pet(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your profile or another player's profile")
    @app_commands.describe(player="Another player to look up (leave empty for your own profile)")
    async def profile(self, interaction: discord.Interaction, player: discord.Member = None):
        target = player or interaction.user
        is_self = target.id == interaction.user.id

        async with aiosqlite.connect(db.DB_PATH) as conn:
            p = await db.get_player(conn, target.id)
            if not p:
                msg = "You haven't started yet! Use `/start` to begin." if is_self else f"**{target.display_name}** hasn't started yet."
                await interaction.response.send_message(msg, ephemeral=True)
                return
            pet = await db.get_active_pet(conn, target.id)
            if not pet:
                msg = "You have no active pet." if is_self else f"**{target.display_name}** has no active pet."
                await interaction.response.send_message(msg, ephemeral=True)
                return
            all_pets = await db.get_player_pets(conn, target.id)

        embed, file = pet_embed(pet, target)
        if is_self:
            embed.set_footer(text=f"💰 {p['coins']} coins | Team: {len(all_pets)} pet(s)")
        else:
            embed.set_footer(text=f"Team: {len(all_pets)} pet(s)")

        # Own profile is private; viewing someone else's is public
        await interaction.response.send_message(embed=embed, file=file, ephemeral=is_self)

    @app_commands.command(name="pet", description="Detailed view of your active pet's stats and bonuses")
    async def pet_cmd(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pet = await db.get_active_pet(conn, interaction.user.id)
            if not pet:
                await interaction.response.send_message("No active pet found.", ephemeral=True)
                return

        element = pet["element"]
        variant = pet["variant"]
        stage = pet["stage"]
        level = pet["level"]
        name = pet.get("nickname") or PET_NAMES[element][variant][stage]
        color = ELEMENT_COLORS[element]
        emoji = ELEMENT_EMOJIS[element]

        stats = effective_stats(pet)

        embed = discord.Embed(
            title=f"{emoji} {name} — Full Stats",
            color=color
        )

        embed.add_field(
            name="Base Stats",
            value=(
                f"HP: {pet['base_hp']} (+{pet['bonus_hp']}) = **{stats['hp']}**\n"
                f"ATK: {pet['base_atk']} (+{pet['bonus_atk']}) = **{stats['atk']}**\n"
                f"DEF: {pet['base_def']} (+{pet['bonus_def']}) = **{stats['def']}**"
            ),
            inline=True
        )
        embed.add_field(
            name="​",
            value=(
                f"SPD: {pet['base_spd']} (+{pet['bonus_spd']}) = **{stats['spd']}**\n"
                f"MGK: {pet['base_mgk']} (+{pet['bonus_mgk']}) = **{stats['mgk']}**\n"
                f"RES: {pet['base_res']} (+{pet['bonus_res']}) = **{stats['res']}**"
            ),
            inline=True
        )
        embed.add_field(name="​", value="​", inline=False)
        embed.add_field(name="Stage", value=STAGE_NAMES[stage], inline=True)
        embed.add_field(name="Level", value=f"{level}/100", inline=True)
        embed.add_field(name="Exploration", value=f"{pet['exploration']}/100", inline=True)

        # Stat caps info
        from config import stat_cap
        cap_hp = stat_cap(pet["base_hp"], level)
        embed.add_field(
            name="📊 Stat Caps (at level " + str(level) + ")",
            value=(
                f"HP cap: **{cap_hp}** | Room: +{cap_hp - (pet['base_hp'] + pet['bonus_hp'])}\n"
                f"ATK cap: **{stat_cap(pet['base_atk'], level)}** | "
                f"MGK cap: **{stat_cap(pet['base_mgk'], level)}**"
            ),
            inline=False
        )

        image_path = get_pet_image(element, variant, stage)
        file = discord.File(image_path, filename="pet.png")
        embed.set_thumbnail(url="attachment://pet.png")
        await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="feed", description="Feed a food item to your active pet")
    @app_commands.describe(item="The food item to feed (e.g. apple, bread, fish, cake)")
    async def feed(self, interaction: discord.Interaction, item: str):
        item = item.lower().strip()
        if item not in FOOD_ITEMS:
            await interaction.response.send_message(
                f"Unknown food: **{item}**. Valid foods: " + ", ".join(FOOD_ITEMS.keys()),
                ephemeral=True
            )
            return

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pet = await db.get_active_pet(conn, interaction.user.id)
            if not pet:
                await interaction.response.send_message("No active pet.", ephemeral=True)
                return

            # Check expedition lock
            exp = await db.get_active_expedition(conn, interaction.user.id)
            if exp and exp["pet_id"] == pet["id"]:
                await interaction.response.send_message(
                    "Your pet is on an expedition! It can't be fed right now.", ephemeral=True
                )
                return

            has_food = await db.has_item(conn, interaction.user.id, item)
            if not has_food:
                await interaction.response.send_message(
                    f"You don't have any **{FOOD_ITEMS[item]['display']}** in your inventory.\n"
                    "Check `/shop` or claim drops with `/claim`!",
                    ephemeral=True
                )
                return

            food = FOOD_ITEMS[item]
            stat_key = food["stat"]
            boost = food["boost"]
            xp_gain = food["xp"]
            feed_count = pet["first_fed"]  # 0, 1, 2 = egg feeding progress; 3+ = hatched

            # Remove food from inventory
            await db.remove_item(conn, interaction.user.id, item)

            # Apply stat bonus (even to eggs — bonus carries over on hatch)
            actual_boost, was_capped = apply_stat_bonus(pet, stat_key, boost)
            if actual_boost > 0:
                await conn.execute(
                    f"UPDATE pets SET bonus_{stat_key}=bonus_{stat_key}+? WHERE id=?",
                    (actual_boost, pet["id"])
                )

            evolved = False
            evo_message = ""
            new_feed_count = feed_count + 1

            if pet["stage"] == 0:
                # Egg phase — needs 3 feedings to hatch
                await conn.execute(
                    "UPDATE pets SET first_fed=? WHERE id=?", (new_feed_count, pet["id"])
                )
                if new_feed_count >= 3:
                    # Hatch!
                    await evolve_pet(conn, pet, 1)
                    evolved = True
                    evo_name = PET_NAMES[pet["element"]][pet["variant"]][1]
                    evo_message = (
                        f"🌟 **HATCHED!** Your egg burst open and **{evo_name}** emerged!\n"
                        "Your journey has truly begun!"
                    )
                    pet = await db.get_pet(conn, pet["id"])
                await db.add_xp(conn, pet["id"], xp_gain)
            else:
                await db.add_xp(conn, pet["id"], xp_gain)

            await conn.commit()
            pet = await db.get_pet(conn, pet["id"])

        food_display = food["display"]
        stat_display = stat_key.upper()
        element = pet["element"]
        variant = pet["variant"]
        stage = pet["stage"]
        name = pet.get("nickname") or PET_NAMES[element][variant][stage]
        color = ELEMENT_COLORS[element]

        image_path = get_pet_image(element, variant, stage) if evolved else get_food_image(item)
        try:
            file = discord.File(image_path, filename="img.png")
            has_img = True
        except FileNotFoundError:
            has_img = False

        embed = discord.Embed(color=color)
        stat_line = f"+{actual_boost} {stat_display}" if actual_boost > 0 else f"{stat_display} is at cap!"
        cap_note = " *(stat capped)*" if was_capped and actual_boost == 0 else ""

        if evolved:
            embed.title = f"🌟 {name} hatched!"
            embed.description = evo_message
            if has_img:
                embed.set_image(url="attachment://img.png")
        elif pet["stage"] == 0:
            # Still an egg
            remaining = 3 - new_feed_count
            dots = "🟡" * new_feed_count + "⚪" * remaining
            embed.title = f"🥚 Your egg enjoyed the meal!"
            embed.description = f"{dots} **{new_feed_count}/3 feedings** — {remaining} more to hatch!"
            food_file_path = get_food_image(item)
            try:
                file = discord.File(food_file_path, filename="img.png")
                has_img = True
                embed.set_thumbnail(url="attachment://img.png")
            except FileNotFoundError:
                has_img = False
        else:
            embed.title = f"🍽️ {name} ate {food_display}!"
            if has_img:
                embed.set_thumbnail(url="attachment://img.png")

        embed.add_field(name="Stat Boost", value=f"{stat_line}{cap_note}", inline=True)
        embed.add_field(name="XP Gained", value=f"+{xp_gain} XP", inline=True)

        if pet["stage"] > 0:
            lvl_after = pet["level"]
            xp_after = pet["xp"]
            embed.add_field(
                name="Level", value=f"Level {lvl_after} | {xp_after}/{xp_for_next_level(lvl_after)} XP",
                inline=False
            )

        if has_img:
            await interaction.response.send_message(embed=embed, file=file)
        else:
            await interaction.response.send_message(embed=embed)

        # Broadcast hatch to channel
        if evolved and interaction.guild:
            evo_name = PET_NAMES[pet["element"]][pet["variant"]][1]
            emoji = ELEMENT_EMOJIS[pet["element"]]
            await interaction.channel.send(
                f"🎉 {interaction.user.mention}'s egg just hatched! Say hello to **{evo_name}** {emoji}!"
            )

    @app_commands.command(name="train", description="Daily training — boost a random stat and gain XP")
    async def train(self, interaction: discord.Interaction):
        import random
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pet = await db.get_active_pet(conn, interaction.user.id)
            if not pet or pet["stage"] == 0:
                await interaction.response.send_message(
                    "Your pet needs to hatch first! Feed it with `/feed`.", ephemeral=True
                )
                return

            # Cooldown check
            if player["last_train"]:
                last = datetime.fromisoformat(player["last_train"])
                if (datetime.now(timezone.utc) - last) < timedelta(hours=TRAIN_COOLDOWN_HOURS):
                    remaining = (last + timedelta(hours=TRAIN_COOLDOWN_HOURS)) - datetime.now(timezone.utc)
                    hrs = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)
                    await interaction.response.send_message(
                        f"You already trained today! Come back in **{hrs}h {mins}m**.", ephemeral=True
                    )
                    return

            stats = ["hp", "atk", "def", "spd", "mgk", "res"]
            chosen_stat = random.choice(stats)
            actual, capped = apply_stat_bonus(pet, chosen_stat, TRAIN_STAT_BOOST)
            if actual > 0:
                await conn.execute(
                    f"UPDATE pets SET bonus_{chosen_stat}=bonus_{chosen_stat}+? WHERE id=?",
                    (actual, pet["id"])
                )
            await db.add_xp(conn, pet["id"], TRAIN_XP)
            await conn.execute(
                "UPDATE players SET last_train=? WHERE user_id=?",
                (db.now_iso(), interaction.user.id)
            )
            await conn.commit()
            pet = await db.get_pet(conn, pet["id"])

        name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        color = ELEMENT_COLORS[pet["element"]]
        cap_note = " *(capped)*" if capped and actual == 0 else ""

        embed = discord.Embed(
            title=f"💪 {name} trained hard!",
            description=(
                f"+{actual} **{chosen_stat.upper()}**{cap_note}\n"
                f"+{TRAIN_XP} **XP**\n\n"
                f"Level {pet['level']} | {pet['xp']}/{xp_for_next_level(pet['level'])} XP"
            ),
            color=color
        )
        embed.set_footer(text="Training resets every 20 hours.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rename", description="Give your active pet a custom name")
    @app_commands.describe(name="The new name (leave empty to reset to default)")
    async def rename(self, interaction: discord.Interaction, name: str = ""):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pet = await db.get_active_pet(conn, interaction.user.id)
            if not pet:
                await interaction.response.send_message("No active pet.", ephemeral=True)
                return
            nick = name.strip()[:24] if name.strip() else None
            await conn.execute("UPDATE pets SET nickname=? WHERE id=?", (nick, pet["id"]))
            await conn.commit()

        if nick:
            await interaction.response.send_message(f"Your pet is now known as **{nick}**! 🎀")
        else:
            default = PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
            await interaction.response.send_message(f"Nickname cleared. Back to **{default}**.")

    @app_commands.command(name="activepet", description="Switch which of your pets is the active one")
    @app_commands.describe(slot="Pet slot number (1 = first pet, 2 = second, etc.)")
    async def activepet(self, interaction: discord.Interaction, slot: int):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            pets = await db.get_player_pets(conn, interaction.user.id)
            if not pets:
                await interaction.response.send_message("You have no pets.", ephemeral=True)
                return
            if slot < 1 or slot > len(pets):
                await interaction.response.send_message(
                    f"Invalid slot. You have {len(pets)} pet(s).", ephemeral=True
                )
                return
            chosen = pets[slot - 1]
            # Check it's not on expedition
            exp = await db.get_active_expedition(conn, interaction.user.id)
            if exp and exp["pet_id"] == chosen["id"]:
                await interaction.response.send_message(
                    "That pet is currently on an expedition!", ephemeral=True
                )
                return
            await conn.execute(
                "UPDATE players SET active_pet=? WHERE user_id=?",
                (chosen["id"], interaction.user.id)
            )
            await conn.commit()

        name = chosen.get("nickname") or PET_NAMES[chosen["element"]][chosen["variant"]][chosen["stage"]]
        await interaction.response.send_message(f"Active pet switched to **{name}**! ✅")


async def setup(bot: commands.Bot):
    await bot.add_cog(Pet(bot))
