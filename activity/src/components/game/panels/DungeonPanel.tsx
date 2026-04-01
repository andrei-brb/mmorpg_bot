import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CombatEncounterView } from "@/components/game/CombatEncounterView";
import { useGameSession } from "@/context/GameSessionContext";
import type { CombatStatePayload, DungeonCatalogEntry, DungeonPartyStatus, DungeonParticipant } from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
}

type RunState = { dungeon: DungeonCatalogEntry; floor: number };

export type DungeonPanelProps = {
  playerLevel?: number;
};

export function DungeonPanel({ playerLevel = 1 }: DungeonPanelProps) {
  const { accessToken, guildId, inventory, loadCombatSnapshot, startCombat, combatAction, refreshInventory, refreshProgress } =
    useGameSession();

  const [catalog, setCatalog] = useState<DungeonCatalogEntry[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [run, setRun] = useState<RunState | null>(null);
  const [combatState, setCombatState] = useState<CombatStatePayload | null>(null);
  const [outcome, setOutcome] = useState<{ title?: string; lines?: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState<"browser" | "run" | "fight" | "complete" | "failed">("browser");
  
  // Party state
  const [partyStatus, setPartyStatus] = useState<DungeonPartyStatus | null>(null);
  const [partyLoading, setPartyLoading] = useState(false);
  const [inviteUserId, setInviteUserId] = useState<string>("");

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    setCatalogLoading(true);
    void api
      .getDungeons(accessToken, guildId)
      .then((j) => {
        if (cancelled) return;
        setCatalog(j.dungeons || []);
      })
      .catch(() => {
        if (cancelled) return;
        setCatalog([]);
        toast.error("Could not load dungeons.");
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId]);

  // Load party status on mount and when phase changes
  useEffect(() => {
    if (!accessToken || phase !== "browser") return;
    let cancelled = false;
    void api
      .getDungeonPartyStatus(accessToken, guildId)
      .then((status) => {
        if (cancelled) return;
        setPartyStatus(status);
      })
      .catch(() => {
        if (cancelled) return;
        setPartyStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId, phase]);

  const resetAll = useCallback(() => {
    setRun(null);
    setCombatState(null);
    setOutcome(null);
    setPhase("browser");
  }, []);

  // Refresh party status
  const refreshPartyStatus = useCallback(async () => {
    if (!accessToken) return;
    try {
      const status = await api.getDungeonPartyStatus(accessToken, guildId);
      setPartyStatus(status);
    } catch (e) {
      setPartyStatus(null);
    }
  }, [accessToken, guildId]);

  // Create party
  const onCreateParty = async (d: DungeonCatalogEntry) => {
    if (!accessToken) return;
    setPartyLoading(true);
    try {
      const result = await api.postDungeonPartyCreate(accessToken, d.key, guildId);
      if (result.ok && result.run_id) {
        setPartyStatus({ in_party: true, run_id: result.run_id, is_leader: true, dungeon_key: d.key, participants: result.participants });
        toast.success(`Party created for ${d.name}! Invite members or start when ready.`);
        await refreshPartyStatus();
      } else {
        toast.error(result.message || "Failed to create party.");
      }
    } catch (e) {
      toast.error("Failed to create party.");
    } finally {
      setPartyLoading(false);
    }
  };

  // Invite player
  const onInvitePlayer = async () => {
    if (!accessToken || !partyStatus?.run_id || !inviteUserId.trim()) return;
    setPartyLoading(true);
    try {
      const result = await api.postDungeonPartyInvite(accessToken, inviteUserId.trim(), guildId);
      if (result.ok) {
        toast.success(result.message || "Player invited!");
        setInviteUserId("");
        await refreshPartyStatus();
      } else {
        toast.error(result.message || "Failed to invite player.");
      }
    } catch (e) {
      toast.error("Failed to invite player.");
    } finally {
      setPartyLoading(false);
    }
  };

  // Leave party
  const onLeaveParty = async () => {
    if (!accessToken) return;
    setPartyLoading(true);
    try {
      const result = await api.postDungeonPartyLeave(accessToken, guildId);
      if (result.ok) {
        toast.success("Left the party.");
        setPartyStatus({ in_party: false });
        await refreshPartyStatus();
      } else {
        toast.error(result.message || "Failed to leave party.");
      }
    } catch (e) {
      toast.error("Failed to leave party.");
    } finally {
      setPartyLoading(false);
    }
  };

  // Resume Activity dungeon combat if the server still has an active session
  useEffect(() => {
    if (!catalog.length) return;
    let cancelled = false;
    void (async () => {
      const snap = await loadCombatSnapshot();
      if (cancelled) return;
      const st = snap.state;
      if (!snap.active || !st?.dungeon_key || st.dungeon_floor == null) return;
      const d = catalog.find((x) => x.key === st.dungeon_key);
      if (!d) return;
      setRun({ dungeon: d, floor: st.dungeon_floor });
      setCombatState(st);
      setPhase("fight");
    })();
    return () => {
      cancelled = true;
    };
  }, [catalog, loadCombatSnapshot]);

  const enterSolo = (d: DungeonCatalogEntry) => {
    setRun({ dungeon: d, floor: 1 });
    setPhase("run");
    toast(`Entering ${d.name}…`, { description: `${d.floors} floors — fight each floor with your real skills.` });
  };

  const startFloorFight = async () => {
    if (!run) return;
    setLoading(true);
    try {
      const r = await startCombat({ kind: "dungeon", dungeonKey: run.dungeon.key, floor: run.floor });
      if (r.state) {
        setCombatState(r.state);
        setPhase("fight");
        return;
      }
      toast.error(r.message || "Could not start combat");
    } finally {
      setLoading(false);
    }
  };

  const onAbility = async (key: string) => {
    setLoading(true);
    try {
      const json = await combatAction({ ability: key });
      if (json.ended && json.outcome) {
        setCombatState(null);
        const t = json.outcome.type;
        if (t === "victory") {
          await refreshInventory();
          await refreshProgress();
          setRun((prev) => {
            if (!prev) return prev;
            const f = prev.floor;
            if (f >= prev.dungeon.floors) {
              setOutcome({ title: json.outcome?.title, lines: json.outcome?.lines });
              setPhase("complete");
              return prev;
            }
            toast.success(`Floor ${f} cleared!`);
            setPhase("run");
            return { ...prev, floor: f + 1 };
          });
          return;
        }
        if (t === "flee") {
          await refreshInventory();
          await refreshProgress();
          resetAll();
          return;
        }
        setOutcome({ title: json.outcome.title, lines: json.outcome.lines });
        setPhase("failed");
        await refreshInventory();
        await refreshProgress();
        return;
      }
      if (json.state) setCombatState(json.state);
    } finally {
      setLoading(false);
    }
  };

  const onFlee = async () => {
    setLoading(true);
    try {
      const json = await combatAction({ flee: true });
      if (json.ended && json.outcome) {
        setCombatState(null);
        await refreshInventory();
        await refreshProgress();
        resetAll();
        toast.info("You left the encounter.");
        return;
      }
      if (json.state) setCombatState(json.state);
    } finally {
      setLoading(false);
    }
  };

  const onPotion = async () => {
    setLoading(true);
    try {
      const json = await combatAction({ potion: true });
      if (json.state) setCombatState(json.state);
    } finally {
      setLoading(false);
    }
  };

  if (phase === "fight" && combatState && run) {
    return (
      <CombatEncounterView
        dungeonHeader={{
          emoji: run.dungeon.emoji,
          name: run.dungeon.name,
          floor: run.floor,
          totalFloors: run.dungeon.floors,
        }}
        state={combatState}
        inventory={inventory}
        loading={loading}
        onAbility={onAbility}
        onFlee={onFlee}
        onPotion={onPotion}
      />
    );
  }

  if (phase === "complete" && outcome && run) {
    return (
      <div className="space-y-4">
        <div className="game-panel text-center py-8">
          <div className="text-5xl mb-4" style={{ filter: "drop-shadow(0 2px 6px hsl(0 0% 0% / 0.6))" }}>🏆</div>
          <h2
            className="font-cinzel text-xl font-bold text-foreground mb-1"
            style={{ textShadow: "0 0 8px hsl(43 78% 50% / 0.3)" }}
          >
            {run.dungeon.emoji} {run.dungeon.name} complete!
          </h2>
          <p className="text-sm text-muted-foreground mb-2">Rewards are applied from the server (XP, gold, loot).</p>
          <div className="ornament-divider my-3 mx-auto max-w-[200px]" />
          <ul className="text-xs text-muted-foreground space-y-1 text-left max-w-xs mx-auto mb-4">
            {(outcome.lines || []).map((l, i) => (
              <li key={i}>{stripMd(l)}</li>
            ))}
          </ul>
          <button type="button" onClick={resetAll} className="game-btn-primary px-6 py-2">
            Back to dungeons
          </button>
        </div>
      </div>
    );
  }

  if (phase === "failed" && outcome) {
    return (
      <div className="space-y-4">
        <div className="game-panel text-center py-8">
          <div className="text-5xl mb-4" style={{ filter: "drop-shadow(0 2px 6px hsl(0 0% 0% / 0.6))" }}>💀</div>
          <h2 className="font-cinzel text-xl font-bold text-foreground mb-1">{outcome.title || "Defeated"}</h2>
          <ul className="text-xs text-muted-foreground space-y-1 text-left max-w-xs mx-auto mb-4">
            {(outcome.lines || []).map((l, i) => (
              <li key={i}>{stripMd(l)}</li>
            ))}
          </ul>
          <button type="button" onClick={resetAll} className="game-btn-primary px-5 py-2">
            Back to dungeons
          </button>
        </div>
      </div>
    );
  }

  if (phase === "run" && run) {
    const preview = run.dungeon.floor_preview.find((p) => p.floor === run.floor);
    const isBossFloor = preview?.is_boss ?? run.floor === run.dungeon.floors;

    return (
      <div className="space-y-4">
        <div className="game-panel">
          <div className="game-panel-header">
            {run.dungeon.emoji} {run.dungeon.name} — Floor {run.floor}/{run.dungeon.floors}
          </div>
          <p className="text-xs text-muted-foreground mb-3">
            Uses the same combat engine as Overworld: your class skills, stats, and potions. You must be in a valid zone on
            the map (travel in Explore if needed).
          </p>
          <div className="flex items-center gap-1 mb-4 flex-wrap">
            {Array.from({ length: run.dungeon.floors }).map((_, i) => (
              <div
                key={i}
                className={`w-6 h-6 rounded-sm border text-[10px] flex items-center justify-center font-pixel ${
                  i < run.floor - 1
                    ? "border-primary/60 bg-primary/20 text-primary"
                    : i === run.floor - 1
                      ? "border-primary bg-primary/30 text-primary ring-1 ring-primary/40"
                      : "border-border bg-muted/30 text-muted-foreground"
                }`}
              >
                {i + 1}
              </div>
            ))}
            <span className="text-[10px] text-muted-foreground ml-2 font-cinzel">
              {isBossFloor ? "⭐ Boss floor" : `Trash`}
            </span>
          </div>

          {preview && (
            <div className="mb-4">
              <p className="text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground mb-1">This encounter</p>
              <p className={`text-sm font-cinzel font-semibold ${isBossFloor ? "text-destructive" : "text-foreground"}`}>
                {preview.emoji} {preview.name}
              </p>
            </div>
          )}

          <div className="flex gap-2 flex-wrap">
            <button type="button" onClick={() => void startFloorFight()} disabled={loading} className="game-btn-danger text-xs px-4 py-2 flex-1 min-w-[140px]">
              ⚔️ {isBossFloor ? "Fight boss" : `Fight floor ${run.floor}`}
            </button>
            <button type="button" onClick={resetAll} disabled={loading} className="game-btn-secondary text-xs px-4 py-2">
              Leave
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (catalogLoading) {
    return <p className="text-sm text-muted-foreground">Loading dungeons…</p>;
  }

  return (
    <div className="space-y-4">
      {/* Party Panel */}
      {partyStatus?.in_party && (
        <div className="game-panel">
          <div className="game-panel-header">
            🏰 Dungeon Party {partyStatus.is_leader && "(Leader)"}
          </div>
          <div className="mb-3">
            <p className="text-xs text-muted-foreground mb-2">
              Dungeon: <span className="text-foreground font-semibold">{partyStatus.dungeon_key}</span>
            </p>
            <p className="text-xs text-muted-foreground mb-3">
              Members: <span className="text-foreground font-semibold">{partyStatus.participants?.length || 0}/{5}</span>
            </p>
            
            <div className="space-y-1 mb-3">
              {(partyStatus.participants || []).map((p, i) => (
                <div key={i} className="text-xs flex items-center gap-2">
                  <span className={p.role === "leader" ? "text-primary font-semibold" : "text-muted-foreground"}>
                    {p.role === "leader" ? "👑 " : "• "} {p.name} (Lv {p.level})
                  </span>
                </div>
              ))}
            </div>

            {partyStatus.is_leader && (
              <div className="space-y-2 mb-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="User ID to invite..."
                    value={inviteUserId}
                    onChange={(e) => setInviteUserId(e.target.value)}
                    className="flex-1 bg-muted/30 border border-border rounded px-2 py-1 text-xs text-foreground"
                  />
                  <button
                    type="button"
                    onClick={onInvitePlayer}
                    disabled={partyLoading || !inviteUserId.trim()}
                    className="game-btn-primary text-xs px-3 py-1 disabled:opacity-50"
                  >
                    Invite
                  </button>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  💡 To get User ID: Enable Developer Mode in Discord → Right-click user → Copy ID
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={onLeaveParty}
              disabled={partyLoading}
              className="game-btn-secondary text-xs px-4 py-2 w-full"
            >
              Leave Party
            </button>
          </div>
        </div>
      )}

      <div className="game-panel">
        <div className="game-panel-header">⚔️ Dungeons</div>
        <p className="text-xs text-muted-foreground mb-4">
          Server-driven runs — enemies match <code className="text-[10px]">/dungeon</code> in Discord. Requires a valid map
          zone (use Explore to travel).
        </p>

        <div className="space-y-3">
          {catalog.map((d) => {
            const locked = playerLevel < d.level_req;
            return (
              <div
                key={d.key}
                className={`rounded-sm transition-all ${locked ? "opacity-50" : ""}`}
                style={{
                  background: locked
                    ? "linear-gradient(180deg, hsl(228 18% 10%) 0%, hsl(228 20% 8%) 100%)"
                    : "linear-gradient(180deg, hsl(228 18% 14%) 0%, hsl(228 20% 10%) 100%)",
                  border: locked ? "1px solid hsl(228 16% 16%)" : "1px solid hsl(43 50% 35% / 0.4)",
                  boxShadow: locked ? "none" : "0 0 8px hsl(43 78% 50% / 0.05)",
                }}
              >
                <div className="p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg" style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.5))" }}>
                          {d.emoji}
                        </span>
                        <h3 className="font-cinzel font-semibold text-sm text-foreground truncate">{d.name}</h3>
                        {locked && <span className="text-[10px] text-destructive font-pixel shrink-0">🔒 LOCKED</span>}
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{d.description}</p>
                      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px]">
                        <span className="text-muted-foreground">
                          Lv <span className="text-foreground font-semibold">{d.level_req}+</span>
                        </span>
                        <span className="text-muted-foreground">
                          Floors <span className="text-foreground font-semibold">{d.floors}</span>
                        </span>
                        <span className="text-muted-foreground">
                          XP <span className="text-primary font-semibold">~{d.xp_per_floor}/floor</span>
                        </span>
                        <span className="text-muted-foreground">
                          Gold{" "}
                          <span className="text-primary font-semibold">
                            {d.gold_min}–{d.gold_max} 🪙/floor
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2 mt-3">
                    <button
                      type="button"
                      onClick={() => enterSolo(d)}
                      disabled={locked || partyStatus?.in_party}
                      className={`text-xs px-3 py-1.5 flex-1 ${locked || partyStatus?.in_party ? "game-btn-secondary opacity-50 cursor-not-allowed" : "game-btn-primary"}`}
                    >
                      ⚔️ Enter solo
                    </button>
                    <button
                      type="button"
                      onClick={() => onCreateParty(d)}
                      disabled={locked || partyStatus?.in_party || partyLoading}
                      className={`text-xs px-3 py-1.5 flex-1 ${locked || partyStatus?.in_party ? "game-btn-secondary opacity-50 cursor-not-allowed" : "game-btn-secondary"}`}
                    >
                      👥 {partyStatus?.in_party ? "In Party" : "Create Party"}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
