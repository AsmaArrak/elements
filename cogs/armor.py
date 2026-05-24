import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import json

import database as db
from config import (
    PET_NAMES, ELEMENT_EMOJIS, STAGE_NAMES, RARITY_EMOJIS,
    ARMOR_SETS, ARMOR_LEVEL_XP, ARMOR_UPGRADE_COINS, ARMOR_FODDER_XP,
    ARMOR_SUBSTAT_UNLOCK_LEVELS, ARMOR_LEVEL_MULT,
)
from game.dungeon_loot import roll_substat, xp_to_next_armor_level


# ── Constants ─────────────────────────────────────────────────────────────────

SLOT_EMOJIS = {"Crown": "👑", "Plate": "🛡️", "Gauntlets": "🧤", "Greaves": "👢"}
SLOT_DESCS  = {
    "Crown":     "Head armor slot",
    "Plate":     "Body armor slot",
    "Gauntlets": "Hand armor slot",
    "Greaves":   "Leg armor slot",
}
RARITY_ORDER = ["legendary", "rare", "uncommon", "common"]

# How many armor lines to show per embed page in /armor
ARMOR_PAGE_SIZE = 8


# ── Helpers ───────────────────────────────────────────────────────────────────

def armor_bonus_line(row: dict) -> str:
    bonuses = []
    for stat in ("hp", "atk", "def", "spd", "mgk", "res"):
        val = row.get(f"bonus_{stat}", 0)
        if val:
            bonuses.append(f"+{val} {stat.upper()}")
    return " · ".join(bonuses) if bonuses else "no bonuses"


def armor_sell_price(rarity: str) -> int:
    return {"common": 150, "uncommon": 400, "rare": 1000, "legendary": 3000}.get(rarity, 150)


def get_equipped_ids(pets: list[dict]) -> set[int]:
    equipped = set()
    for pet in pets:
        for col in ("slot_crown", "slot_plate", "slot_gauntlets", "slot_greaves"):
            val = pet.get(col)
            if val:
                equipped.add(int(val))
    return equipped


def _pet_options(pets: list[dict]) -> list[discord.SelectOption]:
    opts = []
    for p in pets:
        name = p.get("nickname") or PET_NAMES[p["element"]][p["variant"]][p["stage"]]
        slots_filled = [
            emoji for emoji, col in (
                ("👑", "slot_crown"), ("🛡️", "slot_plate"),
                ("🧤", "slot_gauntlets"), ("👢", "slot_greaves")
            ) if p.get(col)
        ]
        slot_str = " ".join(slots_filled) if slots_filled else "no armor"
        opts.append(discord.SelectOption(
            label=name, value=str(p["id"]),
            description=f"Lv {p['level']} · {STAGE_NAMES[p['stage']]} · {slot_str}",
            emoji=ELEMENT_EMOJIS[p["element"]]
        ))
    return opts


# ── /armor pagination ─────────────────────────────────────────────────────────

