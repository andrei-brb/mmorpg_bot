import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CombatEnemy, CombatEnemiesMeta, CombatStatePayload } from "@/lib/apiTypes";
import { CombatEncounterView } from "@/components/game/CombatEncounterView";
import { DungeonPanel } from "@/components/game/panels/DungeonPanel";
import { enemyPortraitSrc, isBossKind } from "@/lib/enemyPortraitUrl";
import { ZONES as ZONES_DATA } from "@/data/zones";
import { cn } from "@/lib/utils";
import * as api from "@/lib/gameApi";
import { WomPanel } from "@/components/wom/WomUi";

type CombatTabMode = "overworld" | "dungeon";
type RichOutcome = NonNullable<api.CombatActionJson["outcome"]>;

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
}

function stripLeadingEmoji(s: string): string {
  // Remove leading pictographic glyphs (emoji + variation selectors) so we can render a consistent icon column.
  // Uses a Unicode property escape; if unsupported for any reason, fall back to trimming only.
  try {
    return s.replace(/^[\p{Extended_Pictographic}\uFE0F\u200D\s]+/u, "").trim();
  } catch {
    return s.trim();
  }
}

function OutcomeBadgeIcon({ kind }: { kind: "victory" | "defeat" | "neutral" }) {
  const common = "h-10 w-10 drop-shadow-[0_2px_4px_rgba(0,0,0,0.55)]";
  if (kind === "victory") {
    return (
      <svg className={common} viewBox="0 0 64 64" fill="none" aria-hidden>
        <path
          d="M20 10h24v10c0 8-5 15-12 17-7-2-12-9-12-17V10Z"
          stroke="currentColor"
          strokeWidth="3"
          className="text-amber-200"
        />
        <path
          d="M24 44h16v6H24v-6Z"
          fill="currentColor"
          className="text-amber-300/90"
        />
        <path
          d="M18 50h28v6H18v-6Z"
          fill="currentColor"
          className="text-amber-200/70"
        />
        <path
          d="M20 14H12c0 10 6 18 14 20"
          stroke="currentColor"
          strokeWidth="3"
          className="text-amber-200/90"
        />
        <path
          d="M44 14h8c0 10-6 18-14 20"
          stroke="currentColor"
          strokeWidth="3"
          className="text-amber-200/90"
        />
      </svg>
    );
  }
  if (kind === "defeat") {
    return (
      <svg className={common} viewBox="0 0 64 64" fill="none" aria-hidden>
        <path
          d="M32 10c12 0 22 8 22 22s-10 22-22 22S10 44 10 32 20 10 32 10Z"
          stroke="currentColor"
          strokeWidth="3"
          className="text-slate-200/90"
        />
        <path
          d="M22 27c0-3 2-5 5-5s5 2 5 5-2 5-5 5-5-2-5-5Zm15 0c0-3 2-5 5-5s5 2 5 5-2 5-5 5-5-2-5-5Z"
          fill="currentColor"
          className="text-slate-200/80"
        />
        <path
          d="M24 44c2-3 5-5 8-5s6 2 8 5"
          stroke="currentColor"
          strokeWidth="3"
          className="text-slate-200/85"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  return (
    <svg className={common} viewBox="0 0 64 64" fill="none" aria-hidden>
      <path
        d="M18 46 46 18m-6 0h6v6"
        stroke="currentColor"
        strokeWidth="4"
        className="text-foreground/70"
        strokeLinecap="round"
      />
      <path
        d="M22 18h10l-6 6"
        stroke="currentColor"
        strokeWidth="4"
        className="text-foreground/70"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MiniIcon({ kind }: { kind: "xp" | "gold" | "level" }) {
  const cls = "h-3.5 w-3.5";
  if (kind === "gold") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M12 3c5 0 9 2 9 5s-4 5-9 5-9-2-9-5 4-5 9-5Z"
          stroke="currentColor"
          strokeWidth="2"
          className="text-amber-200/95"
        />
        <path
          d="M3 8v6c0 3 4 5 9 5s9-2 9-5V8"
          stroke="currentColor"
          strokeWidth="2"
          className="text-amber-200/85"
        />
      </svg>
    );
  }
  if (kind === "level") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M12 3l2.2 6.5H21l-5.6 4 2.1 6.5L12 16.7 6.5 20l2.1-6.5-5.6-4h6.8L12 3Z"
          fill="currentColor"
          className="text-emerald-200/90"
        />
      </svg>
    );
  }
  return (
    <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 3c5 0 9 2 9 5s-4 5-9 5-9-2-9-5 4-5 9-5Z"
        stroke="currentColor"
        strokeWidth="2"
        className="text-sky-200/90"
      />
      <path
        d="M3 8v6c0 3 4 5 9 5s9-2 9-5V8"
        stroke="currentColor"
        strokeWidth="2"
        className="text-sky-200/70"
      />
    </svg>
  );
}

