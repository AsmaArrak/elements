import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import random
from datetime import datetime, timezone, timedelta

import database as db
from config import (
    ELEMENT_DISPLAY, ELEMENT_EMOJIS, FOOD_ITEMS, SHOP_ITEMS, STAT_ITEMS,
    DAILY_LOGIN_XP, DAILY_LOGIN_COINS
)

GAMBLE_MIN = 50
GAMBLE_MAX = 10_000

# In-memory pending trades: trade_id -> TradeState
pending_trades: dict[int, dict] = {}


def item_label(item_key: str, item_type: str, element: str = None, qty: int = 1) -> str:
    if item_type == "food":
        return f"{FOOD_ITEMS.get(item_key, {}).get('display', item_key)} ×{qty}"
    if item_type == "stat_item":
        return f"{STAT_ITEMS.get(item_key, {}).get('display', item_key)} ×{qty}"
    if item_type == "evo_stone":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "")
        name = "Uncommon Evo Stone" if item_key == "evo_stone_uncommon" else "Rare Evo Stone"
        return f"{prefix} {name} ×{qty}"
    if item_type == "mega_stone":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "")
        return f"{prefix} Mega Stone ⭐ ×{qty}"
    if item_type == "egg":
        prefix = ELEMENT_DISPLAY.get(element, element.title() if element else "")
        return f"{prefix} Egg 🥚 ×{qty}"
    if item_type == "coins":
        return f"{qty} Coins 💰"
    return f"{item_key} ×{qty}"


class TradeOfferView(discord.ui.View):
    def __init__(self, trade_id: int, sender: discord.Member, receiver: discord.Member,
                 offered: list[dict], requested: list[dict]):
        super().__init__(timeout=120)
        self.trade_id = trade_id
        self.sender = sender
        self.receiver = receiver
        self.offered = offered
        self.requested = requested

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.receiver.id:
            await interaction.response.send_message("This trade isn't for you!", ephemeral=True)
            return
        self.stop()

        async with aiosqlite.connect(db.DB_PATH) as conn:
            # Verify sender still has offered items
            for item in self.offered:
                if not await db.has_item(conn, self.sender.id, item["item_key"],
                                          item.get("qty", 1), item.get("element")):
                    await interaction.response.edit_message(
                        content="❌ Trade failed — sender no longer has the offered items.",
                        embed=None, view=None
                    )
                    return
            # Verify receiver has requested items
            for item in self.requested:
                if not await db.has_item(conn, self.receiver.id, item["item_key"],
                                          item.get("qty", 1), item.get("element")):
                    await interaction.response.edit_message(
                        content="❌ Trade failed — you don't have the requested items.",
                        embed=None, view=None
                    )
                    return

            # Execute trade
            for item in self.offered:
                await db.remove_item(conn, self.sender.id, item["item_key"],
                                     item.get("qty", 1), item.get("element"))
                await db.add_item(conn, self.receiver.id, item["item_key"], item["item_type"],
                                  item.get("qty", 1), item.get("element"))
            for item in self.requested:
                await db.remove_item(conn, self.receiver.id, item["item_key"],
                                     item.get("qty", 1), item.get("element"))
                await db.add_item(conn, self.sender.id, item["item_key"], item["item_type"],
                                  item.get("qty", 1), item.get("element"))
            await conn.commit()

        await interaction.response.edit_message(
            content=f"✅ Trade complete! {self.sender.mention} and {self.receiver.mention} exchanged items.",
            embed=None, view=None
        )

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.sender.id, self.receiver.id):
            await interaction.response.send_message("Not your trade!", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(
            content="❌ Trade declined.", embed=None, view=None
        )


# ── Shop UI ───────────────────────────────────────────────────────────────────

class CustomAmountModal(discord.ui.Modal, title="Custom Amount"):
    amount = discord.ui.TextInput(
        label="How many to buy? (1–99)",
        placeholder="e.g. 15",
        min_length=1,
        max_length=2,
    )

    def __init__(self, qty_view: "QuantityView"):
        super().__init__()
        self.qty_view = qty_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.amount.value)
            if qty < 1 or qty > 99:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Enter a number between 1 and 99.", ephemeral=True)
            return
        await self.qty_view.do_purchase(interaction, qty)


