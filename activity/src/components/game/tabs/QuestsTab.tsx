import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { QuestLogRow } from "@/lib/apiTypes";

const STATE_STYLES: Record<string, string> = {
  active: "bg-accent/60 text-accent-foreground border border-accent",
  completed: "bg-primary/15 text-primary border border-primary/30",
};

export function QuestsTab() {
  const { refreshQuests, quests, npcInteract } = useGameSession();
  const [rows, setRows] = useState<QuestLogRow[]>([]);

  useEffect(() => { void refreshQuests(); }, [refreshQuests]);
  useEffect(() => { setRows(quests?.quests || []); }, [quests]);

  return (
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">Quest Log</div>
        <p className="text-xs text-muted-foreground">
          Complete objectives, then <span className="text-primary font-semibold">Turn in</span> to the quest NPC or <span className="text-primary font-semibold">Talk</span> to advance.
        </p>
      </div>

      {rows.length === 0 && <p className="text-xs text-muted-foreground">No quests in your log.</p>}

      {rows.map((q, idx) => {
        const isCompleted = (q.state || "active").toLowerCase() === "completed";
        return (
          <div key={`${q.quest_id ?? idx}`} className="quest-card">
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <h3 className="font-cinzel font-semibold text-foreground text-sm">{q.quest_name ?? "Quest"}</h3>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <span className={`text-[10px] px-2 py-0.5 rounded-sm uppercase font-semibold tracking-wider ${
                    STATE_STYLES[(q.state || "active").toLowerCase()] || STATE_STYLES.active
                  }`}>
                    {q.state ?? "active"}
                  </span>
                  {q.expires_at && (
                    <span className="text-[10px] px-2 py-0.5 rounded-sm bg-destructive/15 text-destructive border border-destructive/25">
                      ⏱ expires
                    </span>
                  )}
                </div>
              </div>
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
                  className="game-btn-primary text-xs px-3 py-1.5 shrink-0"
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
                          description: "Check Discord DMs if a quest was offered.",
                        });
                      } else {
                        toast.error(r.message || r.error || "Could not talk to NPC.");
                      }
                      void refreshQuests();
                    });
                  }}
                  className="game-btn-secondary text-xs px-3 py-1.5 shrink-0"
                >
                  Talk
                </button>
              )}
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
