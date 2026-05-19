import math
from config import BASE_STATS, STAGE_MULTIPLIERS, stat_cap

def calc_base_stats(element: str, stage: int) -> dict:
    """Return the recalculated base stats for a given element at a given stage."""
    raw = BASE_STATS[element]
    mult = STAGE_MULTIPLIERS[stage]
    return {k: max(1, int(v * mult)) for k, v in raw.items()}

def effective_stat(base: int, bonus: int, level: int) -> int:
    cap = stat_cap(base, level)
    return min(base + bonus, cap)

def effective_stats(pet: dict) -> dict:
    level = pet["level"]
    return {
        "hp":  effective_stat(pet["base_hp"],  pet["bonus_hp"],  level),
        "atk": effective_stat(pet["base_atk"], pet["bonus_atk"], level),
        "def": effective_stat(pet["base_def"], pet["bonus_def"], level),
        "spd": effective_stat(pet["base_spd"], pet["bonus_spd"], level),
        "mgk": effective_stat(pet["base_mgk"], pet["bonus_mgk"], level),
        "res": effective_stat(pet["base_res"], pet["bonus_res"], level),
    }

def max_hp(pet: dict) -> int:
    return effective_stats(pet)["hp"]

def calc_physical_damage(attacker_stats: dict, defender_stats: dict) -> int:
    import random
    dmg = max(1, attacker_stats["atk"] - defender_stats["def"] // 2)
    dmg = int(dmg * random.uniform(0.88, 1.12))
    return max(1, dmg)

def calc_magic_damage(attacker: dict, defender: dict,
                      attacker_stats: dict, defender_stats: dict) -> tuple[int, bool]:
    """Return (damage, is_super_effective)."""
    import random
    from config import TYPE_ADVANTAGE
    super_eff = defender["element"] in TYPE_ADVANTAGE.get(attacker["element"], [])
    mult = 1.5 if super_eff else 1.0
    dmg = max(1, int(attacker_stats["mgk"] * mult) - defender_stats["res"] // 2)
    dmg = int(dmg * random.uniform(0.88, 1.12))
    return max(1, dmg), super_eff

def apply_stat_bonus(pet: dict, stat: str, bonus: int) -> tuple[int, bool]:
    """Apply a bonus to pet's bonus stat, respecting the cap. Returns (applied_amount, capped)."""
    base_key = f"base_{stat}"
    bonus_key = f"bonus_{stat}"
    cap = stat_cap(pet[base_key], pet["level"])
    current_total = pet[base_key] + pet[bonus_key]
    room = cap - current_total
    actual = min(bonus, max(0, room))
    return actual, actual < bonus

def hp_bar(current: int, maximum: int, length: int = 10) -> str:
    if maximum == 0:
        return "░" * length
    filled = round((current / maximum) * length)
    return "█" * filled + "░" * (length - filled)
