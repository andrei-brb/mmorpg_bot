import { Swords, Shield, Zap, Clock, SkipForward } from "lucide-react";
import type { PvpMatchState } from "@/lib/pvpTypes";

interface PvpMatchProps {
  match: PvpMatchState;
  onAction: (action: "attack" | "skill" | "defend" | "pass", skillKey?: string) => void;
}

function HpResourceBar({ current, max, kind }: { current: number; max: number; kind: "hp" | "mana" }) {
  const pct = max <= 0 ? 0 : Math.max(0, (current / max) * 100);
  const isLow = kind === "hp" && pct < 30;
  return (
    <div className="hp-bar-track">
      <div
        className={`h-full rounded-sm transition-all duration-500 ${
          kind === "mana"
            ? "shadow-[inset_0_1px_0_hsl(210_65%_60%/0.35)]"
            : "hp-bar-fill"
        }`}
        style={
          kind === "mana"
            ? {
                width: `${pct}%`,
                background: "linear-gradient(180deg, hsl(210 65% 48%) 0%, hsl(210 55% 32%) 100%)",
                boxShadow: "inset 0 1px 0 hsl(210 65% 60% / 0.35), 0 0 6px hsl(210 65% 40% / 0.25)",
              }
            : isLow
              ? {
                  width: `${pct}%`,
                  background: "linear-gradient(180deg, hsl(0 55% 42%) 0%, hsl(0 50% 28%) 100%)",
                  boxShadow: "inset 0 1px 0 hsl(0 60% 50% / 0.35), 0 0 6px hsl(0 60% 35% / 0.3)",
                }
              : { width: `${pct}%` }
        }
      />
    </div>
  );
}

function PlayerCard({ player, isRight }: { player: PvpMatchState["player"]; isRight?: boolean }) {
  return (
    <div className="game-panel">
      <div className="p-3 space-y-3">
        <div className={`flex items-center gap-3 ${isRight ? "flex-row-reverse text-right" : ""}`}>
          <div className="w-12 h-12 rounded-sm bg-muted border border-border flex items-center justify-center shrink-0">
            <Shield className="w-6 h-6 text-muted-foreground" />
          </div>
          <div>
            <p className="font-cinzel text-xs font-bold text-foreground tracking-wide">{player.character_name}</p>
            <p className="text-[10px] text-muted-foreground font-crimson">
              Lv.{player.level} {player.class}
            </p>
          </div>
        </div>
        <div className="space-y-2">
          <div>
            <div className="flex items-center justify-between text-[10px] font-crimson mb-1">
              <span className="text-muted-foreground uppercase tracking-wider">Hit Points</span>
              <span className="text-foreground tabular-nums">
                {player.hp} / {player.max_hp}
              </span>
            </div>
            <HpResourceBar current={player.hp} max={player.max_hp} kind="hp" />
          </div>
          <div>
            <div className="flex items-center justify-between text-[10px] font-crimson mb-1">
              <span className="text-muted-foreground uppercase tracking-wider">Mana</span>
              <span className="text-foreground tabular-nums">
                {player.resource} / {player.max_resource}
              </span>
            </div>
            <HpResourceBar current={player.resource} max={player.max_resource} kind="mana" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function PvpMatch({ match, onAction }: PvpMatchProps) {
  const { is_your_turn, turn_timer, combat_log, skills } = match;

  return (
    <div className="space-y-4">
      <div className={`game-panel text-center py-3 ${is_your_turn ? "border-gold/40" : ""}`}>
        <div className="flex items-center justify-center gap-2">
          <Clock className={`w-4 h-4 ${is_your_turn ? "text-gold" : "text-muted-foreground"}`} />
          <span
            className={`font-cinzel text-xs uppercase tracking-widest font-bold ${
              is_your_turn ? "text-gold" : "text-muted-foreground"
            }`}
          >
            {is_your_turn ? `Your Turn — ${turn_timer}s` : "Opponent's Turn — Resolving…"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-start">
        <PlayerCard player={match.player} />
        <div className="flex items-center justify-center py-4">
          <Swords className="w-6 h-6 text-gold" />
        </div>
        <PlayerCard player={match.opponent} isRight />
      </div>

      <div className="game-panel">
        <div className="game-panel-header">Actions</div>
        <div className="p-3">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="game-btn-primary"
              disabled={!is_your_turn}
              onClick={() => onAction("attack")}
            >
              <Swords className="w-3 h-3 inline mr-1" /> Attack
            </button>

            {skills.map((skill) => {
              const notEnough = typeof skill.cost === "number" && skill.cost > match.player.resource;
              return (
                <button
                  key={skill.key}
                  type="button"
                  className="game-btn-secondary"
                  disabled={!is_your_turn || skill.cooldown > 0 || notEnough}
                  onClick={() => onAction("skill", skill.key)}
                  title={
                    (skill.description || "") +
                    (skill.cooldown > 0 ? ` (CD: ${skill.cooldown})` : "") +
                    (notEnough ? ` — Requires ${skill.cost} ${skill.cost_type || "resource"}` : "")
                  }
                >
                  <Zap className="w-3 h-3 inline mr-1" />
                  {skill.name}
                  {skill.cooldown > 0 && <span className="text-muted-foreground ml-1">({skill.cooldown})</span>}
                  {notEnough && <span className="text-xs text-muted-foreground ml-2">(No {skill.cost_type || "resource"})</span>}
                </button>
              );
            })}

            <button type="button" className="game-btn-secondary" disabled={!is_your_turn} onClick={() => onAction("defend")}>
              <Shield className="w-3 h-3 inline mr-1" /> Defend
            </button>

            <button type="button" className="game-btn-secondary" disabled={!is_your_turn} onClick={() => onAction("pass")}>
              <SkipForward className="w-3 h-3 inline mr-1" /> Pass
            </button>
          </div>
          {!is_your_turn && <p className="text-[10px] text-muted-foreground mt-2 font-crimson">Wait for your turn to act.</p>}
        </div>
      </div>

      <div className="game-panel">
        <div className="game-panel-header">Combat Log</div>
        <div className="h-40 overflow-y-auto p-3 space-y-0.5 font-mono text-[11px]">
          {combat_log.map((entry) => (
            <p
              key={entry.id}
              className={
                entry.type === "system"
                  ? "text-gold"
                  : entry.type === "damage"
                    ? "text-destructive"
                    : entry.type === "heal"
                      ? "text-emerald-400"
                      : "text-muted-foreground"
              }
            >
              <span className="text-muted-foreground">[{entry.timestamp}]</span> {entry.message}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}