function InlineLogIcon({ kind }: { kind: "attack" | "bleed" | "heal" | "crit" | "victory" | "death" | "potion" | "gold" }) {
  const cls = "inline-block h-4 w-4 align-[-2px]";
  if (kind === "heal") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M12 21s-7-4.7-9.5-9C.7 8.6 2.6 5 6.3 5c1.9 0 3.2 1 3.7 2 0 0 1.2-2 4-2 3.7 0 5.6 3.6 3.8 7-2.5 4.3-9.8 9-9.8 9Z"
          fill="currentColor"
          className="text-emerald-300/90"
        />
        <path
          d="M12 8v6m-3-3h6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          className="text-emerald-950/70"
        />
      </svg>
    );
  }
  if (kind === "bleed") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M12 2c4 6 6 9 6 13a6 6 0 1 1-12 0c0-4 2-7 6-13Z"
          fill="currentColor"
          className="text-red-400/90"
        />
      </svg>
    );
  }
  if (kind === "crit") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M12 2l2.6 7.6H22l-6.2 4.4L18.4 22 12 17.9 5.6 22l2.6-8L2 9.6h7.4L12 2Z"
          fill="currentColor"
          className="text-amber-300/90"
        />
      </svg>
    );
  }
  if (kind === "potion") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M9 2h6v3l-1 1v2.2l3.1 3.1A6.5 6.5 0 1 1 6.9 11.3L10 8.2V6L9 5V2Z"
          stroke="currentColor"
          strokeWidth="2"
          className="text-violet-200/85"
        />
        <path
          d="M8.5 14.5h7"
          stroke="currentColor"
          strokeWidth="2"
          className="text-violet-200/60"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  if (kind === "gold") {
    return (
      <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M12 3c5 0 9 2 9 5s-4 5-9 5-9-2-9-5 4-5 9-5Z"
          stroke="currentColor"
          strokeWidth="2"
          className="text-amber-200/95"
        />
        <path
          d="M3 8v6c0 3 4 5 9 5s9-2 9-5V8"
          stroke="currentColor"
          strokeWidth="2"
          className="text-amber-200/80"
        />
      </svg>
    );
  }
  if (kind === "victory") {
    return <OutcomeBadgeIcon kind="victory" />;
  }
  if (kind === "death") {
    return <OutcomeBadgeIcon kind="defeat" />;
  }
  // attack
  return (
    <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 20 20 4m-6 0h6v6"
        stroke="currentColor"
        strokeWidth="2.5"
        className="text-foreground/80"
        strokeLinecap="round"
      />
    </svg>
  );
}

const INLINE_EMOJI_MAP: Array<{ re: RegExp; kind: Parameters<typeof InlineLogIcon>[0]["kind"] }> = [
  { re: /⚔️|🗡️|🪓|🔪|🛡️/g, kind: "attack" },
  { re: /🩸|🩸️|🩸/g, kind: "bleed" },
  { re: /💚|❤️|❤/g, kind: "heal" },
  { re: /🏆/g, kind: "victory" },
  { re: /💀/g, kind: "death" },
  { re: /🧪/g, kind: "potion" },
  { re: /🪙|💰/g, kind: "gold" },
];

function renderLineWithIcons(line: string): React.ReactNode {
  // Replace known emojis with inline icons; strip any remaining emoji glyphs.
  let parts: Array<string | { kind: Parameters<typeof InlineLogIcon>[0]["kind"] }> = [line];
  for (const { re, kind } of INLINE_EMOJI_MAP) {
    const next: typeof parts = [];
    for (const p of parts) {
      if (typeof p !== "string") {
        next.push(p);
        continue;
      }
      const s = p;
      let last = 0;
      for (const m of s.matchAll(re)) {
        const idx = m.index ?? -1;
        if (idx < 0) continue;
        if (idx > last) next.push(s.slice(last, idx));
        next.push({ kind });
        last = idx + m[0].length;
      }
      if (last < s.length) next.push(s.slice(last));
    }
    parts = next;
  }

  const out: React.ReactNode[] = [];
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i];
    if (typeof p === "string") {
      // Strip any remaining emoji characters anywhere in the line.
      const cleaned = p.replace(/[\p{Extended_Pictographic}\uFE0F\u200D]/gu, "");
      if (cleaned) out.push(cleaned);
      continue;
    }
    out.push(<InlineLogIcon key={`ico-${i}`} kind={p.kind} />);
  }
  return out;
}

