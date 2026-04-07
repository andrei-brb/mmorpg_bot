import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CombatEnemy, CombatStatePayload } from "@/lib/apiTypes";
import { CombatEncounterView } from "@/components/game/CombatEncounterView";
import { DungeonPanel } from "@/components/game/panels/DungeonPanel";
import * as api from "@/lib/gameApi";

type CombatTabMode = "overworld" | "dungeon";

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
}

export function CombatTab({ focusMode }: { focusMode?: boolean }) {
  const {
    accessToken,
    guildId,
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
  const [combatTabMode, setCombatTabMode] = useState<CombatTabMode>("overworld");

  const zoneLabel = map?.zones?.find((z) => z.key === map?.current_zone);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const snap = await loadCombatSnapshot();
      if (snap.ended_outcome?.outcome) {
        toast.info(snap.ended_outcome.outcome.title || "Encounter ended", {
          description: (snap.ended_outcome.outcome.lines || []).slice(0, 3).map(stripMd).join(" "),
        });
        if (accessToken) await api.postCombatStateAck(accessToken, guildId);
        return;
      }
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
        const r = await startCombat({ kind: "zone", enemyKey: pend });
        if (r.state) { setState(r.state); setMode("fight"); return; }
        toast.error(r.message || "Could not start combat");
      }
      setState(null); setMode("pick"); setOutcome(null);
      if (snap.enemies.length) setEnemyPick((prev) => prev || snap.enemies[0].key);
    } finally { setLoading(false); }
  }, [accessToken, guildId, loadCombatSnapshot, startCombat, pendingCombatEnemyKey]);

  useEffect(() => {
    if (combatTabMode !== "overworld") return;
    void refresh();
  }, [combatTabMode, refresh]);

  // Tell the shell when to enter/exit Combat Focus Mode (overworld API combat only).
  // Important: do NOT clear focus in a cleanup that runs on every `state` update — that was
  // briefly setting combatFocusActive to false after each skill, so tabs/header reappeared.
  useEffect(() => {
    if (combatTabMode !== "overworld") {
      setCombatFocusActive(false);
      return;
    }
    const active = mode === "fight" && Boolean(state);
    setCombatFocusActive(active);
  }, [combatTabMode, mode, state, setCombatFocusActive]);

  useEffect(() => {
    return () => setCombatFocusActive(false);
  }, [setCombatFocusActive]);

  const onStart = async () => {
    if (!enemyPick) return;
    setLoading(true);
    try {
      const r = await startCombat({ kind: "zone", enemyKey: enemyPick });
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
      // Combat continues - use state from response
      if (json.state) {
        setState(json.state);
        setMode("fight");
      }
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

  const modeSegment = (
    <div
      className="flex rounded-sm mb-4 p-0.5"
      style={{
        background: "hsl(228 20% 10%)",
        border: "1px solid hsl(43 45% 35% / 0.35)",
        boxShadow: "inset 0 1px 0 hsl(228 14% 22% / 0.25)",
      }}
    >
      <button
        type="button"
        onClick={() => setCombatTabMode("overworld")}
        className={`flex-1 px-3 py-1.5 text-xs font-cinzel font-semibold rounded-sm transition-all ${
          combatTabMode === "overworld"
            ? "text-primary"
            : "text-muted-foreground hover:text-foreground/80"
        }`}
        style={
          combatTabMode === "overworld"
            ? {
                background: "linear-gradient(180deg, hsl(228 18% 16%) 0%, hsl(228 20% 12%) 100%)",
                border: "1px solid hsl(43 50% 35% / 0.45)",
                boxShadow: "0 0 8px hsl(43 78% 50% / 0.12), inset 0 1px 0 hsl(228 14% 22% / 0.35)",
                textShadow: "0 0 6px hsl(43 78% 50% / 0.25)",
              }
            : { border: "1px solid transparent" }
        }
      >
        Overworld
      </button>
      <button
        type="button"
        onClick={() => setCombatTabMode("dungeon")}
        className={`flex-1 px-3 py-1.5 text-xs font-cinzel font-semibold rounded-sm transition-all ${
          combatTabMode === "dungeon"
            ? "text-primary"
            : "text-muted-foreground hover:text-foreground/80"
        }`}
        style={
          combatTabMode === "dungeon"
            ? {
                background: "linear-gradient(180deg, hsl(228 18% 16%) 0%, hsl(228 20% 12%) 100%)",
                border: "1px solid hsl(43 50% 35% / 0.45)",
                boxShadow: "0 0 8px hsl(43 78% 50% / 0.12), inset 0 1px 0 hsl(228 14% 22% / 0.35)",
                textShadow: "0 0 6px hsl(43 78% 50% / 0.25)",
              }
            : { border: "1px solid transparent" }
        }
      >
        Dungeon
      </button>
    </div>
  );

  if (combatTabMode === "dungeon") {
    return (
      <div>
        {modeSegment}
        <DungeonPanel playerLevel={inventory?.character?.level ?? 1} />
      </div>
    );
  }

  if (loading && mode === "pick" && !enemies.length) {
    return (
      <div>
        {modeSegment}
        <p className="text-sm text-muted-foreground">Loading combat…</p>
      </div>
    );
  }

  // Outcome screen (Lovable style)
  if (mode === "outcome" && outcome) {
    const isVictory = (outcome.title || "").toLowerCase().includes("victory") || (outcome.title || "").toLowerCase().includes("won");
    return (
      <div>
        {modeSegment}
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
          <button type="button" onClick={() => void refresh()} className="game-btn-primary">Fight Again</button>
          <button type="button" onClick={() => void onRest()} className="game-btn-secondary">Rest</button>
        </div>
        </div>
      </div>
    );
  }

  // Fighting screen — same combat engine as Discord /fight (real skills + stats)
  if (mode === "fight" && state) {
    return (
      <div className={focusMode ? "flex flex-col gap-4 h-full min-h-0" : "space-y-4"}>
        {modeSegment}
        <CombatEncounterView
          focusMode={focusMode}
          zoneLabel={zoneLabel}
          state={state}
          inventory={inventory}
          loading={loading}
          onAbility={onAbility}
          onFlee={onFlee}
          onPotion={onPotion}
          showDiscordDungeonBanner={Boolean(state.in_dungeon)}
        />
      </div>
    );
  }

  // Idle / pick screen (Lovable style)
  return (
    <div>
      {modeSegment}
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
    </div>
  );
}
