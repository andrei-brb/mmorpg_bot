import { useEffect, useMemo, useRef, useState } from "react";
import { Search, Trophy, X, Loader2, Shield, Eye, Send, Crown, Flame } from "lucide-react";
import type { PvpStatus } from "@/lib/pvpTypes";
import type { PvpPlayerSearchRow } from "@/hooks/usePvpApi";
import { WomPanel } from "@/components/wom/WomUi";
import { ArenaActionCard, ArenaPanel, ArenaPlayerAvatar } from "@/components/arena/arenaParts";

interface PvpHubProps {
  status: PvpStatus;
  onJoinQueue: (mode: "casual" | "ranked") => void;
  onLeaveQueue: () => void;
  onChallenge: (target: string) => void;
  onCancelChallenge: () => void;
  onAcceptChallenge: () => void;
  onSearchPlayers: (q: string) => Promise<PvpPlayerSearchRow[]>;
}

export function PvpHub({
  status,
  onJoinQueue,
  onLeaveQueue,
  onChallenge,
  onCancelChallenge,
  onAcceptChallenge,
  onSearchPlayers,
}: PvpHubProps) {
  const [challengeTarget, setChallengeTarget] = useState("");
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<PvpPlayerSearchRow[]>([]);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const lastQueryRef = useRef("");
  const debounceRef = useRef<number | null>(null);
  const [showRules, setShowRules] = useState(false);
  const { stats, player, rules, match_status, incoming_challenge } = status;

  const isQueued = match_status === "queued";
  const isChallenged = match_status === "challenged";

  const query = useMemo(() => {
    const v = challengeTarget.trim();
    if (!v.startsWith("@")) return "";
    const q = v.slice(1).trim();
    return q.length >= 1 ? q : "";
  }, [challengeTarget]);

  useEffect(() => {
    if (!selectedTargetId) return;
    const v = challengeTarget.trim();
    if (!v.startsWith("@")) {
      setSelectedTargetId(null);
    }
  }, [challengeTarget, selectedTargetId]);

  useEffect(() => {
    if (!query) {
      setSuggestions([]);
      setSuggestOpen(false);
      lastQueryRef.current = "";
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
      debounceRef.current = null;
      return;
    }
    if (query === lastQueryRef.current) return;
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      void onSearchPlayers(query)
        .then((rows) => {
          lastQueryRef.current = query;
          setSuggestions(rows);
          setSuggestOpen(true);
        })
        .catch(() => {
          lastQueryRef.current = query;
          setSuggestions([]);
          setSuggestOpen(false);
        });
    }, 120);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
      debounceRef.current = null;
    };
  }, [query, onSearchPlayers]);

  return (
    <div className="w-full min-w-0 space-y-6">
      {incoming_challenge && (
        <div className="hero-forge-edge-gold hero-forge-clip-blade-sm tex-forge border border-gold/30 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="font-display text-xs tracking-[0.25em] text-gold-bright">CHALLENGE RECEIVED</p>
              <p className="mt-1 text-xs text-parchment font-crimson">
                <span className="font-semibold text-foreground">{incoming_challenge.from_name}</span> wants a{" "}
                {incoming_challenge.mode} duel.
              </p>
            </div>
            <button
              type="button"
              className="hero-forge-clip-tag shrink-0 bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] px-4 py-2 font-display text-[11px] tracking-[0.28em] text-black transition-[filter] hover:brightness-110"
              onClick={() => void onAcceptChallenge()}
            >
              ACCEPT
            </button>
          </div>
        </div>
      )}

      {stats && (
        <ArenaPanel title="PVP Stats" icon={<Trophy className="h-3.5 w-3.5" />}>
          <div className="grid grid-cols-2 gap-px border border-gold/25 bg-gold/15 sm:grid-cols-3 lg:grid-cols-6">
            <ArenaStatCell label="Rating" value={String(stats.rating)} tone="bright" />
            <ArenaStatCell label="Rank" value={stats.rank_tier} tone="bright" />
            <ArenaStatCell label="Wins" value={String(stats.wins)} tone="bright" />
            <ArenaStatCell label="Losses" value={String(stats.losses)} tone="blood" />
            <ArenaStatCell label="Draws" value={String(stats.draws)} tone="dim" />
            <ArenaStatCell label="Win Rate" value={`${stats.win_rate}%`} tone="bright" />
          </div>
          <div className="mt-3 flex flex-col gap-2 px-1 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-display uppercase tracking-[0.35em] text-gold-dim">Streak</span>
              <span className="inline-flex items-center gap-1 hero-forge-clip-tag border border-ember/50 bg-ember/20 px-2 py-0.5 font-display text-[11px] tracking-widest text-ember">
                <Flame className="h-3 w-3" /> {stats.streak}
              </span>
            </div>
            <span className="text-[10px] font-display uppercase tracking-[0.35em] text-gold-dim">Rated · Live</span>
          </div>
        </ArenaPanel>
      )}

      {player && rules && (
        <ArenaPanel title="Loadout" icon={<Shield className="h-3.5 w-3.5" />}>
          <div className="flex min-w-0 flex-col gap-4 hero-forge-edge-gold hero-forge-clip-blade-sm tex-forge p-4 sm:flex-row sm:items-center">
            <ArenaPlayerAvatar name={player.character_name || player.username} src={player.portrait_url} size={56} />
            <div className="min-w-0 flex-1">
              <p className="break-words font-display text-lg leading-none tracking-[0.18em] text-gold-bright">
                {(player.character_name || player.username).toUpperCase()}{" "}
                <span className="text-gold">LV.{player.level}</span>
              </p>
              <p className="mt-1 text-[11px] font-display uppercase tracking-[0.3em] text-gold-dim">
                {player.class}
                {player.spec ? ` · ${player.spec}` : ""} · {rules.bracket} · Gear normalized:{" "}
                <span className="text-blood">{rules.gear_normalized ? "On" : "Off"}</span>
              </p>
            </div>
            <button
              type="button"
              className="hero-forge-clip-tag inline-flex shrink-0 items-center gap-2 border border-gold/40 bg-background/80 px-4 py-1.5 font-display text-[11px] tracking-[0.3em] text-gold-bright transition-colors hover:border-gold-bright"
              onClick={() => setShowRules(true)}
            >
              <Eye className="h-3.5 w-3.5" /> DETAILS
            </button>
          </div>
        </ArenaPanel>
      )}

      {!isQueued && !isChallenged && (
        <div className="grid min-h-0 w-full min-w-0 grid-cols-1 grid-flow-row gap-3 sm:grid-cols-3 sm:items-stretch">
          <ArenaActionCard
            icon={<Crown className="h-4 w-4" />}
            title="Challenge"
            body={
              <div className="flex min-h-0 min-w-0 flex-col gap-2 sm:flex-row sm:items-stretch">
                <div className="relative min-h-0 min-w-0 flex-1">
                  <input
                    type="text"
                    placeholder="@username"
                    value={challengeTarget}
                    onChange={(e) => {
                      setChallengeTarget(e.target.value);
                      setSelectedTargetId(null);
                    }}
                    onFocus={() => {
                      if (suggestions.length) setSuggestOpen(true);
                    }}
                    onBlur={() => {
                      window.setTimeout(() => setSuggestOpen(false), 120);
                    }}
                    className="w-full hero-forge-clip-tag border border-gold/30 bg-black/50 px-3 py-2 font-crimson text-xs text-foreground placeholder:text-muted-foreground focus:border-gold/50 focus:outline-none"
                  />
                  {suggestOpen && suggestions.length > 0 && (
                    <div
                      className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 overflow-hidden hero-forge-clip-blade-sm border border-gold/25 bg-black/90 shadow-lg"
                      role="listbox"
                    >
                      {suggestions.map((p) => (
                        <button
                          key={p.id}
                          type="button"
                          className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left font-crimson text-xs hover:bg-gold/10"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => {
                            setSelectedTargetId(p.id);
                            setChallengeTarget(`@${p.username}`);
                            setSuggestOpen(false);
                          }}
                        >
                          <span className="truncate text-foreground">{p.username}</span>
                          <span className="shrink-0 tabular-nums text-[10px] text-muted-foreground">{p.id}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  disabled={!challengeTarget.trim()}
                  className="hero-forge-clip-tag inline-flex shrink-0 items-center gap-1.5 bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] px-3 py-2 font-display text-[10px] tracking-[0.3em] text-black transition-[filter] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                  onClick={() => {
                    onChallenge((selectedTargetId || challengeTarget.trim()).trim());
                    setChallengeTarget("");
                    setSelectedTargetId(null);
                    setSuggestions([]);
                  }}
                >
                  <Send className="h-3 w-3" /> SEND
                </button>
              </div>
            }
          />
          <ArenaActionCard
            icon={<Search className="h-4 w-4" />}
            title="Find Match"
            body={
              <div className="space-y-3">
                <p className="text-[11px] leading-relaxed text-gold-dim font-crimson">
                  Casual <span className="text-gold-bright">— no rating changes.</span>
                </p>
                <button
                  type="button"
                  className="w-full hero-forge-clip-tag bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] py-2 font-display text-[11px] tracking-[0.25em] text-black transition-[filter] hover:brightness-110"
                  onClick={() => onJoinQueue("casual")}
                >
                  QUEUE CASUAL
                </button>
              </div>
            }
          />
          <ArenaActionCard
            icon={<Trophy className="h-4 w-4" />}
            title="Ranked"
            body={
              <div className="space-y-3">
                <p className="text-[11px] leading-relaxed text-gold-dim font-crimson">
                  Compete for rating. <span className="text-gold-bright">~±15</span> per match.
                </p>
                <button
                  type="button"
                  className="w-full hero-forge-clip-tag border border-gold/40 bg-black/40 py-2 font-display text-[11px] tracking-[0.25em] text-gold-bright transition-colors hover:border-gold-bright hover:bg-black/55"
                  onClick={() => onJoinQueue("ranked")}
                >
                  QUEUE RANKED
                </button>
              </div>
            }
          />
        </div>
      )}

      {isQueued && (
        <div className="hero-forge-edge-gold hero-forge-clip-blade-sm tex-forge border border-gold/25 p-8 text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-gold-bright" />
          <p className="mt-4 font-display text-sm uppercase tracking-[0.28em] text-gold-bright">Searching for opponent…</p>
          <p className="mt-1 text-xs text-gold-dim font-crimson">Mode: {status.mode}</p>
          <button
            type="button"
            className="mt-6 hero-forge-clip-tag border border-blood/60 bg-blood/20 px-4 py-2 font-display text-[11px] tracking-[0.2em] text-blood transition-colors hover:bg-blood/30"
            onClick={onLeaveQueue}
          >
            <X className="mr-1 inline h-3 w-3" /> CANCEL QUEUE
          </button>
        </div>
      )}

      {isChallenged && (
        <div className="hero-forge-edge-gold hero-forge-clip-blade-sm tex-forge border border-gold/25 p-8 text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-gold-bright" />
          <p className="mt-4 font-display text-sm uppercase tracking-[0.28em] text-gold-bright">
            Challenge sent to <span className="text-gold-200">{status.challenge_target}</span>
          </p>
          <p className="mt-1 text-xs text-gold-dim font-crimson">Waiting… ({status.challenge_timer}s)</p>
          <button
            type="button"
            className="mt-6 hero-forge-clip-tag border border-blood/60 bg-blood/20 px-4 py-2 font-display text-[11px] tracking-[0.2em] text-blood transition-colors hover:bg-blood/30"
            onClick={onCancelChallenge}
          >
            <X className="mr-1 inline h-3 w-3" /> CANCEL
          </button>
        </div>
      )}

      {showRules && (
        <div
          className="animate-backdrop fixed inset-0 z-50 flex items-center justify-center bg-background/90 p-4"
          onClick={() => setShowRules(false)}
          role="presentation"
        >
          <WomPanel glow className="max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <div className="game-panel-header">Arena Rules</div>
            <div className="space-y-3 p-5 font-crimson text-xs text-foreground">
              <p>
                <span className="text-gold">Bracket:</span> {rules?.bracket}
              </p>
              <p>
                <span className="text-gold">Level Range:</span> {rules?.level_range}
              </p>
              <p>
                <span className="text-gold">Gear Normalized:</span>{" "}
                {rules?.gear_normalized ? "Yes — all gear stats are equalized." : "No — your actual gear matters."}
              </p>
              <p className="border-t border-border pt-2 text-muted-foreground">
                Matches are turn-based with a 60-second timer per turn. If time expires, the server automatically passes
                your turn. Disconnecting forfeits after 2 missed turns.
              </p>
            </div>
            <div className="border-t border-border p-4">
              <button type="button" className="game-btn-secondary w-full" onClick={() => setShowRules(false)}>
                Close
              </button>
            </div>
          </WomPanel>
        </div>
      )}
    </div>
  );
}

function ArenaStatCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "bright" | "blood" | "dim";
}) {
  const toneCls =
    tone === "bright" ? "text-gold-bright" : tone === "blood" ? "text-blood" : "text-gold-dim";
  return (
    <div className="tex-forge p-4 text-center">
      <p className="text-[9px] font-display uppercase tracking-[0.35em] text-gold-dim">{label}</p>
      <p className={`mt-1 font-display text-2xl tracking-wide ${toneCls}`}>{value}</p>
    </div>
  );
}
