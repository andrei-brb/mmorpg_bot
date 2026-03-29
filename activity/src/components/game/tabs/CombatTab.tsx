import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CombatEnemy, CombatStatePayload } from "@/lib/apiTypes";
import { looksLikeEmoji } from "@/lib/itemIcons";

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
}

function splitLeadingEmojiName(full: string): { emoji: string; rest: string } {
  const t = (full || "").trim();
  const sp = t.indexOf(" ");
  if (sp < 1) return { emoji: "", rest: t };
  const first = t.slice(0, sp);
  if (looksLikeEmoji(first)) {
    const rest = t.slice(sp + 1).trim();
    return { emoji: first, rest: rest || t };
  }
  return { emoji: "", rest: t };
}

function lastDamageFromLog(lines: string[]): string | null {
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const raw = lines[i] || "";
    const m = raw.match(/\*\*(\d[\d,]*)\*\*\s*dmg/i) || raw.match(/(\d[\d,]*)\s*dmg/i);
    if (m?.[1]) return m[1];
  }
  return null;
}

function totalDamageFromLog(lines: string[]): number {
  let sum = 0;
  for (const line of lines) {
    const re = /\*\*(\d[\d,]*)\*\*[\s\S]*?dmg|(\d[\d,]*)\s*dmg/gi;
    let m: RegExpExecArray | null;
    while ((m = re.exec(line)) !== null) {
      const g = m[1] || m[2];
      if (g) sum += parseInt(g.replace(/,/g, ""), 10) || 0;
    }
  }
  return sum;
}

function formatCombatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

