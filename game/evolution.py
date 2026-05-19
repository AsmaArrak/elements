from game.stats import calc_base_stats

async def evolve_pet(db, pet: dict, target_stage: int):
    """Update a pet's base stats and stage in the database."""
    new_bases = calc_base_stats(pet["element"], target_stage)
    await db.execute(
        """UPDATE pets SET stage=?, base_hp=?, base_atk=?, base_def=?,
           base_spd=?, base_mgk=?, base_res=? WHERE id=?""",
        (target_stage,
         new_bases["hp"], new_bases["atk"], new_bases["def"],
         new_bases["spd"], new_bases["mgk"], new_bases["res"],
         pet["id"])
    )
    await db.commit()

async def check_auto_evolve(db, pet: dict, announce_channel=None, bot=None) -> bool:
    """No auto-evolve beyond stage 1 — those need items. Returns False."""
    return False

def can_evolve_to(pet: dict, target_stage: int, has_item: bool, item_key: str = None) -> tuple[bool, str]:
    from config import EVO_REQUIREMENTS
    req_level, req_item = EVO_REQUIREMENTS[target_stage]

    if pet["stage"] != target_stage - 1:
        return False, f"Your pet is not at the right stage to evolve to {target_stage}."

    if target_stage == 1:
        # Egg → Evo1 happens on first feed, not via /use
        return False, "Feed your egg to trigger its first evolution!"

    if pet["level"] < req_level:
        return False, f"Your pet needs to be **Level {req_level}** (currently {pet['level']})."

    if target_stage == 4:
        if pet["exploration"] < 100:
            return False, f"Your pet's Exploration stat must be **maxed (100/100)** (currently {pet['exploration']}/100)."

    if req_item and not has_item:
        item_names = {
            "evo_stone_uncommon": "Uncommon Evo Stone",
            "evo_stone_rare": "Rare Evo Stone",
            "mega_stone": f"{pet['element'].title()} Mega Stone",
        }
        return False, f"You need a **{item_names[req_item]}** for your element."

    return True, "Evolution is possible!"
