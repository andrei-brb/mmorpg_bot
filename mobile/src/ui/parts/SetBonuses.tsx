import { useGameSession } from "@/context/GameSessionContext";

/**
 * Set bonuses you are actually receiving.
 *
 * These have been applied to live stats for as long as the game has existed
 * (CharacterService.get_derived_stats) but were never sent to any client, and
 * the old Hero tab showed a fake "SET BONUS x/5" that counted epic and
 * legendary pieces instead. So players were getting bonuses they could not see,
 * plan around, or chase.
 *
 * The payload is computed server-side from the same table that grants the
 * bonus, so what's shown here cannot drift from what's applied.
 *
 * Deliberately renders nothing when no set pieces are worn: only 8 of 568
 * templates belong to a set today, so an always-present "0 sets" card would be
 * noise for almost everyone.
 */
export function SetBonuses() {
  const { inventory } = useGameSession();
  const sets = inventory?.item_sets ?? [];

  if (sets.length === 0) return null;

  return (
    <div className="e-card e-card--warm p-4">
      <div className="e-label mb-3">Set bonuses</div>
      <div className="space-y-3">
        {sets.map((s) => {
          const max = Number(s.max_pieces ?? 0);
          const pct = max > 0 ? Math.min(100, (s.equipped / max) * 100) : 0;
          return (
            <div key={s.set_id}>
              <div className="mb-1 flex items-baseline justify-between gap-2">
                <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold" style={{ color: "var(--e-300)" }}>
                  {s.name}
                </span>
                <span className="e-num shrink-0 text-[11.5px]" style={{ color: "var(--a-300)" }}>
                  {s.equipped}
                  {max > 0 ? ` / ${max}` : ""}
                </span>
              </div>

              {max > 0 ? (
                <div className="e-bar e-bar--xp mb-1.5" style={{ height: 4 }}>
                  <i style={{ width: `${pct}%` }} />
                </div>
              ) : null}

              {s.active_bonus ? (
                <p className="text-[12px] leading-relaxed" style={{ color: "var(--vital)" }}>
                  ✓ {s.active_tier}-piece: {s.active_bonus}
                </p>
              ) : (
                <p className="text-[12px]" style={{ color: "var(--a-700)" }}>
                  No bonus active yet.
                </p>
              )}

              {/* The chase. Absent when the set has no reachable next tier, so
                  we never dangle a bonus that cannot be earned. */}
              {s.next_bonus && s.pieces_to_next ? (
                <p className="mt-0.5 text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
                  {s.pieces_to_next} more {s.pieces_to_next === 1 ? "piece" : "pieces"} →{" "}
                  <span style={{ color: "var(--e-400)" }}>{s.next_bonus}</span>
                </p>
              ) : s.active_bonus ? (
                <p className="mt-0.5 text-[12px]" style={{ color: "var(--a-700)" }}>
                  Complete — this set has nothing further.
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