const ZONE_EMOJI_MAP: Record<string, string> = {
  elwynn_forest: "🌲",
  dun_morogh: "❄️",
  barrens: "🌵",
  stranglethorn: "🌴",
  blackrock_depths: "🌋",
};

function riskTierPresentation(tier: string | undefined): {
  label: string;
  dotClass: string;
  panelClass: string;
} {
  const t = String(tier || "fair").toLowerCase();
  if (t === "deadly") {
    return {
      label: "Deadly — you are likely outmatched.",
      dotClass: "bg-red-500",
      panelClass: "border-red-500/55 bg-red-950/40 text-red-100",
    };
  }
  if (t === "risky") {
    return {
      label: "Risky — expect a very hard fight.",
      dotClass: "bg-orange-500",
      panelClass: "border-orange-500/45 bg-orange-950/30 text-orange-100",
    };
  }
  if (t === "caution") {
    return {
      label: "Caution — winnable, but dangerous.",
      dotClass: "bg-amber-400",
      panelClass: "border-amber-500/40 bg-amber-950/25 text-amber-50",
    };
  }
  return {
    label: "Fair — should be manageable at your level.",
    dotClass: "bg-emerald-500",
    panelClass: "border-emerald-600/40 bg-emerald-950/25 text-emerald-50",
  };
}

