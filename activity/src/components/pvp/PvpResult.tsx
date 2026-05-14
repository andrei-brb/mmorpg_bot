import { Trophy, Skull, Minus, RotateCcw, ArrowLeft } from "lucide-react";
import type { PvpMatchState } from "@/lib/pvpTypes";
import { WomPanel } from "@/components/wom/WomUi";

interface PvpResultProps {
  match: PvpMatchState;
  onRematch: () => void;
  onBackToHub: () => void;
}

export function PvpResult({ match, onRematch, onBackToHub }: PvpResultProps) {
  const { result, result_stats, mode, opponent } = match;

  const Icon = result === "victory" ? Trophy : result === "defeat" ? Skull : Minus;
  const title = result === "victory" ? "Victory!" : result === "defeat" ? "Defeat" : "Draw";
  const titleColor =
    result === "victory" ? "text-emerald-400" : result === "defeat" ? "text-destructive" : "text-muted-foreground";

  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <WomPanel glow className="max-w-md w-full text-center">
        <div className="p-8 space-y-5">
          <Icon className={`w-14 h-14 mx-auto ${titleColor}`} />
          <h2 className={`font-cinzel text-2xl font-black tracking-widest uppercase ${titleColor}`}>{title}</h2>
          <p className="text-xs text-muted-foreground font-crimson">
            vs <span className="text-foreground">{opponent.character_name}</span>
          </p>

          {result_stats && (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Damage Dealt" value={result_stats.damage_dealt.toLocaleString()} />
              <Stat label="Damage Taken" value={result_stats.damage_taken.toLocaleString()} />
              <Stat label="Critical Hits" value={result_stats.crits} />
              <Stat
                label="Duration"
                value={`${Math.floor(result_stats.duration_seconds / 60)}m ${result_stats.duration_seconds % 60}s`}
              />
            </div>
          )}

          {result_stats?.rating_delta != null && mode === "ranked" && (
            <WomPanel bracket={false} glow={false} className="p-3">
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-cinzel">Rating Change</p>
              <p
                className={`text-xl font-cinzel font-bold ${
                  result_stats.rating_delta > 0 ? "text-emerald-400" : "text-destructive"
                }`}
              >
                {result_stats.rating_delta > 0 ? "+" : ""}
                {result_stats.rating_delta}
              </p>
            </WomPanel>
          )}

          <div className="flex gap-3 justify-center pt-2 flex-wrap">
            <button type="button" className="game-btn-secondary" onClick={onRematch}>
              <RotateCcw className="w-3 h-3 inline mr-1" /> Rematch
            </button>
            <button type="button" className="game-btn-primary" onClick={onBackToHub}>
              <ArrowLeft className="w-3 h-3 inline mr-1" /> Back to Hub
            </button>
          </div>
        </div>
      </WomPanel>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-muted/50 rounded-sm p-2 border border-border">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-cinzel">{label}</p>
      <p className="text-foreground text-sm font-semibold font-crimson">{value}</p>
    </div>
  );
}
