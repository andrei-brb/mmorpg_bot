import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CombatEnemy, CombatStatePayload } from "@/lib/apiTypes";
import { skillIconUrl } from "@/lib/skillIconUrl";
import { classIconUrl, specIconUrl } from "@/lib/classAndSpecIconUrl";

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
}

export function CombatTab({ focusMode }: { focusMode?: boolean }) {
  const {
    loadCombatSnapshot, startCombat, combatAction, rest,
    pendingCombatEnemyKey, refreshInventory, refreshProgress, map,
    inventory, combatFocusActive, setCombatFocusActive,
  } = useGameSession();

  const [mode, setMode] = useState<"pick" | "fight" | "outcome">("pick");
  const [enemies, setEnemies] = useState<CombatEnemy[]>([]);
  const [state, setState] = useState<CombatStatePayload | null>(null);
  const [enemyPick, setEnemyPick] = useState("");
  const [outcome, setOutcome] = useState<{ title?: string; lines?: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [useClassFallback, setUseClassFallback] = useState(false);
  const [useSpecFallback, setUseSpecFallback] = useState(false);

  const zoneLabel = map?.zones?.find((z) => z.key === map?.current_zone);
  const classKey = inventory?.character?.class || "";
  const specKey = inventory?.character?.specialization || "";

  // Reset icon fallbacks when the underlying keys change.
  useEffect(() => {
    setUseClassFallback(false);
  }, [classKey]);

  useEffect(() => {
    setUseSpecFallback(false);
  }, [specKey]);

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
        if (r.state) { setState(r.state); setMode("fight"); return; }
        toast.error(r.message || "Could not start combat");
      }
      setState(null); setMode("pick"); setOutcome(null);
      if (snap.enemies.length) setEnemyPick((prev) => prev || snap.enemies[0].key);
    } finally { setLoading(false); }
  }, [loadCombatSnapshot, startCombat, pendingCombatEnemyKey]);

  useEffect(() => { void refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  // Tell the shell when to enter/exit Combat Focus Mode.
  useEffect(() => {
    const active = mode === "fight" && Boolean(state);
    if (combatFocusActive !== active) setCombatFocusActive(active);
    return () => {
      // Ensure we exit focus mode if the tab unmounts mid-fight.
      setCombatFocusActive(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, state]);

  const onStart = async () => {
    if (!enemyPick) return;
    setLoading(true);
    try {
      const r = await startCombat(enemyPick);
      if (r.state) { setState(r.state); setMode("fight"); return; }
      toast.error(r.message || "Start failed");
    } finally { setLoading(false); }
  };

  const onAbility = async (key: string) => {
    setLoading(true);
    try {
      const json = await combatAction({ ability: key });
      if (json.ended && json.outcome) {
        setOutcome({ title: json.outcome.title, lines: json.outcome.lines });
        setMode("outcome");
        if (json.outcome.type === "victory" || json.outcome.type === "flee") {
          await refreshInventory(); await refreshProgress();
        }
        return;
      }
      if (json.state) setState(json.state);
    } finally { setLoading(false); }
  };

  const onFlee = async () => {
    setLoading(true);
    try {
      const json = await combatAction({ flee: true });
      if (json.ended && json.outcome) {
        setOutcome({ title: json.outcome.title, lines: json.outcome.lines });
        setMode("outcome");
        await refreshInventory(); await refreshProgress();
      } else if (json.state) setState(json.state);
    } finally { setLoading(false); }
  };

  const onPotion = async () => {
    setLoading(true);
    try {
      const json = await combatAction({ potion: true });
      if (json.state) setState(json.state);
    } finally { setLoading(false); }
  };

  const onRest = async () => {
    setLoading(true);
    try {
      const r = await rest();
      if (!r.ok && r.message) toast.error(r.message);
      else toast.success("Rested.");
      await refresh();
    } finally { setLoading(false); }
  };

  if (loading && mode === "pick" && !enemies.length) {
    return <p className="text-sm text-muted-foreground">Loading combat…</p>;
  }

  // Outcome screen (Lovable style)
  if (mode === "outcome" && outcome) {
    const isVictory = (outcome.title || "").toLowerCase().includes("victory") || (outcome.title || "").toLowerCase().includes("won");
    return (
      <div className="game-panel text-center py-8">
        <div className="text-5xl mb-4" style={{ filter: 'drop-shadow(0 2px 4px hsl(0 0% 0% / 0.5))' }}>
          {isVictory ? "🏆" : "💀"}
        </div>
        <h2 className="font-cinzel text-xl font-bold text-foreground mb-2"
          style={{ textShadow: isVictory ? '0 0 8px hsl(43 78% 50% / 0.3)' : 'none' }}>
          {outcome.title || "Combat ended"}
        </h2>
        <div className="ornament-divider my-3 mx-auto max-w-[200px]" />
        <ul className="text-xs text-muted-foreground space-y-1 text-left max-w-xs mx-auto mb-4">
          {(outcome.lines || []).map((l, i) => <li key={i}>{stripMd(l)}</li>)}
        </ul>
        <div className="flex gap-3 justify-center mt-5">
          <button onClick={() => void refresh()} className="game-btn-primary">Fight Again</button>
          <button onClick={() => void onRest()} className="game-btn-secondary">Rest</button>
        </div>
      </div>
    );
  }

  // Fighting screen (Lovable style)
  if (mode === "fight" && state) {
    const php = state.player.max_hp ? (100 * state.player.current_hp) / state.player.max_hp : 0;
    const ehp = state.enemy.max_hp ? (100 * state.enemy.current_hp) / state.enemy.max_hp : 0;
    return (
      <div className={focusMode ? "flex flex-col gap-4 h-full min-h-0" : "space-y-4"}>
        {/* Zone bar */}
        <div className="game-panel py-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground font-cinzel tracking-wider">
            {zoneLabel?.emoji} {zoneLabel?.name ?? "Zone"}
          </span>
          <span className="text-xs text-primary font-pixel" style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.3)' }}>
            Turn {state.turn}
          </span>
        </div>

        {/* Player vs Enemy */}
        <div className="grid grid-cols-2 gap-4">
          <div className="game-panel text-center">
            <div className="mb-2 flex items-center justify-center" style={{ filter: "drop-shadow(0 2px 4px hsl(0 0% 0% / 0.5))" }}>
              {classKey && !useClassFallback ? (
                <img
                  src={classIconUrl(classKey)}
                  alt=""
                  width={48}
                  height={48}
                  className="w-12 h-12 object-contain rounded-sm"
                  onError={() => {
                    setUseClassFallback(true);
                  }}
                />
              ) : (
                <span className="text-3xl">🧝</span>
              )}
            </div>
            <p className="text-sm font-cinzel font-semibold text-foreground">{state.player.name}</p>
            {specKey && !useSpecFallback && (
              <div className="mt-1 flex items-center justify-center">
                <img
                  src={specIconUrl(specKey)}
                  alt=""
                  width={18}
                  height={18}
                  className="w-[18px] h-[18px] object-contain rounded-[2px]"
                  onError={() => {
                    setUseSpecFallback(true);
                  }}
                />
              </div>
            )}
            <div className="mt-3">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-muted-foreground text-[10px] font-cinzel uppercase tracking-wider">HP</span>
                <span className="text-foreground tabular-nums">{state.player.current_hp}/{state.player.max_hp}</span>
              </div>
              <div className="hp-bar-track">
                <div className="hp-bar-fill" style={{ width: `${php}%` }} />
              </div>
              {state.player.max_res > 0 && (
                <p className="text-[10px] text-muted-foreground mt-1">
                  {state.player.res_type} {state.player.current_res}/{state.player.max_res}
                </p>
              )}
            </div>
          </div>
          <div className="game-panel text-center">
            <div className="text-3xl mb-2" style={{ filter: 'drop-shadow(0 2px 4px hsl(0 0% 0% / 0.5))' }}>
              <EnemyFace name={state.enemy.name} />
            </div>
            <p className="text-sm font-cinzel font-semibold text-foreground">{state.enemy.name}</p>
            <div className="mt-3">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-muted-foreground text-[10px] font-cinzel uppercase tracking-wider">HP</span>
                <span className="text-foreground tabular-nums">{state.enemy.current_hp}/{state.enemy.max_hp}</span>
              </div>
              <div className="hp-bar-track">
                <div className="hp-bar-fill" style={{ width: `${ehp}%` }} />
              </div>
            </div>
          </div>
        </div>

        {/* Turn banner */}
        <div className="text-center">
          <span className="inline-block px-5 py-1.5 font-cinzel font-semibold text-sm text-primary rounded-sm"
            style={{
              background: 'linear-gradient(180deg, hsl(228 18% 14%) 0%, hsl(228 20% 10%) 100%)',
              border: '1px solid hsl(43 50% 35% / 0.5)',
              boxShadow: '0 0 12px hsl(43 78% 50% / 0.1), inset 0 1px 0 hsl(228 14% 22% / 0.4)',
              textShadow: '0 0 6px hsl(43 78% 50% / 0.3)',
            }}>
            ⚔️ Your Turn
          </span>
        </div>

        {/* Skills */}
        <div className="game-panel">
          <div className="game-panel-header">Skills</div>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {(state.abilities || []).map((a) => (
              <button key={a.key} type="button"
                disabled={Boolean(a.disabled) || loading}
                title={a.disabled || undefined}
                className="skill-btn"
                onClick={() => void onAbility(a.key)}>
                <CombatSkillIcon abilityKey={a.key} emoji={a.emoji} />
                <span className="text-foreground font-semibold text-[10px]">{a.name}</span>
                <span className="text-muted-foreground text-[9px]">{a.cost} {a.cost_type}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Combat log */}
        <div className={focusMode ? "game-panel flex-1 min-h-0 overflow-y-auto" : "game-panel max-h-36 overflow-y-auto"}>
          <div className="game-panel-header">Combat Log</div>
          <div className="space-y-1.5">
            {(state.log || []).slice(-12).map((line, i) => (
              <p key={i} className="text-xs text-muted-foreground">{stripMd(line)}</p>
            ))}
          </div>
        </div>

        {/* Flee / Potion */}
        <div className="flex gap-2">
          <button type="button" onClick={() => void onFlee()} disabled={loading} className="game-btn-secondary text-xs px-3 py-1.5">
            🏃 Flee
          </button>
          {state.can_potion && (
            <button type="button" onClick={() => void onPotion()} disabled={loading} className="game-btn-secondary text-xs px-3 py-1.5">
              🧪 Potion
            </button>
          )}
        </div>
      </div>
    );
  }

  // Idle / pick screen (Lovable style)
  return (
    <div className="game-panel">
      <div className="game-panel-header">Choose an Enemy</div>
      {enemies.length === 0 ? (
        <p className="text-xs text-muted-foreground">No enemies in this zone — travel elsewhere or create a character.</p>
      ) : (
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={enemyPick}
            onChange={(e) => setEnemyPick(e.target.value)}
            className="game-select flex-1"
          >
            {enemies.map((e) => (
              <option key={e.key} value={e.key}>
                {e.emoji} {e.name} ({e.kind})
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <button onClick={() => void onStart()} disabled={loading} className="game-btn-danger">
              Start Combat
            </button>
            <button onClick={() => void onRest()} disabled={loading} className="game-btn-secondary">
              Rest
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EnemyFace({ name }: { name: string }) {
  const parts = name.trim().split(/\s+/);
  const emoji = parts[0] && /[^\w\s]/.test(parts[0]) ? parts[0] : "👾";
  return <>{emoji}</>;
}

/** Uses `public/skills/skill_<key>.png` when present; falls back to server emoji. */
function CombatSkillIcon({ abilityKey, emoji }: { abilityKey: string; emoji: string }) {
  const [useEmoji, setUseEmoji] = useState(false);
  if (useEmoji) {
    return (
      <span className="text-2xl leading-none" style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))" }}>
        {emoji}
      </span>
    );
  }
  return (
    <img
      src={skillIconUrl(abilityKey)}
      alt=""
      width={32}
      height={32}
      className="w-8 h-8 object-contain shrink-0"
      style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))" }}
      onError={() => setUseEmoji(true)}
    />
  );
}
