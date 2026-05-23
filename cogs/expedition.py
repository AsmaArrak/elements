import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone, timedelta

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_EMOJIS, ELEMENT_COLORS, PET_NAMES, STAGE_NAMES,
    FOOD_ITEMS, STAT_ITEMS, ACCELERATORS, EXPEDITION_XP, EXPLORATION_GAIN, get_pet_image
)
from game.loot import generate_expedition_loot, generate_armor_drop, generate_scroll_drop


# Duration label → hours (float)
DURATION_MAP: dict[str, float] = {
    "30m":  0.5,
    "1h30": 1.5,
    "4h":   4.0,
    "6h":   6.0,
}

# Human-readable label for each duration
DURATION_LABELS: dict[float, str] = {
    0.5: "30-minute",
    1.5: "1.5-hour",
    4.0: "4-hour",
    6.0: "6-hour",
}


def fmt_dur(hrs: float) -> str:
    return DURATION_LABELS.get(hrs, f"{hrs}-hour")


class ExpeditionPetSelect(discord.ui.View):
    def __init__(self, user_id: int, pets: list[dict], duration: float):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.duration = duration
        self.pets_by_id = {str(p["id"]): p for p in pets}
        options = []
        for p in pets:
            name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
            emoji = ELEMENT_EMOJIS[p["element"]]
            stage_label = STAGE_NAMES[p["stage"]]
            options.append(discord.SelectOption(
                label=name,
                value=str(p["id"]),
                description=f"Level {p['level']} · {stage_label} · Exploration {p['exploration']}/100",
                emoji=emoji
            ))
        select = discord.ui.Select(placeholder="Choose a pet to send...", options=options)
        select.callback = self._callback
        self.add_item(select)

    async def _callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        pet = self.pets_by_id[interaction.data["values"][0]]
        self.stop()
        await interaction.response.defer()

        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute(
                "INSERT INTO expeditions(pet_id, player_id, start_time, duration_hrs) VALUES(?,?,?,?)",
                (pet["id"], interaction.user.id, db.now_iso(), self.duration)
            )
            await conn.commit()

        await _send_expedition_started(interaction, pet, self.duration, followup=True)
        try:
            pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
            await interaction.edit_original_response(
                embed=discord.Embed(description=f"✅ {pet_name} sent on expedition!", color=0x2ECC71),
                view=None
            )
        except Exception:
            pass


async def _send_expedition_started(
    interaction: discord.Interaction, pet: dict, duration: float, followup: bool = False
):
    pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
    emoji = ELEMENT_EMOJIS[pet["element"]]
    color = ELEMENT_COLORS[pet["element"]]
    returns_at = datetime.now(timezone.utc) + timedelta(hours=duration)
    ts = int(returns_at.timestamp())

    embed = discord.Embed(
        title="🗺️ Expedition Started!",
        description=(
            f"{emoji} **{pet_name}** has set out on a **{fmt_dur(duration)} expedition**!\n\n"
            f"Returns: <t:{ts}:R> (<t:{ts}:t>)\n\n"
            f"Your pet is **locked** from battles until it returns.\n"
            f"Exploration: **{pet['exploration']}/100**"
            + (" — Mega Stone eligible! 🌟" if pet["exploration"] >= 100 else "")
        ),
        color=color
    )
    image_path = get_pet_image(pet["element"], pet["variant"], pet["stage"])
    try:
        file = discord.File(image_path, filename="pet.png")
        embed.set_thumbnail(url="attachment://pet.png")
        if followup:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.response.send_message(embed=embed, file=file)
    except Exception:
        if followup:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)


def item_display_name_simple(item_key: str, item_type: str, element: str = None) -> str:
    if item_type == "food":
        return FOOD_ITEMS.get(item_key, {}).get("display", item_key.title())
    if item_type == "stat_item":
        return STAT_ITEMS.get(item_key, {}).get("display", item_key.replace("_", " ").title())
    if item_type == "evo_stone":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "") + " "
        name = "Uncommon Evo Stone" if item_key == "evo_stone_uncommon" else "Rare Evo Stone"
        return f"{prefix}{name}"
    if item_type == "mega_stone":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "") + " "
        return f"{prefix}Mega Stone ⭐"
    if item_type == "egg":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "") + " "
        return f"{prefix}Egg 🥚"
    return item_key.replace("_", " ").title()


# ── Cancel UI ─────────────────────────────────────────────────────────────────

