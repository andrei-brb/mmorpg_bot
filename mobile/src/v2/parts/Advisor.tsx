import { useMemo } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import type { CampSnapshot } from "@mobile/v2/useCampData";
import type { EmberTab } from "@mobile/v2/tabs";

/**
 * "What should I do right now?"
 *
 * A NEW system, not a reorganisation. This game has ten separate systems, each
 * with its own timers and gates, and nothing anywhere answers the question a
 * returning player actually has. The classic UI makes you visit every tab to
 * find out what's ready.
 *
 * This reads live state and ranks it. Ordering is deliberate — free money you
 * already earned first, then things that expire, then things that are merely
 * available:
 *
 *   1  work finished at the forge      (already paid for; claim it)
 *   2  offline earnings                (already earned; collect it)
 *   3  daily quest done                (expires at midnight)
 *   4  gear damaged                    (silently weakening you)
 *   5  the main story compass          (server-driven — it knows better than I do)
 *   6  daily quest not done            (expires at midnight)
 *   7  prestige available              (a big, permanent, deliberate choice)
 *   8  nothing pressing                (go play)
 *
 * It never invents a suggestion: every branch is backed by a real field, and if
 * none fire it says so rather than manufacturing urgency.
 */

export type Suggestion = {
  icon: string;
  title: string;
  detail: string;
  cta: string;
  tab: EmberTab;
  /** Claimables get the warm treatment; everything else stays cool. */
  ready?: boolean;
};

export function useSuggestion(camp: CampSnapshot): Suggestion | null {
  const { inventory, quests, map } = useGameSession();
  const char = inventory?.character ?? null;

  return useMemo(() => {
    const job = inventory?.craft_job ?? null;
    const gold = Number(char?.gold ?? 0);

    // 1 — the forge finished something
    if (job && (job.status === "ready" || job.status === "active")) {
      const done =
        job.status === "ready" ||
        (job.completes_at ? Date.parse(String(job.completes_at)) <= Date.now() : false);
      if (done) {
        return {
          icon: "⚒",
          title: "Your work is finished",
          detail: "The forge is waiting for you to collect it.",
          cta: "Collect it",
          tab: "forge",
          ready: true,
        };
      }
    }

    // 2 — offline earnings
    const pendingGold = Number(camp.idle?.pending_gold ?? 0);
    const pendingXp = Number(camp.idle?.pending_xp ?? 0);
    if (pendingGold > 0 || pendingXp > 0) {
      const hrs = Number(camp.idle?.effective_hours ?? 0);
      return {
        icon: "🔥",
        title: "You've been earning while away",
        detail:
          `${pendingGold.toLocaleString()} gold and ${pendingXp.toLocaleString()} XP` +
          (hrs > 0 ? ` from ${hrs < 1 ? "under an hour" : `${Math.floor(hrs)} hours`}.` : "."),
        cta: "Collect",
        tab: "camp",
        ready: true,
      };
    }

    // 3 — daily quest finished but not turned in
    if (camp.daily?.is_complete) {
      const r = camp.daily.rewards || {};
      return {
        icon: "✦",
        title: "Daily quest complete",
        detail: `${camp.daily.name || "Today's quest"} — ${Number(r.gold ?? 0).toLocaleString()} gold waiting.`,
        cta: "Claim it",
        tab: "camp",
        ready: true,
      };
    }

    // 4 — damaged gear, only if they can actually pay for it
    const damaged = camp.repair?.items?.length ?? 0;
    const repairCost = Number(camp.repair?.total ?? 0);
    if (damaged > 0 && repairCost > 0 && gold >= repairCost) {
      return {
        icon: "🛠",
        title: `${damaged} piece${damaged === 1 ? "" : "s"} of gear ${damaged === 1 ? "is" : "are"} damaged`,
        detail: `Damaged gear fights weaker. Repairing costs ${repairCost.toLocaleString()} gold.`,
        cta: "Repair",
        tab: "forge",
      };
    }

    // 5 — the story compass, straight from the server
    const ptr = quests?.main_quest_pointer ?? null;
    if (ptr && ptr.kind && ptr.kind !== "none" && ptr.kind !== "complete") {
      const hint = String((ptr as Record<string, unknown>).hint || "").trim();
      const qName = String((ptr as Record<string, unknown>).quest_name || "").trim();
      if (ptr.kind === "active" || ptr.kind === "seek_npc") {
        return {
          icon: "🧭",
          title: qName || "Your story continues",
          detail: hint || "Follow the main quest onward.",
          cta: "Go",
          tab: "quests",
        };
      }
    }

    // 6 — daily quest still open
    if (camp.daily && !camp.daily.is_complete) {
      const objs = camp.daily.objectives || [];
      const prog = camp.daily.progress || {};
      const first = objs[0];
      const have = first ? Number(prog[first.id] ?? 0) : 0;
      const need = first ? Number(first.count ?? 0) : 0;
      return {
        icon: "◈",
        title: camp.daily.name || "Today's quest",
        detail:
          first?.description
            ? `${first.description}${need > 0 ? ` — ${have}/${need}` : ""}`
            : "Finish today's quest before it resets.",
        cta: "Head out",
        tab: "quests",
      };
    }

    // 7 — prestige
    if (camp.prestige?.eligible) {
      return {
        icon: "★",
        title: "You can prestige",
        detail: `Reset for a permanent +${Number(camp.prestige.next_xp_bonus_pct ?? 0)}% XP bonus. This is permanent.`,
        cta: "Look at it",
        tab: "hero",
      };
    }

    // 8 — nothing owed; suggest the loop rather than inventing urgency
    const zone = map?.zones?.find((z) => z.is_current);
    return {
      icon: "🗺",
      title: "Nothing's waiting — go make something happen",
      detail: zone?.name ? `You're in ${zone.name}. Explore, or pick a fight.` : "Explore, or pick a fight.",
      cta: "Head out",
      tab: "explore",
    };
  }, [camp.idle, camp.daily, camp.repair, camp.prestige, inventory?.craft_job, char?.gold, quests, map]);
}

export function AdvisorCard({
  suggestion,
  onGo,
}: {
  suggestion: Suggestion;
  onGo: (s: Suggestion) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onGo(suggestion)}
      className={`e-card ${suggestion.ready ? "e-card--ready" : "e-card--warm"} w-full p-4 text-left`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0 text-xl leading-none" aria-hidden>
          {suggestion.icon}
        </span>
        <div className="min-w-0 flex-1">
          <div className="e-label mb-1">Next</div>
          <p className="text-[15px] font-semibold leading-snug" style={{ color: "var(--a-100)" }}>
            {suggestion.title}
          </p>
          <p className="mt-1 text-[12.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
            {suggestion.detail}
          </p>
        </div>
        <span
          className="e-pill e-pill--ember mt-0.5 shrink-0 whitespace-nowrap"
          style={{ alignSelf: "center" }}
        >
          {suggestion.cta} →
        </span>
      </div>
    </button>
  );
}
