import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { QuestLogRow } from "@/lib/apiTypes";

function questPillClass(state: string | undefined): string {
  const s = (state || "active").toLowerCase();
  if (s === "completed") return "border-emerald-500/50 text-emerald-200 bg-emerald-950/40";
  return "border-slate-400/45 text-slate-200";
}

export function QuestsTab() {
  const { refreshQuests, quests, npcInteract } = useGameSession();
  const [rows, setRows] = useState<QuestLogRow[]>([]);

  useEffect(() => {
    void (async () => {
      await refreshQuests();
    })();
  }, [refreshQuests]);

  useEffect(() => {
    setRows(quests?.quests || []);
  }, [quests]);

  return (
    <div id="tab-quests" className="tab-pane space-y-4">
      <div className="panel v0-panel">
        <h2>Quest Log</h2>
        <p className="hint">
          Talk to NPCs from Explore results. Use Talk when an NPC id is available on the quest.
        </p>
      </div>

      {rows.length === 0 ? (
        <p className="hint">No quests in your log.</p>
      ) : (
        <div className="quest-grid">
          {rows.map((q, idx) => (
            <div key={`${q.quest_id ?? idx}`} className="quest-card panel v0-panel">
              <div className="quest-head">
                <div>
                  <div className="quest-title">{q.quest_name ?? "Quest"}</div>
                  <div className="quest-pills mt-1.5">
                    <span className={`quest-pill ${questPillClass(q.state)}`}>{(q.state ?? "active").toUpperCase()}</span>
                  </div>
                </div>
                {q.npc_id ? (
                  <div className="quest-actions">
                    <button
                      type="button"
                      className="mini-btn quest-interact"
                      data-npc={q.npc_id}
                      onClick={() => {
                        void npcInteract(q.npc_id).then(() => {
                          toast("NPC interact sent");
                          void refreshQuests();
                        });
                      }}
                    >
                      Talk
                    </button>
                  </div>
                ) : null}
              </div>
              <div className="hint text-[0.78rem] mb-1">
                {q.npc_name ? (
                  <>
                    From <span className="text-foreground font-semibold">{q.npc_name}</span>
                  </>
                ) : null}
                {q.current_step != null && q.total_steps != null ? (
                  <span>
                    {" "}
                    · Step {q.current_step}/{q.total_steps}
                  </span>
                ) : null}
              </div>
              {q.objective ? <div className="quest-obj">{q.objective}</div> : null}
              {q.progress && q.progress.needed != null ? (
                <div className="flex items-center gap-2 mt-2">
                  <div className="flex-1 h-2 rounded-sm overflow-hidden bg-[#0b1023] border border-[#28335d]">
                    <div
                      className="h-full rounded-sm bg-[#727cff]"
                      style={{
                        width: `${Math.min(100, ((q.progress.current ?? 0) / Math.max(1, q.progress.needed)) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="hint tabular-nums text-[0.72rem]">
                    {q.progress.current ?? 0}/{q.progress.needed}
                  </span>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
