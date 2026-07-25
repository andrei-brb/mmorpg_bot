import { useMemo } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import type { CampSnapshot } from "@mobile/v2/useCampData";

/**
 * Legend — "How am I doing, long term?"
 *
 * The classic UI scatters long-term progress across Battle Pass (its own tab),
 * prestige (a panel inside Hero), and achievements/milestones/story (three of
 * Realm's seven sub-tabs). Nowhere shows you the shape of your account.
 *
 * This is the answer to "what have I actually built here" — every permanent
 * axis on one screen, read-only. Claiming still happens where claiming happens.
 */

function Row({
  label,
  value,
  hint,
  pct,
}: {
  label: string;
  value: string;
  hint?: string;
  pct?: number;
}) {
  return (
    <div className="e-card p-3.5">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="e-label">{label}</span>
        <span className="e-num text-[13px] font-semibold" style={{ color: "var(--a-100)" }}>
          {value}
        </span>
      </div>
      {pct != null ? (
        <div className="e-bar e-bar--xp mt-2" style={{ height: 4 }}>
          <i style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
        </div>
      ) : null}
      {hint ? (
        <p className="mt-1.5 text-[11px] leading-relaxed" style={{ color: "var(--a-700)" }}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function LegendScreen({ camp }: { camp: CampSnapshot }) {
  const { inventory, progress } = useGameSession();
  const char = inventory?.character ?? null;

  const pass = camp.pass ?? null;
  const season = pass?.season ?? null;
  const prestige = camp.prestige ?? null;

  const achievements = progress?.achievements ?? [];
  const points = useMemo(
    () => achievements.reduce((a, x) => a + Number(x.points ?? 0), 0),
    [achievements],
  );

  const stats = progress?.stats ?? null;
  const wins = Number(stats?.wins ?? 0);
  const losses = Number(stats?.losses ?? 0);
  const total = Number(stats?.total_combats ?? 0);
  const winRate = total > 0 ? Math.round((wins / total) * 100) : 0;

  const level = Number(char?.level ?? 0);
  const xpIn = Number(char?.xp_in_level ?? 0);
  const xpNext = Number(char?.xp_to_next ?? 0);

  return (
    <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
      <div className="mb-3 px-4">
        <span className="e-label">Legend</span>
      </div>

      <div className="space-y-3 px-4">
        {/* ── The headline: what you've built ── */}
        <div className="e-card e-card--warm p-4">
          <div className="e-label mb-2">Your account</div>
          <div className="flex items-end gap-4">
            <div>
              <div className="e-num text-3xl font-bold leading-none" style={{ color: "var(--e-400)" }}>
                {level || "—"}
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--a-500)" }}>
                character level
              </div>
            </div>
            <div>
              <div className="e-num text-2xl font-bold leading-none" style={{ color: "var(--a-100)" }}>
                {char?.crafting_level ?? 1}
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--a-500)" }}>
                forge level
              </div>
            </div>
            <div>
              <div className="e-num text-2xl font-bold leading-none" style={{ color: "var(--g-400)" }}>
                {Number(prestige?.prestige ?? 0)}
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--a-500)" }}>
                prestige
              </div>
            </div>
          </div>
          {xpNext > 0 && level < 60 ? (
            <div className="mt-3">
              <div className="e-bar e-bar--xp" style={{ height: 4 }}>
                <i style={{ width: `${Math.min(100, (xpIn / xpNext) * 100)}%` }} />
              </div>
              <p className="mt-1.5 text-[11px]" style={{ color: "var(--a-700)" }}>
                {(xpNext - xpIn).toLocaleString()} XP to level {level + 1}
              </p>
            </div>
          ) : null}
        </div>

        {/* ── Season ── */}
        {season?.is_live ? (
          <Row
            label="Battle pass"
            value={`Tier ${Number(pass?.progress?.tier ?? 0)} / ${Number(season?.max_tier ?? 0)}`}
            pct={
              Number(season?.max_tier ?? 0) > 0
                ? (Number(pass?.progress?.tier ?? 0) / Number(season?.max_tier ?? 1)) * 100
                : 0
            }
            hint={season.name ? `${season.name} — claim rewards in the classic Battle Pass tab.` : undefined}
          />
        ) : (
          <Row label="Battle pass" value="No live season" hint="Nothing running right now." />
        )}

        {/* ── Prestige ── */}
        {prestige ? (
          <Row
            label="Prestige"
            value={`Rank ${Number(prestige.prestige ?? 0)} / ${Number(prestige.max ?? 0)}`}
            hint={
              prestige.eligible
                ? `You can prestige now for a permanent +${Number(prestige.next_xp_bonus_pct ?? 0)}% XP bonus. It resets your level.`
                : `+${Number(prestige.xp_bonus_pct ?? 0)}% XP from prestige so far.${
                    prestige.required_level ? ` Next rank needs level ${prestige.required_level}.` : ""
                  }`
            }
          />
        ) : null}

        {/* ── Combat record ── */}
        {total > 0 ? (
          <div className="e-card p-4">
            <div className="e-label mb-3">Combat record</div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <div className="e-num text-xl font-bold" style={{ color: "var(--vital)" }}>
                  {wins.toLocaleString()}
                </div>
                <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
                  won
                </div>
              </div>
              <div>
                <div className="e-num text-xl font-bold" style={{ color: "var(--wound)" }}>
                  {losses.toLocaleString()}
                </div>
                <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
                  lost
                </div>
              </div>
              <div>
                <div className="e-num text-xl font-bold" style={{ color: "var(--a-100)" }}>
                  {winRate}%
                </div>
                <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
                  win rate
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {/* ── Achievements ── */}
        <div className="e-card p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <span className="e-label">Achievements</span>
            <span className="e-num text-[11px]" style={{ color: "var(--g-400)" }}>
              {points.toLocaleString()} points
            </span>
          </div>
          {achievements.length === 0 ? (
            <p className="text-[12px]" style={{ color: "var(--a-500)" }}>
              None earned yet.
            </p>
          ) : (
            <ul className="space-y-2">
              {achievements.slice(0, 8).map((a, i) => (
                <li key={a.id ?? i} className="flex items-baseline gap-2.5">
                  <span className="shrink-0 text-[13px]" aria-hidden>
                    {a.icon || "◆"}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[12.5px]" style={{ color: "var(--a-100)" }}>
                      {a.name}
                    </span>
                    {a.description ? (
                      <span className="block truncate text-[10.5px]" style={{ color: "var(--a-700)" }}>
                        {a.description}
                      </span>
                    ) : null}
                  </span>
                  {a.points ? (
                    <span className="e-num shrink-0 text-[10.5px]" style={{ color: "var(--g-400)" }}>
                      +{a.points}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        <p className="px-1 text-center text-[11px] leading-relaxed" style={{ color: "var(--a-700)" }}>
          Talents, reputation and story deeds live in the classic Realm tab —
          switch back in Settings to reach them.
        </p>
      </div>
    </div>
  );
}
