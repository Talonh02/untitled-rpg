"""
Economic Simulation — runs once per game-day, zero model calls.

Each region produces resources based on terrain. Cities consume based on
population. Surplus trades along roads. Prosperity rises/falls. Rich cities
field bigger armies. Poor cities breed bandits.

All numbers are simple: production - consumption = surplus.
Trade flows surplus to deficit along connected roads.
Prosperity = how well-fed and supplied the city is (1-10).
Military capacity = what the city can afford to field.
"""
import math
import random

from app.data import World, Location, Road


# ============================================================
# RESOURCE PRODUCTION BY TERRAIN
# Units: production per day per region (scales with population)
# ============================================================

TERRAIN_RESOURCES = {
    "coastal":      {"fish": 80, "salt": 30, "timber": 20, "grain": 10},
    "plains":       {"grain": 100, "livestock": 40, "wool": 20, "timber": 10},
    "forest":       {"timber": 80, "herbs": 30, "game": 20, "grain": 10},
    "mountain":     {"iron": 60, "stone": 50, "gems": 10, "timber": 10},
    "river valley": {"grain": 70, "fish": 40, "clay": 20, "timber": 15},
    "steppe":       {"livestock": 60, "leather": 30, "horses": 20, "grain": 15},
    "swamp":        {"herbs": 40, "peat": 20, "fish": 15},
}

# What a city of 10,000 people consumes per day
CONSUMPTION_PER_10K = {
    "grain": 15, "fish": 5, "timber": 3, "iron": 2,
    "livestock": 3, "salt": 1, "herbs": 1,
}

# Base prices in coins per unit
BASE_PRICES = {
    "grain": 2, "fish": 3, "timber": 4, "iron": 8,
    "livestock": 10, "salt": 5, "herbs": 6, "game": 4,
    "wool": 3, "leather": 5, "horses": 50, "stone": 3,
    "clay": 2, "gems": 100, "peat": 1,
}


# ============================================================
# INITIALIZATION — set up economy for a freshly generated world
# ============================================================

def initialize_economy(world: World):
    """Set up economic data for every location. Call once after world gen."""
    for loc in world.locations.values():
        if not hasattr(loc, '_economy'):
            loc._economy = {}

        if loc.type == "region":
            terrain = loc.terrain or "plains"
            resources = dict(TERRAIN_RESOURCES.get(terrain, TERRAIN_RESOURCES["plains"]))
            # Scale production by population (more people = more workers)
            pop_scale = max(0.5, loc.population / 300_000)
            for r in resources:
                resources[r] = int(resources[r] * pop_scale)
            loc._economy = {
                "production": resources,
                "stockpile": {r: v * 10 for r, v in resources.items()},  # start with 10 days reserve
            }

        elif loc.type == "city":
            pop_10k = max(1, loc.population / 10_000)
            consumption = {r: int(v * pop_10k) for r, v in CONSUMPTION_PER_10K.items()}
            # Cities also produce a little based on their economy type
            city_production = {}
            econ = (loc.economy or "").lower()
            if "trade" in econ:
                city_production = {"grain": 5, "fish": 3}
            elif "agriculture" in econ:
                city_production = {"grain": 20, "livestock": 5}
            elif "mining" in econ:
                city_production = {"iron": 15, "stone": 10}
            elif "fishing" in econ:
                city_production = {"fish": 20, "salt": 5}
            elif "crafts" in econ:
                city_production = {"timber": 5, "iron": 3}

            prosperity = 5  # start neutral
            treasury = loc.population * 2  # 2 coins per person starting

            loc._economy = {
                "consumption": consumption,
                "production": city_production,
                "stockpile": {r: v * 5 for r, v in consumption.items()},  # 5 days reserve
                "prosperity": prosperity,
                "treasury": treasury,
                "tax_rate": 0.10,
                "prices": dict(BASE_PRICES),
                "military_budget": int(treasury * 0.15),
                "max_soldiers": int(loc.population * prosperity * 0.01),
            }


