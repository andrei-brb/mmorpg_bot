import type { CombatAbility, CombatStatePayload } from "@/lib/apiTypes";
import type { PvpMatchState } from "@/lib/pvpTypes";

function slugClass(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, "_");
}

function buildAbilities(match: PvpMatchState): CombatAbility[] {
  const out: CombatAbility[] = [
    {
      key: "__pvp_attack",
      name: "Attack",
      emoji: "⚔️",
      cost: 0,
      cost_type: "none",
      cooldown: 0,
      description: "A direct weapon strike.",
    },
  ];

  for (const s of match.skills) {
    const notEnough = typeof s.cost === "number" && s.cost > match.player.resource;
    let disabled: string | null = null;
    if (s.cooldown > 0) disabled = `Cooldown: ${s.cooldown}`;
    else if (notEnough) disabled = `Not enough ${s.cost_type || "resource"}`;

    out.push({
      key: s.key,
      name: s.name,
      emoji: s.emoji || "✨",
      cost: s.cost ?? 0,
      cost_type: s.cost_type || "none",
      cooldown: s.cooldown,
      description: s.description || undefined,
      disabled,
      dmg_min: s.dmg_min ?? undefined,
      dmg_max: s.dmg_max ?? undefined,
      heal_estimate: s.heal_estimate ?? undefined,
      crit_pct: s.crit_pct ?? undefined,
      is_aoe: s.is_aoe,
    });
  }

  out.push(
    {
      key: "__pvp_defend",
      name: "Defend",
      emoji: "🛡️",
      cost: 0,
      cost_type: "none",
      cooldown: 0,
      description: "Brace to reduce damage taken.",
    },
    {
      key: "__pvp_pass",
      name: "Pass",
      emoji: "⏭️",
      cost: 0,
      cost_type: "none",
      cooldown: 0,
      description: "Skip your action this turn.",
    },
  );

  return out;
}

/** Maps Arena match state into the shared combat UI payload (1v1, turn-gated via party_mode + your_turn). */
export function pvpMatchToCombatState(match: PvpMatchState): CombatStatePayload {
  const logLines = (match.combat_log || []).map((e) => `[${e.timestamp}] ${e.message}`);

  return {
    turn: Math.max(1, match.combat_log?.length ?? 1),
    player: {
      name: match.player.character_name,
      current_hp: match.player.hp,
      max_hp: match.player.max_hp,
      current_res: match.player.resource,
      max_res: match.player.max_resource,
      res_type: "mana",
      class: slugClass(match.player.class),
      specialization: match.player.spec ? slugClass(match.player.spec) : null,
    },
    enemy: {
      name: match.opponent.character_name,
      current_hp: match.opponent.hp,
      max_hp: match.opponent.max_hp,
      current_res: match.opponent.resource,
      max_res: match.opponent.max_resource,
      res_type: "mana",
    },
    log: logLines,
    abilities: buildAbilities(match),
    can_potion: false,
    party_mode: true,
    your_turn: match.is_your_turn,
  };
}
