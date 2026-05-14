import { useEffect } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import type { ProgressPayload } from "@/lib/apiTypes";
import { WomPanel } from "@/components/wom/WomUi";

const TYPE_ICONS: Record<string, string> = {
  victory: "🏆",
  defeat: "💀",
  gold: "✨",
  combat_session: "⚔️",
  combat_gold: "🪙",
};

function formatHistoryAt(at: string | undefined): string {
  if (!at) return "";
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? at : d.toLocaleString();
}

function historyLine(h: NonNullable<ProgressPayload["history"]>[number]): string {
  if (h.type === "combat_session") {
    const o = h.outcome || "unknown";
    const z = h.zone ? ` · ${h.zone}` : "";
    return `${o}${z}`;
  }
  if (h.type === "combat_gold" || h.amount != null) {
    const amt = h.amount ?? 0;
    const r = h.reason || "reward";
    return `+${amt} ${r}`;
  }
  return h.reason || h.type || "—";
}

export function ProgressTab() {
  const { progress, refreshProgress, inventory } = useGameSession();

  useEffect(() => {
    void refreshProgress();
  }, [refreshProgress]);

  /** Match legacy: fall back to inventory character until progress API returns. */
  const c = progress?.character ?? inventory?.character ?? undefined;
  const s = progress?.stats;
  const ach = progress?.achievements || [];
  const hist = progress?.history || [];

  const stats = [
    { label: "Level", value: c?.level ?? "—", icon: "⭐" },
    { label: "Specialization", value: c?.specialization_name || c?.specialization || "—", icon: "🗡️" },
    { label: "Gold", value: c?.gold != null ? Number(c.gold).toLocaleString() : "—", icon: "🪙" },
    {
      label: "Win Rate",
      value: s?.win_rate != null ? `${Math.round(s.win_rate * 10000) / 100}%` : "—",
      icon: "📈",
    },
    { label: "Combats", value: s?.total_combats != null ? s.total_combats : "—", icon: "⚔️" },
    {
      label: "Record",
      value:
        s?.wins != null || s?.losses != null ? `${s?.wins ?? 0}W / ${s?.losses ?? 0}L` : "—",
      icon: "🏆",
    },
  ];

  return (
    <div className="space-y-4">
      {/* Stats grid */}
      <WomPanel glow>
        <div className="game-panel-header">Progress</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {stats.map((st) => (
            <div key={st.label} className="stat-card">
              <div className="text-2xl mb-1.5" style={{ filter: 'drop-shadow(0 1px 2px hsl(0 0% 0% / 0.5))' }}>{st.icon}</div>
              <div className="text-lg font-cinzel font-bold text-foreground tabular-nums"
                style={{ textShadow: '0 1px 2px hsl(0 0% 0% / 0.4)' }}>{st.value}</div>
              <div className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider mt-0.5">{st.label}</div>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          {s ? (
            <>
              Combats: {s.total_combats ?? 0} · W {s.wins ?? 0} / L {s.losses ?? 0} / Fled {s.fled ?? 0}
            </>
          ) : (
            <>Loading combat stats…</>
          )}
        </p>
      </WomPanel>

      {/* Achievements */}
      <WomPanel glow>
        <div className="game-panel-header">Achievements</div>
        <div className="space-y-1">
          {ach.length === 0 && <p className="text-xs text-muted-foreground">None earned yet.</p>}
          {ach.map((a, i) => (
            <div key={`${a.id ?? a.name ?? i}`}>
              <div className="flex items-center gap-3 p-2.5">
                <span className="text-xl" style={{ filter: 'drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))' }}>{a.icon || "🏅"}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-foreground font-cinzel">{a.name}</div>
                  <div className="text-xs text-muted-foreground">{a.description}</div>
                </div>
                <span className="text-xs text-primary font-semibold shrink-0"
                  style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.2)' }}>+{a.points ?? 0} pts</span>
              </div>
              {i < ach.length - 1 && <div className="ornament-divider" />}
            </div>
          ))}
        </div>
      </WomPanel>

      {/* History */}
      <WomPanel glow>
        <div className="game-panel-header">History</div>
        <div className="space-y-0">
          {hist.length === 0 && <p className="text-xs text-muted-foreground">No history.</p>}
          {hist.map((h, i) => (
            <div key={i}>
              <div className="flex items-center gap-2 text-xs py-2">
                <span>{TYPE_ICONS[h.type || ""] || "✨"}</span>
                <span className="text-foreground flex-1">{historyLine(h)}</span>
                {h.type !== "combat_session" && h.zone && (
                  <span className="text-muted-foreground hidden sm:inline">{h.zone}</span>
                )}
                <span className="text-muted-foreground shrink-0 tabular-nums">{formatHistoryAt(h.at)}</span>
              </div>
              {i < hist.length - 1 && <div className="ornament-divider" />}
            </div>
          ))}
        </div>
      </WomPanel>
    </div>
  );
}
