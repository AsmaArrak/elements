import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

import database as db
from config import PET_NAMES, ELEMENT_EMOJIS, STAGE_NAMES, RARITY_EMOJIS
from game.skills import SKILLS, SKILL_COMPATIBILITY, MAX_SKILLS, SCROLL_SELL_PRICE


class LearnView(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict], scrolls: list[dict]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pets = pets
        self.scrolls = scrolls
        self.selected_pet = pets[0] if len(pets) == 1 else None
        self.selected_scroll = None

        if len(pets) > 1:
            opts = []
            for p in pets:
                name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
                opts.append(discord.SelectOption(
                    label=name, value=str(p["id"]),
                    description=f"Level {p['level']} · {STAGE_NAMES[p['stage']]}",
                    emoji=ELEMENT_EMOJIS[p["element"]]
                ))
            ps = discord.ui.Select(placeholder="Choose a pet...", options=opts, row=0)
            ps.callback = self._pet_cb
            self.add_item(ps)

        scroll_opts = []
        for s in scrolls[:25]:
            skill = SKILLS.get(s["item_key"], {})
            r_emoji = RARITY_EMOJIS.get(s.get("element_rarity") or skill.get("rarity", "common"), "⚪")
            scroll_opts.append(discord.SelectOption(
                label=skill.get("name", s["item_key"]),
                value=s["item_key"],
                description=f"{skill.get('rarity','?').title()} · {ELEMENT_EMOJIS.get(skill.get('element',''),'')}{skill.get('element','').title()} · x{s['quantity']}",
                emoji=r_emoji
            ))
        ss = discord.ui.Select(placeholder="Choose a scroll to learn...", options=scroll_opts, row=1)
        ss.callback = self._scroll_cb
        self.add_item(ss)

        btn = discord.ui.Button(label="📖 Learn Skill", style=discord.ButtonStyle.success, row=2)
        btn.callback = self._learn_cb
        self.add_item(btn)

    async def _pet_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        pid = int(interaction.data["values"][0])
        self.selected_pet = next(p for p in self.pets if p["id"] == pid)
        await interaction.response.defer()

    async def _scroll_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.selected_scroll = interaction.data["values"][0]
        await interaction.response.defer()

    async def _learn_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        if not self.selected_pet:
            await interaction.response.send_message("Select a pet first.", ephemeral=True)
            return
        if not self.selected_scroll:
            await interaction.response.send_message("Select a scroll first.", ephemeral=True)
            return

        pet = self.selected_pet
        skill_key = self.selected_scroll
        skill = SKILLS.get(skill_key)
        if not skill:
            await interaction.response.send_message("Invalid skill.", ephemeral=True)
            return

        # Check compatibility
        compatible = SKILL_COMPATIBILITY.get(pet["element"], [pet["element"]])
        if skill["element"] not in compatible:
            await interaction.response.send_message(
                f"❌ **{pet.get('nickname') or PET_NAMES[pet['element']][pet['variant']][pet['stage']]}** "
                f"cannot learn {skill['element'].title()} skills!\n"
                f"Compatible elements: {', '.join(compatible)}",
                ephemeral=True
            )
            return

        self.stop()
        async with aiosqlite.connect(db.DB_PATH) as conn:
            # Check already knows it
            async with conn.execute(
                "SELECT 1 FROM pet_skills WHERE pet_id=? AND skill_key=?", (pet["id"], skill_key)
            ) as cur:
                if await cur.fetchone():
                    await interaction.response.edit_message(
                        embed=discord.Embed(description="This pet already knows that skill!", color=0xFF0000),
                        view=None
                    )
                    return

            # Check skill count
            async with conn.execute(
                "SELECT COUNT(*) FROM pet_skills WHERE pet_id=?", (pet["id"],)
            ) as cur:
                count = (await cur.fetchone())[0]
            if count >= MAX_SKILLS:
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        description=f"❌ This pet already knows {MAX_SKILLS} skills (max)! Forget one first with `/forgetskill`.",
                        color=0xFF0000
                    ),
                    view=None
                )
                return

            await conn.execute(
                "INSERT INTO pet_skills(pet_id, skill_key) VALUES(?,?)", (pet["id"], skill_key)
            )
            await db.remove_item(conn, interaction.user.id, skill_key, 1)
            await conn.commit()

        pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        r_emoji = RARITY_EMOJIS.get(skill["rarity"], "")
        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"📖 Skill Learned!",
                description=f"**{pet_name}** learned {r_emoji} **{skill['name']}**!\n"
                            f"*{skill['desc']}*\n\n"
                            f"Damage: **{skill['mult']}x** {'ATK' if skill['type'] == 'physical' else 'MGK'}",
                color=0x2ECC71
            ),
            view=None
        )