def _build_armor_embed(armor_list: list[dict], page: int) -> tuple[discord.Embed, int]:
    """Build a paginated embed for /armor. Returns (embed, total_pages)."""
    # Build flat list of (rarity_label, line) pairs
    lines_all = []
    for ar in armor_list:
        r_emoji = RARITY_EMOJIS.get(ar["rarity"], "⚪")
        sell = armor_sell_price(ar["rarity"])
        lv = ar.get("armor_level") or 1
        line = (
            ar["rarity"],
            f"{r_emoji} **{ar['name']}** (ID:{ar['id']}) Lv{lv} — "
            f"{armor_bonus_line(ar)} | sell: {sell}🪙"
        )
        lines_all.append(line)

    total = len(lines_all)
    total_pages = max(1, (total + ARMOR_PAGE_SIZE - 1) // ARMOR_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * ARMOR_PAGE_SIZE
    chunk = lines_all[start:start + ARMOR_PAGE_SIZE]

    embed = discord.Embed(
        title="🛡️ Your Armor Collection",
        description=f"Showing **{start + 1}–{start + len(chunk)}** of **{total}** pieces",
        color=0x7B68EE
    )

    # Group this page's lines by rarity for nicer display
    by_rarity: dict[str, list[str]] = {}
    for rarity, line in chunk:
        by_rarity.setdefault(rarity, []).append(line)

    for rarity in RARITY_ORDER:
        if rarity in by_rarity:
            embed.add_field(
                name=rarity.title(),
                value="\n".join(by_rarity[rarity]),
                inline=False
            )

    embed.set_footer(text=f"Page {page + 1}/{total_pages} · /equip to equip · /sellarmor <id> to sell")
    return embed, total_pages


class ArmorPageView(discord.ui.View):
    def __init__(self, user_id: int, armor_list: list[dict], page: int = 0):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.armor_list = armor_list
        self.page = page
        _, self.total_pages = _build_armor_embed(armor_list, page)
        self._refresh_buttons()

    def _refresh_buttons(self):
        self.clear_items()
        prev_btn = discord.ui.Button(
            label="◀ Prev", style=discord.ButtonStyle.secondary,
            disabled=(self.page == 0), row=0
        )
        prev_btn.callback = self._prev_cb
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(
            label="Next ▶", style=discord.ButtonStyle.secondary,
            disabled=(self.page >= self.total_pages - 1), row=0
        )
        next_btn.callback = self._next_cb
        self.add_item(next_btn)

    async def _prev_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.page -= 1
        self._refresh_buttons()
        embed, _ = _build_armor_embed(self.armor_list, self.page)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _next_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.page += 1
        self._refresh_buttons()
        embed, _ = _build_armor_embed(self.armor_list, self.page)
        await interaction.response.edit_message(embed=embed, view=self)


# ── /equip two-phase view ─────────────────────────────────────────────────────

class EquipView(discord.ui.View):
    """
    Phase 1: pet picker (if multiple pets) + slot-type picker.
    Phase 2 (after slot chosen): pet picker + slot picker + filtered armor + confirm.
    """

    def __init__(self, user_id: int, pets: list[dict], armor_list: list[dict]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pets = pets
        self.armor_list = armor_list
        self.selected_pet = pets[0] if len(pets) == 1 else None
        self.selected_armor_id: int | None = None
        self.selected_piece_type: str | None = None
        self._multi_pet = len(pets) > 1
        self._phase1()

    # ── builders ─────────────────────────────────────────────────────────────

    def _phase1(self):
        self.clear_items()
        row = 0
        if self._multi_pet:
            ps = discord.ui.Select(placeholder="1️⃣ Choose a pet...", options=_pet_options(self.pets), row=row)
            ps.callback = self._pet_cb
            self.add_item(ps)
            row += 1

        slot_opts = [
            discord.SelectOption(
                label=f"{SLOT_EMOJIS[s]} {s}", value=s,
                description=SLOT_DESCS[s]
            )
            for s in ("Crown", "Plate", "Gauntlets", "Greaves")
        ]
        step = "2️⃣" if self._multi_pet else "1️⃣"
        ss = discord.ui.Select(placeholder=f"{step} Choose armor slot...", options=slot_opts, row=row)
        ss.callback = self._slot_cb
        self.add_item(ss)

    def _phase2(self):
        self.clear_items()
        row = 0
        equipped_ids = get_equipped_ids(self.pets)

        if self._multi_pet:
            ps = discord.ui.Select(placeholder="1️⃣ Choose a pet...", options=_pet_options(self.pets), row=row)
            ps.callback = self._pet_cb
            self.add_item(ps)
            row += 1

        # Slot picker (kept so user can switch slot)
        slot_opts = [
            discord.SelectOption(
                label=f"{SLOT_EMOJIS[s]} {s}", value=s,
                description=SLOT_DESCS[s],
                default=(s == self.selected_piece_type)
            )
            for s in ("Crown", "Plate", "Gauntlets", "Greaves")
        ]
        step_slot = "2️⃣" if self._multi_pet else "1️⃣"
        ss = discord.ui.Select(
            placeholder=f"{step_slot} Slot: {SLOT_EMOJIS.get(self.selected_piece_type,'')} {self.selected_piece_type}",
            options=slot_opts, row=row
        )
        ss.callback = self._slot_cb
        self.add_item(ss)
        row += 1

        # Filtered armor list
        filtered = [a for a in self.armor_list if a.get("piece_type") == self.selected_piece_type]
        armor_opts = []
        for ar in filtered[:25]:
            r_emoji = RARITY_EMOJIS.get(ar["rarity"], "⚪")
            is_eq = ar["id"] in equipped_ids
            equip_tag = "✅ " if is_eq else ""
            lv = ar.get("armor_level") or 1
            desc = f"{equip_tag}{ar['rarity'].title()} Lv{lv} · {armor_bonus_line(ar)}"
            armor_opts.append(discord.SelectOption(
                label=ar["name"], value=str(ar["id"]),
                description=desc[:100], emoji=r_emoji
            ))

        step_arm = str(int(step_slot[0]) + 1) + "️⃣"
        arm_sel = discord.ui.Select(
            placeholder=f"{step_arm} Choose {self.selected_piece_type}...",
            options=armor_opts, row=row
        )
        arm_sel.callback = self._armor_cb
        self.add_item(arm_sel)
        row += 1

        confirm = discord.ui.Button(label="✅ Equip", style=discord.ButtonStyle.success, row=row)
        confirm.callback = self._confirm_cb
        self.add_item(confirm)

    # ── callbacks ─────────────────────────────────────────────────────────────

    async def _pet_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        pid = int(interaction.data["values"][0])
        self.selected_pet = next(p for p in self.pets if p["id"] == pid)
        await interaction.response.defer()

    async def _slot_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.selected_piece_type = interaction.data["values"][0]
        self.selected_armor_id = None

        filtered = [a for a in self.armor_list if a.get("piece_type") == self.selected_piece_type]
        if not filtered:
            await interaction.response.send_message(
                f"You have no **{self.selected_piece_type}** pieces! "
                "Farm dungeons or go on expeditions to find some.",
                ephemeral=True
            )
            return

        self._phase2()
        emoji = SLOT_EMOJIS.get(self.selected_piece_type, "")
        await interaction.response.edit_message(
            content=f"Choose a **{emoji} {self.selected_piece_type}** to equip:",
            view=self
        )

    async def _armor_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.selected_armor_id = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def _confirm_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        if not self.selected_pet:
            await interaction.response.send_message("Select a pet first.", ephemeral=True)
            return
        if not self.selected_armor_id:
            await interaction.response.send_message("Select an armor piece first.", ephemeral=True)
            return

        self.stop()
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT name, rarity, piece_type FROM armor_inventory WHERE id=?",
                (self.selected_armor_id,)
            ) as cur:
                ar = await cur.fetchone()
            if not ar:
                await interaction.response.send_message("Armor not found.", ephemeral=True)
                return
            piece_type = ar[2] or ""
            slot_col = db.ARMOR_SLOT_COLS.get(piece_type)
            if not slot_col:
                await interaction.response.send_message(
                    f"Unknown piece type '{piece_type}'. Cannot equip.", ephemeral=True
                )
                return
            await conn.execute(
                f"UPDATE pets SET {slot_col}=? WHERE id=?",
                (self.selected_armor_id, self.selected_pet["id"])
            )
            await conn.commit()

        pet_name = (
            self.selected_pet.get("nickname")
            or PET_NAMES[self.selected_pet["element"]][self.selected_pet["variant"]][self.selected_pet["stage"]]
        )
        r_emoji = RARITY_EMOJIS.get(ar[1], "")
        slot_emoji = SLOT_EMOJIS.get(piece_type, "")
        await interaction.response.edit_message(
            embed=discord.Embed(
                description=f"✅ **{pet_name}** equipped {r_emoji} **{ar[0]}** ({slot_emoji} {piece_type} slot)!",
                color=0x2ECC71
            ),
            view=None
        )


# ── /upgradearmor two-phase view ──────────────────────────────────────────────

class UpgradeArmorView(discord.ui.View):
    """
    Phase 1: rarity filter for target + rarity filter for fodder.
    Phase 2: filtered target select + filtered fodder select + upgrade button.
    """

    def __init__(self, user_id: int, upgradeable: list[dict], all_armor: list[dict],
                 equipped_ids: set[int] | None = None):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.upgradeable = upgradeable
        self.all_armor = all_armor
        self.equipped_ids: set[int] = equipped_ids or set()
        self.target_id: int | None = None
        self.fodder_ids: list[int] = []
        self.target_rarity: str | None = None
        self.fodder_rarity: str | None = None
        self._phase1()

    # ── builders ─────────────────────────────────────────────────────────────

    def _rarity_opts(self, pool: list[dict], label_prefix: str) -> list[discord.SelectOption]:
        """Build rarity filter options for only rarities present in pool."""
        present = {a["rarity"] for a in pool}
        opts = []
        for r in RARITY_ORDER:
            if r in present:
                count = sum(1 for a in pool if a["rarity"] == r)
                opts.append(discord.SelectOption(
                    label=f"{r.title()} ({count})",
                    value=r,
                    description=f"Show {r} {label_prefix} pieces",
                    emoji=RARITY_EMOJIS.get(r, "⚪")
                ))
        return opts

    def _phase1(self):
        self.clear_items()

        t_opts = self._rarity_opts(self.upgradeable, "upgradeable")
        if not t_opts:
            return
        t_sel = discord.ui.Select(
            placeholder="1️⃣ Target rarity (piece to upgrade)...",
            options=t_opts, row=0
        )
        t_sel.callback = self._target_rarity_cb
        self.add_item(t_sel)

        f_opts = self._rarity_opts(self.all_armor, "fodder")
        if not f_opts:
            return
        f_sel = discord.ui.Select(
            placeholder="2️⃣ Fodder rarity (pieces to sacrifice)...",
            options=f_opts, row=1
        )
        f_sel.callback = self._fodder_rarity_cb
        self.add_item(f_sel)

        go_btn = discord.ui.Button(
            label="Show Pieces →", style=discord.ButtonStyle.primary, row=2
        )
        go_btn.callback = self._go_cb
        self.add_item(go_btn)

    def _phase2(self):
        self.clear_items()

        # Target select
        t_pool = [a for a in self.upgradeable if a["rarity"] == self.target_rarity]
        t_opts = []
        for a in t_pool[:25]:
            r_emoji = RARITY_EMOJIS.get(a["rarity"], "⚪")
            lv = a.get("armor_level") or 1
            is_eq = a["id"] in self.equipped_ids
            equip_tag = "✅ " if is_eq else ""
            t_opts.append(discord.SelectOption(
                label=f"{a['name']} (Lv {lv})",
                value=str(a["id"]),
                description=f"{equip_tag}{a['rarity'].title()} · {armor_bonus_line(a)[:40]}"[:100],
                emoji=r_emoji
            ))
        t_sel = discord.ui.Select(placeholder="3️⃣ Piece to UPGRADE...", options=t_opts, row=0)
        t_sel.callback = self._target_cb
        self.add_item(t_sel)

        # Fodder select — filter by chosen rarity, sort common-first within that rarity
        f_pool = [a for a in self.all_armor if a["rarity"] == self.fodder_rarity]
        f_opts = []
        for a in f_pool[:25]:
            r_emoji = RARITY_EMOJIS.get(a["rarity"], "⚪")
            lv = a.get("armor_level") or 1
            xp_val = ARMOR_FODDER_XP.get(a["rarity"], 100)
            is_eq = a["id"] in self.equipped_ids
            equip_tag = "✅ " if is_eq else ""
            f_opts.append(discord.SelectOption(
                label=f"{a['name']} (Lv {lv})",
                value=str(a["id"]),
                description=f"{equip_tag}Gives {xp_val} XP · {a['rarity'].title()}"[:100],
                emoji=r_emoji
            ))
        f_sel = discord.ui.Select(
            placeholder="4️⃣ Fodder to SACRIFICE (up to 4)...",
            options=f_opts, row=1,
            min_values=1, max_values=min(4, len(f_opts))
        )
        f_sel.callback = self._fodder_cb
        self.add_item(f_sel)

        # Back button + upgrade button
        back_btn = discord.ui.Button(label="◀ Back", style=discord.ButtonStyle.secondary, row=2)
        back_btn.callback = self._back_cb
        self.add_item(back_btn)

        upg_btn = discord.ui.Button(label="🔨 Upgrade", style=discord.ButtonStyle.success, row=2)
        upg_btn.callback = self._upgrade_cb
        self.add_item(upg_btn)

    # ── callbacks ─────────────────────────────────────────────────────────────

    async def _target_rarity_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.target_rarity = interaction.data["values"][0]
        self.target_id = None
        await interaction.response.defer()

    async def _fodder_rarity_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.fodder_rarity = interaction.data["values"][0]
        self.fodder_ids = []
        await interaction.response.defer()

    async def _go_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        if not self.target_rarity:
            await interaction.response.send_message("Choose a target rarity first.", ephemeral=True)
            return
        if not self.fodder_rarity:
            await interaction.response.send_message("Choose a fodder rarity first.", ephemeral=True)
            return
        self._phase2()
        await interaction.response.edit_message(
            content=(
                f"**🔨 Armor Upgrade** — Target: `{self.target_rarity.title()}` · "
                f"Fodder: `{self.fodder_rarity.title()}`\n"
                "Select the piece to upgrade and the pieces to sacrifice:"
            ),
            view=self
        )

    async def _back_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.target_id = None
        self.fodder_ids = []
        self._phase1()
        await interaction.response.edit_message(
            content="**🔨 Armor Upgrade**\nFilter by rarity to find your pieces:",
            view=self
        )

    async def _target_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.target_id = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def _fodder_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        self.fodder_ids = [int(v) for v in interaction.data["values"]]
        await interaction.response.defer()

    async def _upgrade_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu!", ephemeral=True)
            return
        if not self.target_id:
            await interaction.response.send_message("Select a piece to upgrade first.", ephemeral=True)
            return
        if not self.fodder_ids:
            await interaction.response.send_message("Select at least one fodder piece.", ephemeral=True)
            return
        if self.target_id in self.fodder_ids:
            await interaction.response.send_message(
                "You can't use the upgrade target as fodder!", ephemeral=True
            )
            return

        # Warn if any chosen fodder is currently equipped
        equipped_fodder = [fid for fid in self.fodder_ids if fid in self.equipped_ids]
        if equipped_fodder:
            piece_word = "piece" if len(equipped_fodder) == 1 else "pieces"
            await interaction.response.send_message(
                f"⚠️ **{len(equipped_fodder)} equipped {piece_word}** selected as fodder!\n"
                "Sacrificing equipped armor will unequip it from your pet. "
                "Unequip it first with `/equip` if you didn't mean to, or press **Upgrade** again to confirm.",
                ephemeral=True
            )
            self.fodder_ids = [fid for fid in self.fodder_ids if fid not in self.equipped_ids]
            return

        self.stop()
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE id=? AND player_id=?",
                (self.target_id, self.user_id)
            ) as cur:
                cols = [d[0] for d in cur.description]
                row = await cur.fetchone()
            if not row:
                await interaction.response.send_message("Target armor not found.", ephemeral=True)
                return
            target = dict(zip(cols, row))
            current_level = target.get("armor_level") or 1
            if current_level >= 15:
                await interaction.response.send_message(
                    "This piece is already at max level (15)!", ephemeral=True
                )
                return

            # Calculate XP from fodder
            total_xp = 0
            for fid in self.fodder_ids:
                async with conn.execute(
                    "SELECT rarity, armor_level FROM armor_inventory WHERE id=? AND player_id=?",
                    (fid, self.user_id)
                ) as cur:
                    frow = await cur.fetchone()
                if frow:
                    base_xp = ARMOR_FODDER_XP.get(frow[0], 100)
                    fodder_lv = frow[1] or 1
                    total_xp += int(base_xp * (1 + (fodder_lv - 1) * 0.1))

            player = await db.get_player(conn, self.user_id)
            player_coins = player.get("coins") or 0
            current_armor_xp = target.get("armor_xp") or 0
            armor_xp = current_armor_xp + total_xp

            # Process level-ups
            new_level = current_level
            total_coins = 0
            sub_stats = json.loads(target.get("sub_stats") or "[]")
            new_substats_gained = []

            while new_level < 15:
                needed = xp_to_next_armor_level(new_level)
                if needed is None or armor_xp < needed:
                    break
                coin_cost = ARMOR_UPGRADE_COINS.get(new_level, 500)
                if player_coins < total_coins + coin_cost:
                    break
                total_coins += coin_cost
                armor_xp -= needed
                new_level += 1
                if new_level in ARMOR_SUBSTAT_UNLOCK_LEVELS:
                    new_ss = roll_substat({**target, "sub_stats": json.dumps(sub_stats)})
                    if new_ss:
                        sub_stats.append(new_ss)
                        new_substats_gained.append(new_ss)

            if total_coins > player_coins:
                await interaction.response.send_message(
                    f"❌ Not enough coins! Need **{total_coins:,}**, you have **{player_coins:,}**.",
                    ephemeral=True
                )
                return

            if new_level == current_level:
                xp_needed_now = xp_to_next_armor_level(new_level)
                if xp_needed_now is not None and armor_xp >= xp_needed_now:
                    coin_cost_needed = ARMOR_UPGRADE_COINS.get(new_level, 500)
                    await interaction.response.send_message(
                        f"❌ You have enough XP to level up but need **{coin_cost_needed:,} coins** to do it! "
                        f"You only have **{player_coins:,} coins**.",
                        ephemeral=True
                    )
                    return
                await conn.execute(
                    "UPDATE armor_inventory SET armor_xp=? WHERE id=?",
                    (armor_xp, self.target_id)
                )
            else:
                await conn.execute(
                    "UPDATE players SET coins=coins-? WHERE user_id=?",
                    (total_coins, self.user_id)
                )
                await conn.execute(
                    "UPDATE armor_inventory SET armor_level=?, armor_xp=?, sub_stats=? WHERE id=?",
                    (new_level, armor_xp, json.dumps(sub_stats), self.target_id)
                )

            # Delete fodder
            for fid in self.fodder_ids:
                await db.unequip_armor_id(conn, fid, self.user_id)
                await conn.execute(
                    "DELETE FROM armor_inventory WHERE id=? AND player_id=?",
                    (fid, self.user_id)
                )
            await conn.commit()

        r_emoji = RARITY_EMOJIS.get(target["rarity"], "⚪")
        embed = discord.Embed(title="🔨 Armor Upgraded!", color=0xF39C12)

        if new_level > current_level:
            piece_value = f"Level **{current_level}** → **{new_level}**"
        else:
            xp_needed = xp_to_next_armor_level(new_level) or 0
            piece_value = (
                f"Level **{current_level}** — XP stored (+{total_xp} XP)\n"
                f"Progress: **{armor_xp}/{xp_needed} XP** to level {current_level + 1}"
            )
        embed.add_field(name=f"{r_emoji} {target['name']}", value=piece_value, inline=False)

        if new_substats_gained:
            ss_lines = [f"✨ **+{ss['value']} {ss['stat'].upper()}** unlocked!" for ss in new_substats_gained]
            embed.add_field(name="New Substats!", value="\n".join(ss_lines), inline=False)
        if total_coins:
            embed.add_field(name="Coins Spent", value=f"{total_coins:,} 🪙", inline=True)
        embed.add_field(name="Fodder Used", value=f"{len(self.fodder_ids)} piece(s)", inline=True)
        embed.set_footer(text="Substats unlock at levels 3, 6, 9, 12 · Max level 15")

        await interaction.response.edit_message(embed=embed, view=None)


