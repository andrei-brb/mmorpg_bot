import { useEffect, useMemo, useRef, useState } from "react";
import { Swords, Search, Trophy, UserPlus, X, Loader2, Shield, Eye } from "lucide-react";
import type { PvpStatus } from "@/lib/pvpTypes";
import type { PvpPlayerSearchRow } from "@/hooks/usePvpApi";

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
    // If user edits after selecting, clear selected id unless they keep exact @username.
    if (!selectedTargetId) return;
    const v = challengeTarget.trim();
    if (!v.startsWith("@")) {
      setSelectedTargetId(null);
      return;
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
    <div className="space-y-4">
      {incoming_challenge && (
        <div className="game-panel border-gold/40">
          <div className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <p className="font-cinzel text-sm text-gold">Challenge received</p>
              <p className="text-xs text-muted-foreground font-crimson mt-1">
                <span className="text-foreground font-semibold">{incoming_challenge.from_name}</span> wants a{" "}
                {incoming_challenge.mode} duel.
              </p>
            </div>
            <button type="button" className="game-btn-primary shrink-0" onClick={() => void onAcceptChallenge()}>
              Accept
            </button>
          </div>
        </div>
      )}
      {stats && (
        <div className="game-panel">
          <div className="game-panel-header">PvP Stats</div>
          <div className="p-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 text-center">
              <StatBlock label="Rating" value={stats.rating} highlight />
              <StatBlock label="Rank" value={stats.rank_tier} highlight />
              <StatBlock label="Wins" value={stats.wins} />
              <StatBlock label="Losses" value={stats.losses} />
              <StatBlock label="Draws" value={stats.draws} />
              <StatBlock label="Win Rate" value={`${stats.win_rate}%`} />
              <StatBlock label="Streak" value={`🔥 ${stats.streak}`} />
            </div>
          </div>
        </div>
      )}

      {player && rules && (
        <div className="game-panel">
          <div className="game-panel-header">Loadout</div>
          <div className="p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-sm bg-muted border border-border flex items-center justify-center">
                <Shield className="w-5 h-5 text-gold" />
              </div>
              <div>
                <p className="font-cinzel text-xs font-semibold text-foreground tracking-wide">
                  {player.character_name}{" "}
                  <span className="text-gold">Lv.{player.level}</span> {player.class}
                  {player.spec ? ` · ${player.spec}` : ""}
                </p>
                <p className="text-xs text-muted-foreground font-crimson">
                  {rules.bracket} — Gear normalized: {rules.gear_normalized ? "On" : "Off"}
                </p>
              </div>
            </div>
            <button type="button" className="game-btn-secondary" onClick={() => setShowRules(true)}>
              <Eye className="w-3 h-3 inline mr-1" /> Details
            </button>
          </div>
        </div>
      )}

      {!isQueued && !isChallenged && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="game-panel">
            <div className="game-panel-header flex items-center gap-2">
              <UserPlus className="w-3.5 h-3.5" /> Challenge
            </div>
            <div className="p-4 space-y-3">
              <div className="flex gap-2">
                <div className="relative flex-1">
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
                      // Allow click selection to register.
                      window.setTimeout(() => setSuggestOpen(false), 120);
                    }}
                    className="w-full bg-input border border-border rounded-sm px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary font-crimson"
                  />
                  {suggestOpen && suggestions.length > 0 && (
                    <div
                      className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 rounded-sm border border-border bg-popover shadow-lg overflow-hidden"
                      role="listbox"
                    >
                      {suggestions.map((p) => (
                        <button
                          key={p.id}
                          type="button"
                          className="w-full text-left px-3 py-2 text-xs hover:bg-muted/60 font-crimson flex items-center justify-between gap-2"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => {
                            setSelectedTargetId(p.id);
                            setChallengeTarget(`@${p.username}`);
                            setSuggestOpen(false);
                          }}
                        >
                          <span className="truncate text-foreground">{p.username}</span>
                          <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">{p.id}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="game-btn-primary"
                  disabled={!challengeTarget.trim()}
                  onClick={() => {
                    onChallenge((selectedTargetId || challengeTarget.trim()).trim());
                    setChallengeTarget("");
                    setSelectedTargetId(null);
                    setSuggestions([]);
                  }}
                >
                  Send
                </button>
              </div>
            </div>
          </div>

          <div className="game-panel">
            <div className="game-panel-header flex items-center gap-2">
              <Search className="w-3.5 h-3.5" /> Find Match
            </div>
            <div className="p-4 space-y-3">
              <p className="text-xs text-muted-foreground font-crimson">Casual — no rating changes.</p>
              <button type="button" className="game-btn-primary w-full" onClick={() => onJoinQueue("casual")}>
                Queue Casual
              </button>
            </div>
          </div>

          <div className="game-panel">
            <div className="game-panel-header flex items-center gap-2">
              <Trophy className="w-3.5 h-3.5" /> Ranked
            </div>
            <div className="p-4 space-y-3">
              <p className="text-xs text-muted-foreground font-crimson">Compete for rating. ~±15 per match.</p>
              <button type="button" className="game-btn-secondary w-full" onClick={() => onJoinQueue("ranked")}>
                Queue Ranked
              </button>
            </div>
          </div>
        </div>
      )}

      {isQueued && (
        <div className="game-panel">
          <div className="p-8 text-center space-y-4">
            <Loader2 className="w-8 h-8 text-gold animate-spin mx-auto" />
            <p className="font-cinzel text-sm text-foreground uppercase tracking-wider">Searching for opponent…</p>
            <p className="text-xs text-muted-foreground font-crimson">Mode: {status.mode}</p>
            <button type="button" className="game-btn-danger" onClick={onLeaveQueue}>
              <X className="w-3 h-3 inline mr-1" /> Cancel Queue
            </button>
          </div>
        </div>
      )}

      {isChallenged && (
        <div className="game-panel">
          <div className="p-8 text-center space-y-4">
            <Loader2 className="w-8 h-8 text-gold animate-spin mx-auto" />
            <p className="font-cinzel text-sm text-foreground uppercase tracking-wider">
              Challenge sent to <span className="text-gold">{status.challenge_target}</span>
            </p>
            <p className="text-xs text-muted-foreground">Waiting… ({status.challenge_timer}s)</p>
            <button type="button" className="game-btn-danger" onClick={onCancelChallenge}>
              <X className="w-3 h-3 inline mr-1" /> Cancel
            </button>
          </div>
        </div>
      )}

      {showRules && (
        <div
          className="fixed inset-0 bg-background/90 z-50 flex items-center justify-center p-4"
          onClick={() => setShowRules(false)}
          role="presentation"
        >
          <div className="game-panel max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <div className="game-panel-header">Arena Rules</div>
            <div className="p-5 space-y-3 text-xs text-foreground font-crimson">
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
              <p className="text-muted-foreground pt-2 border-t border-border">
                Matches are turn-based with a 60-second timer per turn. If time expires, the server automatically passes
                your turn. Disconnecting forfeits after 2 missed turns.
              </p>
            </div>
            <div className="p-4 border-t border-border">
              <button type="button" className="game-btn-secondary w-full" onClick={() => setShowRules(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatBlock({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div>
      <p className="text-[10px] text-muted-foreground font-crimson uppercase tracking-widest">{label}</p>
      <p className={`text-sm font-cinzel font-bold ${highlight ? "text-gold" : "text-foreground"}`}>{value}</p>
    </div>
  );
}
