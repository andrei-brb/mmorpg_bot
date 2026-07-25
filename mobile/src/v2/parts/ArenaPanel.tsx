import { usePvpApi } from "@/hooks/usePvpApi";
import { PvpPage } from "@/components/pvp/PvpPage";
import { cn } from "@/lib/utils";

/**
 * The arena, in Ember.
 *
 * Drives the same usePvpApi hook as the classic Coliseum. The hub — your record
 * and the two queue buttons — is rebuilt; once a match actually starts it hands
 * over to PvpPage, because a live PvP fight already renders through
 * CombatEncounterView, which on this phone is the drawer layout built earlier.
 * Three combat views would be two too many.
 */

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <div className="e-num text-lg font-bold leading-none" style={{ color: tone ?? "var(--a-100)" }}>
        {value}
      </div>
      <div className="mt-1 text-[10.5px]" style={{ color: "var(--a-500)" }}>
        {label}
      </div>
    </div>
  );
}

export function ArenaPanel() {
  const { status, match, loading, joinQueue, leaveQueue, acceptChallenge } = usePvpApi();

  // Anything past "waiting around" is a real fight — let the existing flow own it.
  const inFlight =
    match?.status === "active" ||
    status?.match_status === "active" ||
    status?.match_status === "finished";

  if (inFlight) return <PvpPage />;

  if (loading && !status) {
    return (
      <p className="py-10 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
        Entering the coliseum…
      </p>
    );
  }

  const s = status?.stats ?? null;
  const queued = status?.match_status === "queued";
  const challenged = status?.match_status === "challenged";
  const incoming = status?.incoming_challenge ?? null;

  return (
    <div className="space-y-3">
      {/* ── Someone wants to fight you ── */}
      {incoming ? (
        <div className="e-card e-card--ready flex items-center gap-3 p-4">
          <div className="min-w-0 flex-1">
            <div className="e-label mb-1">Challenge</div>
            <p className="text-[13.5px]" style={{ color: "var(--a-100)" }}>
              <span style={{ color: "var(--e-300)" }}>{incoming.from_name || "Someone"}</span> wants
              to fight you
              {incoming.mode ? (
                <span style={{ color: "var(--a-500)" }}> · {incoming.mode}</span>
              ) : null}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void acceptChallenge()}
            className="e-btn e-btn--primary shrink-0 px-4"
          >
            Accept
          </button>
        </div>
      ) : null}

      {/* ── Record ── */}
      <div className="e-card e-card--warm p-4">
        <div className="mb-3 flex items-baseline justify-between">
          <span className="e-label">Your record</span>
          {s?.rank_tier ? <span className="e-pill e-pill--gold">{s.rank_tier}</span> : null}
        </div>
        {s ? (
          <>
            <div className="mb-3 flex items-end gap-5">
              <div>
                <div className="e-num text-3xl font-bold leading-none" style={{ color: "var(--e-400)" }}>
                  {Number(s.rating ?? 0).toLocaleString()}
                </div>
                <div className="mt-1 text-[10.5px]" style={{ color: "var(--a-500)" }}>
                  rating
                </div>
              </div>
              {Number(s.streak ?? 0) > 0 ? (
                <div className="e-pill e-pill--ember mb-1">🔥 {s.streak} in a row</div>
              ) : null}
            </div>
            <div className="grid grid-cols-4 gap-3">
              <Stat label="won" value={String(s.wins ?? 0)} tone="var(--vital)" />
              <Stat label="lost" value={String(s.losses ?? 0)} tone="var(--wound)" />
              <Stat label="drawn" value={String(s.draws ?? 0)} />
              <Stat label="win rate" value={`${Math.round(Number(s.win_rate ?? 0))}%`} />
            </div>
          </>
        ) : (
          <p className="text-[12px]" style={{ color: "var(--a-500)" }}>
            No matches yet. Queue up and find out.
          </p>
        )}
      </div>

      {/* ── Queue ── */}
      {queued || challenged ? (
        <div className="e-card e-card--ready p-4 text-center">
          <p className="mb-1 text-[14px] font-semibold" style={{ color: "var(--a-100)" }}>
            {queued ? "Looking for an opponent…" : "Waiting for them to answer…"}
          </p>
          <p className="mb-3 text-[11.5px]" style={{ color: "var(--a-500)" }}>
            {queued && status?.mode ? `${status.mode} queue` : "You'll be pulled in automatically."}
          </p>
          <button type="button" onClick={() => void leaveQueue()} className="e-btn e-btn--quiet w-full">
            {queued ? "Leave queue" : "Cancel"}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => void joinQueue("ranked")}
            className="e-btn e-btn--primary w-full"
          >
            Queue ranked
          </button>
          <button
            type="button"
            onClick={() => void joinQueue("casual")}
            className={cn("e-btn e-btn--ghost w-full")}
          >
            Queue casual — no rating at stake
          </button>
        </div>
      )}

      <p className="px-1 text-center text-[10.5px] leading-relaxed" style={{ color: "var(--a-700)" }}>
        Challenging a specific player and full match history are in the classic Arena.
      </p>
    </div>
  );
}