# ============================================================
# DAILY TICK — runs once per dawn
# ============================================================

def tick_economy(world: World):
    """
    Daily economic simulation. No model calls. Pure math.
    1. Regions produce resources
    2. Cities consume resources
    3. Trade flows along roads (surplus → deficit)
    4. Prosperity adjusts
    5. Prices adjust
    6. Treasury and military budget update
    """
    # Step 1: Regional production
    for loc in world.locations.values():
        if loc.type == "region" and hasattr(loc, '_economy') and loc._economy:
            econ = loc._economy
            for resource, amount in econ.get("production", {}).items():
                # Add daily production to stockpile (±15% variance)
                produced = int(amount * random.uniform(0.85, 1.15))
                econ["stockpile"][resource] = econ["stockpile"].get(resource, 0) + produced

    # Step 1b: Hinterland feeding — cities draw from parent region before consuming
    # FIX 5: cities pull up to 80% of their needs from the surrounding region first
    for loc in world.locations.values():
        if loc.type == "city" and hasattr(loc, '_economy') and loc._economy:
            parent = world.locations.get(loc.parent_id)
            if parent and hasattr(parent, '_economy') and parent._economy:
                parent_stock = parent._economy.get("stockpile", {})
                city_stock = loc._economy.get("stockpile", {})
                city_consumption = loc._economy.get("consumption", {})
                for resource, need in city_consumption.items():
                    # Draw up to 80% of what we need from the region
                    draw = int(need * 0.8)
                    available = parent_stock.get(resource, 0)
                    actual_draw = min(draw, available)
                    if actual_draw > 0:
                        parent_stock[resource] = available - actual_draw
                        city_stock[resource] = city_stock.get(resource, 0) + actual_draw

    # Step 2: City consumption
    for loc in world.locations.values():
        if loc.type == "city" and hasattr(loc, '_economy') and loc._economy:
            econ = loc._economy

            # Produce what the city makes
            for resource, amount in econ.get("production", {}).items():
                econ["stockpile"][resource] = econ["stockpile"].get(resource, 0) + amount

            # Consume
            satisfaction = 0
            total_needs = 0
            for resource, need in econ.get("consumption", {}).items():
                stock = econ["stockpile"].get(resource, 0)
                consumed = min(stock, need)
                econ["stockpile"][resource] = max(0, stock - consumed)
                satisfaction += consumed
                total_needs += need

            # Prosperity from satisfaction (how well-fed/supplied)
            if total_needs > 0:
                sat_ratio = satisfaction / total_needs
                target_prosperity = max(1, min(10, int(sat_ratio * 10)))
                # Move toward target slowly
                current = econ.get("prosperity", 5)
                if target_prosperity > current:
                    econ["prosperity"] = min(10, current + 0.3)
                elif target_prosperity < current:
                    econ["prosperity"] = max(1, current - 0.3)

    # Step 3: Trade along roads
    _run_trade(world)

    # Step 4: Update prices, treasury, military
    for loc in world.locations.values():
        if loc.type == "city" and hasattr(loc, '_economy') and loc._economy:
            econ = loc._economy
            prosperity = econ.get("prosperity", 5)

            # Prices: low stockpile → high prices, high stockpile → low prices
            for resource, base_price in BASE_PRICES.items():
                stock = econ["stockpile"].get(resource, 0)
                need = econ.get("consumption", {}).get(resource, 1)
                if need > 0:
                    supply_ratio = stock / (need * 5)  # relative to 5-day reserve
                    price_mult = max(0.5, min(3.0, 1.5 - supply_ratio * 0.5))
                else:
                    price_mult = 1.0
                econ["prices"][resource] = max(1, int(base_price * price_mult))

            # Treasury: grows from trade taxes
            trade_income = int(econ.get("trade_volume", 0) * econ.get("tax_rate", 0.1))
            econ["treasury"] = econ.get("treasury", 0) + trade_income

            # Military capacity: what they can afford
            econ["military_budget"] = int(econ.get("treasury", 0) * 0.15)
            econ["max_soldiers"] = int(loc.population * prosperity * 0.01)


