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

  const topBar = useMemo(
    () => (
      <div className="game-panel py-2 flex items-center justify-between">
        <span className="text-xs text-muted-foreground font-cinzel tracking-wider">
          ⚔️ Arena · {match.mode === "ranked" ? "Ranked" : "Casual"}
        </span>
        <span className="text-xs text-primary font-pixel" style={{ textShadow: "0 0 4px hsl(43 78% 50% / 0.3)" }}>
          {match.is_your_turn ? `Your turn — ${match.turn_timer}s` : "Opponent's turn"}
        </span>
      </div>
    ),
    [match.mode, match.is_your_turn, match.turn_timer],
  );

  return (
    <CombatEncounterView
      topBar={topBar}
      battleZoneOverride="dungeon"
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