class CancelConfirmView(discord.ui.View):
    def __init__(self, user_id: int, exp_id: int, pet: dict):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.exp_id = exp_id
        self.pet = pet

    @discord.ui.button(label="❌ Cancel Expedition", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.stop()
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute(
                "UPDATE expeditions SET returned=1 WHERE id=?", (self.exp_id,)
            )
            await conn.commit()
        pet_name = self.pet.get("nickname") or PET_NAMES[self.pet["element"]][self.pet["variant"]][self.pet["stage"]]
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🏠 Expedition Cancelled",
                description=f"**{pet_name}** has been recalled. No items were collected.",
                color=0xFF6B6B
            ),
            view=None
        )

    @discord.ui.button(label="Keep going", style=discord.ButtonStyle.secondary)
    async def keep(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(description="✅ Expedition continues!", color=0x2ECC71),
            view=None
        )


class CancelSelectView(discord.ui.View):
    """Shown when the player has multiple active expeditions to choose from."""

    def __init__(self, user_id: int, exp_pet_pairs: list[tuple[dict, dict]]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pairs_by_exp = {str(exp["id"]): (exp, pet) for exp, pet in exp_pet_pairs}

        options = []
        for exp, pet in exp_pet_pairs:
            name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
            emoji = ELEMENT_EMOJIS[pet["element"]]
            end = datetime.fromisoformat(exp["start_time"]) + timedelta(hours=exp["duration_hrs"])
            ts = int(end.timestamp())
            options.append(discord.SelectOption(
                label=name,
                value=str(exp["id"]),
                description=f"{fmt_dur(exp['duration_hrs'])} expedition · returns <t:{ts}:R>",
                emoji=emoji
            ))

        select = discord.ui.Select(placeholder="Choose expedition to cancel...", options=options)
        select.callback = self._selected
        self.add_item(select)

    async def _selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        exp, pet = self.pairs_by_exp[interaction.data["values"][0]]
        self.stop()

        pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        emoji = ELEMENT_EMOJIS[pet["element"]]
        end = datetime.fromisoformat(exp["start_time"]) + timedelta(hours=exp["duration_hrs"])
        ts = int(end.timestamp())

        confirm_view = CancelConfirmView(self.user_id, exp["id"], pet)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="⚠️ Cancel Expedition?",
                description=(
                    f"{emoji} **{pet_name}** is on a {fmt_dur(exp['duration_hrs'])} expedition.\n"
                    f"Was due back <t:{ts}:R>.\n\n"
                    "**No items will be collected.** Are you sure?"
                ),
                color=0xFF9800
            ),
            view=confirm_view
        )


# ── Accelerate UI ─────────────────────────────────────────────────────────────

