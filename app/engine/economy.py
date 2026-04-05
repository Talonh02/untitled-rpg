"""
Economy engine — pricing, trade, merchant behavior.
Prices vary by city wealth, merchant honesty, and player reputation.
All formulas from MECHANICS.md section 8.
"""
import random

from app.data import NPC, Player, PRICES


def calculate_price(base_price, merchant, player, city):
    """
    Calculate what a merchant actually charges for an item.
    Base price gets modified by city economy, merchant greed, and player reputation.

    Args:
        base_price: int — the standard price from PRICES table
        merchant: NPC object (the seller)
        player: Player object (the buyer)
        city: Location object (the city this transaction happens in)

    Returns:
        Int — the actual price in coins (always at least 1).
    """
    price = float(base_price)

    # --- City economy modifier ---
    # Trade hubs have competition (cheaper), remote cities have scarcity (expensive)
    economy = ""
    if city:
        economy = getattr(city, "economy", "") or ""

    if economy == "trade_hub":
        price *= 0.85       # 15% cheaper
    elif economy == "remote":
        price *= 1.3        # 30% more expensive
    elif economy == "poor":
        price *= 0.9        # slightly cheaper (less demand)
    elif economy == "wealthy":
        price *= 1.15       # wealthier cities charge more

    # --- Merchant honesty markup ---
    # Honest merchants charge fair prices. Dishonest ones add a markup.
    # honesty 100 = 1.0x (fair), honesty 0 = 1.2x (20% markup)
    if merchant and hasattr(merchant, "stats"):
        merchant_markup = 1.0 + (100 - merchant.stats.honesty) / 500.0
        price *= merchant_markup

    # --- Player reputation in this city ---
    # Respected = 10% discount, Feared = 15% discount (they don't want trouble),
    # Wanted = 50% markup (risk premium)
    if player and hasattr(player, "reputation") and city:
        city_rep = player.reputation.get(city.id, {})
        sentiment = city_rep.get("sentiment", "")

        if sentiment == "respected":
            price *= 0.9
        elif sentiment == "feared":
            price *= 0.85
        elif sentiment == "wanted":
            price *= 1.5

    return max(1, round(price))


def get_base_price(item_name):
    """
    Look up the base price for an item from the PRICES table.
    Returns 0 if the item isn't in the table (unknown item).

    Args:
        item_name: string key like "dagger", "leather", "food_day"

    Returns:
        Int — base price in coins.
    """
    return PRICES.get(item_name, 0)


def can_afford(player, price):
    """Check if the player has enough coins."""
    return player.coins >= price


def execute_purchase(player, item_name, price):
    """
    Complete a purchase — deduct coins and add item to inventory.

    Args:
        player: Player object
        item_name: what they're buying
        price: what they're paying

    Returns:
        Dict with "success", "coins_remaining", and "item" keys.
    """
    if player.coins < price:
        return {"success": False, "error": "Not enough coins",
                "coins_remaining": player.coins}

    player.coins -= price
    player.inventory.append(item_name)
    return {"success": True, "coins_remaining": player.coins, "item": item_name}


def execute_sale(player, item_name, merchant, city):
    """
    Sell an item to a merchant. Sell price is roughly half the buy price,
    modified by merchant honesty and city economy.

    Args:
        player: Player object
        item_name: what they're selling
        merchant: NPC object
        city: Location object

    Returns:
        Dict with "success", "coins_received", "coins_remaining" keys.
    """
    if item_name not in player.inventory:
        return {"success": False, "error": "You don't have that item"}

    # Sell price is about half the buy price
    base = get_base_price(item_name)
    if base == 0:
        base = 5  # unknown items are worth a few coins

    sell_price = max(1, calculate_price(base, merchant, player, city) // 2)

    player.inventory.remove(item_name)
    player.coins += sell_price
    return {"success": True, "coins_received": sell_price, "coins_remaining": player.coins}


def wealth_to_coins(wealth_stat):
    """
    Convert an NPC's wealth stat (0-100) to approximate coin holdings.
    From MECHANICS.md section 8.

    Args:
        wealth_stat: int 0-100

    Returns:
        Int — approximate coins this NPC has.
    """
    if wealth_stat <= 10:
        return random.randint(0, 5)
    elif wealth_stat <= 30:
        return random.randint(5, 30)
    elif wealth_stat <= 50:
        return random.randint(30, 100)
    elif wealth_stat <= 70:
        return random.randint(100, 500)
    elif wealth_stat <= 90:
        return random.randint(500, 5000)
    else:
        return random.randint(5000, 20000)