class SkillsCmd(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="learn", description="Use a skill scroll to teach your pet a new skill")
    async def learn(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pets = [p for p in await db.get_player_pets(conn, interaction.user.id) if p["stage"] > 0]
            inventory = await db.get_inventory(conn, interaction.user.id)
            scrolls = [i for i in inventory if i["item_type"] == "scroll"]

        if not pets:
            await interaction.response.send_message("You need a hatched pet to learn skills.", ephemeral=True)
            return
        if not scrolls:
            await interaction.response.send_message(
                "You have no skill scrolls! Go on expeditions to find them.", ephemeral=True
            )
            return

        view = LearnView(interaction.user.id, pets, scrolls)
        await interaction.response.send_message("Choose a pet and scroll:", view=view, ephemeral=True)

    @app_commands.command(name="skills", description="View a pet's learned skills")
    async def skills(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pets = await db.get_player_pets(conn, interaction.user.id)

        if not pets:
            await interaction.response.send_message("No pets found.", ephemeral=True)
            return

        embed = discord.Embed(title="⚔️ Pet Skills", color=0x7B68EE)
        async with aiosqlite.connect(db.DB_PATH) as conn:
            for pet in pets:
                if pet["stage"] == 0:
                    continue
                pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
                emoji = ELEMENT_EMOJIS[pet["element"]]
                async with conn.execute(
                    "SELECT skill_key FROM pet_skills WHERE pet_id=?", (pet["id"],)
                ) as cur:
                    learned = [r[0] for r in await cur.fetchall()]

                if not learned:
                    embed.add_field(
                        name=f"{emoji} {pet_name}",
                        value="*No skills learned yet — use `/learn` with a scroll!*",
                        inline=False
                    )
                else:
                    lines = []
                    for sk in learned:
                        s = SKILLS.get(sk, {})
                        r_emoji = RARITY_EMOJIS.get(s.get("rarity", ""), "")
                        stat = "ATK" if s.get("type") == "physical" else "MGK"
                        lines.append(f"{r_emoji} **{s.get('name', sk)}** — {s.get('mult', 1)}x {stat} · *{s.get('desc', '')}*")
                    embed.add_field(
                        name=f"{emoji} {pet_name} ({len(learned)}/{MAX_SKILLS})",
                        value="\n".join(lines),
                        inline=False
                    )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="forgetskill", description="Make your pet forget a skill to make room")
    @app_commands.describe(skill_name="The skill name to forget")
    async def forgetskill(self, interaction: discord.Interaction, skill_name: str):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            pet = await db.get_active_pet(conn, interaction.user.id)
            if not pet or pet["stage"] == 0:
                await interaction.response.send_message("No hatched active pet.", ephemeral=True)
                return
            # Find skill key by name
            skill_key = next(
                (k for k, v in SKILLS.items() if v["name"].lower() == skill_name.lower()), None
            )
            if not skill_key:
                await interaction.response.send_message(f"Skill `{skill_name}` not found.", ephemeral=True)
                return
            async with conn.execute(
                "SELECT 1 FROM pet_skills WHERE pet_id=? AND skill_key=?", (pet["id"], skill_key)
            ) as cur:
                if not await cur.fetchone():
                    await interaction.response.send_message("Your pet doesn't know that skill.", ephemeral=True)
                    return
            await conn.execute(
                "DELETE FROM pet_skills WHERE pet_id=? AND skill_key=?", (pet["id"], skill_key)
            )
            await conn.commit()

        pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        await interaction.response.send_message(
            f"**{pet_name}** forgot **{SKILLS[skill_key]['name']}**.", ephemeral=True
        )

    @app_commands.command(name="sellscroll", description="Sell a skill scroll for coins")
    @app_commands.describe(skill_name="The scroll name to sell")
    async def sellscroll(self, interaction: discord.Interaction, skill_name: str):
        skill_key = next(
            (k for k, v in SKILLS.items() if v["name"].lower() == skill_name.lower()), None
        )
        if not skill_key:
            await interaction.response.send_message(f"Scroll `{skill_name}` not found.", ephemeral=True)
            return
        async with aiosqlite.connect(db.DB_PATH) as conn:
            has = await db.has_item(conn, interaction.user.id, skill_key, 1)
            if not has:
                await interaction.response.send_message("You don't have that scroll.", ephemeral=True)
                return
            await db.remove_item(conn, interaction.user.id, skill_key, 1)
            skill = SKILLS[skill_key]
            price = SCROLL_SELL_PRICE.get(skill["rarity"], 200)
            await conn.execute(
                "UPDATE players SET coins=coins+? WHERE user_id=?", (price, interaction.user.id)
            )
            await conn.commit()

        r_emoji = RARITY_EMOJIS.get(SKILLS[skill_key]["rarity"], "")
        await interaction.response.send_message(
            f"Sold {r_emoji} **{SKILLS[skill_key]['name']} Scroll** for **{price} coins**! 💰"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SkillsCmd(bot))
