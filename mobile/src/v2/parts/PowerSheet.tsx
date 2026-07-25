import type { CharacterDerivedStatsPayload } from "@/lib/apiTypes";

/**
 * Where your Combat Power actually comes from.
 *
 * A NEW system. The classic Hero tab prints "COMBAT POWER 6,678" as a single
 * opaque number (HeroTab.tsx:728-739) — the player has no way to learn what
 * moves it, so they can't reason about upgrades. That's a real problem in a game
 * whose whole loop is "get stronger".
 *
 * The formula is already in the codebase; this just shows its terms and what
 * each contributes. Nothing here is invented — the weights are lifted verbatim
 * from HeroTab so the total matches what the rest of the game displays.
 */

const W = {
  attack: 1,
  spell: 1,
  armor: 2,
  hit: 12,
  haste: 15,
  crit: 180,
} as const;

export function computePower(d: CharacterDerivedStatsPayload | null): number {
  if (!d) return 0;
  return Math.round(
    Number(d.attack_power ?? 0) * W.attack +
      Number(d.spell_power ?? 0) * W.spell +
      Number(d.armor ?? 0) * W.armor +
      Number(d.hit_rating ?? 0) * W.hit +
      Number(d.haste ?? 0) * W.haste +
      Number(d.crit_chance ?? 0) * W.crit,
  );
}

type Term = { label: string; raw: string; contribution: number; hint: string };

function terms(d: CharacterDerivedStatsPayload): Term[] {
  const t: Term[] = [
    {
      label: "Attack power",
      raw: Number(d.attack_power ?? 0).toLocaleString(),
      contribution: Number(d.attack_power ?? 0) * W.attack,
      hint: "1 point of power each",
    },
    {
      label: "Spell power",
      raw: Number(d.spell_power ?? 0).toLocaleString(),
      contribution: Number(d.spell_power ?? 0) * W.spell,
      hint: "1 point of power each",
    },
    {
      label: "Armor",
      raw: Number(d.armor ?? 0).toLocaleString(),
      contribution: Number(d.armor ?? 0) * W.armor,
      hint: "worth double",
    },
    {
      label: "Critical chance",
      raw: `${Number(d.crit_chance ?? 0).toFixed(1)}%`,
      contribution: Number(d.crit_chance ?? 0) * W.crit,
      hint: "the heaviest stat — 180× per point",
    },
    {
      label: "Haste",
      raw: Number(d.haste ?? 0).toLocaleString(),
      contribution: Number(d.haste ?? 0) * W.haste,
      hint: "15× per point",
    },
    {
      label: "Hit rating",
      raw: Number(d.hit_rating ?? 0).toLocaleString(),
      contribution: Number(d.hit_rating ?? 0) * W.hit,
      hint: "12× per point",
    },
  ];
  return t.filter((x) => x.contribution > 0).sort((a, b) => b.contribution - a.contribution);
}

export function PowerSheet({
  derived,
  onClose,
}: {
  derived: CharacterDerivedStatsPayload | null;
  onClose: () => void;
}) {
  const total = computePower(derived);
  const rows = derived ? terms(derived) : [];
  const max = rows.length ? rows[0].contribution : 1;

  return (
    <>
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
      />
      <div
        className="e-sheet e-scroll fixed inset-x-0 bottom-0 z-50 max-h-[80dvh] px-4"
        role="dialog"
        aria-modal="true"
        aria-label="Combat power breakdown"
      >
        <div className="e-grabber" />
        <div className="mb-1 flex items-baseline justify-between">
          <h2 className="e-display text-base" style={{ color: "var(--e-300)" }}>
            Combat power
          </h2>
          <span className="e-num text-xl font-bold" style={{ color: "var(--a-100)" }}>
            {total.toLocaleString()}
          </span>
        </div>
        <p className="mb-4 text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
          Every stat is worth a different amount of power. Sorted by what's actually carrying you.
        </p>

        {rows.length === 0 ? (
          <p className="py-6 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
            No stats to break down yet.
          </p>
        ) : (
          <ul className="space-y-3 pb-2">
            {rows.map((r) => (
              <li key={r.label}>
                <div className="mb-1 flex items-baseline justify-between gap-2">
                  <span className="text-[13px]" style={{ color: "var(--a-100)" }}>
                    {r.label}
                  </span>
                  <span className="e-num shrink-0 text-[12px]" style={{ color: "var(--a-300)" }}>
                    {r.raw}
                    <span style={{ color: "var(--a-700)" }}> → </span>
                    <span style={{ color: "var(--e-400)" }}>
                      {Math.round(r.contribution).toLocaleString()}
                    </span>
                  </span>
                </div>
                <div className="e-bar" style={{ height: 5 }}>
                  <i
                    style={{
                      width: `${(r.contribution / max) * 100}%`,
                      background: "linear-gradient(90deg, var(--e-700), var(--e-400))",
                    }}
                  />
                </div>
                <p className="mt-1 text-[10.5px]" style={{ color: "var(--a-700)" }}>
                  {r.hint}
                </p>
              </li>
            ))}
          </ul>
        )}

        <div className="e-card mt-2 p-3">
          <p className="text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
            Because critical chance is weighted 180×, a single point of crit is worth more than 100
            armor. Worth knowing before your next upgrade.
          </p>
        </div>

        <button type="button" onClick={onClose} className="e-btn e-btn--quiet mt-4 w-full">
          Close
        </button>
      </div>
    </>
  );
}
