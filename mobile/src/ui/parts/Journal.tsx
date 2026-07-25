import { useMemo } from "react";
import { useGameSession } from "@/context/GameSessionContext";

/**
 * What your character has been doing.
 *
 * The data already exists — progress.history carries
 * {type, outcome, zone, amount, reason, source, at} — but the classic UI buries
 * it in Realm → Records as a raw log, four taps from home.
 *
 * The reframing: this game's central mechanic is that your character keeps
 * going while you're gone. That's a story, and the numbers are already there to
 * tell it. So history moves to the home screen and reads as prose. Same rows,
 * completely different meaning.
 */

type Row = {
  type?: string;
  outcome?: string;
  zone?: string;
  amount?: number;
  reason?: string;
  source?: string;
  at?: string;
};

function timeAgo(at?: string): string {
  if (!at) return "";
  const t = Date.parse(at);
  if (!Number.isFinite(t)) return "";
  const mins = Math.floor((Date.now() - t) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function titleZone(z?: string): string {
  return String(z || "")
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

/** One history row → one sentence. Returns null for rows not worth a line. */
function narrate(r: Row): { icon: string; text: string; tone: "win" | "loss" | "gold" | "plain" } | null {
  const amt = Number(r.amount ?? 0);
  const zone = titleZone(r.zone);
  const where = zone ? ` in ${zone}` : "";

  if (r.type === "victory" || r.outcome === "victory") {
    return { icon: "⚔", text: `Won a fight${where}.`, tone: "win" };
  }
  if (r.type === "defeat" || r.outcome === "defeat") {
    return { icon: "✖", text: `Fell in battle${where}.`, tone: "loss" };
  }
  if (r.type === "combat_gold" || (r.type === "gold" && amt > 0)) {
    const why = r.reason || r.source || "";
    const because =
      why === "exploration" ? " while exploring" : why === "idle" ? " while you were away" : "";
    return { icon: "🪙", text: `Earned ${amt.toLocaleString()} gold${because}.`, tone: "gold" };
  }
  if (r.type === "gold" && amt < 0) {
    return { icon: "🪙", text: `Spent ${Math.abs(amt).toLocaleString()} gold${r.reason ? ` on ${r.reason}` : ""}.`, tone: "plain" };
  }
  if (r.type === "combat_session") {
    return { icon: "⚔", text: `Fought${where}.`, tone: "plain" };
  }
  // Unknown row shapes are skipped rather than rendered as raw JSON — an
  // unrecognised type should read as "nothing happened", not as a bug.
  return null;
}

const TONE: Record<string, string> = {
  win: "var(--vital)",
  loss: "var(--wound)",
  gold: "var(--g-400)",
  plain: "var(--a-500)",
};

export function Journal({ limit = 6 }: { limit?: number }) {
  const { progress } = useGameSession();

  const lines = useMemo(() => {
    const hist = (progress?.history ?? []) as Row[];
    return hist
      .map((r) => ({ r, n: narrate(r) }))
      .filter((x): x is { r: Row; n: NonNullable<ReturnType<typeof narrate>> } => x.n !== null)
      .slice(0, limit);
  }, [progress?.history, limit]);

  if (lines.length === 0) {
    return (
      <div className="e-card p-4">
        <div className="e-label mb-2">Journal</div>
        <p className="text-[12.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
          Nothing written yet. Head out and your deeds will land here.
        </p>
      </div>
    );
  }

  return (
    <div className="e-card p-4">
      <div className="e-label mb-3">Journal</div>
      <ul className="space-y-2.5">
        {lines.map(({ r, n }, i) => (
          <li key={`${r.at ?? i}-${i}`} className="flex items-baseline gap-2.5">
            <span className="shrink-0 text-[11px] leading-none" style={{ color: TONE[n.tone] }} aria-hidden>
              {n.icon}
            </span>
            <span className="min-w-0 flex-1 text-[12.5px] leading-snug" style={{ color: "var(--a-300)" }}>
              {n.text}
            </span>
            <span className="e-num shrink-0 text-[10px]" style={{ color: "var(--a-700)" }}>
              {timeAgo(r.at)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
