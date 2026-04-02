import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CombatEncounterView } from "@/components/game/CombatEncounterView";
import { useGameSession } from "@/context/GameSessionContext";
import type { CombatStatePayload, DungeonCatalogEntry, DungeonPartyStatus, DungeonParticipant, DungeonPartyInvite } from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";
import type { CombatActionJson } from "@/lib/gameApi";

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
}

type RunState = { dungeon: DungeonCatalogEntry; floor: number };

/** Merge catalog + combat payload so `dungeon.floors` is never `current_floor` (that broke multi-floor victory → floor 2). */
function runStateFromDungeonCombat(
  catalog: DungeonCatalogEntry[],
  st: CombatStatePayload,
): RunState | null {
  if (st.dungeon_key == null || st.dungeon_floor == null) return null;
  const floor = st.dungeon_floor;
  const dk = st.dungeon_key;
  const d = catalog.find((x) => x.key === dk);
  const totalFloors = st.dungeon_total_floors ?? d?.floors ?? Math.max(floor, 1);
  const dungeon: DungeonCatalogEntry = d
    ? { ...d, floors: totalFloors }
    : {
        key: dk,
        name: dk,
        emoji: "⚔️",
        description: "",
        level_req: 1,
        floors: totalFloors,
        xp_per_floor: 0,
        gold_min: 0,
        gold_max: 0,
        floor_preview: [],
      };
  return { dungeon, floor };
}

export type DungeonPanelProps = {
  playerLevel?: number;
};

