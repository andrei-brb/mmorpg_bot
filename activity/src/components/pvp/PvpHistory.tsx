import { Trophy, Skull, Minus, ChevronDown } from "lucide-react";
import type { PvpHistoryResponse } from "@/lib/pvpTypes";
import { WomPanel } from "@/components/wom/WomUi";

interface PvpHistoryProps {
  history: PvpHistoryResponse;
  onLoadMore: () => void;
}

export function PvpHistory({ history, onLoadMore }: PvpHistoryProps) {
  return (
    <WomPanel glow>
      <div className="game-panel-header">Match History</div>
      <div className="divide-y divide-border">
        {history.matches.map((m) => {
          const Icon = m.result === "victory" ? Trophy : m.result === "defeat" ? Skull : Minus;
          const color =
            m.result === "victory"
              ? "text-emerald-400"
              : m.result === "defeat"
                ? "text-destructive"
                : "text-muted-foreground";
          return (
            <div
              key={m.match_id}
              className="flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Icon className={`w-4 h-4 ${color}`} />
                <div>
                  <p className="text-xs font-crimson text-foreground">vs {m.opponent_name}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {m.date} · {m.mode}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <span className={`text-xs font-cinzel font-bold capitalize ${color}`}>{m.result}</span>
                {m.rating_delta != null && (
                  <p className={`text-[10px] ${m.rating_delta > 0 ? "text-emerald-400" : "text-destructive"}`}>
                    {m.rating_delta > 0 ? "+" : ""}
                    {m.rating_delta}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {history.has_more && (
        <div className="p-3 border-t border-border text-center">
          <button type="button" className="game-btn-secondary" onClick={onLoadMore}>
            <ChevronDown className="w-3 h-3 inline mr-1" /> Load More
          </button>
        </div>
      )}
    </WomPanel>
  );
}
