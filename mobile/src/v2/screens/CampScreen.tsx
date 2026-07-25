import { useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { cn } from "@/lib/utils";
import { CharacterHero } from "@mobile/v2/parts/CharacterHero";
import { Journal } from "@mobile/v2/parts/Journal";
import { AdvisorCard, useSuggestion } from "@mobile/v2/parts/Advisor";
import type { CampSnapshot } from "@mobile/v2/useCampData";
import type { EmberTab } from "@mobile/v2/tabs";

/**
 * Camp — the home screen, and the thesis of this redesign.
 *
 * The classic UI has no home. It opens on Hero, which is an equipment
 * management screen, and everything time-gated is scattered: offline earnings
 * are a card inside Hero, daily login is inside Battle Pass, the daily quest is
 * inside Quests, forge work orders are inside Forge. To find out what's waiting
 * for you, you tour the app.
 *
 * Camp inverts that. Everything that wants you is here, claimable in place. A
 * player's entire daily is completable on this one screen without navigating —
 * which is the "quick check-in" half of the brief. The other four tabs are the
 * "settle in for a while" half.
 *
 * The warmth is the point: this is the fire you come back to, so it is the only
 * screen lit this way. Venture is cold on purpose.
 */

function StatChip({ label, value, tone }: { label: string; value: string; tone?: "gold" | "plain" }) {
  return (
    <div className="e-card px-3 py-2">
      <div className="e-label" style={{ fontSize: 9 }}>
        {label}
      </div>
      <div
        className="e-num mt-0.5 text-sm font-semibold"
        style={{ color: tone === "gold" ? "var(--g-400)" : "var(--a-100)" }}
      >
        {value}
      </div>
    </div>
  );
}

export function CampScreen({
  camp,
  onGo,
  onOpenSettings,
}: {
  camp: CampSnapshot;
  onGo: (t: EmberTab) => void;
  onOpenSettings: () => void;
}) {
  const { inventory } = useGameSession();
  const char = inventory?.character ?? null;
  const suggestion = useSuggestion(camp);
  const [busy, setBusy] = useState<string | null>(null);

  const gold = Number(char?.gold ?? 0);
  const pendingGold = Number(camp.idle?.pending_gold ?? 0);
  const pendingXp = Number(camp.idle?.pending_xp ?? 0);
  const hasIdle = pendingGold > 0 || pendingXp > 0;
  const hours = Number(camp.idle?.effective_hours ?? 0);
  const maxHours = Number(camp.idle?.max_hours ?? 0);
  const atCap = maxHours > 0 && hours >= maxHours;

  const login = camp.pass?.daily_login ?? null;
  const seasonLive = camp.pass?.season?.is_live ?? false;
  const canClaimLogin = Boolean(seasonLive && login && !login.claimed_today);

  const daily = camp.daily;

  async function collectIdle() {
    setBusy("idle");
    const r = await camp.claimIdle();
    setBusy(null);
    if (r.ok) toast.success(`Collected ${Number(r.gold ?? 0).toLocaleString()} gold.`);
    else toast.error(r.message || "Nothing to collect.");
  }

  async function collectLogin() {
    setBusy("login");
    const r = await camp.claimDailyLogin();
    setBusy(null);
    if (r.ok) toast.success(r.message || "Daily reward claimed.");
    else toast.error(r.message || "Could not claim.");
  }

  return (
    <div className="e-hearth min-h-full pb-6">
      {/* ── Top bar ── */}
      <div
        className="flex items-center gap-2 px-4"
        style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}
      >
        <span className="e-label flex-1">Camp</span>
        <span className="e-pill e-pill--gold e-num">🪙 {gold.toLocaleString()}</span>
        <button
          type="button"
          onClick={onOpenSettings}
          aria-label="Settings"
          className="grid h-8 w-8 place-items-center rounded-lg"
          style={{ border: "1px solid var(--n-500)", color: "var(--a-500)" }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.6 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H7a1.7 1.7 0 0 0 1-1.5V1a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V7a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
          </svg>
        </button>
      </div>

      {/* ── The character, by the fire ── */}
      <CharacterHero />

      <div className="space-y-3 px-4">
        {/* ── One suggested action ── */}
        {suggestion ? (
          <AdvisorCard
            suggestion={suggestion}
            onGo={(s) => {
              // The advisor points at Camp itself when the thing to do is right
              // here — in that case scroll to it rather than "navigating" to the
              // screen you're already on.
              if (s.tab === "camp") {
                document.getElementById("camp-waiting")?.scrollIntoView({ behavior: "smooth", block: "start" });
              } else onGo(s.tab);
            }}
          />
        ) : null}

        {/* ── Waiting for you ── */}
        <div id="camp-waiting" className="space-y-3" style={{ scrollMarginTop: 12 }}>
          {hasIdle ? (
            <div className="e-card e-card--ready p-4">
              <div className="mb-3 flex items-baseline justify-between">
                <span className="e-label">While you were away</span>
                {hours > 0 ? (
                  <span className="e-num text-[10px]" style={{ color: atCap ? "var(--e-400)" : "var(--a-500)" }}>
                    {hours < 1 ? "under an hour" : `${Math.floor(hours)}h`}
                    {atCap ? " · full" : ""}
                  </span>
                ) : null}
              </div>
              <div className="mb-3 flex gap-3">
                <div className="flex-1">
                  <div className="e-num text-2xl font-bold" style={{ color: "var(--g-400)" }}>
                    {pendingGold.toLocaleString()}
                  </div>
                  <div className="text-[11px]" style={{ color: "var(--a-500)" }}>
                    gold
                  </div>
                </div>
                <div className="flex-1">
                  <div className="e-num text-2xl font-bold" style={{ color: "var(--e-400)" }}>
                    {pendingXp.toLocaleString()}
                  </div>
                  <div className="text-[11px]" style={{ color: "var(--a-500)" }}>
                    experience
                  </div>
                </div>
              </div>
              {/* Being at the cap means you are actively losing earnings — the
                  classic UI shows the hours but never says what they mean. */}
              {atCap ? (
                <p className="mb-3 text-[11.5px] leading-relaxed" style={{ color: "var(--e-300)" }}>
                  You've hit the {maxHours}h cap — nothing more accrues until you collect.
                </p>
              ) : null}
              <button
                type="button"
                disabled={busy === "idle"}
                onClick={() => void collectIdle()}
                className="e-btn e-btn--primary w-full"
              >
                {busy === "idle" ? "Collecting…" : "Collect"}
              </button>
            </div>
          ) : null}

          {canClaimLogin ? (
            <div className="e-card e-card--ready flex items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <div className="e-label mb-1">Daily reward</div>
                <p className="text-[13px]" style={{ color: "var(--a-100)" }}>
                  Day {Number(login?.current_streak ?? 0) + 1} of your streak
                </p>
                {Number(login?.longest_streak ?? 0) > 0 ? (
                  <p className="mt-0.5 text-[11px]" style={{ color: "var(--a-500)" }}>
                    Best run: {login?.longest_streak} days
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                disabled={busy === "login"}
                onClick={() => void collectLogin()}
                className="e-btn e-btn--primary shrink-0 px-4"
              >
                {busy === "login" ? "…" : "Claim"}
              </button>
            </div>
          ) : null}

          {daily ? (
            <div className={cn("e-card p-4", daily.is_complete && "e-card--ready")}>
              <div className="mb-2 flex items-baseline justify-between gap-2">
                <span className="e-label">Today's quest</span>
                {daily.is_complete ? (
                  <span className="e-pill e-pill--ember">Complete</span>
                ) : (
                  <span className="text-[10px]" style={{ color: "var(--a-700)" }}>
                    resets at midnight
                  </span>
                )}
              </div>
              <p className="text-[13.5px] font-semibold" style={{ color: "var(--a-100)" }}>
                {daily.name || "Daily quest"}
              </p>
              {daily.description ? (
                <p className="mt-1 text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
                  {daily.description}
                </p>
              ) : null}

              <div className="mt-3 space-y-2">
                {(daily.objectives || []).map((o) => {
                  const have = Number((daily.progress || {})[o.id] ?? 0);
                  const need = Number(o.count ?? 0);
                  const pct = need > 0 ? Math.min(100, (have / need) * 100) : 0;
                  return (
                    <div key={o.id}>
                      <div className="mb-1 flex items-baseline justify-between gap-2">
                        <span className="min-w-0 flex-1 truncate text-[11.5px]" style={{ color: "var(--a-300)" }}>
                          {o.description || o.kind || "Objective"}
                        </span>
                        <span className="e-num shrink-0 text-[11px]" style={{ color: "var(--a-500)" }}>
                          {have}/{need}
                        </span>
                      </div>
                      <div className="e-bar e-bar--xp" style={{ height: 4 }}>
                        <i style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>

              {daily.rewards ? (
                <div className="mt-3 flex gap-2">
                  {Number(daily.rewards.gold ?? 0) > 0 ? (
                    <span className="e-pill e-pill--gold e-num">
                      🪙 {Number(daily.rewards.gold).toLocaleString()}
                    </span>
                  ) : null}
                  {Number(daily.rewards.xp ?? 0) > 0 ? (
                    <span className="e-pill e-pill--quiet e-num">
                      ✦ {Number(daily.rewards.xp).toLocaleString()} XP
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* ── At a glance ── */}
        <div className="grid grid-cols-3 gap-2">
          <StatChip label="Gold" value={gold.toLocaleString()} tone="gold" />
          <StatChip label="Forge" value={`Lv ${char?.crafting_level ?? 1}`} />
          <StatChip
            label="Bag"
            value={`${inventory?.bag_slots_used ?? 0}/${inventory?.bag_slots_max ?? 0}`}
          />
        </div>

        <Journal />
      </div>
    </div>
  );
}
