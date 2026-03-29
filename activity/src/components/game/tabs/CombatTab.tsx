import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CombatEnemy, CombatStatePayload } from "@/lib/apiTypes";
import { Button } from "@/components/ui/button";

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
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
    // Intentionally once on mount: avoid re-fetch during combat when unrelated context updates.
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
    return <p className="text-sm text-muted-foreground">Loading combat…</p>;
  }

  if (mode === "outcome" && outcome) {
    return (
      <div className="game-panel space-y-3">
        <div className="game-panel-header">{outcome.title || "Combat ended"}</div>
        <ul className="text-xs text-muted-foreground space-y-1">
          {(outcome.lines || []).map((l, i) => (
            <li key={i}>{stripMd(l)}</li>
          ))}
        </ul>
        <Button type="button" onClick={() => void refresh()}>
          Continue
        </Button>
      </div>
    );
  }

  if (mode === "fight" && state) {
    const php = state.player.max_hp ? (100 * state.player.current_hp) / state.player.max_hp : 0;
    const ehp = state.enemy.max_hp ? (100 * state.enemy.current_hp) / state.enemy.max_hp : 0;
    return (
      <div className="space-y-4">
        <div className="game-panel py-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground font-cinzel">
            {zoneLabel?.emoji} {zoneLabel?.name ?? "Zone"}
          </span>
          <span className="text-xs text-primary font-mono">Turn {state.turn}</span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="game-panel text-center">
            <p className="text-sm font-cinzel font-semibold">{state.player.name}</p>
            <div className="mt-2">
              <div className="flex justify-between text-[10px] mb-1">
                <span>HP</span>
                <span>
                  {state.player.current_hp}/{state.player.max_hp}
                </span>
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
            <EnemyFace name={state.enemy.name} />
            <p className="text-sm font-cinzel font-semibold mt-1">{state.enemy.name}</p>
            <div className="mt-2">
              <div className="flex justify-between text-[10px] mb-1">
                <span>HP</span>
                <span>
                  {state.enemy.current_hp}/{state.enemy.max_hp}
                </span>
              </div>
              <div className="hp-bar-track">
                <div className="hp-bar-fill" style={{ width: `${ehp}%` }} />
              </div>
            </div>
          </div>
        </div>
        <div className="game-panel max-h-40 overflow-y-auto">
          <div className="game-panel-header">Log</div>
          {(state.log || []).slice(-12).map((line, i) => (
            <p key={i} className="text-[10px] text-muted-foreground">
              {stripMd(line)}
            </p>
          ))}
        </div>
        <div className="game-panel">
          <div className="game-panel-header">Abilities</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {(state.abilities || []).map((a) => (
              <button
                key={a.key}
                type="button"
                disabled={Boolean(a.disabled) || loading}
                title={a.disabled || undefined}
                className="skill-btn text-left"
                onClick={() => void onAbility(a.key)}
              >
                <span className="text-lg">{a.emoji}</span>
                <span className="block text-[10px] font-semibold">{a.name}</span>
                <span className="text-[9px] text-muted-foreground">
                  {a.cost} {a.cost_type}
                </span>
              </button>
            ))}
            {state.can_potion && (
              <button type="button" className="skill-btn" onClick={() => void onPotion()} disabled={loading}>
                🧪 Potion
              </button>
            )}
            <button type="button" className="skill-btn border-destructive/40" onClick={() => void onFlee()} disabled={loading}>
              🏃 Flee
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">Start combat</div>
        {enemies.length === 0 ? (
          <p className="text-xs text-muted-foreground">No enemies in this zone — travel elsewhere or create a character.</p>
        ) : (
          <>
            <select
              className="game-select w-full bg-background border rounded-sm px-2 py-2 text-sm mb-2"
              value={enemyPick}
              onChange={(e) => setEnemyPick(e.target.value)}
            >
              {enemies.map((e) => (
                <option key={e.key} value={e.key}>
                  {e.emoji} {e.name} ({e.kind})
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <Button type="button" disabled={loading} onClick={() => void onStart()}>
                Start
              </Button>
              <Button type="button" variant="secondary" disabled={loading} onClick={() => void onRest()}>
                Rest
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function EnemyFace({ name }: { name: string }) {
  const parts = name.trim().split(/\s+/);
  const emoji = parts[0] && /[^\w\s]/.test(parts[0]) ? parts[0] : "👾";
  return (
    <div className="text-3xl" style={{ filter: "drop-shadow(0 2px 4px hsl(0 0% 0% / 0.5))" }}>
      {emoji}
    </div>
  );
}
