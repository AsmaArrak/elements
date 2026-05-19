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

    expl = pet['exploration']
    embed.add_field(
        name="🧭 Exploration",
        value=f"{expl}/100 {'✅' if expl >= 100 else f'({100 - expl} to Mega)'}",
        inline=True
    )

    image_path = get_pet_image(element, variant, stage)
    file = discord.File(image_path, filename="pet.png")
    embed.set_image(url="attachment://pet.png")
    return embed, file


async def do_feed(pet: dict, item_key: str, user_id: int, channel) -> tuple[discord.Embed, discord.File | None]:
    """Core feeding logic. Returns (embed, optional file)."""
    async with aiosqlite.connect(db.DB_PATH) as conn:
        # Re-fetch fresh pet state
        pet = await db.get_pet(conn, pet["id"])
        food = FOOD_ITEMS[item_key]
        stat_key = food["stat"]
        boost = food["boost"]
        xp_gain = food["xp"]
        feed_count = pet["first_fed"]

        await db.remove_item(conn, user_id, item_key)

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
            await conn.execute(
                "UPDATE pets SET first_fed=? WHERE id=?", (new_feed_count, pet["id"])
            )
            if new_feed_count >= 3:
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
    stat_line = f"+{actual_boost} {stat_display}" if actual_boost > 0 else f"{stat_display} is at cap!"
    cap_note = " *(stat capped)*" if was_capped and actual_boost == 0 else ""

    embed = discord.Embed(color=color)
    file = None

    if evolved:
        embed.title = f"🌟 {name} hatched!"
        embed.description = evo_message
        try:
            file = discord.File(get_pet_image(element, variant, stage), filename="img.png")
            embed.set_image(url="attachment://img.png")
        except FileNotFoundError:
            pass
        if channel:
            evo_name = PET_NAMES[element][variant][1]
            emoji = ELEMENT_EMOJIS[element]
            await channel.send(
                f"🎉 <@{user_id}>'s egg just hatched! Say hello to **{evo_name}** {emoji}!"
            )
    elif pet["stage"] == 0:
        remaining = 3 - new_feed_count
        dots = "🟡" * new_feed_count + "⚪" * remaining
        embed.title = "🥚 Your egg enjoyed the meal!"
        embed.description = f"{dots} **{new_feed_count}/3 feedings** — {remaining} more to hatch!"
        try:
            file = discord.File(get_food_image(item_key), filename="img.png")
            embed.set_thumbnail(url="attachment://img.png")
        except FileNotFoundError:
            pass
    else:
        embed.title = f"🍽️ {name} ate {food_display}!"
        try:
            file = discord.File(get_food_image(item_key), filename="img.png")
            embed.set_thumbnail(url="attachment://img.png")
        except FileNotFoundError:
            pass

    embed.add_field(name="Stat Boost", value=f"{stat_line}{cap_note}", inline=True)
    embed.add_field(name="XP Gained", value=f"+{xp_gain} XP", inline=True)
    if pet["stage"] > 0:
        embed.add_field(
            name="Level",
            value=f"Level {pet['level']} | {pet['xp']}/{xp_for_next_level(pet['level'])} XP",
            inline=False
        )
    return embed, file


class FeedView(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict], food_inv: list[dict],
                 original_interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pets = pets
        self.food_inv = food_inv
        self.original_interaction = original_interaction
        self.selected_pet: dict | None = pets[0] if len(pets) == 1 else None
        self.selected_food: str | None = None

        # Pet select (only show if more than 1 pet)
        if len(pets) > 1:
            self.add_item(PetSelect(pets))

        # Food select
        self.add_item(FoodSelect(food_inv))

    @discord.ui.button(label="🍽️ Feed!", style=discord.ButtonStyle.success, row=2)
    async def feed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        if not self.selected_pet:
            await interaction.response.send_message("Please select a pet first.", ephemeral=True)
            return
        if not self.selected_food:
            await interaction.response.send_message("Please select a food item first.", ephemeral=True)
            return

        self.stop()
        await interaction.response.defer()

        embed, file = await do_feed(
            self.selected_pet, self.selected_food,
            self.user_id, interaction.channel
        )
        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

        # Edit the original selection message to show it's done
        try:
            await self.original_interaction.edit_original_response(
                embed=discord.Embed(description="✅ Fed!", color=0x2ECC71), view=None
            )
        except Exception:
            pass