class AccelerateView(discord.ui.View):
    def __init__(self, user_id: int, exp_pet_pairs: list[tuple[dict, dict]], acc_inv: list[dict]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pairs_by_exp = {str(exp["id"]): (exp, pet) for exp, pet in exp_pet_pairs}
        self.acc_inv = acc_inv
        self.selected_exp_id: str | None = None if len(exp_pet_pairs) > 1 else str(exp_pet_pairs[0][0]["id"])
        self.selected_acc: str | None = None

        # Expedition select (only if multiple)
        if len(exp_pet_pairs) > 1:
            exp_options = []
            for exp, pet in exp_pet_pairs:
                name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
                emoji = ELEMENT_EMOJIS[pet["element"]]
                end = datetime.fromisoformat(exp["start_time"]) + timedelta(hours=exp["duration_hrs"])
                remaining = end - datetime.now(timezone.utc)
                mins_left = max(0, int(remaining.total_seconds() // 60))
                exp_options.append(discord.SelectOption(
                    label=name,
                    value=str(exp["id"]),
                    description=f"{fmt_dur(exp['duration_hrs'])} · {mins_left}min remaining",
                    emoji=emoji
                ))
            exp_select = discord.ui.Select(placeholder="Choose expedition...", options=exp_options, row=0)
            exp_select.callback = self._exp_selected
            self.add_item(exp_select)

        # Accelerator select
        acc_options = []
        for a in acc_inv:
            info = ACCELERATORS.get(a["key"], {})
            acc_options.append(discord.SelectOption(
                label=info.get("display", a["key"]),
                value=a["key"],
                description=f"×{a['qty']} in bag · {info.get('desc', '')}",
            ))
        acc_select = discord.ui.Select(
            placeholder="Choose accelerator...", options=acc_options,
            row=1 if len(exp_pet_pairs) > 1 else 0
        )
        acc_select.callback = self._acc_selected
        self.add_item(acc_select)

    async def _exp_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.selected_exp_id = interaction.data["values"][0]
        await interaction.response.defer()

    async def _acc_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.selected_acc = interaction.data["values"][0]
        await interaction.response.defer()

    @discord.ui.button(label="⏩ Apply!", style=discord.ButtonStyle.success, row=2)
    async def apply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        if not self.selected_exp_id:
            await interaction.response.send_message("Select an expedition first.", ephemeral=True)
            return
        if not self.selected_acc:
            await interaction.response.send_message("Select an accelerator first.", ephemeral=True)
            return

        self.stop()
        exp, pet = self.pairs_by_exp[self.selected_exp_id]
        acc_info = ACCELERATORS[self.selected_acc]
        shorten_mins = acc_info["minutes"]

        async with aiosqlite.connect(db.DB_PATH) as conn:
            # Verify player still has the accelerator
            async with conn.execute(
                "SELECT quantity FROM inventory WHERE player_id=? AND item_key=? AND item_type='accelerator'",
                (interaction.user.id, self.selected_acc)
            ) as cur:
                row = await cur.fetchone()
            if not row or row[0] < 1:
                await interaction.response.edit_message(
                    embed=discord.Embed(description="❌ You no longer have that accelerator!", color=0xFF0000),
                    view=None
                )
                return

            # Move start_time backwards by shorten_mins
            old_start = datetime.fromisoformat(exp["start_time"])
            new_start = old_start - timedelta(minutes=shorten_mins)
            await conn.execute(
                "UPDATE expeditions SET start_time=? WHERE id=?",
                (new_start.isoformat(), exp["id"])
            )
            # Remove accelerator from inventory
            await db.remove_item(conn, interaction.user.id, self.selected_acc)
            await conn.commit()

        # Calculate new end time
        new_end = new_start + timedelta(hours=exp["duration_hrs"])
        now = datetime.now(timezone.utc)
        remaining = new_end - now
        pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
        emoji = ELEMENT_EMOJIS[pet["element"]]
        ts = int(new_end.timestamp())

        if remaining.total_seconds() <= 0:
            desc = f"{emoji} **{pet_name}** is now ready! Use `/collect` to grab your loot."
        else:
            mins_left = int(remaining.total_seconds() // 60)
            desc = (
                f"{emoji} **{pet_name}'s** expedition was sped up by **{shorten_mins} minutes**!\n"
                f"Now returns <t:{ts}:R> (**{mins_left}min** remaining)"
            )

        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"⏩ Accelerator Applied!",
                description=desc,
                color=0x00CED1
            ),
            view=None
        )


# ── Cog ───────────────────────────────────────────────────────────────────────

class Expedition(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="expedition", description="Send your pet on an expedition, check status, or cancel")
    @app_commands.describe(action="Duration (30m, 1h30, 4h, 6h), 'status', or 'cancel'")
    @app_commands.choices(action=[
        app_commands.Choice(name="30 minutes",     value="30m"),
        app_commands.Choice(name="1 hour 30 min",  value="1h30"),
        app_commands.Choice(name="4 hours",        value="4h"),
        app_commands.Choice(name="6 hours",        value="6h"),
        app_commands.Choice(name="Status",         value="status"),
        app_commands.Choice(name="Cancel",         value="cancel"),
        app_commands.Choice(name="Accelerate ⏩",  value="accelerate"),
    ])
    async def expedition(self, interaction: discord.Interaction, action: str = "status"):
        action = action.lower().strip()

        if action == "status":
            await self._status(interaction)
            return

        if action == "cancel":
            await self._cancel(interaction)
            return

        if action == "accelerate":
            await self._accelerate(interaction)
            return

        duration = DURATION_MAP.get(action)
        if duration is None:
            await interaction.response.send_message(
                "Choose a duration: `30m`, `1h30`, `4h`, or `6h`. Or use `status` / `cancel`.",
                ephemeral=True
            )
            return

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            all_pets = await db.get_player_pets(conn, interaction.user.id)
            async with conn.execute(
                "SELECT pet_id FROM expeditions WHERE player_id=? AND returned=0",
                (interaction.user.id,)
            ) as cur:
                on_exp_ids = {row[0] for row in await cur.fetchall()}

            eligible = [
                p for p in all_pets
                if p["stage"] > 0 and p["id"] not in on_exp_ids
            ]

        if not eligible:
            if any(p["stage"] == 0 for p in all_pets):
                await interaction.response.send_message(
                    "Your egg can't go on expeditions! Feed it first.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "All your pets are already on expedition! Use `/expedition status` to check.",
                    ephemeral=True
                )
            return

        if len(eligible) == 1:
            pet = eligible[0]
            async with aiosqlite.connect(db.DB_PATH) as conn:
                await conn.execute(
                    "INSERT INTO expeditions(pet_id, player_id, start_time, duration_hrs) VALUES(?,?,?,?)",
                    (pet["id"], interaction.user.id, db.now_iso(), duration)
                )
                await conn.commit()
            await _send_expedition_started(interaction, pet, duration)
        else:
            view = ExpeditionPetSelect(interaction.user.id, eligible, duration)
            await interaction.response.send_message(
                f"Which pet do you want to send on a **{fmt_dur(duration)} expedition**?",
                view=view, ephemeral=True
            )

    async def _status(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            async with conn.execute(
                "SELECT id, pet_id, start_time, duration_hrs FROM expeditions WHERE player_id=? AND returned=0",
                (interaction.user.id,)
            ) as cur:
                rows = await cur.fetchall()

            if not rows:
                await interaction.response.send_message(
                    "No active expeditions. Start one with `/expedition 30m` (or `1h30`, `4h`, `6h`).",
                    ephemeral=True
                )
                return

            embeds = []
            for row in rows:
                exp_id, pet_id, start_time, duration_hrs = row
                pet = await db.get_pet(conn, pet_id)
                pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
                emoji = ELEMENT_EMOJIS[pet["element"]]
                color = ELEMENT_COLORS[pet["element"]]

                start = datetime.fromisoformat(start_time)
                end = start + timedelta(hours=duration_hrs)
                now = datetime.now(timezone.utc)
                ts = int(end.timestamp())

                if (end - now).total_seconds() <= 0:
                    embed = discord.Embed(
                        title="📦 Expedition Complete!",
                        description=f"{emoji} **{pet_name}** has returned! Use `/collect` to get your loot.",
                        color=color
                    )
                else:
                    remaining = end - now
                    hrs = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)
                    embed = discord.Embed(
                        title=f"🗺️ {pet_name} is exploring...",
                        description=f"Returns <t:{ts}:R> | **{hrs}h {mins}m** remaining",
                        color=color
                    )
                embed.add_field(name="Duration", value=fmt_dur(duration_hrs), inline=True)
                embed.add_field(name="Exploration", value=f"{pet['exploration']}/100", inline=True)
                embeds.append(embed)

        await interaction.response.send_message(embeds=embeds, ephemeral=True)

    async def _accelerate(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            # Check they have at least one accelerator
            async with conn.execute(
                "SELECT item_key, quantity FROM inventory WHERE player_id=? AND item_type='accelerator' AND quantity>0",
                (interaction.user.id,)
            ) as cur:
                acc_rows = await cur.fetchall()

            if not acc_rows:
                await interaction.response.send_message(
                    "You don't have any Expedition Accelerators!\nGet them from `/fish` or `/dig`.",
                    ephemeral=True
                )
                return

            # Check active expeditions
            async with conn.execute(
                "SELECT id, pet_id, start_time, duration_hrs FROM expeditions WHERE player_id=? AND returned=0",
                (interaction.user.id,)
            ) as cur:
                rows = await cur.fetchall()

            if not rows:
                await interaction.response.send_message(
                    "No active expeditions to accelerate!", ephemeral=True
                )
                return

            exp_pet_pairs = []
            for row in rows:
                exp_id, pet_id, start_time, duration_hrs = row
                pet = await db.get_pet(conn, pet_id)
                exp_dict = {"id": exp_id, "pet_id": pet_id, "start_time": start_time, "duration_hrs": duration_hrs}
                exp_pet_pairs.append((exp_dict, pet))

        acc_inv = [{"key": r[0], "qty": r[1]} for r in acc_rows]
        view = AccelerateView(interaction.user.id, exp_pet_pairs, acc_inv)

        embed = discord.Embed(
            title="⏩ Use an Expedition Accelerator",
            description=(
                "Pick which expedition to speed up and which accelerator to use.\n"
                "The accelerator will shorten the remaining time instantly."
            ),
            color=0x00CED1
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _cancel(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            async with conn.execute(
                "SELECT id, pet_id, start_time, duration_hrs FROM expeditions WHERE player_id=? AND returned=0",
                (interaction.user.id,)
            ) as cur:
                rows = await cur.fetchall()

            if not rows:
                await interaction.response.send_message(
                    "You have no active expeditions to cancel.", ephemeral=True
                )
                return

            exp_pet_pairs = []
            for row in rows:
                exp_id, pet_id, start_time, duration_hrs = row
                pet = await db.get_pet(conn, pet_id)
                exp_dict = {"id": exp_id, "pet_id": pet_id, "start_time": start_time, "duration_hrs": duration_hrs}
                exp_pet_pairs.append((exp_dict, pet))

        if len(exp_pet_pairs) == 1:
            exp, pet = exp_pet_pairs[0]
            pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
            emoji = ELEMENT_EMOJIS[pet["element"]]
            end = datetime.fromisoformat(exp["start_time"]) + timedelta(hours=exp["duration_hrs"])
            ts = int(end.timestamp())

            view = CancelConfirmView(interaction.user.id, exp["id"], pet)
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Cancel Expedition?",
                    description=(
                        f"{emoji} **{pet_name}** is on a {fmt_dur(exp['duration_hrs'])} expedition.\n"
                        f"Was due back <t:{ts}:R>.\n\n"
                        "**No items will be collected.** Are you sure?"
                    ),
                    color=0xFF9800
                ),
                view=view,
                ephemeral=True
            )
        else:
            view = CancelSelectView(interaction.user.id, exp_pet_pairs)
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Cancel an Expedition",
                    description="You have multiple active expeditions. Choose which one to cancel.\n**No items will be collected.**",
                    color=0xFF9800
                ),
                view=view,
                ephemeral=True
            )

    @app_commands.command(name="collect", description="Collect your pet and loot after an expedition")
    async def collect(self, interaction: discord.Interaction):
        try:
         await self._collect(interaction)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            except Exception:
                await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    async def _collect(self, interaction: discord.Interaction):
        from config import PLAYER_XP_SOURCES, RARITY_EMOJIS
        now = datetime.now(timezone.utc)

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            # Fetch ALL active expeditions
            async with conn.execute(
                "SELECT * FROM expeditions WHERE player_id=? AND returned=0",
                (interaction.user.id,)
            ) as cur:
                cols = [d[0] for d in cur.description]
                all_exps = [dict(zip(cols, r)) for r in await cur.fetchall()]

            if not all_exps:
                await interaction.response.send_message(
                    "You don't have any active expeditions.", ephemeral=True
                )
                return

            # Split into ready vs still running
            ready_exps = []
            pending_msgs = []
            for ex in all_exps:
                start = datetime.fromisoformat(ex["start_time"])
                end = start + timedelta(hours=ex["duration_hrs"])
                if now >= end:
                    ready_exps.append(ex)
                else:
                    remaining = end - now
                    hrs = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)
                    pet_r = await db.get_pet(conn, ex["pet_id"])
                    pname = pet_r.get("nickname") or PET_NAMES[pet_r["element"]][pet_r["variant"]][pet_r["stage"]]
                    pending_msgs.append(f"⏳ **{pname}** — {hrs}h {mins}m left")

            if not ready_exps:
                msg = "No pets are back yet!\n" + "\n".join(pending_msgs)
                await interaction.response.send_message(msg, ephemeral=True)
                return

            # Process every ready expedition
            embeds = []
            mega_announcements = []

            for exp in ready_exps:
                pet = await db.get_pet(conn, exp["pet_id"])
                dur = exp["duration_hrs"]

                loot = generate_expedition_loot(dur, pet["element"], pet["exploration"])
                coin_total = 0
                loot_items = []
                for drop in loot:
                    if drop["item_type"] == "coins":
                        coin_total += drop["qty"]
                    else:
                        await db.add_item(
                            conn, interaction.user.id,
                            drop["item_key"], drop["item_type"],
                            drop["qty"], drop.get("element")
                        )
                        loot_items.append(drop)

                if coin_total:
                    await conn.execute(
                        "UPDATE players SET coins=coins+? WHERE user_id=?",
                        (coin_total, interaction.user.id)
                    )

                xp_gain = EXPEDITION_XP.get(dur) or EXPEDITION_XP[min(EXPEDITION_XP, key=lambda k: abs(k - dur))]
                await db.add_xp(conn, pet["id"], xp_gain)

                exp_gain = EXPLORATION_GAIN.get(dur) or EXPLORATION_GAIN[min(EXPLORATION_GAIN, key=lambda k: abs(k - dur))]
                new_exploration = min(100, pet["exploration"] + exp_gain)
                await conn.execute(
                    "UPDATE pets SET exploration=? WHERE id=?", (new_exploration, pet["id"])
                )

                scroll_drop = generate_scroll_drop(dur, pet["element"])
                if scroll_drop:
                    await db.add_item(
                        conn, interaction.user.id,
                        scroll_drop["skill_key"], "scroll", 1, scroll_drop["element"]
                    )

                armor_drop = generate_armor_drop(dur, pet["element"])
                if armor_drop:
                    await conn.execute(
                        """INSERT INTO armor_inventory
                           (player_id, name, rarity, set_name, piece_type, armor_level, armor_xp, sub_stats,
                            bonus_hp, bonus_atk, bonus_def, bonus_spd, bonus_mgk, bonus_res)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (interaction.user.id, armor_drop["name"], armor_drop["rarity"],
                         armor_drop.get("set_name"), armor_drop.get("piece_type"), 1, 0, "[]",
                         armor_drop.get("bonus_hp", 0), armor_drop.get("bonus_atk", 0),
                         armor_drop.get("bonus_def", 0), armor_drop.get("bonus_spd", 0),
                         armor_drop.get("bonus_mgk", 0), armor_drop.get("bonus_res", 0))
                    )

                dur_key = int(dur) if dur == int(dur) else dur
                p_xp = PLAYER_XP_SOURCES.get(f"expedition_{dur_key}", 10)
                await db.add_player_xp(conn, interaction.user.id, p_xp)

                await conn.execute(
                    "UPDATE expeditions SET returned=1 WHERE id=?", (exp["id"],)
                )

                pet = await db.get_pet(conn, pet["id"])
                pet_name = pet.get("nickname") or PET_NAMES[pet["element"]][pet["variant"]][pet["stage"]]
                emoji = ELEMENT_EMOJIS[pet["element"]]
                color = ELEMENT_COLORS[pet["element"]]

                embed = discord.Embed(
                    title=f"📦 {pet_name} returned!",
                    description=f"{emoji} **{fmt_dur(dur)} expedition** complete!",
                    color=color
                )

                loot_lines = []
                mega_found = False
                for drop in loot_items:
                    dname = item_display_name_simple(drop["item_key"], drop["item_type"], drop.get("element"))
                    qty = drop["qty"]
                    loot_lines.append(f"• **{dname}**" + (f" ×{qty}" if qty > 1 else ""))
                    if drop["item_type"] == "mega_stone":
                        mega_found = True
                if coin_total:
                    loot_lines.append(f"• **{coin_total} coins** 💰")
                if scroll_drop:
                    r_emoji = RARITY_EMOJIS.get(scroll_drop["rarity"], "")
                    loot_lines.append(f"• {r_emoji} **{scroll_drop['name']} Scroll** 📜")
                if armor_drop:
                    r_emoji = RARITY_EMOJIS.get(armor_drop["rarity"], "")
                    loot_lines.append(f"• {r_emoji} **{armor_drop['name']}** *(armor)*")

                embed.add_field(
                    name="🎒 Loot",
                    value="\n".join(loot_lines) if loot_lines else "Nothing this time...",
                    inline=False
                )
                embed.add_field(name="XP", value=f"+{xp_gain}", inline=True)
                embed.add_field(name="Exploration", value=f"{new_exploration}/100 (+{exp_gain})", inline=True)
                embeds.append(embed)

                if mega_found:
                    mega_announcements.append((pet_name, pet["element"], emoji))

            # Show any still-running expeditions at the bottom
            if pending_msgs:
                still_running = discord.Embed(
                    title="⏳ Still Running",
                    description="\n".join(pending_msgs),
                    color=0x95A5A6
                )
                embeds.append(still_running)

            await conn.commit()

        # Discord allows up to 10 embeds per message
        await interaction.response.send_message(embeds=embeds[:10])

        # Mega stone announcements
        for pet_name, element, emoji in mega_announcements:
            if interaction.guild:
                async with aiosqlite.connect(db.DB_PATH) as cfg_conn:
                    cfg = await db.get_guild_config(cfg_conn, interaction.guild.id)
                ch_id = cfg.get("announce_channel_id") if cfg else None
                ch = interaction.guild.get_channel(ch_id) if ch_id else interaction.channel
                if ch:
                    await ch.send(
                        f"⚡ **LEGENDARY DROP** ⚡\n"
                        f"{interaction.user.mention}'s **{pet_name}** discovered a "
                        f"**{ELEMENT_DISPLAY[element]} Mega Stone** during exploration! {emoji}"
                    )


async def setup(bot: commands.Bot):
    await bot.add_cog(Expedition(bot))
