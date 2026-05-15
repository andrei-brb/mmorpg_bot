import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { MainQuestPointerPayload, QuestLogRow } from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";
import { ZONES } from "@/data/zones";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { WomPanel } from "@/components/wom/WomUi";

const STATE_STYLES: Record<string, string> = {
  active: "bg-accent/60 text-accent-foreground border border-accent",
  completed: "bg-primary/15 text-primary border border-primary/30",
};

function questBucketLabel(q: QuestLogRow): { label: string; tint: string } {
  const stateLower = String(q.state || "active").toLowerCase().trim();
  if (stateLower === "completed") return { label: "COMPLETE", tint: "text-emerald-200/90" };
  if (q.lore_main) return { label: "STORY", tint: "text-violet-200/90" };
  if (q.expires_at) return { label: "DAILY", tint: "text-amber-200/90" };
  return { label: "WORLD", tint: "text-sky-200/90" };
}

function questStableId(q: QuestLogRow, idx: number): string {
  const id = String(q.quest_id ?? "").trim();
  return id || `row-${idx}`;
}

/** Zone where this quest step's fight must happen (matches server zone enemy lists). */
function zoneKeyForQuestObjectiveFight(ck: { type?: string; value?: string } | null | undefined): string | null {
  if (!ck?.type) return null;
  const t = String(ck.type).trim();
  const v = typeof ck.value === "string" ? ck.value.trim() : "";
  if (t === "kill_any_zone" || t === "kill_boss_zone") return v || null;
  if (t === "kill_enemy" && v) {
    for (const z of ZONES) {
      if (z.mobs.some((m) => m.key === v) || z.bosses.some((b) => b.key === v)) return z.key;
    }
  }
  return null;
}

function StoryBeacon({ ptr }: { ptr: MainQuestPointerPayload }) {
  const kind = ptr.kind ?? "none";
  if (kind === "none") return null;
  const title =
    kind === "complete"
      ? "Main story — complete"
      : kind === "active"
        ? "Main story — in progress"
        : kind === "seek_npc"
          ? "Main story — next step"
          : kind === "blocked_level"
            ? "Main story — level gate"
            : "Main story — waiting on deeds";
  const regions = ptr.regions?.length
    ? ptr.regions.map((r) => `${r.emoji || ""} ${r.name || r.key}`.trim()).join(" · ")
    : null;
  return (
    <WomPanel
      glow
      className="quest-card--main-story"
      style={{
        borderColor: "hsl(270 45% 45% / 0.55)",
        background: "linear-gradient(180deg, hsl(270 28% 14% / 0.5) 0%, hsl(228 20% 10% / 0.4) 100%)",
      }}
    >
      <div className="game-panel-header flex items-center justify-between gap-2">
        <span>{title}</span>
        {ptr.in_current_region && kind !== "complete" && (
          <span
            className="text-[9px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-sm"
            style={{
              color: "hsl(140 55% 70%)",
              border: "1px solid hsl(140 45% 35% / 0.5)",
              background: "hsl(140 30% 12% / 0.5)",
            }}
          >
            In this region
          </span>
        )}
      </div>
      {ptr.hint_base && <p className="text-xs text-foreground/90 leading-relaxed mt-2">{ptr.hint_base}</p>}
      {ptr.hint_region ? (
        <p className="text-xs text-emerald-300/90 leading-relaxed mt-2 font-medium">{ptr.hint_region}</p>
      ) : null}
      {regions && kind !== "complete" && (
        <p className="text-[10px] text-muted-foreground mt-2">
          <span className="font-cinzel uppercase tracking-wider">Regions:</span> {regions}
        </p>
      )}
      {ptr.discovery_hint && (kind === "seek_npc" || kind === "active") && (
        <p className="text-[10px] text-violet-200/80 italic mt-2 leading-relaxed border-t border-violet-500/20 pt-2">
          {ptr.discovery_hint}
        </p>
      )}
      {kind === "blocked_level" && ptr.level_required != null && (
        <p className="text-[10px] text-muted-foreground mt-1 tabular-nums">Required level: {ptr.level_required}</p>
      )}
      {kind === "blocked_deeds" && (ptr.missing_deed_flags?.length ?? 0) > 0 ? (
        <p className="text-[10px] text-violet-200/90 mt-2 leading-relaxed">
          <span className="font-cinzel uppercase tracking-wider">Needed deeds:</span>{" "}
          {ptr.missing_deed_flags!.map((f) => f.replace(/_/g, " ")).join(", ")}
        </p>
      ) : null}
    </WomPanel>
  );
}