export function CombatTab({ focusMode }: { focusMode?: boolean }) {
  const {
    accessToken,
    guildId,
    loadCombatSnapshot, startCombat, combatAction, rest,
    pendingCombatEnemyKey, refreshInventory, refreshProgress, map,
    inventory, combatFocusActive, setCombatFocusActive,
    quickFightAgain,
    lastStartedEnemy,
  } = useGameSession();

  const [mode, setMode] = useState<"pick" | "fight" | "outcome">("pick");
  const [enemies, setEnemies] = useState<CombatEnemy[]>([]);
  const [state, setState] = useState<CombatStatePayload | null>(null);
  const [enemyPick, setEnemyPick] = useState("");
  const [outcome, setOutcome] = useState<RichOutcome | null>(null);
  const [loading, setLoading] = useState(false);
  const [combatTabMode, setCombatTabMode] = useState<CombatTabMode>("overworld");
  const [activeEnemy, setActiveEnemy] = useState<{ key: string; kind: "enemy" | "boss" } | null>(null);
  /** DungeonPanel sets this while `phase === "fight"` so we can hide the Overworld/Dungeon segment. */
  const [dungeonInFight, setDungeonInFight] = useState(false);
  /** Zone whose enemy catalog is shown (may differ from `map.current_zone` for preview). */
  const [foesListZoneId, setFoesListZoneId] = useState("");
  const prevMapZoneRef = useRef<string | undefined>(undefined);
  const [combatEnemiesMeta, setCombatEnemiesMeta] = useState<CombatEnemiesMeta | null>(null);

  const zoneLabel = map?.zones?.find((z) => z.key === map?.current_zone);

  const travelZones = useMemo(() => {
    const apiZones = map?.zones;
    return ZONES_DATA.map((z) => {
      const ap = apiZones?.find((x) => x.key === z.key);
      return {
        id: z.key,
        name: z.name,
        emoji: (typeof ap?.emoji === "string" && ap.emoji.trim()) || ZONE_EMOJI_MAP[z.key] || "🗺️",
        levelMin: z.levelRange[0],
        levelMax: z.levelRange[1],
      };
    });
  }, [map?.zones]);

  useEffect(() => {
    const cur = map?.current_zone?.trim();
    if (!cur) return;
    if (prevMapZoneRef.current !== cur) {
      prevMapZoneRef.current = cur;
      setFoesListZoneId(cur);
    }
  }, [map?.current_zone]);

  const { bossEnemies, normalEnemies } = useMemo(() => {
    const bosses: CombatEnemy[] = [];
    const normals: CombatEnemy[] = [];
    for (const e of enemies) {
      if (isBossKind(e.kind)) bosses.push(e);
      else normals.push(e);
    }
    const byName = (a: CombatEnemy, b: CombatEnemy) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    bosses.sort(byName);
    normals.sort(byName);
    return { bossEnemies: bosses, normalEnemies: normals };
  }, [enemies]);

  const selectedEnemy = useMemo(
    () => enemies.find((e) => e.key === enemyPick) ?? null,
    [enemies, enemyPick],
  );

  const currentTravelZone = useMemo(
    () => travelZones.find((z) => z.id === map?.current_zone?.trim()) ?? null,
    [travelZones, map?.current_zone],
  );

  const curZone = map?.current_zone?.trim() || "";
  const previewingRemoteZone = Boolean(curZone && foesListZoneId && foesListZoneId !== curZone);
  const browseZoneLabel = useMemo(
    () => travelZones.find((z) => z.id === foesListZoneId) ?? null,
    [travelZones, foesListZoneId],
  );

  const selectedRisk = useMemo(
    () => riskTierPresentation(selectedEnemy?.risk_tier),
    [selectedEnemy?.risk_tier],
  );

  const hpRatioNote = useMemo(() => {
    if (!selectedEnemy?.max_hp) return null;
    const pMax = Number(inventory?.character?.max_hp ?? 0);
    if (pMax <= 0) return null;
    const ratio = selectedEnemy.max_hp / pMax;
    if (ratio >= 3) return "This foe has roughly triple your max HP — expect a long fight.";
    if (ratio >= 2) return "This foe has roughly double your max HP — pace yourself and use cooldowns wisely.";
    return null;
  }, [selectedEnemy?.max_hp, inventory?.character?.max_hp]);

  const showSubModeToggle =
    !(combatTabMode === "overworld" && mode === "fight" && Boolean(state)) &&
    !(combatTabMode === "dungeon" && dungeonInFight);

  const refresh = useCallback(async (opts?: { enemiesZoneKey?: string }) => {
    setLoading(true);
    try {
      if (pendingCombatEnemyKey.current && curZone) {
        setFoesListZoneId((z) => (z !== curZone ? curZone : z));
      }
      const browse = (opts?.enemiesZoneKey ?? foesListZoneId).trim();
      const zoneForEnemies = pendingCombatEnemyKey.current ? curZone : browse || curZone;
      const snap = await loadCombatSnapshot(
        zoneForEnemies ? { enemiesZoneKey: zoneForEnemies } : {},
      );
      if (snap.ended_outcome?.outcome) {
        pendingCombatEnemyKey.current = null;
        const oc = snap.ended_outcome.outcome;
        setOutcome(oc || null);
        setMode("outcome");
        setState(null);
        setActiveEnemy(null);
        toast.info(oc.title || "Encounter ended", {
          description: (oc.lines || []).slice(0, 3).map(stripMd).join(" "),
        });
        if (accessToken) await api.postCombatStateAck(accessToken, guildId);
        return;
      }
      if (snap.active && snap.state) {
        const ls = lastStartedEnemy?.current;
        if (ls?.key) setActiveEnemy({ key: ls.key, kind: ls.kind });
        setState(snap.state);
        setMode("fight");
        setOutcome(null);
        return;
      }
      setEnemies(snap.enemies);
      setCombatEnemiesMeta(snap.combatEnemiesMeta ?? null);
      const pend = pendingCombatEnemyKey.current;
      if (pend && snap.enemies.some((e) => e.key === pend)) {
        const r = await startCombat({ kind: "zone", enemyKey: pend });
        if (r.state) {
          const picked = snap.enemies.find((e) => e.key === pend);
          setActiveEnemy({ key: pend, kind: picked?.kind === "boss" ? "boss" : "enemy" });
          setState(r.state);
          setMode("fight");
          return;
        }
        toast.error(r.message || "Could not start combat");
      }
      setState(null); setMode("pick"); setOutcome(null);
      setActiveEnemy(null);
      if (snap.enemies.length) {
        setEnemyPick((prev) => {
          const keys = new Set(snap.enemies.map((e) => e.key));
          if (prev && keys.has(prev)) return prev;
          return snap.enemies[0]?.key ?? "";
        });
      } else {
        setEnemyPick("");
      }
    } finally { setLoading(false); }
  }, [
    accessToken,
    guildId,
    loadCombatSnapshot,
    startCombat,
    pendingCombatEnemyKey,
    foesListZoneId,
    curZone,
  ]);

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
      if (r.state) {
        const picked = enemies.find((e) => e.key === enemyPick);
        setActiveEnemy({ key: enemyPick, kind: picked?.kind === "boss" ? "boss" : "enemy" });
        setState(r.state);
        setMode("fight");
        return;
      }
      toast.error(r.message || "Start failed");
    } finally { setLoading(false); }
  };

  const onAbility = async (key: string) => {
    setLoading(true);
    try {
      const json = await combatAction({ ability: key });
      if (json.ended && json.outcome) {
        // Solo overworld wins do not surface `ended_outcome` on GET /combat/state — clear here so a later
        // `refresh()` (tab focus, Rest, etc.) cannot auto-restart from a stale explore pending key.
        pendingCombatEnemyKey.current = null;
        setOutcome(json.outcome);
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
        pendingCombatEnemyKey.current = null;
        setOutcome(json.outcome);
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
      className="flex rounded-sm mb-3 p-0.5"
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
      <div className={cn("w-full min-w-0", dungeonInFight && "-mt-2 sm:-mt-3")}>
        {showSubModeToggle && modeSegment}
        <DungeonPanel
          playerLevel={inventory?.character?.level ?? 1}
          onCombatUiChange={setDungeonInFight}
        />
      </div>
    );
  }

  if (loading && mode === "pick" && !enemies.length) {
    return (
      <div className="w-full min-w-0">
        {showSubModeToggle && modeSegment}
        <p className="text-sm text-muted-foreground">Loading combat…</p>
      </div>
    );
  }

  // Outcome screen (Lovable style)
  if (mode === "outcome" && outcome) {
    const titleText = String(outcome.title || "Combat ended");
    const isVictory =
      String(outcome.type || "").toLowerCase() === "victory" ||
      titleText.toLowerCase().includes("victory") ||
      titleText.toLowerCase().includes("won");
    const isDefeat =
      String(outcome.type || "").toLowerCase() === "defeat" ||
      titleText.toLowerCase().includes("defeat") ||
      titleText.toLowerCase().includes("defeated");
    const xp = typeof outcome.xp === "number" ? outcome.xp : null;
    const gold = typeof outcome.gold === "number" ? outcome.gold : null;
    const leveledUp = Boolean(outcome.leveled_up);
    const loot = Array.isArray(outcome.loot) ? outcome.loot : [];
    const rawLogLines = (outcome.lines || []).map(stripMd);
    const logLines = rawLogLines.map(stripLeadingEmoji);

    const onClose = () => {
      setOutcome(null);
      setState(null);
      setActiveEnemy(null);
      setMode("pick");
      void refresh();
    };
    return (
      <div className="w-full min-w-0">
        {showSubModeToggle && modeSegment}
        <WomPanel glow className="w-full py-6 sm:py-7">
          <div className="mx-auto w-full max-w-3xl">
            <div className="grid grid-cols-1 gap-3 sm:gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:items-stretch">
              <div className="rounded-sm border border-white/10 bg-black/20 p-3 sm:p-4">
                <OutcomeBadgeIcon kind={isVictory ? "victory" : isDefeat ? "defeat" : "neutral"} />
                <h2
                  className="mt-3 font-cinzel text-lg font-bold text-foreground"
                  style={{ textShadow: isVictory ? "0 0 8px hsl(43 78% 50% / 0.3)" : "none" }}
                >
                  {titleText}
                </h2>
                <div className="ornament-divider my-3 max-w-[220px]" />

                <div className="flex flex-wrap gap-2">
                  {xp != null ? (
                    <span className="inline-flex items-center gap-1.5 rounded-sm border border-white/10 bg-black/25 px-2 py-1 text-[11px] font-semibold text-foreground/90">
                      <MiniIcon kind="xp" />
                      <span className="tabular-nums">+{xp.toLocaleString()}</span> XP
                    </span>
                  ) : null}
                  {gold != null ? (
                    <span className="inline-flex items-center gap-1.5 rounded-sm border border-white/10 bg-black/25 px-2 py-1 text-[11px] font-semibold text-foreground/90">
                      <MiniIcon kind="gold" />
                      <span className="tabular-nums">+{gold.toLocaleString()}</span>
                    </span>
                  ) : null}
                  {leveledUp ? (
                    <span className="inline-flex items-center gap-1.5 rounded-sm border border-emerald-500/30 bg-emerald-950/20 px-2 py-1 text-[11px] font-semibold text-emerald-50">
                      <MiniIcon kind="level" />
                      LEVEL UP
                    </span>
                  ) : null}
                </div>

                {loot.length > 0 ? (
                  <div className="mt-3">
                    <div className="text-[10px] font-cinzel font-semibold uppercase tracking-wider text-muted-foreground">
                      Loot
                    </div>
                    <ul className="mt-2 space-y-1 text-[12px] leading-relaxed text-muted-foreground">
                      {loot.slice(0, 6).map((l, i) => (
                        <li key={i} className="leading-snug">
                          {renderLineWithIcons(stripMd(l))}
                        </li>
                      ))}
                      {loot.length > 6 ? (
                        <li className="text-[10px] text-muted-foreground/80">+{loot.length - 6} more…</li>
                      ) : null}
                    </ul>
                  </div>
                ) : null}

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      void quickFightAgain().then((r) => {
                        if (r.state) {
                          const ls = lastStartedEnemy?.current;
                          if (ls?.key) setActiveEnemy({ key: ls.key, kind: ls.kind });
                          setState(r.state);
                          setMode("fight");
                          setOutcome(null);
                          return;
                        }
                        void refresh();
                        if (r.message) toast.error(r.message);
                      });
                    }}
                    className="game-btn-primary"
                  >
                    Fight Again
                  </button>
                  <button type="button" onClick={() => void onRest()} className="game-btn-secondary">
                    Rest
                  </button>
                  <button type="button" onClick={onClose} className="game-btn-secondary">
                    Close
                  </button>
                </div>
              </div>

              <div className="rounded-sm border border-white/10 bg-black/15 p-3 sm:p-4">
                <div className="text-[10px] font-cinzel font-semibold uppercase tracking-wider text-muted-foreground">
                  Combat log
                </div>
                <div className="mt-2 max-h-[42vh] overflow-y-auto overscroll-contain rounded-sm border border-white/10 bg-black/25 p-2 sm:p-2.5">
                  {logLines.length ? (
                    <ul className="space-y-2 text-[12.5px] leading-relaxed text-foreground/85 sm:text-[13px]">
                      {logLines.map((l, i) => (
                        <li
                          key={i}
                          className="rounded-sm border border-white/5 bg-black/10 px-2 py-1.5"
                        >
                          {renderLineWithIcons(l)}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[12px] text-muted-foreground">No log lines.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </WomPanel>
      </div>
    );
  }

  // Fighting screen — same combat engine as Discord /fight (real skills + stats)
  if (mode === "fight" && state) {
    return (
      <div
        className={cn(
          "w-full min-w-0",
          focusMode ? "flex h-full min-h-0 flex-col gap-2 -mt-2 pt-0 sm:-mt-3" : "space-y-4",
        )}
      >
        {showSubModeToggle && modeSegment}
        <CombatEncounterView
          focusMode={focusMode}
          zoneLabel={zoneLabel}
          battleZoneOverride={map?.current_zone}
          state={state}
          inventory={inventory}
          loading={loading}
          onAbility={onAbility}
          onFlee={onFlee}
          onPotion={onPotion}
          showDiscordDungeonBanner={Boolean(state.in_dungeon)}
          enemyKey={activeEnemy?.key || undefined}
          enemyKind={activeEnemy?.kind || undefined}
          presentation="battle-preview"
        />
      </div>
    );
  }

  // Idle / pick screen (Lovable style)
  return (
    <div className="w-full min-w-0">
      {showSubModeToggle && modeSegment}
      <WomPanel glow className="w-full">
      <div className="game-panel-header">Choose an Enemy</div>
      {previewingRemoteZone ? (
        <div className="mb-3 rounded-sm border border-amber-500/40 bg-amber-950/25 px-2 py-2 text-[10px] leading-snug text-amber-50">
          <span className="font-semibold text-amber-100">Previewing another zone.</span>{" "}
          You are still in {currentTravelZone ? `${currentTravelZone.emoji} ${currentTravelZone.name}` : "your current zone"}. Use{" "}
          <span className="font-medium text-foreground/90">Explore</span> (or Discord) to go there and fight these foes, or switch this list
          back to your zone below.
        </div>
      ) : null}
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-stretch">
        <label className="sr-only" htmlFor="combat-foes-list-zone">
          Zone to list foes for
        </label>
        <select
          id="combat-foes-list-zone"
          className="game-select flex-1 min-w-0"
          value={foesListZoneId || curZone || travelZones[0]?.id || ""}
          onChange={(e) => {
            const v = e.target.value;
            setFoesListZoneId(v);
            void refresh({ enemiesZoneKey: v });
          }}
          aria-label="Zone to list foes for"
        >
          {travelZones.map((z) => (
            <option key={z.id} value={z.id}>
              {z.emoji} {z.name} (Lv {z.levelMin}–{z.levelMax})
            </option>
          ))}
        </select>
        {previewingRemoteZone && curZone ? (
          <button
            type="button"
            className="game-btn-secondary shrink-0 px-3 text-[11px]"
            onClick={() => {
              setFoesListZoneId(curZone);
              void refresh({ enemiesZoneKey: curZone });
            }}
            disabled={loading}
          >
            My zone
          </button>
        ) : null}
      </div>
      <p className="mb-3 text-[10px] text-muted-foreground px-0.5">
        {browseZoneLabel ? (
          <>
            Listing <span className="text-foreground/90 font-medium">{browseZoneLabel.emoji} {browseZoneLabel.name}</span>
            {!previewingRemoteZone ? " — you can start combat here." : " — catalog only until you are in this zone."}
          </>
        ) : null}
      </p>
      {enemies.length === 0 ? (
        <p className="text-xs text-muted-foreground">No enemies in this zone — pick another zone above or create a character.</p>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-3 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:items-stretch lg:gap-4">
            {/* List first on mobile (thumb-first scanning) */}
            <div className="order-1 flex min-h-0 max-h-[min(52vh,380px)] flex-col rounded-sm border border-white/10 bg-black/15 lg:max-h-[min(60vh,440px)]">
              <div className="shrink-0 border-b border-white/10 px-2 py-1.5 text-[10px] font-cinzel font-semibold uppercase tracking-wider text-muted-foreground">
                Foes in zone
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-1.5">
                {bossEnemies.length > 0 && (
                  <div className="mb-2">
                    <div className="px-1.5 py-1 text-[9px] font-semibold uppercase tracking-wider text-boss-purple/90">
                      Bosses
                    </div>
                    <div className="flex flex-col gap-1">
                      {bossEnemies.map((e) => {
                        const selected = e.key === enemyPick;
                        const src = enemyPortraitSrc(e.key, e.kind);
                        const risk = riskTierPresentation(e.risk_tier);
                        return (
                          <button
                            key={e.key}
                            type="button"
                            onClick={() => setEnemyPick(e.key)}
                            aria-pressed={selected}
                            aria-current={selected ? "true" : undefined}
                            className={`flex w-full items-center gap-2 rounded-sm px-1.5 py-1.5 text-left transition-colors ${
                              selected
                                ? "bg-boss-purple/15 ring-1 ring-boss-purple/50"
                                : "hover:bg-white/5"
                            }`}
                          >
                            <span className="relative h-10 w-10 shrink-0 overflow-hidden rounded-sm border border-white/10 bg-black/30">
                              <span className="pointer-events-none absolute inset-0 z-0 flex items-center justify-center text-lg">
                                {e.emoji}
                              </span>
                              {src ? (
                                <img
                                  src={src}
                                  alt=""
                                  className="absolute inset-0 z-10 h-full w-full object-cover object-center"
                                  onError={(ev) => {
                                    (ev.currentTarget as HTMLImageElement).style.display = "none";
                                  }}
                                />
                              ) : null}
                            </span>
                            <span
                              className={cn("mt-1.5 h-2 w-2 shrink-0 self-start rounded-full", risk.dotClass)}
                              title={risk.label}
                              aria-hidden
                            />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-xs font-semibold text-foreground">{e.name}</span>
                              <span className="text-[10px] text-boss-purple/90">
                                Boss
                                {e.max_hp != null ? (
                                  <span className="ml-1.5 tabular-nums text-muted-foreground">· {e.max_hp} HP</span>
                                ) : null}
                              </span>
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
                {normalEnemies.length > 0 && (
                  <div>
                    <div className="px-1.5 py-1 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Enemies
                    </div>
                    <div className="flex flex-col gap-1">
                      {normalEnemies.map((e) => {
                        const selected = e.key === enemyPick;
                        const src = enemyPortraitSrc(e.key, e.kind);
                        const risk = riskTierPresentation(e.risk_tier);
                        return (
                          <button
                            key={e.key}
                            type="button"
                            onClick={() => setEnemyPick(e.key)}
                            aria-pressed={selected}
                            aria-current={selected ? "true" : undefined}
                            className={`flex w-full items-center gap-2 rounded-sm px-1.5 py-1.5 text-left transition-colors ${
                              selected ? "bg-primary/10 ring-1 ring-primary/45" : "hover:bg-white/5"
                            }`}
                          >
                            <span className="relative h-10 w-10 shrink-0 overflow-hidden rounded-sm border border-white/10 bg-black/30">
                              <span className="pointer-events-none absolute inset-0 z-0 flex items-center justify-center text-lg">
                                {e.emoji}
                              </span>
                              {src ? (
                                <img
                                  src={src}
                                  alt=""
                                  className="absolute inset-0 z-10 h-full w-full object-cover object-center"
                                  onError={(ev) => {
                                    (ev.currentTarget as HTMLImageElement).style.display = "none";
                                  }}
                                />
                              ) : null}
                            </span>
                            <span
                              className={cn("mt-1.5 h-2 w-2 shrink-0 self-start rounded-full", risk.dotClass)}
                              title={risk.label}
                              aria-hidden
                            />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-xs font-semibold text-foreground">{e.name}</span>
                              <span className="text-[10px] capitalize text-muted-foreground">
                                {e.kind}
                                {e.max_hp != null ? (
                                  <span className="ml-1.5 tabular-nums">· {e.max_hp} HP</span>
                                ) : null}
                              </span>
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="order-2 flex min-h-0 flex-col gap-2">
              <div className="flex min-h-0 flex-1 flex-col gap-3 rounded-sm border border-white/10 bg-black/20 p-2 sm:p-3 lg:flex-row lg:items-stretch">
                <div className="flex shrink-0 flex-row gap-2 sm:gap-3 lg:w-[124px] lg:flex-col lg:justify-center lg:border-r lg:border-white/10 lg:pr-3">
                  <button
                    type="button"
                    onClick={() => void onStart()}
                    disabled={loading || !enemyPick || previewingRemoteZone}
                    className="game-btn-danger flex-1 lg:flex-none lg:w-full"
                  >
                    Start Combat
                  </button>
                  <button
                    type="button"
                    onClick={() => void onRest()}
                    disabled={loading}
                    className="game-btn-secondary flex-1 lg:flex-none lg:w-full"
                  >
                    Rest
                  </button>
                </div>
                <div className="flex min-h-0 flex-1 flex-col">
              <div className="text-[10px] font-cinzel font-semibold uppercase tracking-wider text-muted-foreground">
                Preview
              </div>
                {selectedEnemy ? (
                  <>
                    <div className="mt-1 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-serif text-sm font-semibold text-foreground">
                          <span className="mr-1.5">{selectedEnemy.emoji}</span>
                          {selectedEnemy.name}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          {isBossKind(selectedEnemy.kind) ? "World boss — high risk, high reward." : "Zone enemy — standard encounter."}
                        </p>
                        {combatEnemiesMeta?.zone_level_min != null && combatEnemiesMeta?.zone_level_max != null && (
                          <p className="mt-0.5 text-[10px] text-muted-foreground/90">
                            Zone band: Lv {combatEnemiesMeta.zone_level_min}–{combatEnemiesMeta.zone_level_max}
                            {typeof combatEnemiesMeta.character_level === "number"
                              ? ` · You: Lv ${combatEnemiesMeta.character_level}`
                              : null}
                          </p>
                        )}
                        <div
                          className={cn(
                            "mt-2 rounded-sm border px-2 py-1.5 text-[10px] leading-snug",
                            selectedRisk.panelClass,
                          )}
                        >
                          {selectedRisk.label}
                        </div>
                        <div className="mt-2 space-y-1 text-[10px] text-muted-foreground">
                          <div className="flex justify-between gap-2">
                            <span>Foe max HP</span>
                            <span className="font-semibold tabular-nums text-foreground">
                              {selectedEnemy.max_hp != null ? selectedEnemy.max_hp : "—"}
                            </span>
                          </div>
                          {inventory?.character?.max_hp != null ? (
                            <div className="flex justify-between gap-2">
                              <span>Your max HP</span>
                              <span className="tabular-nums text-foreground/90">{inventory.character.max_hp}</span>
                            </div>
                          ) : null}
                        </div>
                        {previewingRemoteZone ? (
                          <p className="mt-1.5 text-[10px] text-amber-200/90">
                            Go to this zone from Explore (or Discord) to unlock Start Combat for these foes.
                          </p>
                        ) : null}
                        {hpRatioNote ? (
                          <p className="mt-1.5 text-[10px] text-amber-200/90">{hpRatioNote}</p>
                        ) : null}
                      </div>
                    </div>
                    <div className="relative mx-auto mt-2 aspect-[3/4] w-full max-w-[220px] overflow-hidden rounded-sm border border-white/15 bg-black/35 shadow-[0_12px_40px_-10px_rgba(0,0,0,0.75)]">
                      <span className="pointer-events-none absolute inset-0 z-0 flex items-center justify-center text-5xl opacity-40">
                        {selectedEnemy.emoji}
                      </span>
                      <img
                        src={enemyPortraitSrc(selectedEnemy.key, selectedEnemy.kind)}
                        alt=""
                        className="absolute inset-0 z-10 h-full w-full object-contain object-bottom"
                        style={{ objectPosition: "center bottom" }}
                        onError={(ev) => {
                          (ev.currentTarget as HTMLImageElement).style.display = "none";
                        }}
                      />
                      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 h-1/4 bg-gradient-to-t from-black/55 to-transparent" />
                    </div>
                  </>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">Select a foe from the list.</p>
                )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      </WomPanel>
    </div>
  );
}
