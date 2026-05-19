import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import random
from datetime import datetime, timezone, timedelta

import database as db
from config import FOOD_ITEMS, STAT_ITEMS, FISH_COOLDOWN_MINUTES, DIG_COOLDOWN_MINUTES


TRIVIA_QUESTIONS = [
    # Game lore
    {"q": "Which element is strong against Bloom and Crystal?", "choices": ["Ember 🔥", "Void 🌑", "Storm ⚡", "Tide 🌊"], "answer": 0},
    {"q": "What stat determines who attacks first in battle?", "choices": ["ATK", "SPD", "MGK", "DEF"], "answer": 1},
    {"q": "What is the maximum level a pet can reach?", "choices": ["50", "75", "100", "99"], "answer": 2},
    {"q": "What does the Exploration stat affect?", "choices": ["Battle speed", "Mega Stone drops", "Food XP", "Coin rewards"], "answer": 1},
    {"q": "How many pets can a player have at most?", "choices": ["3", "4", "5", "6"], "answer": 2},
    {"q": "What evolution stage does the 'Uncommon Evo Stone' unlock?", "choices": ["Egg to Evo 1", "Evo 1 to Evo 2", "Evo 2 to Evo 3", "Evo 3 to Mega"], "answer": 1},
    {"q": "Which element's Mega is called Leviarcus?", "choices": ["Phantom", "Void", "Tide", "Storm"], "answer": 2},
    {"q": "What magic multiplier applies when hitting a weakness?", "choices": ["1.2x", "1.5x", "2.0x", "1.75x"], "answer": 1},
    {"q": "Which food boosts the MGK stat?", "choices": ["Apple", "Cheese", "Fish", "Bread"], "answer": 2},
    {"q": "What triggers a pet's first evolution from Egg to Evo 1?", "choices": ["Reaching level 10", "First feeding", "First battle", "Buying an evo stone"], "answer": 1},
    {"q": "Which element is Void strong against?", "choices": ["Bloom, Crystal", "Phantom, Cosmic", "Storm, Forge", "Tide, Ember"], "answer": 1},
    {"q": "What is the Forge Mega Evolution named?", "choices": ["Forgegod", "Titanforge", "Forgeknight", "Megalith"], "answer": 1},
    # General trivia
    {"q": "How many elements are in Elementals?", "choices": ["8", "9", "10", "12"], "answer": 2},
    {"q": "Which stat reduces incoming physical damage?", "choices": ["RES", "HP", "DEF", "SPD"], "answer": 2},
    {"q": "What do you need to max out before a Mega Stone has any chance of dropping?", "choices": ["Level", "Exploration stat", "ATK stat", "Coins"], "answer": 1},
    # General knowledge
    {"q": "How many sides does a hexagon have?", "choices": ["5", "6", "7", "8"], "answer": 1},
    {"q": "What is the chemical symbol for Gold?", "choices": ["Go", "Gd", "Au", "Ag"], "answer": 2},
    {"q": "Which planet is known as the Red Planet?", "choices": ["Venus", "Jupiter", "Mars", "Saturn"], "answer": 2},
    {"q": "How many continents are there on Earth?", "choices": ["5", "6", "7", "8"], "answer": 2},
    {"q": "What is the largest ocean on Earth?", "choices": ["Atlantic", "Indian", "Arctic", "Pacific"], "answer": 3},
    {"q": "Who painted the Mona Lisa?", "choices": ["Michelangelo", "Raphael", "Leonardo da Vinci", "Donatello"], "answer": 2},
    {"q": "How many colors are in a rainbow?", "choices": ["5", "6", "7", "8"], "answer": 2},
    {"q": "What is the capital city of Japan?", "choices": ["Beijing", "Seoul", "Tokyo", "Bangkok"], "answer": 2},
    {"q": "What is the fastest land animal?", "choices": ["Lion", "Leopard", "Cheetah", "Greyhound"], "answer": 2},
    {"q": "How many bones are in the adult human body?", "choices": ["196", "206", "216", "226"], "answer": 1},
    {"q": "What is the smallest planet in our solar system?", "choices": ["Mars", "Mercury", "Venus", "Pluto"], "answer": 1},
    {"q": "In what year did World War II end?", "choices": ["1943", "1944", "1945", "1946"], "answer": 2},
    {"q": "What language has the most native speakers?", "choices": ["English", "Spanish", "Hindi", "Mandarin"], "answer": 3},
    {"q": "How many strings does a standard guitar have?", "choices": ["4", "5", "6", "7"], "answer": 2},
    {"q": "What is the boiling point of water in Celsius?", "choices": ["90°", "95°", "100°", "105°"], "answer": 2},
]