export function DungeonPanel({ playerLevel = 1 }: DungeonPanelProps) {
  const {
    accessToken,
    guildId,
    inventory,
    loadCombatSnapshot,
    startCombat,
    combatAction,
    refreshInventory,
    refreshProgress,
  } = useGameSession();

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
  const [inviteUsername, setInviteUsername] = useState<string>("");
  const [playerSuggestions, setPlayerSuggestions] = useState<Array<{ id: string; username: string; level: number; class: string }>>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  
  // Incoming invites state
  const [incomingInvites, setIncomingInvites] = useState<DungeonPartyInvite[]>([]);
  const [invitesLoading, setInvitesLoading] = useState(false);

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

  const applyEndedOutcome = useCallback(
    async (json: CombatActionJson) => {
      if (!json.ended || !json.outcome) return;
      try {
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
          toast.info("You left the encounter.");
          return;
        }
        setOutcome({ title: json.outcome.title, lines: json.outcome.lines });
        setPhase("failed");
        await refreshInventory();
        await refreshProgress();
      } finally {
        if (accessToken) await api.postCombatStateAck(accessToken, guildId);
      }
    },
    [accessToken, guildId, refreshInventory, refreshProgress, resetAll],
  );

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

  // Fetch player suggestions for invite autocomplete
  const fetchPlayerSuggestions = useCallback(async (query: string) => {
    if (!accessToken || query.length < 1) {
      setPlayerSuggestions([]);
      return;
    }
    try {
      const data = await api.getDungeonPartyPlayers(accessToken, query, guildId);
      setPlayerSuggestions(data.players || []);
    } catch (e) {
      console.error("Failed to fetch player suggestions:", e);
      setPlayerSuggestions([]);
    }
  }, [accessToken, guildId]);

  // Fetch incoming invites
  const fetchIncomingInvites = useCallback(async () => {
    if (!accessToken || phase !== "browser") return;
    setInvitesLoading(true);
    try {
      const data = await api.getDungeonPartyInvites(accessToken, guildId);
      setIncomingInvites(data.invites || []);
    } catch (e) {
      console.error("Failed to fetch invites:", e);
    } finally {
      setInvitesLoading(false);
    }
  }, [accessToken, guildId, phase]);

  // Load incoming invites on mount and when phase changes
  useEffect(() => {
    if (!accessToken || phase !== "browser") return;
    fetchIncomingInvites();
  }, [accessToken, guildId, phase, fetchIncomingInvites]);

  // Poll party + invites — REST only (no WebSocket), so leaders see new members without reloading
  useEffect(() => {
    if (!accessToken || phase !== "browser") return;
    const id = window.setInterval(() => {
      void refreshPartyStatus();
      void fetchIncomingInvites();
    }, 3000);
    return () => window.clearInterval(id);
  }, [accessToken, phase, refreshPartyStatus, fetchIncomingInvites]);

  // Accept invite
  const onAcceptInvite = useCallback(async (inviteId: string) => {
    if (!accessToken) return;
    setPartyLoading(true);
    try {
      const result = await api.postDungeonPartyInviteAccept(accessToken, inviteId, guildId);
      if (result.ok) {
        toast.success("Joined the party!");
        setPartyStatus({ in_party: true, run_id: result.run_id, is_leader: false, participants: result.participants });
        fetchIncomingInvites(); // Refresh invites
      } else {
        toast.error(result.message || "Failed to accept invite.");
      }
    } catch (e) {
      toast.error("Failed to accept invite.");
    } finally {
      setPartyLoading(false);
    }
  }, [accessToken, guildId, fetchIncomingInvites]);

  // Decline invite
  const onDeclineInvite = useCallback(async (inviteId: string) => {
    if (!accessToken) return;
    try {
      await api.postDungeonPartyInviteDecline(accessToken, inviteId, guildId);
      toast.success("Invite declined.");
      fetchIncomingInvites(); // Refresh invites
    } catch (e) {
      toast.error("Failed to decline invite.");
    }
  }, [accessToken, guildId, fetchIncomingInvites]);

  // Enter dungeon (party mode) — server starts Activity combat; we must mirror solo flow and set local fight UI
  const onEnterDungeon = useCallback(async () => {
    if (!accessToken) return;
    setPartyLoading(true);
    try {
      const result = await api.postDungeonPartyEnter(accessToken, guildId);
      if (result.state) {
        toast.success("Entering dungeon…");
        const st = result.state;
        const pair = runStateFromDungeonCombat(catalog, st);
        if (pair) setRun(pair);
        setCombatState(st);
        setPhase("fight");
      } else {
        toast.error(result.message || result.error || "Failed to enter dungeon.");
      }
    } catch (e) {
      toast.error("Failed to enter dungeon.");
    } finally {
      setPartyLoading(false);
    }
  }, [accessToken, guildId, catalog]);

  // Leave dungeon (reset combat status)
  const onLeaveDungeon = useCallback(async () => {
    if (!accessToken) return;
    setPartyLoading(true);
    try {
      // Call rest endpoint to clear combat status
      await api.postRest(accessToken, guildId);
      toast.success("Left dungeon and resting.");
      // Reset local state
      setRun(null);
      setCombatState(null);
      setPhase("browser");
    } catch (e) {
      toast.error("Failed to leave dungeon.");
    } finally {
      setPartyLoading(false);
    }
  }, [accessToken, guildId]);

  // Create party
  const onCreateParty = async (d: DungeonCatalogEntry) => {
    if (!accessToken) return;
    setPartyLoading(true);
    try {
      const result = await api.postDungeonPartyCreate(accessToken, d.key, guildId);
      if (result.ok && result.run_id) {
        // Set party status directly from create response (we ARE the leader)
        setPartyStatus({ 
          in_party: true, 
          run_id: result.run_id, 
          is_leader: true, 
          dungeon_key: d.key, 
          participants: result.participants 
        });
        toast.success(`Party created for ${d.name}! Invite members or start when ready.`);
        // Don't refresh immediately - we already have the correct status
      } else {
        toast.error(result.message || "Failed to create party.");
      }
    } catch (e) {
      console.error("Failed to create party:", e);
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
        setInviteUsername("");
        setPlayerSuggestions([]);
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

  const handleInviteInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInviteUsername(value);
    if (value.startsWith("@")) {
      fetchPlayerSuggestions(value.slice(1));
      setShowSuggestions(true);
    } else {
      setPlayerSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const selectPlayer = (player: { id: string; username: string }) => {
    setInviteUserId(player.id);
    setInviteUsername(`@${player.username}`);
    setShowSuggestions(false);
    setPlayerSuggestions([]);
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
      if (snap.ended_outcome) {
        await applyEndedOutcome(snap.ended_outcome);
        return;
      }
      const st = snap.state;
      if (!snap.active || !st?.dungeon_key || st.dungeon_floor == null) return;
      const pair = runStateFromDungeonCombat(catalog, st);
      if (!pair) return;
      setRun(pair);
      setCombatState(st);
      setPhase("fight");
    })();
    return () => {
      cancelled = true;
    };
  }, [catalog, loadCombatSnapshot, applyEndedOutcome]);

  // Party members: poll until leader starts shared combat (leader POSTs enter; members GET state)
  useEffect(() => {
    if (!accessToken) return;
    if (phase === "fight" || phase === "complete" || phase === "failed") return;
    if (!partyStatus?.in_party || partyStatus.is_leader) return;
    if ((partyStatus.participants?.length || 0) < 2) return;

    const id = setInterval(() => {
      void (async () => {
        const snap = await loadCombatSnapshot();
        if (snap.ended_outcome) {
          await applyEndedOutcome(snap.ended_outcome);
          return;
        }
        if (snap.active && snap.state?.dungeon_key != null && snap.state.dungeon_floor != null) {
          const st = snap.state;
          const pair = runStateFromDungeonCombat(catalog, st);
          if (pair) setRun(pair);
          setCombatState(st);
          setPhase("fight");
        }
      })();
    }, 2500);
    return () => clearInterval(id);
  }, [accessToken, phase, partyStatus, catalog, loadCombatSnapshot, applyEndedOutcome]);

  // While in a shared party fight, continuously refresh snapshot so both clients
  // see turn changes, abilities, and action availability without manual actions.
  useEffect(() => {
    if (!accessToken) return;
    if (phase !== "fight") return;
    if (!combatState?.party_mode) return;

    const id = setInterval(() => {
      void (async () => {
        const snap = await loadCombatSnapshot();
        if (snap.ended_outcome) {
          await applyEndedOutcome(snap.ended_outcome);
          return;
        }
        if (snap.active && snap.state) {
          setCombatState((prev) => {
            if (!prev) return snap.state;
            // Avoid unnecessary rerenders if server state is unchanged.
            const prevJson = JSON.stringify(prev);
            const nextJson = JSON.stringify(snap.state);
            return prevJson === nextJson ? prev : snap.state;
          });
        }
      })();
    }, 1200);

    return () => clearInterval(id);
  }, [accessToken, phase, combatState?.party_mode, loadCombatSnapshot, applyEndedOutcome]);

  const partyBlocksSoloDungeon =
    Boolean(partyStatus?.in_party) && (partyStatus?.participants?.length || 0) >= 2;

  const enterSolo = (d: DungeonCatalogEntry) => {
    if (partyBlocksSoloDungeon) {
      toast.error("You're in a party with 2+ players. Use the leader's Enter Dungeon — do not start a solo run.");
      return;
    }
    setRun({ dungeon: d, floor: 1 });
    setPhase("run");
    toast(`Entering ${d.name}…`, { description: `${d.floors} floors — fight each floor with your real skills.` });
  };

  const startFloorFight = async () => {
    if (!run) return;
    if (partyBlocksSoloDungeon) {
      toast.error("Party mode: the leader must start from Enter Dungeon above — this button would start a separate fight.");
      return;
    }
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
        await applyEndedOutcome(json);
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
        await applyEndedOutcome(json);
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
    const partySize = partyStatus?.participants?.length || 0;
    const inLargeParty = Boolean(partyStatus?.in_party) && partySize >= 2;

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
            <button
              type="button"
              onClick={() => void startFloorFight()}
              disabled={loading || partyBlocksSoloDungeon}
              className="game-btn-danger text-xs px-4 py-2 flex-1 min-w-[140px] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ⚔️ {isBossFloor ? "Fight boss" : `Fight floor ${run.floor}`}
            </button>
            {inLargeParty && (
              <button
                type="button"
                onClick={() => void onEnterDungeon()}
                disabled={partyLoading || !partyStatus?.is_leader}
                className="game-btn-primary text-xs px-4 py-2 flex-1 min-w-[140px] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                🏰 {partyStatus?.is_leader ? `Enter Floor ${run.floor} (Party)` : "Waiting for leader…"}
              </button>
            )}
            <button type="button" onClick={onLeaveDungeon} disabled={loading} className="game-btn-secondary text-xs px-4 py-2">
              Leave Dungeon
            </button>
          </div>
          {partyBlocksSoloDungeon && (
            <p className="text-[10px] text-amber-600/90 mt-2">
              Party (2+): only the leader can start the next floor. Party members will auto-join when the fight starts.
            </p>
          )}
        </div>
      </div>
    );
  }

  if (catalogLoading) {
    return <p className="text-sm text-muted-foreground">Loading dungeons…</p>;
  }

  return (
    <div className="space-y-4">
      {/* Incoming Invites Panel */}
      {incomingInvites.length > 0 && (
        <div className="game-panel">
          <div className="game-panel-header">
            📨 Dungeon Party Invites ({incomingInvites.length})
          </div>
          <div className="space-y-2">
            {incomingInvites.map((invite) => (
              <div
                key={invite.invite_id}
                className="flex items-center justify-between gap-2 p-2 rounded-sm bg-muted/30 border border-border"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-cinzel font-semibold text-foreground truncate">
                    {invite.inviter.name} (Lv.{invite.inviter.level} {invite.inviter.class})
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {invite.dungeon_key} • Expires in {invite.expires_at ? Math.round((new Date(invite.expires_at).getTime() - Date.now()) / 60000) : 15} min
                  </p>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => onAcceptInvite(invite.invite_id)}
                    disabled={partyLoading}
                    className="game-btn-primary text-[10px] px-2 py-1"
                  >
                    ✓ Accept
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeclineInvite(invite.invite_id)}
                    disabled={partyLoading}
                    className="game-btn-secondary text-[10px] px-2 py-1"
                  >
                    ✗ Decline
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
                  <div className="relative flex-1">
                    <input
                      type="text"
                      placeholder="@username"
                      value={inviteUsername}
                      onChange={handleInviteInputChange}
                      onFocus={() => inviteUsername.startsWith("@") && setShowSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                      className="w-full bg-input border border-border rounded-sm px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary font-crimson"
                    />
                    {showSuggestions && playerSuggestions.length > 0 && (
                      <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 rounded-sm border border-border bg-popover shadow-lg overflow-hidden">
                        {playerSuggestions.map((player) => (
                          <button
                            key={player.id}
                            type="button"
                            className="w-full text-left px-3 py-2 text-xs hover:bg-muted/60 font-crimson flex items-center justify-between gap-2"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => selectPlayer(player)}
                          >
                            <span className="truncate text-foreground">@{player.username}</span>
                            <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
                              Lv.{player.level} {player.class}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
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
                  💡 Type @ to search players, or enable Developer Mode → Right-click user → Copy ID
                </p>
              </div>
            )}

            <div className="flex gap-2 mb-3 flex-wrap">
              {partyStatus.is_leader ? (
                <button
                  type="button"
                  onClick={onEnterDungeon}
                  disabled={partyLoading || (partyStatus.participants?.length || 0) < 2}
                  className="game-btn-danger text-xs px-4 py-2 flex-1 min-w-[140px] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  ⚔️ Enter Dungeon
                </button>
              ) : (
                <p className="text-xs text-muted-foreground flex-1 min-w-[140px] py-2">
                  Wait for the party leader to start the encounter. You will join the same fight automatically.
                </p>
              )}
              <button
                type="button"
                onClick={onLeaveParty}
                disabled={partyLoading}
                className="game-btn-secondary text-xs px-4 py-2"
              >
                Leave Party
              </button>
            </div>
            {partyStatus.is_leader && (partyStatus.participants?.length || 0) < 2 && (
              <p className="text-[10px] text-muted-foreground">
                💡 Need 2+ players for shared party combat
              </p>
            )}
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