class QuantityView(discord.ui.View):
    def __init__(self, user_id: int, item_key: str, price: int, display: str, item_type: str, coins: int):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.item_key = item_key
        self.price = price
        self.display = display
        self.item_type = item_type

        for qty in [1, 5, 10, 25, 50]:
            total = qty * price
            affordable = total <= coins

            def make_cb(q):
                async def cb(inter: discord.Interaction):
                    await self.do_purchase(inter, q)
                return cb

            btn = discord.ui.Button(
                label=f"×{qty}  ({total:,}c)",
                style=discord.ButtonStyle.success if affordable else discord.ButtonStyle.secondary,
                disabled=not affordable,
                row=0,
            )
            btn.callback = make_cb(qty)
            self.add_item(btn)

    @discord.ui.button(label="✏️ Custom", style=discord.ButtonStyle.secondary, row=1)
    async def custom_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your shop!", ephemeral=True)
            return
        await interaction.response.send_modal(CustomAmountModal(self))

    async def do_purchase(self, interaction: discord.Interaction, qty: int):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your shop!", ephemeral=True)
            return
        total = qty * self.price
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, self.user_id)
            if not player or player["coins"] < total:
                have = player["coins"] if player else 0
                await interaction.response.edit_message(
                    content=f"❌ Not enough coins! Need **{total:,}**, you have **{have:,}**.",
                    view=None,
                )
                return
            await conn.execute(
                "UPDATE players SET coins=coins-? WHERE user_id=?", (total, self.user_id)
            )
            await db.add_item(conn, self.user_id, self.item_key, self.item_type, qty)
            await conn.commit()
            new_bal = player["coins"] - total

        await interaction.response.edit_message(
            content=(
                f"✅ Bought **×{qty} {self.display}** for **{total:,} coins**!\n"
                f"💰 Balance: **{new_bal:,} coins**"
            ),
            view=None,
        )


