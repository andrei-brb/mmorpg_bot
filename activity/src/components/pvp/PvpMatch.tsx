import { Clock } from "lucide-react";
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
      <div
        className={`game-panel py-3 ${match.is_your_turn ? "border-primary/45" : ""}`}
        style={
          match.is_your_turn
            ? { boxShadow: "0 0 0 1px hsl(43 78% 50% / 0.2), inset 0 1px 0 hsl(228 14% 22% / 0.35)" }
            : undefined
        }
      >
        <div className="flex items-center justify-center gap-2">
          <Clock className={`w-4 h-4 shrink-0 ${match.is_your_turn ? "text-primary" : "text-muted-foreground"}`} />
          <span
            className={`font-cinzel text-xs uppercase tracking-widest font-bold ${
              match.is_your_turn ? "text-primary" : "text-muted-foreground"
            }`}
            style={match.is_your_turn ? { textShadow: "0 0 8px hsl(43 78% 50% / 0.25)" } : undefined}
          >
            {match.is_your_turn ? `Your Turn — ${match.turn_timer}s` : "Opponent's Turn — Resolving…"}
          </span>
        </div>
      </div>
    ),
    [match.is_your_turn, match.turn_timer],
  );

  return (
    <CombatEncounterView
      presentation="arena-duel"
      topBar={topBar}
      combatSessionId={match.match_id}
      enemyClassKey={slugClass(match.opponent.class)}
      enemyClassDisplayName={match.opponent.class}
      playerLevelOverride={match.player.level}
      enemyLevelOverride={match.opponent.level}
      skillsPanelTitle="Actions"
      primaryAbilityKey="__pvp_attack"
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
