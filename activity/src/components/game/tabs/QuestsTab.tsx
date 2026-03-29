import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { QuestLogRow } from "@/lib/apiTypes";
import { Button } from "@/components/ui/button";

const STATE_STYLES: Record<string, string> = {
  active: "bg-accent/60 text-accent-foreground border border-accent",
  completed: "bg-primary/15 text-primary border border-primary/30",
};

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
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">Quest log</div>
        <p className="text-xs text-muted-foreground">
          Talk to NPCs from Explore results. Use the button on an active quest if the NPC id is known.
        </p>
      </div>

      {rows.length === 0 && <p className="text-xs text-muted-foreground">No quests in your log.</p>}

      {rows.map((q, idx) => (
        <div key={`${q.quest_id ?? idx}`} className="quest-card">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div>
              <h3 className="font-cinzel font-semibold text-foreground text-sm">{q.quest_name ?? "Quest"}</h3>
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                <span
                  className={`text-[10px] px-2 py-0.5 rounded-sm uppercase font-semibold tracking-wider ${
                    STATE_STYLES[(q.state || "active").toLowerCase()] || STATE_STYLES.active
                  }`}
                >
                  {q.state ?? "active"}
                </span>
              </div>
            </div>
            {q.npc_id && (
              <Button
                type="button"
                size="sm"
                className="text-xs shrink-0 quest-interact"
                data-npc={q.npc_id}
                onClick={() => {
                  void npcInteract(q.npc_id).then(() => {
                    toast("NPC interact sent");
                    void refreshQuests();
                  });
                }}
              >
                Talk
              </Button>
            )}
          </div>
          <div className="ornament-divider my-2" />
          <div className="text-xs text-muted-foreground mb-1.5">
            {q.npc_name && (
              <>
                From <span className="text-foreground font-semibold">{q.npc_name}</span>
              </>
            )}
            {q.current_step != null && q.total_steps != null && (
              <span>
                {" "}
                · Step {q.current_step}/{q.total_steps}
              </span>
            )}
          </div>
          {q.objective && <div className="text-sm text-foreground mb-2">{q.objective}</div>}
          {q.progress && q.progress.needed != null && (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 rounded-sm overflow-hidden bg-muted">
                <div
                  className="h-full rounded-sm bg-primary/80"
                  style={{
                    width: `${Math.min(100, ((q.progress.current ?? 0) / Math.max(1, q.progress.needed)) * 100)}%`,
                  }}
                />
              </div>
              <span className="text-xs text-muted-foreground tabular-nums">
                {q.progress.current ?? 0}/{q.progress.needed}
              </span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
