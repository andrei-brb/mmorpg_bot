"""Guild tech tree: ~24 nodes across Economy / War / Accord branches + member research funds."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

TECH_BRANCHES = ("economy", "war", "accord")

# Legacy node IDs preserved for existing unlock rows.
TECH_NODES: Dict[str, Dict[str, Any]] = {
    # --- Economy ---
    "guild_bounty_1": {
        "branch": "economy",
        "name": "Bounty Board I",
        "description": "+2% gold from exploration and combat for all members.",
        "cost_guild_xp": 300,
        "cost_bank_gold": 0,
        "fund_gold_required": 500,
        "requires": [],
        "effects": {"gold_mult": 0.02},
    },
    "guild_bounty_2": {
        "branch": "economy",
        "name": "Bounty Board II",
        "description": "+2% gold (stacks with Bounty I).",
        "cost_guild_xp": 600,
        "cost_bank_gold": 0,
        "fund_gold_required": 1_500,
        "requires": ["guild_bounty_1"],
        "effects": {"gold_mult": 0.02},
    },
    "guild_bounty_3": {
        "branch": "economy",
        "name": "Bounty Board III",
        "description": "+3% gold for all members.",
        "cost_guild_xp": 1_200,
        "cost_bank_gold": 1_000,
        "fund_gold_required": 4_000,
        "requires": ["guild_bounty_2"],
        "effects": {"gold_mult": 0.03},
    },
    "guild_treasury_1": {
        "branch": "economy",
        "name": "Treasury Charter",
        "description": "+1% gold; raises daily bank withdraw cap.",
        "cost_guild_xp": 250,
        "cost_bank_gold": 500,
        "fund_gold_required": 800,
        "requires": ["guild_bounty_1"],
        "effects": {"gold_mult": 0.01, "bank_withdraw_cap_add": 500_000},
    },
    "guild_market_1": {
        "branch": "economy",
        "name": "Market Toll",
        "description": "+1% gold from all sources.",
        "cost_guild_xp": 450,
        "cost_bank_gold": 0,
        "fund_gold_required": 1_200,
        "requires": ["guild_treasury_1"],
        "effects": {"gold_mult": 0.01},
    },
    "guild_bank_charter_1": {
        "branch": "economy",
        "name": "Bank Charter I",
        "description": "Guild daily withdraw cap +1,000,000 gold.",
        "cost_guild_xp": 500,
        "cost_bank_gold": 2_000,
        "fund_gold_required": 2_500,
        "requires": ["guild_treasury_1"],
        "effects": {"bank_withdraw_cap_add": 1_000_000},
    },
    "guild_bank_charter_2": {
        "branch": "economy",
        "name": "Bank Charter II",
        "description": "Guild daily withdraw cap +1,500,000 gold.",
        "cost_guild_xp": 900,
        "cost_bank_gold": 5_000,
        "fund_gold_required": 6_000,
        "requires": ["guild_bank_charter_1"],
        "effects": {"bank_withdraw_cap_add": 1_500_000},
    },
    "guild_deposit_bonus_1": {
        "branch": "economy",
        "name": "Vault Incentives",
        "description": "+2% gold (guild-wide passive).",
        "cost_guild_xp": 700,
        "cost_bank_gold": 0,
        "fund_gold_required": 3_000,
        "requires": ["guild_market_1", "guild_bank_charter_1"],
        "effects": {"gold_mult": 0.02},
    },
    # --- War ---
    "guild_war_raid_2": {
        "branch": "war",
        "name": "Raid Charter II",
        "description": "Unlock **Ironfang Hold** guild raids.",
        "cost_guild_xp": 800,
        "cost_bank_gold": 1_500,
        "fund_gold_required": 3_500,
        "requires": [],
        "effects": {"unlock_raid_template": "ironfang_hold_raid"},
    },
    "guild_war_raid_3": {
        "branch": "war",
        "name": "Raid Charter III",
        "description": "Unlock **Shadow Crypt** guild raids.",
        "cost_guild_xp": 1_400,
        "cost_bank_gold": 4_000,
        "fund_gold_required": 8_000,
        "requires": ["guild_war_raid_2"],
        "effects": {"unlock_raid_template": "shadow_crypt_raid"},
    },
    "guild_strike_1": {
        "branch": "war",
        "name": "Strike Training I",
        "description": "+10% raid and guild boss strike damage.",
        "cost_guild_xp": 400,
        "cost_bank_gold": 0,
        "fund_gold_required": 1_000,
        "requires": [],
        "effects": {"strike_damage_mult": 0.10},
    },
    "guild_strike_2": {
        "branch": "war",
        "name": "Strike Training II",
        "description": "+10% raid and guild boss strike damage.",
        "cost_guild_xp": 900,
        "cost_bank_gold": 0,
        "fund_gold_required": 2_500,
        "requires": ["guild_strike_1"],
        "effects": {"strike_damage_mult": 0.10},
    },
    "guild_boss_hunter_1": {
        "branch": "war",
        "name": "Boss Hunter I",
        "description": "Unlock tier-2 guild world boss hunts.",
        "cost_guild_xp": 600,
        "cost_bank_gold": 1_000,
        "fund_gold_required": 2_000,
        "requires": ["guild_strike_1"],
        "effects": {"unlock_boss_key": "defias_hideout_boss"},
    },
    "guild_boss_hunter_2": {
        "branch": "war",
        "name": "Boss Hunter II",
        "description": "Unlock tier-3 guild world boss hunts.",
        "cost_guild_xp": 1_100,
        "cost_bank_gold": 3_000,
        "fund_gold_required": 5_000,
        "requires": ["guild_boss_hunter_1", "guild_war_raid_2"],
        "effects": {"unlock_boss_key": "shadowfang_boss"},
    },
    "guild_war_banner_1": {
        "branch": "war",
        "name": "War Banner",
        "description": "+1% gold and +1% XP for members.",
        "cost_guild_xp": 500,
        "cost_bank_gold": 0,
        "fund_gold_required": 1_800,
        "requires": ["guild_strike_2"],
        "effects": {"gold_mult": 0.01, "xp_mult": 0.01},
    },
    "guild_war_raid_1": {
        "branch": "war",
        "name": "Raid Charter I",
        "description": "Formalize guild sorties (+5% raid strike damage).",
        "cost_guild_xp": 200,
        "cost_bank_gold": 0,
        "fund_gold_required": 400,
        "requires": [],
        "effects": {"strike_damage_mult": 0.05},
    },
    # --- Accord ---
    "guild_wisdom_1": {
        "branch": "accord",
        "name": "Wisdom of the Hall I",
        "description": "+2% XP from all sources.",
        "cost_guild_xp": 400,
        "cost_bank_gold": 0,
        "fund_gold_required": 500,
        "requires": [],
        "effects": {"xp_mult": 0.02},
    },
    "guild_wisdom_2": {
        "branch": "accord",
        "name": "Wisdom of the Hall II",
        "description": "+2% XP from all sources.",
        "cost_guild_xp": 800,
        "cost_bank_gold": 0,
        "fund_gold_required": 1_800,
        "requires": ["guild_wisdom_1"],
        "effects": {"xp_mult": 0.02},
    },
    "guild_pathfinder_1": {
        "branch": "accord",
        "name": "Pathfinder's Accord",
        "description": "+0.5% explore boss encounter weight.",
        "cost_guild_xp": 600,
        "cost_bank_gold": 0,
        "fund_gold_required": 1_200,
        "requires": ["guild_wisdom_1"],
        "effects": {"explore_boss_chance_add": 0.005},
    },
    "guild_pathfinder_2": {
        "branch": "accord",
        "name": "Pathfinder's Accord II",
        "description": "+0.5% explore boss encounter weight.",
        "cost_guild_xp": 1_000,
        "cost_bank_gold": 0,
        "fund_gold_required": 2_800,
        "requires": ["guild_pathfinder_1"],
        "effects": {"explore_boss_chance_add": 0.005},
    },
    "guild_checkin_1": {
        "branch": "accord",
        "name": "Check-in Rites I",
        "description": "+25% guild XP from daily hall check-in.",
        "cost_guild_xp": 350,
        "cost_bank_gold": 0,
        "fund_gold_required": 600,
        "requires": [],
        "effects": {"checkin_guild_xp_mult": 0.25},
    },
    "guild_checkin_2": {
        "branch": "accord",
        "name": "Check-in Rites II",
        "description": "+25% guild XP from daily hall check-in.",
        "cost_guild_xp": 700,
        "cost_bank_gold": 0,
        "fund_gold_required": 1_500,
        "requires": ["guild_checkin_1"],
        "effects": {"checkin_guild_xp_mult": 0.25},
    },
    "guild_accord_crest": {
        "branch": "accord",
        "name": "Accord Crest",
        "description": "+1% XP and +1% gold for all members.",
        "cost_guild_xp": 900,
        "cost_bank_gold": 500,
        "fund_gold_required": 3_500,
        "requires": ["guild_wisdom_2", "guild_pathfinder_2"],
        "effects": {"xp_mult": 0.01, "gold_mult": 0.01},
    },
    "guild_explore_1": {
        "branch": "accord",
        "name": "Scout's Eye",
        "description": "+1% XP from exploration.",
        "cost_guild_xp": 450,
        "cost_bank_gold": 0,
        "fund_gold_required": 900,
        "requires": ["guild_pathfinder_1"],
        "effects": {"xp_mult": 0.01},
    },
}

DEFAULT_BANK_WITHDRAW_CAP = 2_000_000


def tech_definitions_payload() -> List[Dict[str, Any]]:
    out = []
    for node_id, cfg in TECH_NODES.items():
        out.append(
            {
                "id": node_id,
                "branch": cfg.get("branch", "economy"),
                "name": cfg["name"],
                "description": cfg["description"],
                "cost_guild_xp": cfg["cost_guild_xp"],
                "cost_bank_gold": cfg["cost_bank_gold"],
                "fund_gold_required": int(cfg.get("fund_gold_required") or 0),
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


async def fund_contributed(db, guild_id: UUID, node_id: str) -> int:
    v = await db.fetchval(
        """
        SELECT COALESCE(SUM(amount), 0)::bigint
        FROM guild_tech_contributions
        WHERE guild_id = $1 AND node_id = $2
        """,
        guild_id,
        node_id,
    )
    return int(v or 0)


async def merged_tech_multipliers(db, guild_id: UUID) -> Tuple[float, float, float]:
    """Returns additive deltas: (xp_add, gold_add, boss_chance_add)."""
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


async def strike_damage_mult(db, guild_id: UUID) -> float:
    unlocked = set(await fetch_unlocked_ids(db, guild_id))
    mult = 1.0
    for nid, cfg in TECH_NODES.items():
        if nid not in unlocked:
            continue
        eff = cfg.get("effects") or {}
        mult += float(eff.get("strike_damage_mult") or 0.0)
    return mult


async def bank_withdraw_cap(db, guild_id: UUID) -> int:
    unlocked = set(await fetch_unlocked_ids(db, guild_id))
    cap = DEFAULT_BANK_WITHDRAW_CAP
    for nid, cfg in TECH_NODES.items():
        if nid not in unlocked:
            continue
        eff = cfg.get("effects") or {}
        cap += int(eff.get("bank_withdraw_cap_add") or 0)
    return cap


async def raid_templates_unlocked(db, guild_id: UUID) -> List[str]:
    """Raid template keys unlocked via war branch (base sortie always available)."""
    from services.guild.guild_raid import RAID_TEMPLATES

    unlocked_nodes = set(await fetch_unlocked_ids(db, guild_id))
    out: List[str] = []
    for key, tpl in RAID_TEMPLATES.items():
        req = tpl.get("requires_tech")
        if req and req not in unlocked_nodes:
            continue
        out.append(key)
    return out


async def boss_keys_unlocked(db, guild_id: UUID) -> List[str]:
    """Extra boss keys from tech; base bosses remain guild_boss defaults."""
    unlocked = set(await fetch_unlocked_ids(db, guild_id))
    keys: List[str] = []
    for nid, cfg in TECH_NODES.items():
        if nid not in unlocked:
            continue
        bk = (cfg.get("effects") or {}).get("unlock_boss_key")
        if bk:
            keys.append(str(bk))
    return keys


async def checkin_guild_xp_mult(db, guild_id: UUID) -> float:
    unlocked = set(await fetch_unlocked_ids(db, guild_id))
    add = 0.0
    for nid, cfg in TECH_NODES.items():
        if nid not in unlocked:
            continue
        add += float((cfg.get("effects") or {}).get("checkin_guild_xp_mult") or 0.0)
    return 1.0 + add


async def tech_progress_payload(db, guild_id: UUID) -> Dict[str, Any]:
    unlocked = set(await fetch_unlocked_ids(db, guild_id))
    funds: Dict[str, Dict[str, int]] = {}
    for node_id, cfg in TECH_NODES.items():
        if node_id in unlocked:
            funds[node_id] = {"contributed": int(cfg.get("fund_gold_required") or 0), "required": int(cfg.get("fund_gold_required") or 0)}
        else:
            req = int(cfg.get("fund_gold_required") or 0)
            contrib = await fund_contributed(db, guild_id, node_id)
            funds[node_id] = {"contributed": contrib, "required": req}
    return {"funds": funds}


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
    fund_req = int(cfg.get("fund_gold_required") or 0)
    if fund_req > 0:
        contrib = await fund_contributed(db, guild_id, node_id)
        if contrib < fund_req:
            return False, f"Research fund incomplete ({contrib:,} / {fund_req:,} gold donated)."
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


async def contribute(
    db,
    char_svc,
    guild_id: UUID,
    node_id: str,
    character_id: UUID,
    gold_amount: int,
) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    if node_id not in TECH_NODES:
        return False, "Unknown tech node.", None
    if gold_amount <= 0:
        return False, "Amount must be positive.", None
    unlocked = set(await fetch_unlocked_ids(db, guild_id))
    if node_id in unlocked:
        return False, "Node already unlocked.", None
    cfg = TECH_NODES[node_id]
    for req in cfg.get("requires") or []:
        if req not in unlocked:
            return False, f"Requires: {req}", None

    fund_req = int(cfg.get("fund_gold_required") or 0)
    current = await fund_contributed(db, guild_id, node_id)
    if fund_req > 0 and current >= fund_req:
        return False, "Research fund is full — finalize research.", None

    to_add = gold_amount
    if fund_req > 0:
        to_add = min(gold_amount, fund_req - current)
    if to_add <= 0:
        return False, "Research fund is full.", None

    ok = await char_svc.deduct_gold(character_id, to_add, "guild_tech_contribute")
    if not ok:
        return False, "Not enough gold.", None

    await db.execute(
        """
        INSERT INTO guild_tech_contributions (guild_id, node_id, character_id, amount)
        VALUES ($1, $2, $3, $4)
        """,
        guild_id,
        node_id,
        character_id,
        to_add,
    )
    new_total = await fund_contributed(db, guild_id, node_id)
    return True, f"Donated {to_add:,} gold to research.", {
        "contributed": new_total,
        "required": fund_req,
        "node_id": node_id,
    }


async def finalize_research(
    db,
    guild_id: UUID,
    node_id: str,
    actor_character_id: UUID,
    _guild_rank: Optional[str],
) -> tuple[bool, str]:
    """Any member may finalize when fund + guild XP + bank gold are met."""
    ok, msg = await can_unlock(db, guild_id, node_id)
    if not ok:
        return False, msg
    return await _do_unlock(db, guild_id, node_id, actor_character_id)


async def unlock_node(
    db,
    guild_id: UUID,
    node_id: str,
    actor_character_id: UUID,
    guild_rank: Optional[str],
) -> tuple[bool, str]:
    """Legacy officer unlock — same requirements as finalize."""
    from services.guild.guild_permissions import can_officer_actions

    if not can_officer_actions(guild_rank):
        return False, "Use **Donate** to fill the research fund, then **Finalize research** (any member)."
    ok, msg = await can_unlock(db, guild_id, node_id)
    if not ok:
        return False, msg
    return await _do_unlock(db, guild_id, node_id, actor_character_id)


async def _do_unlock(
    db,
    guild_id: UUID,
    node_id: str,
    actor_character_id: UUID,
) -> tuple[bool, str]:
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
            fund_req = int(cfg.get("fund_gold_required") or 0)
            if fund_req > 0:
                row = await conn.fetchrow(
                    """
                    SELECT COALESCE(SUM(amount), 0)::bigint AS total
                    FROM guild_tech_contributions
                    WHERE guild_id = $1 AND node_id = $2
                    """,
                    guild_id,
                    node_id,
                )
                total = int(row["total"] or 0) if row else 0
                if total < fund_req:
                    return False, "Research fund incomplete."
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