export function QuestsTab() {
  const {
    refreshQuests,
    quests,
    npcInteract,
    abandonQuest,
    startCombat,
    accessToken,
    guildId,
    setQuickFightIntent,
    progress,
    travel,
  } = useGameSession();
  const [rows, setRows] = useState<QuestLogRow[]>([]);
  /** Discord Activity WebViews often block or no-op `window.confirm` — use inline confirm instead. */
  const [pendingAbandonId, setPendingAbandonId] = useState<string | null>(null);
  const [selectedQuestId, setSelectedQuestId] = useState<string | null>(null);
  const [travelFightPrompt, setTravelFightPrompt] = useState<{
    zoneKey: string;
    zoneName: string;
    resumeFight: () => Promise<{ ok: boolean; message?: string; error?: string }>;
  } | null>(null);
  const [travelFightBusy, setTravelFightBusy] = useState(false);

  useEffect(() => { void refreshQuests(); }, [refreshQuests]);
  useEffect(() => { setRows(quests?.quests || []); }, [quests]);
  useEffect(() => {
    if (!pendingAbandonId) return;
    const stillHere = (quests?.quests || []).some(
      (x) => String(x.quest_id ?? "").trim() === pendingAbandonId,
    );
    if (!stillHere) setPendingAbandonId(null);
  }, [quests, pendingAbandonId]);

  const mainPtr = quests?.main_quest_pointer;
  const playerLevel = progress?.character?.level ?? null;
  const playerName = progress?.character?.name ?? null;

  useEffect(() => {
    const list = rows;
    if (list.length === 0) {
      if (selectedQuestId !== null) setSelectedQuestId(null);
      return;
    }
    const exists = selectedQuestId && list.some((q, i) => questStableId(q, i) === selectedQuestId);
    if (exists) return;
    const firstActive =
      list.find((q) => String(q.state || "active").toLowerCase().trim() !== "completed") ?? list[0];
    const idx = list.indexOf(firstActive);
    setSelectedQuestId(questStableId(firstActive, Math.max(0, idx)));
  }, [rows, selectedQuestId]);

  const selected =
    selectedQuestId != null
      ? rows.find((q, i) => questStableId(q, i) === selectedQuestId) ?? null
      : null;

  return (
    <>
    <div className="space-y-4 w-full pb-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_380px] items-start">
        <div className="space-y-4 min-w-0">
          <WomPanel
            glow
            className="overflow-hidden"
            style={{
              background: "linear-gradient(180deg, hsl(226 30% 14% / 0.9) 0%, hsl(230 32% 10% / 0.92) 100%)",
              border: "1px solid hsl(43 50% 35% / 0.35)",
              boxShadow: "0 10px 40px hsl(0 0% 0% / 0.35), inset 0 1px 0 hsl(228 14% 30% / 0.25)",
            }}
          >
            <div className="game-panel-header flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="text-[10px] font-cinzel uppercase tracking-widest text-muted-foreground">
                  {mainPtr?.quest_name ? "ARCHON QUEST" : "QUEST"}
                </div>
                <div className="font-cinzel font-bold text-foreground text-base truncate">
                  {selected?.quest_name ?? mainPtr?.quest_name ?? "Quest Log"}
                </div>
                {selected?.npc_name || mainPtr?.npc_name ? (
                  <div className="text-[11px] text-muted-foreground font-crimson mt-0.5 truncate">
                    {(selected?.npc_title ? `${selected?.npc_title} ` : mainPtr?.npc_title ? `${mainPtr?.npc_title} ` : "") +
                      (selected?.npc_name || mainPtr?.npc_name || "")}
                  </div>
                ) : null}
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {selected ? (() => {
                  const stateLower = String(selected.state || "active").toLowerCase().trim();
                  const { label, tint } = questBucketLabel(selected);
                  return (
                    <>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-sm uppercase font-semibold tracking-wider ${
                          STATE_STYLES[stateLower] || STATE_STYLES.active
                        }`}
                      >
                        {selected.state ?? "active"}
                      </span>
                      <span className={`text-[10px] font-semibold uppercase tracking-wider ${tint}`}>{label}</span>
                    </>
                  );
                })() : null}
              </div>
            </div>

            <div className="px-4 pb-4">
              <div className="ornament-divider my-2" />

              {mainPtr ? (
                <div className="mb-3">
                  <StoryBeacon ptr={mainPtr} />
                </div>
              ) : null}

              {!selected && rows.length === 0 ? (
                <p className="text-sm text-muted-foreground">No quests in your log.</p>
              ) : null}

              {selected ? (
                <>
                  <div className="text-xs text-muted-foreground mb-2">
                    {selected.current_step != null && selected.total_steps != null ? (
                      <span className="tabular-nums">Step {selected.current_step}/{selected.total_steps}</span>
                    ) : (
                      <span className="text-muted-foreground">In progress</span>
                    )}
                    {selected.expires_at ? <span className="ml-2 text-amber-200/80">⏱ timed</span> : null}
                  </div>

                  {selected.objective ? (
                    <div className="text-sm text-foreground leading-relaxed mb-3">{selected.objective}</div>
                  ) : null}

                  {selected.progress && selected.progress.needed != null ? (
                    <div className="flex items-center gap-2 mb-4">
                      <div
                        className="flex-1 h-2 rounded-sm overflow-hidden"
                        style={{
                          background: "hsl(226 30% 8% / 0.75)",
                          border: "1px solid hsl(228 18% 22% / 0.9)",
                          boxShadow: "inset 0 1px 3px hsl(0 0% 0% / 0.45)",
                        }}
                      >
                        <div
                          className="h-full rounded-sm transition-all"
                          style={{
                            width: `${Math.min(
                              100,
                              ((selected.progress.current ?? 0) / Math.max(1, selected.progress.needed)) * 100,
                            )}%`,
                            background: "linear-gradient(90deg, hsl(43 78% 45%), hsl(43 78% 55%))",
                            boxShadow: "0 0 10px hsl(43 78% 50% / 0.25)",
                          }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {selected.progress.current ?? 0}/{selected.progress.needed}
                      </span>
                    </div>
                  ) : null}

                  <div className="flex items-end justify-between gap-3 flex-wrap">
                    <div className="text-[11px] text-muted-foreground max-w-[520px]">
                      Complete objectives, then{" "}
                      <span className="text-primary font-semibold">Turn in</span> to the quest NPC or{" "}
                      <span className="text-primary font-semibold">Talk</span> to advance.
                      <span className="block mt-1 text-[10px] text-violet-200/80">Main story quests cannot be abandoned.</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {[
                        { icon: "⭐", label: "XP" },
                        { icon: "🪙", label: "Gold" },
                        { icon: "🎁", label: "Loot" },
                      ].map((r) => (
                        <div
                          key={r.label}
                          className="relative h-10 w-10 rounded-lg flex items-center justify-center"
                          style={{
                            background: "linear-gradient(180deg, hsl(43 78% 50% / 0.18) 0%, hsl(230 32% 10% / 0.85) 100%)",
                            border: "1px solid hsl(43 50% 45% / 0.35)",
                            boxShadow: "0 0 18px hsl(43 78% 50% / 0.12), inset 0 1px 0 hsl(0 0% 100% / 0.06)",
                          }}
                          title={r.label}
                        >
                          <span className="text-lg leading-none" aria-hidden>
                            {r.icon}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="ornament-divider my-3" />

                  {(() => {
                    const q = selected;
                    const stateLower = String(q.state || "active").toLowerCase().trim();
                    const isCompleted = stateLower === "completed";
                    const loreMain = Boolean(q.lore_main);
                    const questIdTrimmed = String(q.quest_id ?? "").trim();
                    const ck = q.completion_check || null;
                    const canFightDirect =
                      !isCompleted && ck?.type === "kill_enemy" && typeof ck?.value === "string" && ck.value.length > 0;
                    const canFightZoneAny = !isCompleted && ck?.type === "kill_any_zone";
                    const canFightZoneBoss = !isCompleted && ck?.type === "kill_boss_zone";
                    const canAbandon =
                      !loreMain && !isCompleted && (stateLower === "active" || stateLower === "offered") && questIdTrimmed.length > 0;

                    return (
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {(canFightDirect || canFightZoneAny || canFightZoneBoss) && (
                          <button
                            type="button"
                            onClick={() => {
                              const run = async () => {
                                if (canFightDirect) {
                                  const enemyKey = String(ck?.value || "").trim();
                                  setQuickFightIntent({ kind: "enemy", enemyKey });
                                  return await startCombat({ kind: "zone", enemyKey });
                                }
                                if (!accessToken) return { ok: false, message: "No session token." };
                                setQuickFightIntent(canFightZoneBoss ? { kind: "zone_boss" } : { kind: "zone_any" });
                                const zoneKey = typeof ck?.value === "string" ? ck.value : undefined;
                                const res = await api.getCombatEnemies(accessToken, guildId, zoneKey);
                                const j = (await res.json()) as { enemies?: { key?: string; kind?: string }[] };
                                const list = Array.isArray(j.enemies) ? j.enemies : [];
                                const wantBoss = canFightZoneBoss;
                                const pick = list.find((e) => (wantBoss ? e.kind === "boss" : e.kind !== "boss") && e.key);
                                const enemyKey = String(pick?.key || "").trim();
                                if (!enemyKey) return { ok: false, message: "No suitable enemy found for this zone." };
                                return await startCombat({ kind: "zone", enemyKey });
                              };

                              const finish = (r: { ok: boolean; message?: string; error?: string }) => {
                                if (r.ok) {
                                  window.dispatchEvent(new CustomEvent("game:setActiveTab", { detail: "Combat" }));
                                  toast.success("Combat started.", { description: "Switched to Combat tab." });
                                  return;
                                }
                                const wrongZone =
                                  r.error === "invalid_enemy" ||
                                  /not in your current zone/i.test(String(r.message || ""));
                                if (wrongZone) {
                                  const zk = zoneKeyForQuestObjectiveFight(ck);
                                  if (zk) {
                                    const z = ZONES.find((x) => x.key === zk);
                                    setTravelFightPrompt({
                                      zoneKey: zk,
                                      zoneName: z?.name || zk,
                                      resumeFight: run,
                                    });
                                    return;
                                  }
                                }
                                toast.error(r.message || "Could not start combat.");
                              };

                              void run().then(finish);
                            }}
                            className="game-btn-primary text-xs px-3 py-2"
                          >
                            Fight
                          </button>
                        )}

                        {isCompleted && q.npc_id && (
                          <button
                            type="button"
                            onClick={() => {
                              void npcInteract(q.npc_id).then((r) => {
                                if (r.ok) {
                                  toast.success(r.message || "Quest turned in!", {
                                    description: q.quest_name ? `${q.quest_name}` : undefined,
                                  });
                                } else {
                                  toast.error(r.message || r.error || "Could not turn in quest.");
                                }
                                void refreshQuests();
                              });
                            }}
                            className="game-btn-primary text-xs px-3 py-2"
                          >
                            Turn in
                          </button>
                        )}

                        {!isCompleted && q.npc_id && (
                          <button
                            type="button"
                            onClick={() => {
                              void npcInteract(q.npc_id).then((r) => {
                                if (!r.ok) {
                                  toast.error(r.message || r.error || "Could not talk to NPC.");
                                  void refreshQuests();
                                  return;
                                }
                                if (r.openedQuestOffer || r.openedCompletion) {
                                  if (r.message) {
                                    toast.success(r.message, { description: "A quest offer or completion window opened if applicable." });
                                  }
                                } else {
                                  toast.info(r.message || "Nothing new from this NPC right now.", {
                                    description:
                                      "They may have no quest for your current progress, or requirements are not met yet. Your quest log may still update — check the list.",
                                  });
                                }
                                void refreshQuests();
                              });
                            }}
                            className="game-btn-secondary text-xs px-3 py-2"
                          >
                            Talk
                          </button>
                        )}

                        {canAbandon && pendingAbandonId !== questIdTrimmed && (
                          <button
                            type="button"
                            onClick={() => setPendingAbandonId(questIdTrimmed)}
                            className="text-xs px-3 py-2 rounded-sm border border-destructive/40 text-destructive hover:bg-destructive/10"
                          >
                            Abandon
                          </button>
                        )}

                        {canAbandon && pendingAbandonId === questIdTrimmed && (
                          <span className="flex flex-wrap items-center gap-1.5">
                            <span className="text-[10px] text-muted-foreground max-w-[160px]">Abandon this side quest?</span>
                            <button
                              type="button"
                              onClick={() => {
                                void abandonQuest(questIdTrimmed)
                                  .then((r) => {
                                    setPendingAbandonId(null);
                                    if (r.ok) toast.success(r.message || "Quest abandoned.");
                                    else toast.error(r.message || r.error || "Could not abandon quest.");
                                    void refreshQuests();
                                  })
                                  .catch((e) => {
                                    setPendingAbandonId(null);
                                    toast.error(e instanceof Error ? e.message : "Could not abandon quest.");
                                    void refreshQuests();
                                  });
                              }}
                              className="text-xs px-2 py-1 rounded-sm bg-destructive/90 text-destructive-foreground hover:bg-destructive"
                            >
                              Yes
                            </button>
                            <button
                              type="button"
                              onClick={() => setPendingAbandonId(null)}
                              className="text-xs px-2 py-1 rounded-sm border border-border text-foreground hover:bg-muted/30"
                            >
                              No
                            </button>
                          </span>
                        )}
                      </div>
                    );
                  })()}
                </>
              ) : null}
            </div>
          </WomPanel>
        </div>

        <div className="space-y-4">
          <WomPanel
            glow
            style={{
              background: "linear-gradient(180deg, hsl(226 28% 14% / 0.85) 0%, hsl(230 32% 10% / 0.9) 100%)",
              border: "1px solid hsl(43 50% 35% / 0.3)",
              boxShadow: "0 8px 30px hsl(0 0% 0% / 0.25), inset 0 1px 0 hsl(228 14% 30% / 0.22)",
            }}
          >
            <div className="game-panel-header flex items-center justify-between gap-2">
              <span>Active Quests</span>
              <span className="text-[10px] text-muted-foreground tabular-nums">{rows.length}</span>
            </div>

            <div className="max-h-[420px] overflow-y-auto overscroll-contain pr-1">
              <div className="space-y-1 p-2">
                {rows.length === 0 ? (
                  <p className="text-xs text-muted-foreground p-2">No quests yet. Explore to meet NPCs.</p>
                ) : (
                  rows.map((q, idx) => {
                    const id = questStableId(q, idx);
                    const isActive = id === selectedQuestId;
                    const { label, tint } = questBucketLabel(q);
                    const stateLower = String(q.state || "active").toLowerCase().trim();
                    const dot =
                      stateLower === "completed"
                        ? "bg-emerald-400/80"
                        : q.lore_main
                          ? "bg-violet-400/80"
                          : "bg-sky-400/70";
                    const hasProgress = q.progress && q.progress.needed != null;
                    const pct = hasProgress
                      ? Math.min(100, ((q.progress?.current ?? 0) / Math.max(1, q.progress?.needed ?? 1)) * 100)
                      : null;
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setSelectedQuestId(id)}
                        className="w-full text-left rounded-sm px-2 py-2 transition-all duration-150 hover:bg-muted/20"
                        style={{
                          background: isActive ? "hsl(43 78% 50% / 0.10)" : "transparent",
                          border: isActive ? "1px solid hsl(43 50% 45% / 0.35)" : "1px solid transparent",
                        }}
                      >
                        <div className="flex items-start gap-2">
                          <span className={`mt-1 h-2 w-2 rounded-full shrink-0 ${dot}`} aria-hidden />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0">
                                <div className="text-xs font-cinzel font-semibold text-foreground truncate">
                                  {q.quest_name ?? "Quest"}
                                </div>
                                <div className={`text-[10px] font-semibold uppercase tracking-wider ${tint}`}>
                                  {label}
                                  {q.expires_at ? " · TIMED" : ""}
                                </div>
                              </div>
                              <span
                                className={`text-[9px] px-2 py-0.5 rounded-sm uppercase font-semibold tracking-wider ${
                                  STATE_STYLES[stateLower] || STATE_STYLES.active
                                }`}
                              >
                                {q.state ?? "active"}
                              </span>
                            </div>
                            {pct != null ? (
                              <div className="mt-1">
                                <div
                                  className="h-1 rounded-sm overflow-hidden"
                                  style={{ background: "hsl(226 30% 8% / 0.75)", border: "1px solid hsl(228 18% 22% / 0.7)" }}
                                >
                                  <div
                                    className="h-full"
                                    style={{
                                      width: `${pct}%`,
                                      background: "linear-gradient(90deg, hsl(43 78% 45%), hsl(43 78% 55%))",
                                    }}
                                  />
                                </div>
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </WomPanel>

          <WomPanel
            glow
            style={{
              background: "linear-gradient(180deg, hsl(226 28% 14% / 0.85) 0%, hsl(230 32% 10% / 0.9) 100%)",
              border: "1px solid hsl(43 50% 35% / 0.3)",
              boxShadow: "0 8px 30px hsl(0 0% 0% / 0.25), inset 0 1px 0 hsl(228 14% 30% / 0.22)",
            }}
          >
            <div className="game-panel-header flex items-center justify-between">
              <span>Battle Pass</span>
              <span className="text-[10px] text-muted-foreground">{playerName || "Adventurer"}</span>
            </div>
            <div className="p-4 pt-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-cinzel font-semibold text-foreground">
                  Lv {playerLevel ?? "—"} / 50
                </div>
                <div className="text-[10px] text-muted-foreground tabular-nums">6400/10000</div>
              </div>
              <div className="mt-2 h-2 rounded-sm overflow-hidden" style={{ background: "hsl(226 30% 8% / 0.75)", border: "1px solid hsl(228 18% 22% / 0.8)" }}>
                <div
                  className="h-full"
                  style={{
                    width: "64%",
                    background: "linear-gradient(90deg, hsl(180 70% 55%), hsl(200 78% 60%))",
                    boxShadow: "0 0 12px hsl(190 78% 55% / 0.25)",
                  }}
                />
              </div>
              <div className="mt-2 text-[10px] text-muted-foreground">
                Cosmetic UI for now — we can wire this to real progression later.
              </div>
            </div>
          </WomPanel>
        </div>
      </div>
    </div>

    <Dialog
      open={travelFightPrompt !== null}
      onOpenChange={(open) => {
        if (!open && !travelFightBusy) setTravelFightPrompt(null);
      }}
    >
      <DialogContent className="z-[95] max-w-[min(96vw,420px)]">
        <DialogHeader>
          <DialogTitle className="font-cinzel">Travel to fight?</DialogTitle>
          <DialogDescription className="text-left text-sm leading-relaxed pt-1">
            {travelFightPrompt ? (
              <>
                This step targets <span className="text-foreground font-medium">{travelFightPrompt.zoneName}</span>.
                You are not in that zone right now. Travel there and start combat?
              </>
            ) : null}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={travelFightBusy}
            onClick={() => !travelFightBusy && setTravelFightPrompt(null)}
          >
            No
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={travelFightBusy || !travelFightPrompt}
            onClick={() => {
              const p = travelFightPrompt;
              if (!p || travelFightBusy) return;
              setTravelFightBusy(true);
              void (async () => {
                try {
                  const t = await travel(p.zoneKey);
                  if (!t.ok) {
                    toast.error(t.message || "Could not travel.");
                    return;
                  }
                  if (t.message && !/^already here/i.test(t.message)) {
                    toast.success(t.message, { description: p.zoneName });
                  }
                  const r = await p.resumeFight();
                  setTravelFightPrompt(null);
                  if (r.ok) {
                    window.dispatchEvent(new CustomEvent("game:setActiveTab", { detail: "Combat" }));
                    toast.success("Combat started.", { description: "Switched to Combat tab." });
                  } else {
                    toast.error(r.message || "Could not start combat.");
                  }
                } finally {
                  setTravelFightBusy(false);
                }
              })();
            }}
          >
            {travelFightBusy ? "…" : "Yes, travel & fight"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  );
}
