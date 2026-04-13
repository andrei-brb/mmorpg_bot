import { useMemo } from "react";
import { CombatEncounterView } from "@/components/game/CombatEncounterView";
import { useGameSession } from "@/context/GameSessionContext";
import { pvpMatchToCombatState } from "@/lib/pvpCombatAdapter";
import type { PvpMatchState } from "@/lib/pvpTypes";

interface PvpMatchProps {
  match: PvpMatchState;
  onAction: (action: "attack" | "skill" | "defend" | "pass", skillKey?: string) => void;
}

function slugClass(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, "_");
}

export function PvpMatch({ match, onAction }: PvpMatchProps) {
  const { inventory } = useGameSession();
  const state = useMemo(() => pvpMatchToCombatState(match), [match]);

  return (
    <CombatEncounterView
      battleZoneOverride="volcano"
      combatSessionId={match.match_id}
      enemyClassKey={slugClass(match.opponent.class)}
      playerLevelOverride={match.player.level}
      enemyLevelOverride={match.opponent.level}
      showFleeButton={false}
      showPotionButton={false}
      turnBannerSeconds={match.is_your_turn ? match.turn_timer : null}
      opponentTurnLabel="⏳ Opponent's Turn — Resolving…"
      state={state}
      inventory={inventory}
      loading={false}
      onAbility={(key) => {
        if (key === "__pvp_attack") onAction("attack");
        else if (key === "__pvp_defend") onAction("defend");
        else if (key === "__pvp_pass") onAction("pass");
        else onAction("skill", key);
      }}
      onFlee={() => {}}
      onPotion={() => {}}
    />
  );
}