class ShopView(discord.ui.View):
    def __init__(self, user_id: int, coins: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.coins = coins

        options = []
        for key, data in SHOP_ITEMS.items():
            food = FOOD_ITEMS.get(key, {})
            display = food.get("display", key.title())
            options.append(discord.SelectOption(
                label=display,
                value=key,
                description=f"{data['price']} coins · {data['description']}",
            ))

        self.item_select = discord.ui.Select(
            placeholder="🛒 Choose an item to buy...",
            options=options,
        )
        self.item_select.callback = self.on_item_select
        self.add_item(self.item_select)

    async def on_item_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your shop!", ephemeral=True)
            return
        item_key = self.item_select.values[0]
        data = SHOP_ITEMS[item_key]
        food = FOOD_ITEMS.get(item_key, {})
        display = food.get("display", item_key.title())
        item_type = data.get("type", "food")
        price = data["price"]

        qty_view = QuantityView(self.user_id, item_key, price, display, item_type, self.coins)
        await interaction.response.send_message(
            f"**{display}** — {price:,} coins each · You have **{self.coins:,} coins**\nHow many?",
            view=qty_view,
            ephemeral=True,
        )


class CoinflipView(discord.ui.View):
    """Two-button coin flip — user picks Heads or Tails, outcome is 50/50."""

    def __init__(self, user_id: int, bet: int):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.bet = bet

    async def _resolve(self, interaction: discord.Interaction, player_choice: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your flip!", ephemeral=True)
            return

        self.stop()

        result = random.choice(["heads", "tails"])
        won = player_choice == result
        coin_emoji = "🪙" if result == "heads" else "🔄"

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.edit_message(
                    content="❌ Account not found.", embed=None, view=None
                )
                return

            current_coins = player.get("coins") or 0

            if won:
                winnings = self.bet * 2
                await conn.execute(
                    "UPDATE players SET coins=coins+? WHERE user_id=?",
                    (winnings, interaction.user.id)
                )
                await conn.commit()
                new_bal = current_coins + winnings
                embed = discord.Embed(
                    title="🎉 You won!",
                    description=(
                        f"The coin landed on **{result.title()}** {coin_emoji}\n"
                        f"You picked **{player_choice.title()}** — correct!\n\n"
                        f"**+{winnings:,} coins** 💰"
                    ),
                    color=0x2ECC71
                )
            else:
                loss = min(self.bet, current_coins)
                await conn.execute(
                    "UPDATE players SET coins=coins-? WHERE user_id=?",
                    (loss, interaction.user.id)
                )
                await conn.commit()
                new_bal = current_coins - loss
                embed = discord.Embed(
                    title="😬 You lost!",
                    description=(
                        f"The coin landed on **{result.title()}** {coin_emoji}\n"
                        f"You picked **{player_choice.title()}** — wrong!\n\n"
                        f"**−{loss:,} coins** 💸"
                    ),
                    color=0xE74C3C
                )

        embed.set_footer(text=f"New balance: {new_bal:,} coins")
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="🪙 Heads", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, "heads")

    @discord.ui.button(label="🔄 Tails", style=discord.ButtonStyle.secondary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve(interaction, "tails")


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Check your coin balance")
    async def balance(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
        if not player:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"💰 **{interaction.user.display_name}** has **{player['coins']} coins**."
        )

    @app_commands.command(name="shop", description="Browse the item shop")
    async def shop(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
        coins = player["coins"] if player else 0

        embed = discord.Embed(title="🛒 Item Shop", color=0xF1C40F)
        lines = []
        for key, data in SHOP_ITEMS.items():
            food_data = FOOD_ITEMS.get(key, {})
            display = food_data.get("display", key.title())
            lines.append(f"**{display}** — {data['price']:,} coins | {data['description']}")
        embed.add_field(name="🍖 Food", value="\n".join(lines), inline=False)
        embed.set_footer(text="Rare items (cake, honey, dragonfruit…) only drop from the world")
        embed.set_footer(text=f"💰 Your balance: {coins:,} coins · Select an item below to buy in bulk")

        view = ShopView(interaction.user.id, coins)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="buy", description="Buy an item from the shop")
    @app_commands.describe(
        item="Item name (e.g. apple, bread, fish)",
        quantity="How many to buy (default 1)"
    )
    async def buy(self, interaction: discord.Interaction, item: str, quantity: int = 1):
        item = item.lower().strip()
        if quantity < 1:
            await interaction.response.send_message("Quantity must be at least 1.", ephemeral=True)
            return
        if quantity > 99:
            await interaction.response.send_message("You can buy at most 99 at a time.", ephemeral=True)
            return
        if item not in SHOP_ITEMS:
            await interaction.response.send_message(
                f"**{item}** isn't sold here. Use `/shop` to see what's available.", ephemeral=True
            )
            return
        price_each = SHOP_ITEMS[item]["price"]
        total = price_each * quantity
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            if player["coins"] < total:
                await interaction.response.send_message(
                    f"Not enough coins! You have **{player['coins']}**, need **{total}** ({quantity}× {price_each}).",
                    ephemeral=True
                )
                return
            await conn.execute(
                "UPDATE players SET coins=coins-? WHERE user_id=?", (total, interaction.user.id)
            )
            await db.add_item(conn, interaction.user.id, item, "food", quantity)
            await conn.commit()
            new_bal = player["coins"] - total

        display = FOOD_ITEMS[item]["display"]
        qty_str = f"×{quantity} " if quantity > 1 else ""
        await interaction.response.send_message(
            f"🛒 Bought **{qty_str}{display}** for **{total} coins**! Balance: **{new_bal} coins**."
        )

    @app_commands.command(name="sell", description="Sell an item to the shop for coins")
    @app_commands.describe(
        item="Item to sell (food name or stat item key)",
        qty="How many to sell (default 1)"
    )
    async def sell(self, interaction: discord.Interaction, item: str, qty: int = 1):
        item = item.lower().strip()
        if qty < 1:
            await interaction.response.send_message("Quantity must be at least 1.", ephemeral=True)
            return

        # Determine sell price
        sell_prices: dict[str, int] = {}
        for k, v in SHOP_ITEMS.items():
            sell_prices[k] = v["price"] // 2
        # Food not in shop sells for less
        for k in FOOD_ITEMS:
            if k not in sell_prices:
                sell_prices[k] = 10
        for k in STAT_ITEMS:
            sell_prices[k] = 80

        if item not in sell_prices:
            await interaction.response.send_message(
                f"**{item}** can't be sold here.", ephemeral=True
            )
            return

        price_each = sell_prices[item]
        total = price_each * qty

        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            # Determine item type
            item_type = "food" if item in FOOD_ITEMS else "stat_item"
            if not await db.has_item(conn, interaction.user.id, item, qty):
                await interaction.response.send_message(
                    f"You don't have {qty}× **{item}**.", ephemeral=True
                )
                return
            await db.remove_item(conn, interaction.user.id, item, qty)
            await conn.execute(
                "UPDATE players SET coins=coins+? WHERE user_id=?", (total, interaction.user.id)
            )
            await conn.commit()
            new_bal = player["coins"] + total

        display = FOOD_ITEMS.get(item, {}).get("display") or STAT_ITEMS.get(item, {}).get("display") or item.title()
        await interaction.response.send_message(
            f"💰 Sold {qty}× **{display}** for **{total} coins**! Balance: **{new_bal} coins**."
        )

    @app_commands.command(name="daily", description="Claim your daily login bonus")
    async def daily(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.ensure_player(conn, interaction.user.id)
            if player["last_daily"]:
                last = datetime.fromisoformat(player["last_daily"])
                if (datetime.now(timezone.utc) - last) < timedelta(hours=20):
                    remaining = (last + timedelta(hours=20)) - datetime.now(timezone.utc)
                    hrs = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)
                    await interaction.response.send_message(
                        f"Already claimed! Come back in **{hrs}h {mins}m**.", ephemeral=True
                    )
                    return

            await conn.execute(
                "UPDATE players SET coins=coins+?, last_daily=? WHERE user_id=?",
                (DAILY_LOGIN_COINS, db.now_iso(), interaction.user.id)
            )

            pet = await db.get_active_pet(conn, interaction.user.id)
            leveled_info = None
            if pet and pet["stage"] > 0:
                leveled_info = await db.add_xp(conn, pet["id"], DAILY_LOGIN_XP)

            await conn.commit()
            new_bal = player["coins"] + DAILY_LOGIN_COINS

        embed = discord.Embed(
            title="🌅 Daily Bonus!",
            description=f"+**{DAILY_LOGIN_COINS} coins** | +**{DAILY_LOGIN_XP} XP**",
            color=0xF1C40F
        )
        embed.set_footer(text=f"New balance: {new_bal} coins | Resets every 20 hours.")
        if leveled_info and leveled_info.get("leveled_up"):
            embed.add_field(name="📈 Level Up!", value=f"Your pet reached Level {leveled_info['level']}!", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="trade", description="Propose a trade with another player")
    @app_commands.describe(
        target="Player to trade with",
        offer="What you're offering (e.g. 'apple 3' or 'evo_stone_uncommon bloom 1')",
        request="What you want in return (e.g. 'fish 2')"
    )
    async def trade(
        self, interaction: discord.Interaction,
        target: discord.Member,
        offer: str,
        request: str
    ):
        if target.bot or target.id == interaction.user.id:
            await interaction.response.send_message("Invalid trade target.", ephemeral=True)
            return

        # Parse offer/request strings: "item_key [element] [qty]"
        def parse_trade_item(text: str) -> dict | None:
            parts = text.strip().split()
            if not parts:
                return None
            key = parts[0].lower()
            qty = 1
            element = None

            # Look for element name in parts
            from config import ELEMENTS
            for p in parts[1:]:
                if p.lower() in ELEMENTS:
                    element = p.lower()
                elif p.isdigit():
                    qty = int(p)

            # Determine item type
            if key in FOOD_ITEMS:
                return {"item_key": key, "item_type": "food", "qty": qty, "element": None}
            if key in STAT_ITEMS:
                return {"item_key": key, "item_type": "stat_item", "qty": qty, "element": None}
            if key in ("evo_stone_uncommon", "evo_stone_rare"):
                return {"item_key": key, "item_type": "evo_stone", "qty": qty, "element": element}
            if key == "mega_stone":
                return {"item_key": key, "item_type": "mega_stone", "qty": qty, "element": element}
            if key == "egg":
                return {"item_key": key, "item_type": "egg", "qty": qty, "element": element}
            return None

        offered_item = parse_trade_item(offer)
        requested_item = parse_trade_item(request)

        if not offered_item or not requested_item:
            await interaction.response.send_message(
                "Couldn't parse trade items.\n"
                "Format: `/trade @user offer:apple 2 request:fish 1`\n"
                "For stones: `evo_stone_uncommon bloom 1`",
                ephemeral=True
            )
            return

        async with aiosqlite.connect(db.DB_PATH) as conn:
            if not await db.has_item(conn, interaction.user.id, offered_item["item_key"],
                                     offered_item["qty"], offered_item.get("element")):
                await interaction.response.send_message(
                    f"You don't have {offered_item['qty']}× **{offered_item['item_key']}** to offer.",
                    ephemeral=True
                )
                return

        embed = discord.Embed(
            title="🤝 Trade Proposal",
            color=0x2ECC71
        )
        embed.add_field(
            name=f"{interaction.user.display_name} offers:",
            value=item_label(**offered_item),
            inline=True
        )
        embed.add_field(name="⇄", value="for", inline=True)
        embed.add_field(
            name=f"{target.display_name} gives:",
            value=item_label(**requested_item),
            inline=True
        )
        embed.set_footer(text="Trade expires in 2 minutes.")

        view = TradeOfferView(0, interaction.user, target,
                              [offered_item], [requested_item])
        await interaction.response.send_message(
            content=target.mention, embed=embed, view=view
        )

    @app_commands.command(name="give", description="Give coins to another player")
    @app_commands.describe(target="Who to give to", amount="Amount of coins")
    async def give(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        if target.bot or target.id == interaction.user.id:
            await interaction.response.send_message("Invalid target.", ephemeral=True)
            return
        if amount < 1:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player or player["coins"] < amount:
                await interaction.response.send_message(
                    f"Not enough coins! You have **{(player or {}).get('coins', 0)}**.", ephemeral=True
                )
                return
            await db.ensure_player(conn, target.id)
            await conn.execute(
                "UPDATE players SET coins=coins-? WHERE user_id=?", (amount, interaction.user.id)
            )
            await conn.execute(
                "UPDATE players SET coins=coins+? WHERE user_id=?", (amount, target.id)
            )
            await conn.commit()
        await interaction.response.send_message(
            f"💸 {interaction.user.mention} gave **{amount} coins** to {target.mention}!"
        )


    # ── Gambling ──────────────────────────────────────────────────────────────

    @app_commands.command(name="coinflip", description="Bet coins on a coin flip — double or nothing!")
    @app_commands.describe(bet="Amount of coins to bet (50–10,000)")
    async def coinflip(self, interaction: discord.Interaction, bet: int):
        if bet < GAMBLE_MIN or bet > GAMBLE_MAX:
            await interaction.response.send_message(
                f"Bet must be between **{GAMBLE_MIN:,}** and **{GAMBLE_MAX:,}** coins.", ephemeral=True
            )
            return
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            if (player.get("coins") or 0) < bet:
                await interaction.response.send_message(
                    f"You only have **{player.get('coins', 0):,} coins**.", ephemeral=True
                )
                return

        view = CoinflipView(interaction.user.id, bet)
        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=f"**{interaction.user.display_name}** is betting **{bet:,} coins**!\nPick your side:",
            color=0xF1C40F
        )
        embed.set_footer(text="Win: +2× bet · Lose: −bet")
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="dice", description="Roll the dice and gamble your coins!")
    @app_commands.describe(bet="Amount of coins to bet (50–10,000)")
    async def dice(self, interaction: discord.Interaction, bet: int):
        if bet < GAMBLE_MIN or bet > GAMBLE_MAX:
            await interaction.response.send_message(
                f"Bet must be between **{GAMBLE_MIN:,}** and **{GAMBLE_MAX:,}** coins.", ephemeral=True
            )
            return
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
            if not player:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            if (player.get("coins") or 0) < bet:
                await interaction.response.send_message(
                    f"You only have **{player.get('coins', 0):,} coins**.", ephemeral=True
                )
                return

            roll = random.randint(1, 6)
            dice_faces = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

            if roll == 1:
                # Cursed roll — lose 2× bet
                loss = min(bet * 2, player.get("coins", 0))
                await conn.execute(
                    "UPDATE players SET coins=coins-? WHERE user_id=?", (loss, interaction.user.id)
                )
                await conn.commit()
                color, title = 0xE74C3C, "💀 Cursed Roll!"
                desc = f"You rolled {dice_faces[roll]} — **snake eyes!**\nYou lose **{loss:,} coins** (double penalty)! 😬"
            elif roll <= 3:
                # Lose bet
                await conn.execute(
                    "UPDATE players SET coins=coins-? WHERE user_id=?", (bet, interaction.user.id)
                )
                await conn.commit()
                color, title = 0xE74C3C, "❌ Bad Roll"
                desc = f"You rolled {dice_faces[roll]} — not good enough.\nYou lose **{bet:,} coins**."
            elif roll <= 5:
                # Win 2× bet
                winnings = bet * 2
                await conn.execute(
                    "UPDATE players SET coins=coins+? WHERE user_id=?", (winnings, interaction.user.id)
                )
                await conn.commit()
                color, title = 0x2ECC71, "✅ Nice Roll!"
                desc = f"You rolled {dice_faces[roll]} — solid!\nYou win **{winnings:,} coins** (2×)!"
            else:
                # Roll 6 — win 3× bet
                winnings = bet * 3
                await conn.execute(
                    "UPDATE players SET coins=coins+? WHERE user_id=?", (winnings, interaction.user.id)
                )
                await conn.commit()
                color, title = 0xF1C40F, "🎰 JACKPOT!"
                desc = f"You rolled {dice_faces[roll]} — **PERFECT ROLL!**\nYou win **{winnings:,} coins** (3×)! 🎉"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(text="1=lose 2× · 2-3=lose · 4-5=win 2× · 6=win 3×")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="restart", description="Delete everything and start over from scratch")
    async def restart(self, interaction: discord.Interaction):
        async with aiosqlite.connect(db.DB_PATH) as conn:
            player = await db.get_player(conn, interaction.user.id)
        if not player:
            await interaction.response.send_message(
                "You haven't started yet! Use `/start`.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⚠️ Are you sure you want to restart?",
            description=(
                "This will **permanently delete**:\n"
                "• All your pets\n"
                "• Your entire inventory\n"
                "• All your coins\n"
                "• Your expedition progress\n\n"
                "**This cannot be undone.**"
            ),
            color=0xFF0000
        )
        view = RestartConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class RestartConfirmView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=30)
        self.user_id = user_id

    @discord.ui.button(label="✅ Yes, delete everything", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your restart!", ephemeral=True)
            return
        self.stop()

        async with aiosqlite.connect(db.DB_PATH) as conn:
            uid = interaction.user.id
            await conn.execute("DELETE FROM inventory WHERE player_id=?", (uid,))
            await conn.execute("DELETE FROM expeditions WHERE player_id=?", (uid,))
            await conn.execute("DELETE FROM armor_inventory WHERE player_id=?", (uid,))
            await conn.execute("DELETE FROM pet_skills WHERE pet_id IN (SELECT id FROM pets WHERE player_id=?)", (uid,))
            await conn.execute("DELETE FROM boss_damage_log WHERE player_id=?", (uid,))
            await conn.execute("DELETE FROM element_pity WHERE player_id=?", (uid,))
            await conn.execute("DELETE FROM pets WHERE player_id=?", (uid,))
            await conn.execute("DELETE FROM players WHERE user_id=?", (uid,))
            await conn.commit()

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Account reset!",
                description="Everything has been wiped. Use `/start` to begin a new journey!",
                color=0x2ECC71
            ),
            view=None
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't yours!", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Cancelled",
                description="Your account is safe. Nothing was deleted.",
                color=0x95A5A6
            ),
            view=None
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
