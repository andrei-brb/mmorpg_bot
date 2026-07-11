import { Trophy, Skull, Minus, ChevronDown, ScrollText } from "lucide-react";
import type { PvpHistoryResponse, PvpHistoryEntry } from "@/lib/pvpTypes";
import { ArenaPanel, ArenaPlayerAvatar } from "@/components/arena/arenaParts";

interface PvpHistoryProps {
  history: PvpHistoryResponse;
  onLoadMore: () => void;
}

export function PvpHistory({ history, onLoadMore }: PvpHistoryProps) {
  return (
    <ArenaPanel title="Match History" icon={<ScrollText className="h-3.5 w-3.5" />}>
      <div className="space-y-2">
        {history.matches.map((m) => (
          <ArenaHistoryRow key={m.match_id} match={m} />
        ))}
      </div>
      {history.has_more && (
        <div className="mt-4 border-t border-gold/20 pt-3 text-center">
          <button
            type="button"
            className="hero-forge-clip-tag border border-gold/40 bg-black/40 px-4 py-2 font-display text-[11px] tracking-[0.25em] text-gold-bright transition-colors hover:border-gold-bright"
            onClick={onLoadMore}
          >
            <ChevronDown className="mr-1 inline h-3 w-3" /> LOAD MORE
          </button>
        </div>
      )}
    </ArenaPanel>
  );
}

function ArenaHistoryRow({ match: m }: { match: PvpHistoryEntry }) {
  const win = m.result === "victory";
  const loss = m.result === "defeat";
  const Icon = win ? Trophy : loss ? Skull : Minus;
  const ratingStr =
    m.rating_delta != null ? `${m.rating_delta > 0 ? "+" : ""}${m.rating_delta}` : null;

  return (
    <div className="group relative flex min-w-0 items-center gap-3 hero-forge-clip-blade-sm border border-gold/20 px-3 py-2.5 tex-forge transition-colors hover:border-gold/50">
      <div
        className={`relative flex h-9 w-9 shrink-0 items-center justify-center hero-forge-clip-rhombus ${
          win ? "border border-gold/50 bg-gold/20" : loss ? "border border-blood/50 bg-blood/20" : "border border-gold/20 bg-black/30"
        }`}
      >
        <Icon className={`h-4 w-4 ${win ? "text-gold-bright" : loss ? "text-blood" : "text-muted-foreground"}`} />
      </div>

      <ArenaPlayerAvatar name={m.opponent_name} size={38} />

      <div className="min-w-0 flex-1">
        <p className="break-words font-display text-sm leading-none tracking-[0.18em] text-parchment">
          vs <span className="text-gold-bright">{m.opponent_name}</span>
        </p>
        <p className="mt-1 text-[10px] font-display uppercase tracking-[0.3em] text-gold-dim">
          {m.date} · <span className={m.mode === "ranked" ? "text-arcane" : ""}>{m.mode}</span>
        </p>
      </div>

      {ratingStr != null && (
        <span
          className={`hidden shrink-0 hero-forge-clip-tag px-2 py-0.5 font-display text-[10px] tracking-widest sm:inline-block ${
            win
              ? "border border-gold/40 bg-gold/15 text-gold-bright"
              : loss
                ? "border border-blood/40 bg-blood/15 text-blood"
                : "border border-gold/20 text-gold-dim"
          }`}
        >
          {ratingStr}
        </span>
      )}

      <span
        className={`shrink-0 font-display text-xs tracking-[0.25em] capitalize ${win ? "text-gold-bright" : loss ? "text-blood" : "text-muted-foreground"}`}
      >
        {m.result}
      </span>
    </div>
  );
}