class PetSelect(discord.ui.Select):
    def __init__(self, pets: list[dict]):
        options = []
        for p in pets:
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            emoji = ELEMENT_EMOJIS[p["element"]]
            stage_label = STAGE_NAMES[p["stage"]]
            options.append(discord.SelectOption(
                label=name,
                value=str(p["id"]),
                description=f"Level {p['level']} · {stage_label}",
                emoji=emoji
            ))
        super().__init__(placeholder="Choose a pet to feed...", options=options, row=0)
        self.pets_by_id = {str(p["id"]): p for p in pets}

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_pet = self.pets_by_id[self.values[0]]
        await interaction.response.defer()


class FoodSelect(discord.ui.Select):
    def __init__(self, food_inv: list[dict]):
        options = []
        for item in food_inv:
            key = item["item_key"]
            food_data = FOOD_ITEMS.get(key, {})
            display = food_data.get("display", key.title())
            stat = food_data.get("stat", "?").upper()
            boost = food_data.get("boost", 0)
            qty = item["quantity"]
            options.append(discord.SelectOption(
                label=display,
                value=key,
                description=f"×{qty} in bag · +{boost} {stat}",
            ))
        super().__init__(placeholder="Choose a food to feed...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_food = self.values[0]
        await interaction.response.defer()


class PetViewSelect(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pets_by_id = {str(p["id"]): p for p in pets}
        options = []
        for p in pets:
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            emoji = ELEMENT_EMOJIS[p["element"]]
            stage_label = STAGE_NAMES[p["stage"]]
            options.append(discord.SelectOption(
                label=name,
                value=str(p["id"]),
                description=f"Level {p['level']} · {stage_label}",
                emoji=emoji
            ))
        select = discord.ui.Select(placeholder="Choose a pet to inspect...", options=options)
        select.callback = self._callback
        self.add_item(select)

    async def _callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        pet = self.pets_by_id[interaction.data["values"][0]]
        self.stop()
        await interaction.response.defer()
        pet_cog = interaction.client.get_cog("Pet")
        await pet_cog._send_pet_stats(interaction, pet, followup=True)


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
        embed.set_footer(text=f"💰 {p['coins']} coins | Team: {len(all_pets)} pet(s)")

        # Own profile is private; viewing someone else's is public
        await interaction.response.send_message(embed=embed, file=file, ephemeral=is_self)

    @app_commands.command(name="pet", description="Detailed view of your active pet's stats and bonuses")
    async def pet_cmd(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pets = await db.get_player_pets(conn, interaction.user.id)
            hatched = [p for p in pets if p["stage"] > 0]

        if not pets:
            await interaction.response.send_message("No active pet found.", ephemeral=True)
            return

        if len(pets) > 1:
            view = PetViewSelect(interaction.user.id, pets)
            await interaction.response.send_message(
                "Which pet would you like to inspect?", view=view, ephemeral=True
            )
            return

        await self._send_pet_stats(interaction, pets[0])

    async def _send_pet_stats(self, interaction: discord.Interaction, pet: dict, followup: bool = False):
        from config import stat_cap
        element = pet["element"]
        variant = pet["variant"]
        stage = pet["stage"]
        level = pet["level"]
        name = pet.get("nickname") or PET_NAMES[element][variant][stage]
        color = ELEMENT_COLORS[element]
        emoji = ELEMENT_EMOJIS[element]

        stats = effective_stats(pet)

        embed = discord.Embed(title=f"{emoji} {name} — Full Stats", color=color)

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
        expl = pet['exploration']
        expl_note = " ✅ Mega unlocked!" if expl >= 100 else f" ({100 - expl} to Mega)"
        embed.add_field(name="🧭 Exploration", value=f"{expl}/100{expl_note}", inline=True)

        cap_hp = stat_cap(pet["base_hp"], level)
        embed.add_field(
            name=f"📊 Stat Caps (at level {level})",
            value=(
                f"HP cap: **{cap_hp}** | Room: +{cap_hp - (pet['base_hp'] + pet['bonus_hp'])}\n"
                f"ATK cap: **{stat_cap(pet['base_atk'], level)}** | "
                f"MGK cap: **{stat_cap(pet['base_mgk'], level)}**"
            ),
            inline=False
        )
        expl_val = pet['exploration']
        if expl_val >= 100:
            expl_desc = f"**{expl_val}/100** ✅\n*Mega Stone drops **unlocked**! You can now find them on expeditions.*"
        else:
            expl_desc = f"**{expl_val}/100**\n*Increases by going on expeditions. Reach **100** to unlock Mega Stone drops!*"
        embed.add_field(name="🧭 Exploration", value=expl_desc, inline=False)

        # Equipped armor
        armor_id = pet.get("equipped_armor")
        if armor_id:
            async with aiosqlite.connect(db.DB_PATH) as conn:
                async with conn.execute(
                    "SELECT name, rarity, bonus_hp, bonus_atk, bonus_def, bonus_spd, bonus_mgk, bonus_res FROM armor_inventory WHERE id=?",
                    (armor_id,)
                ) as cur:
                    ar = await cur.fetchone()
            if ar:
                from config import RARITY_EMOJIS
                r_emoji = RARITY_EMOJIS.get(ar[1], "")
                bonuses = []
                labels = [("HP", ar[2]), ("ATK", ar[3]), ("DEF", ar[4]), ("SPD", ar[5]), ("MGK", ar[6]), ("RES", ar[7])]
                for stat, val in labels:
                    if val:
                        bonuses.append(f"+{val} {stat}")
                embed.add_field(
                    name="🛡️ Equipped Armor",
                    value=f"{r_emoji} **{ar[0]}** *({ar[1]})*\n{' · '.join(bonuses)}",
                    inline=False
                )
        else:
            embed.add_field(name="🛡️ Equipped Armor", value="*None — use `/equip` to equip armor*", inline=False)

        image_path = get_pet_image(element, variant, stage)
        file = discord.File(image_path, filename="pet.png")
        embed.set_thumbnail(url="attachment://pet.png")
        if followup:
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="feed", description="Choose a pet and food item to feed from your inventory")
    async def feed(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            all_pets = await db.get_player_pets(conn, interaction.user.id)
            exp = await db.get_active_expedition(conn, interaction.user.id)
            exp_pet_id = exp["pet_id"] if exp else None

            # Pets that can be fed (not on expedition)
            feedable = [p for p in all_pets if p["id"] != exp_pet_id]
            if not feedable:
                await interaction.response.send_message(
                    "All your pets are on expedition!", ephemeral=True
                )
                return

            # Food items in inventory
            inventory = await db.get_inventory(conn, interaction.user.id)
            food_inv = [i for i in inventory if i["item_type"] == "food"]
            if not food_inv:
                await interaction.response.send_message(
                    "You have no food! Buy some with `/shop` or claim a drop with `/claim`.",
                    ephemeral=True
                )
                return

        view = FeedView(interaction.user.id, feedable, food_inv, interaction)
        embed = discord.Embed(
            title="🍽️ Feed a pet",
            description="Select a pet and a food item below, then click **Feed**.",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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



async def setup(bot: commands.Bot):
    await bot.add_cog(Pet(bot))
