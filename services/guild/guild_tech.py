"""Static guild tech definitions + merged reward multipliers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

TECH_NODES: Dict[str, Dict[str, Any]] = {
    "guild_bounty_1": {
        "name": "Bounty Board I",
        "description": "+2% gold from exploration and combat drops for all members.",
        "cost_guild_xp": 300,
        "cost_bank_gold": 0,
        "requires": [],
        "effects": {"gold_mult": 0.02},
    },
    "guild_wisdom_1": {
        "name": "Wisdom of the Hall I",
        "description": "+2% XP from all sources for all members.",
        "cost_guild_xp": 400,
        "cost_bank_gold": 0,
        "requires": [],
        "effects": {"xp_mult": 0.02},
    },
    "guild_treasury_1": {
        "name": "Treasury Charter",
        "description": "+1% gold; requires Bounty Board I.",
        "cost_guild_xp": 250,
        "cost_bank_gold": 500,
        "requires": ["guild_bounty_1"],
        "effects": {"gold_mult": 0.01},
    },
    "guild_pathfinder_1": {
        "name": "Pathfinder's Accord",
        "description": "+0.5% extra chance weight toward dangerous explore outcomes (boss band helper).",
        "cost_guild_xp": 600,
        "cost_bank_gold": 0,
        "requires": ["guild_wisdom_1"],
        "effects": {"explore_boss_chance_add": 0.005},
    },
}


def tech_definitions_payload() -> List[Dict[str, Any]]:
    out = []
    for node_id, cfg in TECH_NODES.items():
        out.append(
            {
                "id": node_id,
                "name": cfg["name"],
                "description": cfg["description"],
                "cost_guild_xp": cfg["cost_guild_xp"],
                "cost_bank_gold": cfg["cost_bank_gold"],
                "requires": list(cfg.get("requires") or []),
            }
        )
    return out


async def fetch_unlocked_ids(db, guild_id: UUID) -> List[str]:
    rows = await db.fetch(
        "SELECT node_id FROM guild_tech_unlocks WHERE guild_id=$1 ORDER BY node_id",
        guild_id,
    )
    return [r["node_id"] for r in rows]


async def merged_tech_multipliers(db, guild_id: UUID) -> Tuple[float, float, float]:
    """Returns additive deltas: (xp_add, gold_add, boss_chance_add) from tech — multiply as (1+x)."""
    unlocked = set(await fetch_unlocked_ids(db, guild_id))
    xp_add = 0.0
    gold_add = 0.0
    boss_add = 0.0
    for nid, cfg in TECH_NODES.items():
        if nid not in unlocked:
            continue
        eff = cfg.get("effects") or {}
        xp_add += float(eff.get("xp_mult") or 0.0)
        gold_add += float(eff.get("gold_mult") or 0.0)
        boss_add += float(eff.get("explore_boss_chance_add") or 0.0)
    return xp_add, gold_add, boss_add


async def can_unlock(db, guild_id: UUID, node_id: str) -> tuple[bool, str]:
    if node_id not in TECH_NODES:
        return False, "Unknown tech node."
    unlocked = set(await fetch_unlocked_ids(db, guild_id))
    if node_id in unlocked:
        return False, "Already unlocked."
    cfg = TECH_NODES[node_id]
    for req in cfg.get("requires") or []:
        if req not in unlocked:
            return False, f"Requires: {req}"
    g = await db.fetchrow(
        "SELECT guild_xp, bank_gold FROM guilds WHERE id=$1",
        guild_id,
    )
    if not g:
        return False, "Guild not found."
    if int(g["guild_xp"] or 0) < int(cfg["cost_guild_xp"]):
        return False, "Not enough guild XP."
    if int(g["bank_gold"] or 0) < int(cfg["cost_bank_gold"]):
        return False, "Not enough gold in the guild bank."
    return True, ""


async def unlock_node(
    db,
    guild_id: UUID,
    node_id: str,
    actor_character_id: UUID,
    guild_rank: Optional[str],
) -> tuple[bool, str]:
    from services.guild.guild_permissions import can_officer_actions

    if not can_officer_actions(guild_rank):
        return False, "Only officers or the guildmaster can unlock guild tech."
    ok, msg = await can_unlock(db, guild_id, node_id)
    if not ok:
        return False, msg
    cfg = TECH_NODES[node_id]
    gx = int(cfg["cost_guild_xp"])
    gold_cost = int(cfg["cost_bank_gold"])

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            g = await conn.fetchrow(
                "SELECT guild_xp, bank_gold FROM guilds WHERE id=$1 FOR UPDATE",
                guild_id,
            )
            if not g:
                return False, "Guild not found."
            dup = await conn.fetchrow(
                "SELECT 1 FROM guild_tech_unlocks WHERE guild_id=$1 AND node_id=$2",
                guild_id,
                node_id,
            )
            if dup:
                return False, "Already unlocked."
            if int(g["guild_xp"] or 0) < gx:
                return False, "Not enough guild XP."
            if int(g["bank_gold"] or 0) < gold_cost:
                return False, "Not enough gold in the guild bank."
            await conn.execute(
                "UPDATE guilds SET guild_xp = guild_xp - $2, bank_gold = bank_gold - $3 WHERE id=$1",
                guild_id,
                gx,
                gold_cost,
            )
            await conn.execute(
                "INSERT INTO guild_tech_unlocks (guild_id, node_id) VALUES ($1, $2)",
                guild_id,
                node_id,
            )

    if gold_cost > 0:
        from services.guild.guild_bank import append_ledger

        await append_ledger(
            db,
            guild_id,
            actor_character_id,
            -gold_cost,
            "system",
            {"kind": "tech_unlock", "node_id": node_id},
        )
    return True, ""