export function CombatTab() {
  const {
    loadCombatSnapshot,
    startCombat,
    combatAction,
    rest,
    pendingCombatEnemyKey,
    refreshInventory,
    refreshProgress,
    map,
  } = useGameSession();

  const [mode, setMode] = useState<"pick" | "fight" | "outcome">("pick");
  const [enemies, setEnemies] = useState<CombatEnemy[]>([]);
  const [state, setState] = useState<CombatStatePayload | null>(null);
  const [enemyPick, setEnemyPick] = useState("");
  const [outcome, setOutcome] = useState<{ title?: string; lines?: string[] } | null>(null);
  const [loading, setLoading] = useState(false);

  const zoneLabel = map?.zones?.find((z) => z.key === map?.current_zone);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const snap = await loadCombatSnapshot();
      if (snap.active && snap.state) {
        setState(snap.state);
        setMode("fight");
        setOutcome(null);
        return;
      }
      setEnemies(snap.enemies);
      const pend = pendingCombatEnemyKey.current;
      if (pend && snap.enemies.some((e) => e.key === pend)) {
        pendingCombatEnemyKey.current = null;
        const r = await startCombat(pend);
        if (r.state) {
          setState(r.state);
          setMode("fight");
          return;
        }
        toast.error(r.message || "Could not start combat");
      }
      setState(null);
      setMode("pick");
      setOutcome(null);
      if (snap.enemies.length) {
        setEnemyPick((prev) => prev || snap.enemies[0].key);
      }
    } finally {
      setLoading(false);
    }
  }, [loadCombatSnapshot, startCombat, pendingCombatEnemyKey]);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onStart = async () => {
    if (!enemyPick) return;
    setLoading(true);
    try {
      const r = await startCombat(enemyPick);
      if (r.state) {
        setState(r.state);
        setMode("fight");
        return;
      }
      toast.error(r.message || "Start failed");
    } finally {
      setLoading(false);
    }
  };

  const onAbility = async (key: string) => {
    setLoading(true);
    try {
      const json = await combatAction({ ability: key });
      if (json.ended && json.outcome) {
        setOutcome({ title: json.outcome.title, lines: json.outcome.lines });
        setMode("outcome");
        if (json.outcome.type === "victory" || json.outcome.type === "flee") {
          await refreshInventory();
          await refreshProgress();
        }
        return;
      }
      if (json.state) setState(json.state);
    } finally {
      setLoading(false);
    }
  };

  const onFlee = async () => {
    setLoading(true);
    try {
      const json = await combatAction({ flee: true });
      if (json.ended && json.outcome) {
        setOutcome({ title: json.outcome.title, lines: json.outcome.lines });
        setMode("outcome");
        await refreshInventory();
        await refreshProgress();
      } else if (json.state) setState(json.state);
    } finally {
      setLoading(false);
    }
  };

  const onPotion = async () => {
    setLoading(true);
    try {
      const json = await combatAction({ potion: true });
      if (json.state) setState(json.state);
    } finally {
      setLoading(false);
    }
  };

  const onRest = async () => {
    setLoading(true);
    try {
      const r = await rest();
      if (!r.ok && r.message) toast.error(r.message);
      else toast.success("Rested.");
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  if (loading && mode === "pick" && !enemies.length) {
    return (
      <div id="tab-combat" className="tab-pane">
        <div id="combat-mount">
          <p className="hint">Loading combat…</p>
        </div>
      </div>
    );
  }

  if (mode === "outcome" && outcome) {
    return (
      <div id="tab-combat" className="tab-pane">
        <div id="combat-mount">
          <div className="panel v0-panel outcome-panel">
            <h2>{outcome.title || "Combat ended"}</h2>
            <ul className="hint space-y-1 list-none p-0 m-0">
              {(outcome.lines || []).map((l, i) => (
                <li key={i}>{stripMd(l)}</li>
              ))}
            </ul>
            <div className="outcome-actions row-actions">
              <button type="button" className="btn" onClick={() => void refresh()}>
                Continue
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => void onRest()}>
                💤 Rest
              </button>
            </div>
            <p className="hint muted-mini mt-2">Rest restores HP and your resource (same rules as /rest).</p>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "fight" && state) {
    const php = state.player.max_hp ? (100 * state.player.current_hp) / state.player.max_hp : 0;
    const ehp = state.enemy.max_hp ? (100 * state.enemy.current_hp) / state.enemy.max_hp : 0;
    const logs = state.log || [];
    const floatDmg = lastDamageFromLog(logs);
    const totalDmg = totalDamageFromLog(logs);
    const latestLine = logs.length ? stripMd(logs[logs.length - 1]) : "Battle started.";
    const enemyDisp = splitLeadingEmojiName(state.enemy.name);
    const enemyLabel = enemyDisp.rest || state.enemy.name;
    const enemyShort = enemyLabel.length > 22 ? `${enemyLabel.slice(0, 20)}…` : enemyLabel;
    const resLine =
      state.player.max_res > 0 ? (
        <p className="hint res-line">
          <strong>
            {state.player.res_type === "mana"
              ? "💙 Mana"
              : state.player.res_type === "energy"
                ? "⚡ Energy"
                : state.player.res_type === "rage"
                  ? "🔴 Rage"
                  : state.player.res_type}
          </strong>{" "}
          {state.player.current_res}/{state.player.max_res}
        </p>
      ) : null;

    const logHtml = logs.slice(-14).map((line, li) => (
      <div key={`${li}-${line.slice(0, 24)}`} className="log-line v0-log-line">
        {stripMd(line)}
      </div>
    ));

    return (
      <div id="tab-combat" className="tab-pane">
        <div id="combat-mount">
          <div className="combat-compact">
            <div className="combat-zone-bar">
              <div className="combat-zone-bar__left">
                <span className="combat-zone-bar__title">
                  {zoneLabel?.emoji} {zoneLabel?.name ?? "Current battle"}
                </span>
                <span className="combat-zone-bar__sub">
                  Turn-based · same rules as <code>/fight</code>
                </span>
              </div>
              <div className="combat-zone-bar__right">
                <span className="combat-zone-bar__turn">Turn {state.turn}</span>
              </div>
            </div>

            <div className="scene-wrap">
              <div className="scene">
                <div className="bg-layer" />
                <div className="player">
                  <div className="scene-sprite" role="img" aria-label={state.player.name} />
                  <div className="name">{state.player.name}</div>
                  <div className="hpbar">
                    <div className="hpfill playerhp" style={{ width: `${php}%` }} />
                  </div>
                  <div className="hptext">
                    {state.player.current_hp} / {state.player.max_hp}
                  </div>
                  {resLine}
                </div>
                <div className="enemy">
                  <div
                    className={
                      enemyDisp.emoji ? "scene-sprite scene-sprite--enemy scene-sprite--emoji" : "scene-sprite scene-sprite--enemy"
                    }
                    role="img"
                    aria-label={enemyLabel}
                  >
                    {enemyDisp.emoji || ""}
                  </div>
                  <div className="name">{enemyLabel}</div>
                  <div className="hpbar">
                    <div className="hpfill enemyhp" style={{ width: `${ehp}%` }} />
                  </div>
                  <div className="hptext">
                    {state.enemy.current_hp} / {state.enemy.max_hp}
                  </div>
                </div>
                {floatDmg ? <div className="damage">-{floatDmg}</div> : null}
              </div>
            </div>

            <div className="skills skills--under-scene" aria-label="Abilities">
              {(state.abilities || []).map((a) => (
                <button
                  key={a.key}
                  type="button"
                  disabled={Boolean(a.disabled) || loading}
                  title={a.disabled || undefined}
                  className="skill-btn"
                  onClick={() => void onAbility(a.key)}
                >
                  <span className="skill-name">
                    {a.emoji} {a.name}
                  </span>
                  <span className="skill-cost">
                    {a.cost} {a.cost_type}
                  </span>
                </button>
              ))}
              {state.can_potion ? (
                <button type="button" className="skill-btn alt" onClick={() => void onPotion()} disabled={loading}>
                  <span className="skill-name">🧪 Potion</span>
                  <span className="skill-cost">Use</span>
                </button>
              ) : null}
              <button type="button" className="skill-btn flee-btn" onClick={() => void onFlee()} disabled={loading}>
                <span className="skill-name">🏃 Flee</span>
                <span className="skill-cost">Escape</span>
              </button>
            </div>

            <div className={`combat-mid-band${state.in_dungeon ? "" : " combat-mid-band--solo"}`}>
              <div className="combat-mid-band__log">
                <div className="combat-log-stack">
                  <div className="combat-stats-row" aria-label="Combat summary">
                    <div className="combat-stat">
                      <span className="combat-stat__k">Turn</span>
                      <span className="combat-stat__v">{state.turn}</span>
                    </div>
                    <div className="combat-stat">
                      <span className="combat-stat__k">Total damage</span>
                      <span className="combat-stat__v">{formatCombatNumber(totalDmg)}</span>
                    </div>
                    <div className="combat-stat combat-stat--grow">
                      <span className="combat-stat__k">Encounter</span>
                      <span className="combat-stat__v combat-stat__v--truncate" title={state.enemy.name}>
                        {enemyShort}
                      </span>
                    </div>
                  </div>
                  <div className="combat-turn-banner" role="status">
                    Your turn — use the skill bar above.
                  </div>
                  <div className="log-box log-box--flush">
                    <div className="log-highlight">{latestLine}</div>
                    <div className="combat-log">{logHtml.length ? logHtml : <p className="hint">—</p>}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div id="tab-combat" className="tab-pane">
      <div id="combat-mount">
        <div className="panel v0-panel">
          <h2>Start combat</h2>
          {zoneLabel && (
            <p className="hint mb-2">
              Zone: {zoneLabel.emoji} {zoneLabel.name}
            </p>
          )}
          {enemies.length === 0 ? (
            <p className="hint">No enemies in this zone — travel elsewhere or create a character.</p>
          ) : (
            <>
              <label className="select-label" htmlFor="enemy-pick">
                Opponent
              </label>
              <select
                id="enemy-pick"
                className="enemy-select mb-3"
                value={enemyPick}
                onChange={(e) => setEnemyPick(e.target.value)}
              >
                {enemies.map((e) => (
                  <option key={e.key} value={e.key}>
                    {e.emoji} {e.name} ({e.kind})
                  </option>
                ))}
              </select>
              <div className="row-actions">
                <button type="button" className="btn" disabled={loading} onClick={() => void onStart()}>
                  Start
                </button>
                <button type="button" className="btn btn-secondary" disabled={loading} onClick={() => void onRest()}>
                  Rest
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