def _run_trade(world: World):
    """Simple trade: surplus flows from region to connected cities."""
    # For each road connecting a region to a city (or city to city),
    # move surplus resources from the one with more to the one with less
    for road in world.roads:
        loc_a = world.locations.get(road.from_id)
        loc_b = world.locations.get(road.to_id)
        if not loc_a or not loc_b:
            continue
        if not hasattr(loc_a, '_economy') or not hasattr(loc_b, '_economy'):
            continue
        econ_a = loc_a._economy
        econ_b = loc_b._economy
        if not econ_a or not econ_b:
            continue

        stock_a = econ_a.get("stockpile", {})
        stock_b = econ_b.get("stockpile", {})

        # War disrupts trade (danger > 50 on the road = reduced flow)
        trade_efficiency = max(0.1, 1.0 - road.danger_rating / 100)

        trade_volume = 0
        all_resources = set(list(stock_a.keys()) + list(stock_b.keys()))
        for resource in all_resources:
            a_has = stock_a.get(resource, 0)
            b_has = stock_b.get(resource, 0)
            if a_has > b_has + 5:
                # A has surplus, send to B
                # FIX 5: transfer rate 50% (was 20%) for faster market balancing
                transfer = int((a_has - b_has) * 0.5 * trade_efficiency)
                transfer = min(transfer, a_has)
                stock_a[resource] = a_has - transfer
                stock_b[resource] = b_has + transfer
                trade_volume += transfer * BASE_PRICES.get(resource, 1)
            elif b_has > a_has + 5:
                # FIX 5: transfer rate 50% (was 20%)
                transfer = int((b_has - a_has) * 0.5 * trade_efficiency)
                transfer = min(transfer, b_has)
                stock_b[resource] = b_has - transfer
                stock_a[resource] = a_has + transfer
                trade_volume += transfer * BASE_PRICES.get(resource, 1)

        # Track trade volume for tax calculation
        econ_a["trade_volume"] = econ_a.get("trade_volume", 0) + trade_volume // 2
        econ_b["trade_volume"] = econ_b.get("trade_volume", 0) + trade_volume // 2


# ============================================================
# QUERY HELPERS — used by the game engine
# ============================================================

def get_city_economy(loc: Location) -> dict:
    """Get economic summary for a city. Used by frontend and Director."""
    if not hasattr(loc, '_economy') or not loc._economy:
        return {"prosperity": 5, "treasury": 0, "prices": dict(BASE_PRICES)}
    econ = loc._economy
    return {
        "prosperity": round(econ.get("prosperity", 5), 1),
        "treasury": econ.get("treasury", 0),
        "military_budget": econ.get("military_budget", 0),
        "max_soldiers": econ.get("max_soldiers", 0),
        "prices": econ.get("prices", dict(BASE_PRICES)),
        "stockpile": econ.get("stockpile", {}),
        "production": econ.get("production", {}),
    }


def get_economic_summary(world: World) -> str:
    """Build a text summary of the world economy for the Director/narrator."""
    lines = []
    cities = [(lid, loc) for lid, loc in world.locations.items()
              if loc.type == "city" and hasattr(loc, '_economy') and loc._economy]

    # Sort by prosperity
    cities.sort(key=lambda x: x[1]._economy.get("prosperity", 5), reverse=True)

    for lid, loc in cities[:10]:
        econ = loc._economy
        p = econ.get("prosperity", 5)
        t = econ.get("treasury", 0)
        m = econ.get("max_soldiers", 0)
        status = "thriving" if p > 7 else "stable" if p > 4 else "struggling" if p > 2 else "collapsing"
        lines.append(f"  {loc.name}: {status} (prosperity {p:.0f}/10, treasury {t:,}c, can field {m:,} soldiers)")

    return "Economic overview:\n" + "\n".join(lines) if lines else "No economic data."
