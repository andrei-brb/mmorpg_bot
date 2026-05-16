"""Guild bank deposits, withdrawals, and append-only ledger."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from services.guild.guild_permissions import can_officer_actions

log = logging.getLogger("guild.bank")

MAX_DEPOSIT = 2_000_000_000
MAX_WITHDRAW_SINGLE = 500_000
GUILD_DAILY_WITHDRAW_CAP = 2_000_000


async def _today_withdraw_total(db, guild_id: UUID) -> int:
    row = await db.fetchrow(
        """
        SELECT COALESCE(SUM(-delta), 0)::bigint AS total
        FROM guild_bank_ledger
        WHERE guild_id = $1
          AND reason = 'withdraw'
          AND created_at >= date_trunc('day', NOW())
        """,
        guild_id,
    )
    return int(row["total"] or 0) if row else 0


async def append_ledger(
    db,
    guild_id: UUID,
    character_id: Optional[UUID],
    delta: int,
    reason: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    await db.execute(
        """
        INSERT INTO guild_bank_ledger (guild_id, character_id, delta, reason, meta)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        """,
        guild_id,
        character_id,
        delta,
        reason,
        json.dumps(meta or {}),
    )


async def deposit(
    db,
    char_svc,
    guild_id: UUID,
    character_id: UUID,
    amount: int,
) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Amount must be positive."
    if amount > MAX_DEPOSIT:
        return False, "Deposit too large."

    g = await db.fetchrow("SELECT id FROM guilds WHERE id=$1", guild_id)
    if not g:
        return False, "Guild not found."

    ok = await char_svc.deduct_gold(character_id, amount, "guild_bank_deposit")
    if not ok:
        return False, "Not enough gold."

    await db.execute("UPDATE guilds SET bank_gold = bank_gold + $2 WHERE id=$1", guild_id, amount)
    await append_ledger(db, guild_id, character_id, amount, "donation", {"amount": amount})
    return True, ""


async def withdraw(
    db,
    char_svc,
    guild_id: UUID,
    character_id: UUID,
    guild_rank: Optional[str],
    amount: int,
) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Amount must be positive."
    if not can_officer_actions(guild_rank):
        return False, "Only officers and the guildmaster can withdraw."
    if amount > MAX_WITHDRAW_SINGLE:
        return False, f"Max single withdraw is {MAX_WITHDRAW_SINGLE:,} gold."

    row = await db.fetchrow("SELECT bank_gold FROM guilds WHERE id=$1", guild_id)
    if not row:
        return False, "Guild not found."
    bank = int(row["bank_gold"] or 0)
    if bank < amount:
        return False, "Guild bank does not have enough gold."

    from services.guild import guild_tech as guild_tech_mod

    daily_cap = await guild_tech_mod.bank_withdraw_cap(db, guild_id)
    already = await _today_withdraw_total(db, guild_id)
    if already + amount > daily_cap:
        return False, f"Guild daily withdraw cap reached ({daily_cap:,} gold/day)."

    await db.execute("UPDATE guilds SET bank_gold = bank_gold - $2 WHERE id=$1", guild_id, amount)
    await char_svc.add_gold(character_id, amount, "guild_bank_withdraw")
    await append_ledger(db, guild_id, character_id, -amount, "withdraw", {"amount": amount})
    return True, ""