class TriviaView(discord.ui.View):
    def __init__(self, question: dict, channel_id: int):
        super().__init__(timeout=20)
        self.question = question
        self.channel_id = channel_id
        self.answered = False
        labels = ["A", "B", "C", "D"]
        for i, choice in enumerate(question["choices"]):
            btn = discord.ui.Button(
                label=f"{labels[i]}: {choice}",
                style=discord.ButtonStyle.secondary,
                custom_id=str(i),
                row=0
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if self.answered:
                await interaction.response.send_message("Already answered!", ephemeral=True)
                return

            correct = idx == self.question["answer"]
            self.answered = True
            self.stop()

            if correct:
                reward = random.randint(40, 120)
                async with aiosqlite.connect(db.DB_PATH) as conn:
                    await db.ensure_player(conn, interaction.user.id)
                    await conn.execute(
                        "UPDATE players SET coins=coins+? WHERE user_id=?",
                        (reward, interaction.user.id)
                    )
                    await conn.commit()
                await interaction.response.edit_message(
                    content=f"✅ **Correct!** {interaction.user.mention} wins **{reward} coins**! 🎉",
                    view=None
                )
            else:
                correct_answer = self.question["choices"][self.question["answer"]]
                await interaction.response.edit_message(
                    content=f"❌ Wrong! {interaction.user.mention} — the answer was **{correct_answer}**.",
                    view=None
                )
        return callback

    async def on_timeout(self):
        correct_answer = self.question["choices"][self.question["answer"]]
        try:
            pass  # Message already done if answered, otherwise it just times out
        except Exception:
            pass


class Minigames(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="fish", description="Cast a fishing line for rewards")
    async def fish(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.ensure_player(conn, interaction.user.id)
            if player["last_fish"]:
                last = datetime.fromisoformat(player["last_fish"])
                if (datetime.now(timezone.utc) - last) < timedelta(minutes=FISH_COOLDOWN_MINUTES):
                    remaining = (last + timedelta(minutes=FISH_COOLDOWN_MINUTES)) - datetime.now(timezone.utc)
                    mins = int(remaining.total_seconds() // 60)
                    secs = int(remaining.total_seconds() % 60)
                    await interaction.response.send_message(
                        f"🎣 Your line is still in the water! Come back in **{mins}m {secs}s**.",
                        ephemeral=True
                    )
                    return

            # Roll catch
            roll = random.random()
            if roll < 0.55:
                # Common: coins
                coins = random.randint(15, 60)
                result_text = f"🐟 You caught a **small fish** and sold it for **{coins} coins**!"
                await conn.execute(
                    "UPDATE players SET coins=coins+?, last_fish=? WHERE user_id=?",
                    (coins, db.now_iso(), interaction.user.id)
                )
            elif roll < 0.80:
                # Uncommon: better coins
                coins = random.randint(60, 180)
                result_text = f"🐠 You caught a **colorful fish** worth **{coins} coins**!"
                await conn.execute(
                    "UPDATE players SET coins=coins+?, last_fish=? WHERE user_id=?",
                    (coins, db.now_iso(), interaction.user.id)
                )
            elif roll < 0.93:
                # Rare: food item
                food = random.choice(["fish", "apple", "bread", "grape"])
                await db.add_item(conn, interaction.user.id, food, "food", 1)
                food_display = FOOD_ITEMS[food]["display"]
                result_text = f"🎣 You reeled in a **{food_display}**! Added to inventory."
                await conn.execute(
                    "UPDATE players SET last_fish=? WHERE user_id=?",
                    (db.now_iso(), interaction.user.id)
                )
            elif roll < 0.99:
                # Very rare: stat item
                stat_item = random.choice(list(STAT_ITEMS.keys()))
                await db.add_item(conn, interaction.user.id, stat_item, "stat_item", 1)
                item_display = STAT_ITEMS[stat_item]["display"]
                result_text = f"✨ **Rare catch!** You found a **{item_display}**! Added to inventory."
                await conn.execute(
                    "UPDATE players SET last_fish=? WHERE user_id=?",
                    (db.now_iso(), interaction.user.id)
                )
            else:
                # Ultra rare: evo stone
                from config import ELEMENTS
                element = random.choice(ELEMENTS)
                await db.add_item(conn, interaction.user.id, "evo_stone_uncommon", "evo_stone", 1, element)
                from config import ELEMENT_DISPLAY, ELEMENT_EMOJIS
                result_text = (
                    f"🌟 **LEGENDARY CATCH!** Somehow tangled in your line: "
                    f"a **{ELEMENT_DISPLAY[element]} Uncommon Evo Stone**! {ELEMENT_EMOJIS[element]}"
                )
                await conn.execute(
                    "UPDATE players SET last_fish=? WHERE user_id=?",
                    (db.now_iso(), interaction.user.id)
                )

            await conn.commit()

        embed = discord.Embed(
            title="🎣 Gone Fishing",
            description=result_text,
            color=0x3498DB
        )
        embed.set_footer(text=f"Fishing resets every {FISH_COOLDOWN_MINUTES} minutes.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dig", description="Excavate a spot for buried treasure")
    async def dig(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.ensure_player(conn, interaction.user.id)
            if player["last_dig"]:
                last = datetime.fromisoformat(player["last_dig"])
                if (datetime.now(timezone.utc) - last) < timedelta(minutes=DIG_COOLDOWN_MINUTES):
                    remaining = (last + timedelta(minutes=DIG_COOLDOWN_MINUTES)) - datetime.now(timezone.utc)
                    mins = int(remaining.total_seconds() // 60)
                    await interaction.response.send_message(
                        f"⛏️ You're too tired to dig! Rest for **{mins}m** more.",
                        ephemeral=True
                    )
                    return

            roll = random.random()
            if roll < 0.35:
                # Empty
                messages = [
                    "⛏️ You dig and dig... nothing but rocks.",
                    "🪨 Just dirt down here. Maybe try somewhere else.",
                    "💨 You find an empty hole. Someone beat you to it!",
                ]
                result_text = random.choice(messages)
                await conn.execute(
                    "UPDATE players SET last_dig=? WHERE user_id=?",
                    (db.now_iso(), interaction.user.id)
                )
            elif roll < 0.65:
                # Coins
                coins = random.randint(25, 100)
                result_text = f"💰 You dug up **{coins} coins**!"
                await conn.execute(
                    "UPDATE players SET coins=coins+?, last_dig=? WHERE user_id=?",
                    (coins, db.now_iso(), interaction.user.id)
                )
            elif roll < 0.82:
                # Food
                food = random.choice(["apple", "bread", "carrot", "cheese", "grape"])
                await db.add_item(conn, interaction.user.id, food, "food", 1)
                food_display = FOOD_ITEMS[food]["display"]
                result_text = f"🌱 You unearthed a **{food_display}**! Added to inventory."
                await conn.execute(
                    "UPDATE players SET last_dig=? WHERE user_id=?",
                    (db.now_iso(), interaction.user.id)
                )
            elif roll < 0.94:
                # Stat item
                stat_item = random.choice(list(STAT_ITEMS.keys()))
                await db.add_item(conn, interaction.user.id, stat_item, "stat_item", 1)
                item_display = STAT_ITEMS[stat_item]["display"]
                result_text = f"💎 You dug up a **{item_display}**! Added to inventory."
                await conn.execute(
                    "UPDATE players SET last_dig=? WHERE user_id=?",
                    (db.now_iso(), interaction.user.id)
                )
            elif roll < 0.99:
                # Cake or honey
                rare_food = random.choice(["cake", "honey"])
                await db.add_item(conn, interaction.user.id, rare_food, "food", 1)
                food_display = FOOD_ITEMS[rare_food]["display"]
                result_text = f"🎉 **Rare find!** You uncovered a **{food_display}**! Added to inventory."
                await conn.execute(
                    "UPDATE players SET last_dig=? WHERE user_id=?",
                    (db.now_iso(), interaction.user.id)
                )
            else:
                # Uncommon evo stone
                from config import ELEMENTS, ELEMENT_DISPLAY, ELEMENT_EMOJIS
                element = random.choice(ELEMENTS)
                await db.add_item(conn, interaction.user.id, "evo_stone_uncommon", "evo_stone", 1, element)
                result_text = (
                    f"⭐ **INCREDIBLE!** You found a **{ELEMENT_DISPLAY[element]} "
                    f"Uncommon Evo Stone**! {ELEMENT_EMOJIS[element]}"
                )
                await conn.execute(
                    "UPDATE players SET last_dig=? WHERE user_id=?",
                    (db.now_iso(), interaction.user.id)
                )

            await conn.commit()

        embed = discord.Embed(
            title="⛏️ Excavation",
            description=result_text,
            color=0x8B4513
        )
        embed.set_footer(text=f"Digging resets every {DIG_COOLDOWN_MINUTES} minutes.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="trivia", description="Answer a trivia question to win coins")
    async def trivia(self, interaction: discord.Interaction):
        question = random.choice(TRIVIA_QUESTIONS)
        labels = ["A", "B", "C", "D"]
        choices_text = "\n".join(
            f"**{labels[i]}:** {choice}"
            for i, choice in enumerate(question["choices"])
        )
        embed = discord.Embed(
            title="❓ Trivia Question",
            description=f"**{question['q']}**\n\n{choices_text}",
            color=0x9B59B6
        )
        embed.set_footer(text="First to click the right answer wins coins! • 20 seconds")
        view = TriviaView(question, interaction.channel_id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="leaderboard", description="See the top pets on this server ranked by level")
    async def leaderboard(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Only works in a server.", ephemeral=True)
            return

        member_ids = [m.id for m in interaction.guild.members if not m.bot]
        if not member_ids:
            await interaction.response.send_message("No members found.", ephemeral=True)
            return

        placeholders = ",".join("?" * len(member_ids))
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                f"""SELECT p.player_id, p.level, p.element, p.variant, p.stage, p.nickname, p.xp
                    FROM pets p
                    WHERE p.player_id IN ({placeholders})
                    AND p.stage > 0
                    ORDER BY p.level DESC, p.stage DESC, p.xp DESC
                    LIMIT 20""",
                member_ids
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message("No hatched pets on this server yet!", ephemeral=True)
            return

        from config import PET_NAMES, ELEMENT_EMOJIS, STAGE_NAMES

        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        stage_stars = {1: "", 2: "★", 3: "★★", 4: "⭐ MEGA"}

        lines = []
        for i, row in enumerate(rows):
            player_id, level, element, variant, stage, nickname, xp = row
            member = interaction.guild.get_member(player_id)
            member_name = member.display_name if member else f"User {player_id}"
            pet_name = nickname or PET_NAMES[element][variant][stage]
            emoji = ELEMENT_EMOJIS[element]
            rank = medals.get(i, f"`#{i+1}`")
            stars = stage_stars.get(stage, "")
            lines.append(
                f"{rank} **{pet_name}** {emoji} — Lv.**{level}** {stars}\n"
                f"└ {STAGE_NAMES[stage]} · *{member_name}*"
            )

        embed = discord.Embed(
            title="🏆 Pet Leaderboard",
            description="\n".join(lines),
            color=0xFFD700
        )
        embed.set_footer(text="Ranked by level — all pets count individually")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Minigames(bot))
