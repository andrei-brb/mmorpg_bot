import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { QuestLogRow } from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";

const STATE_STYLES: Record<string, string> = {
  active: "bg-accent/60 text-accent-foreground border border-accent",
  completed: "bg-primary/15 text-primary border border-primary/30",
};

export function QuestsTab() {
  const { refreshQuests, quests, npcInteract, abandonQuest, startCombat, accessToken, guildId } = useGameSession();
  const [rows, setRows] = useState<QuestLogRow[]>([]);
  /** Discord Activity WebViews often block or no-op `window.confirm` — use inline confirm instead. */
  const [pendingAbandonId, setPendingAbandonId] = useState<string | null>(null);

  useEffect(() => { void refreshQuests(); }, [refreshQuests]);
  useEffect(() => { setRows(quests?.quests || []); }, [quests]);
  useEffect(() => {
    if (!pendingAbandonId) return;
    const stillHere = (quests?.quests || []).some(
      (x) => String(x.quest_id ?? "").trim() === pendingAbandonId,
    );
    if (!stillHere) setPendingAbandonId(null);
  }, [quests, pendingAbandonId]);

  return (
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">Quest Log</div>
        <p className="text-xs text-muted-foreground">
          Complete objectives, then <span className="text-primary font-semibold">Turn in</span> to the quest NPC or <span className="text-primary font-semibold">Talk</span> to advance.
          <span className="block mt-1 text-[10px]">
            <span className="text-violet-300/90 font-semibold">Main story</span> quests have a violet frame and cannot be abandoned.
          </span>
        </p>
      </div>

      {rows.length === 0 && <p className="text-xs text-muted-foreground">No quests in your log.</p>}

      {rows.map((q, idx) => {
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
          <div
            key={`${q.quest_id ?? idx}`}
            className={`quest-card${loreMain ? " quest-card--main-story" : ""}`}
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <h3 className="font-cinzel font-semibold text-foreground text-sm">{q.quest_name ?? "Quest"}</h3>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <span className={`text-[10px] px-2 py-0.5 rounded-sm uppercase font-semibold tracking-wider ${
                    STATE_STYLES[stateLower] || STATE_STYLES.active
                  }`}>
                    {q.state ?? "active"}
                  </span>
                  {loreMain && (
                    <span
                      className="text-[10px] px-2 py-0.5 rounded-sm font-semibold tracking-wide uppercase border"
                      style={{
                        color: "hsl(270 65% 82%)",
                        borderColor: "hsl(270 45% 45% / 0.5)",
                        background: "hsl(270 35% 20% / 0.35)",
                      }}
                    >
                      Main story
                    </span>
                  )}
                  {q.expires_at && (
                    <span className="text-[10px] px-2 py-0.5 rounded-sm bg-destructive/15 text-destructive border border-destructive/25">
                      ⏱ expires
                    </span>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 justify-end shrink-0">
                {(canFightDirect || canFightZoneAny || canFightZoneBoss) && (
                  <button
                    type="button"
                    onClick={() => {
                      const run = async () => {
                        // 1) Direct enemy quest: start that exact enemy.
                        if (canFightDirect) {
                          const enemyKey = String(ck?.value || "").trim();
                          const r = await startCombat({ kind: "zone", enemyKey });
                          return r;
                        }

                        // 2) Zone-any / boss-zone: pick an enemy from zone list.
                        if (!accessToken) return { ok: false, message: "No session token." };
                        const res = await api.getCombatEnemies(accessToken, guildId);
                        const j = (await res.json()) as { enemies?: { key?: string; kind?: string }[] };
                        const list = Array.isArray(j.enemies) ? j.enemies : [];

                        const wantBoss = canFightZoneBoss;
                        const pick = list.find((e) => (wantBoss ? e.kind === "boss" : e.kind !== "boss") && e.key);
                        const enemyKey = String(pick?.key || "").trim();
                        if (!enemyKey) return { ok: false, message: "No suitable enemy found for this zone." };
                        return await startCombat({ kind: "zone", enemyKey });
                      };

                      void run().then((r) => {
                        if (r.ok) {
                          window.dispatchEvent(new CustomEvent("game:setActiveTab", { detail: "Combat" }));
                          toast.success("Combat started.", { description: "Switched to Combat tab." });
                        } else {
                          toast.error(r.message || "Could not start combat.");
                        }
                      });
                    }}
                    className="game-btn-primary text-xs px-3 py-1.5"
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
                    className="game-btn-primary text-xs px-3 py-1.5"
                  >
                    Turn in
                  </button>
                )}
                {!isCompleted && q.npc_id && (
                  <button
                    type="button"
                    onClick={() => {
                      void npcInteract(q.npc_id).then((r) => {
                        if (r.ok) {
                          toast.success(r.message || "NPC interaction sent.", {
                            description: "A quest offer popup will open if available.",
                          });
                        } else {
                          toast.error(r.message || r.error || "Could not talk to NPC.");
                        }
                        void refreshQuests();
                      });
                    }}
                    className="game-btn-secondary text-xs px-3 py-1.5"
                  >
                    Talk
                  </button>
                )}
                {canAbandon && pendingAbandonId !== questIdTrimmed && (
                  <button
                    type="button"
                    onClick={() => setPendingAbandonId(questIdTrimmed)}
                    className="text-xs px-3 py-1.5 rounded-sm border border-destructive/40 text-destructive hover:bg-destructive/10"
                  >
                    Abandon
                  </button>
                )}
                {canAbandon && pendingAbandonId === questIdTrimmed && (
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] text-muted-foreground max-w-[140px]">Abandon this side quest?</span>
                    <button
                      type="button"
                      onClick={() => {
                        void abandonQuest(questIdTrimmed)
                          .then((r) => {
                            setPendingAbandonId(null);
                            if (r.ok) {
                              toast.success(r.message || "Quest abandoned.");
                            } else {
                              toast.error(r.message || r.error || "Could not abandon quest.");
                            }
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
            </div>
            <div className="ornament-divider my-2" />
            <div className="text-xs text-muted-foreground mb-1.5">
              {q.npc_name && (
                <>From <span className="text-foreground font-semibold">{q.npc_name}</span></>
              )}
              {q.current_step != null && q.total_steps != null && (
                <span> · Step {q.current_step}/{q.total_steps}</span>
              )}
            </div>
            {q.objective && <div className="text-sm text-foreground mb-2">{q.objective}</div>}
            {q.progress && q.progress.needed != null && (
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 rounded-sm overflow-hidden"
                  style={{
                    background: 'hsl(228 18% 10%)',
                    border: '1px solid hsl(228 16% 18%)',
                    boxShadow: 'inset 0 1px 3px hsl(0 0% 0% / 0.4)',
                  }}>
                  <div className="h-full rounded-sm transition-all"
                    style={{
                      width: `${Math.min(100, ((q.progress.current ?? 0) / Math.max(1, q.progress.needed)) * 100)}%`,
                      background: 'linear-gradient(90deg, hsl(43 78% 40%), hsl(43 78% 50%))',
                      boxShadow: '0 0 4px hsl(43 78% 50% / 0.3)',
                    }}
                  />
                </div>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {q.progress.current ?? 0}/{q.progress.needed}
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
