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

  const specName = c?.specialization_name || c?.specialization;
  const winRate = Number(s?.win_rate ?? 0);

  return (
    <div id="tab-progress" className="tab-pane space-y-4">
      <div className="panel v0-panel">
        <h2>Progress</h2>
        <div className="progress-stats">
          <div className="progress-card">
            <span className="progress-k">Level</span>
            <strong className="progress-v">{c?.level ?? "—"}</strong>
          </div>
          <div className="progress-card">
            <span className="progress-k">Specialization</span>
            <strong className="progress-v">{specName ? String(specName) : "—"}</strong>
          </div>
          <div className="progress-card">
            <span className="progress-k">Gold</span>
            <strong className="progress-v progress-v--gold">{c?.gold != null ? Number(c.gold).toLocaleString() : "—"}</strong>
          </div>
          <div className="progress-card">
            <span className="progress-k">Win rate</span>
            <strong className="progress-v">{(winRate * 100).toFixed(0)}%</strong>
          </div>
          <div className="progress-card">
            <span className="progress-k">Combats</span>
            <strong className="progress-v">{s?.total_combats ?? 0}</strong>
          </div>
          <div className="progress-card">
            <span className="progress-k">Record</span>
            <strong className="progress-v">
              {s?.wins ?? 0}W / {s?.losses ?? 0}L
            </strong>
          </div>
        </div>
        <p className="hint mt-3">
          Fled {s?.fled ?? 0} · Combats logged: {s?.total_combats ?? 0}
        </p>
      </div>

      <div className="panel v0-panel">
        <h2>Achievements</h2>
        <div className="progress-list">
          {ach.length === 0 ? (
            <p className="hint">No achievements earned yet.</p>
          ) : (
            ach.map((a, i) => (
              <div key={`${a.id ?? a.name ?? i}`} className="progress-row">
                <span>
                  {a.icon || "🏆"} {a.name}
                </span>
                <span className="muted-mini">+{a.points ?? 0} pts</span>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="panel v0-panel">
        <h2>History</h2>
        <div className="progress-list">
          {hist.length === 0 ? (
            <p className="hint">No recent activity yet.</p>
          ) : (
            hist.map((h, i) => {
              const at = h.at ? new Date(h.at).toLocaleString() : "";
              return (
                <div key={i} className="progress-row">
                  <span>
                    {h.type === "combat_session" ? "⚔️ " : "🪙 "}
                    {h.outcome || h.reason || h.type || "—"}
                    {h.zone ? ` · ${h.zone}` : ""}
                    {h.amount != null && h.type !== "combat_session" ? ` +${h.amount}` : ""}
                  </span>
                  <span className="muted-mini">{at}</span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