# ── Cog ───────────────────────────────────────────────────────────────────────

class Armor(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="equip", description="Equip armor to one of your pets")
    async def equip(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            pets = await db.get_player_pets(conn, interaction.user.id)
            pets = [p for p in pets if p["stage"] > 0]
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE player_id=? ORDER BY rarity DESC, name",
                (interaction.user.id,)
            ) as cur:
                cols = [d[0] for d in cur.description]
                armor_list = [dict(zip(cols, r)) for r in await cur.fetchall()]

        if not pets:
            await interaction.response.send_message(
                "You need a hatched pet to equip armor.", ephemeral=True
            )
            return
        if not armor_list:
            await interaction.response.send_message(
                "You have no armor! Go on expeditions or farm dungeons to find some.", ephemeral=True
            )
            return

        view = EquipView(interaction.user.id, pets, armor_list)
        await interaction.response.send_message(
            "Choose an armor **slot**, then pick the piece to equip:", view=view, ephemeral=True
        )

    @app_commands.command(name="armor", description="View your armor collection")
    async def armor_cmd(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE player_id=? ORDER BY rarity DESC, name",
                (interaction.user.id,)
            ) as cur:
                cols = [d[0] for d in cur.description]
                armor_list = [dict(zip(cols, r)) for r in await cur.fetchall()]

        if not armor_list:
            await interaction.response.send_message(
                "You have no armor yet. Farm dungeons or go on expeditions to find some!", ephemeral=True
            )
            return

        embed, total_pages = _build_armor_embed(armor_list, 0)
        view = ArmorPageView(interaction.user.id, armor_list, 0) if total_pages > 1 else None
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="sellarmor", description="Sell a piece of armor for coins")
    @app_commands.describe(armor_id="The armor ID shown in /armor")
    async def sellarmor(self, interaction: discord.Interaction, armor_id: int):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE id=? AND player_id=?",
                (armor_id, interaction.user.id)
            ) as cur:
                cols = [d[0] for d in cur.description]
                row = await cur.fetchone()

            if not row:
                await interaction.response.send_message(
                    "Armor not found in your collection.", ephemeral=True
                )
                return
            ar = dict(zip(cols, row))

            await db.unequip_armor_id(conn, armor_id, interaction.user.id)
            await conn.execute("DELETE FROM armor_inventory WHERE id=?", (armor_id,))
            price = armor_sell_price(ar["rarity"])
            await conn.execute(
                "UPDATE players SET coins=coins+? WHERE user_id=?", (price, interaction.user.id)
            )
            await conn.commit()

        r_emoji = RARITY_EMOJIS.get(ar["rarity"], "")
        await interaction.response.send_message(
            f"Sold {r_emoji} **{ar['name']}** for **{price} coins**! 💰"
        )

    @app_commands.command(name="upgradearmor", description="Use armor pieces as fodder to upgrade another piece")
    async def upgradearmor(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            async with conn.execute(
                "SELECT * FROM armor_inventory WHERE player_id=? ORDER BY rarity DESC, armor_level DESC",
                (interaction.user.id,)
            ) as cur:
                cols = [d[0] for d in cur.description]
                armor_list = [dict(zip(cols, r)) for r in await cur.fetchall()]
            pets = await db.get_player_pets(conn, interaction.user.id)

        equipped_ids = get_equipped_ids(pets)
        upgradeable = [a for a in armor_list if (a.get("armor_level") or 1) < 15 and a.get("set_name")]
        fodder_pool = [a for a in armor_list if a.get("set_name")]

        if not upgradeable:
            await interaction.response.send_message(
                "No upgradeable armor! Farm dungeons or go on expeditions to get set armor pieces.",
                ephemeral=True
            )
            return
        if len(fodder_pool) < 2:
            await interaction.response.send_message(
                "You need at least 2 armor pieces — one to upgrade and one as fodder.",
                ephemeral=True
            )
            return

        view = UpgradeArmorView(interaction.user.id, upgradeable, fodder_pool, equipped_ids)
        await interaction.response.send_message(
            "**🔨 Armor Upgrade**\nFilter by rarity to find your pieces:",
            view=view, ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Armor(bot))
