import { useEffect } from "react";
import { useGameSession } from "@/context/GameSessionContext";

export function ProgressTab() {
  const { progress, refreshProgress } = useGameSession();

  useEffect(() => {
    void refreshProgress();
  }, [refreshProgress]);

  const c = progress?.character;
  const s = progress?.stats;
  const ach = progress?.achievements || [];
  const hist = progress?.history || [];

  return (
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">Character</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div className="stat-card">
            <div className="text-2xl mb-1.5">⭐</div>
            <div className="text-lg font-cinzel font-bold text-foreground tabular-nums">{c?.level ?? "—"}</div>
            <div className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider mt-0.5">Level</div>
          </div>
          <div className="stat-card">
            <div className="text-2xl mb-1.5">🪙</div>
            <div className="text-lg font-cinzel font-bold text-foreground tabular-nums">
              {c?.gold != null ? Number(c.gold).toLocaleString() : "—"}
            </div>
            <div className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider mt-0.5">Gold</div>
          </div>
          <div className="stat-card">
            <div className="text-2xl mb-1.5">📈</div>
            <div className="text-lg font-cinzel font-bold text-foreground tabular-nums">
              {s?.win_rate != null ? `${Math.round(s.win_rate * 100) / 100}%` : "—"}
            </div>
            <div className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider mt-0.5">Win rate</div>
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Combats: {s?.total_combats ?? 0} · W {s?.wins ?? 0} / L {s?.losses ?? 0} / Fled {s?.fled ?? 0}
        </p>
      </div>

      <div className="game-panel">
        <div className="game-panel-header">Achievements</div>
        <div className="space-y-1">
          {ach.length === 0 && <p className="text-xs text-muted-foreground">None earned yet.</p>}
          {ach.map((a, i) => (
            <div key={`${a.id ?? a.name ?? i}`}>
              <div className="flex items-center gap-3 p-2.5">
                <span className="text-xl">{a.icon || "🏅"}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-foreground font-cinzel">{a.name}</div>
                  <div className="text-xs text-muted-foreground">{a.description}</div>
                </div>
                <span className="text-xs text-primary font-semibold shrink-0">+{a.points ?? 0} pts</span>
              </div>
              {i < ach.length - 1 && <div className="ornament-divider" />}
            </div>
          ))}
        </div>
      </div>

      <div className="game-panel">
        <div className="game-panel-header">History</div>
        <div className="space-y-0">
          {hist.length === 0 && <p className="text-xs text-muted-foreground">No history.</p>}
          {hist.map((h, i) => (
            <div key={i}>
              <div className="flex items-center gap-2 text-xs py-2">
                <span className="text-foreground flex-1">{h.reason || h.type || "—"}</span>
                {h.zone && <span className="text-muted-foreground hidden sm:inline">{h.zone}</span>}
                <span className="text-muted-foreground shrink-0 tabular-nums text-[10px]">{h.at || ""}</span>
              </div>
              {i < hist.length - 1 && <div className="ornament-divider" />}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
