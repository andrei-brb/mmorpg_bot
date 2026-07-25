import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { CombatTab } from "@/components/game/tabs/CombatTab";
import { zoneMapImageUrl } from "@/data/zoneMapArt";
import { cn } from "@/lib/utils";

/**
 * Venture — "I want to go do something."
 *
 * Explore, fight and quests are one intent, so they're one tab. The classic UI
 * splits them across three, which means the loop (explore → find enemy → fight →
 * explore again) crosses two tab switches every cycle.
 *
 * This screen is deliberately COLD. Camp is the only warm screen in the app;
 * stepping out here should feel like stepping outside, and the temperature shift
 * is the navigation cue.
 *
 * Combat itself renders the existing CombatTab, which already uses the
 * phone-native drawer layout from earlier in this project — no reason to build
 * a third combat view.
 */

function ZoneArt({ zoneKey, name }: { zoneKey: string; name: string }) {
  const url = zoneMapImageUrl(zoneKey);
  return (
    <div
      className="relative h-28 w-full overflow-hidden rounded-xl"
      style={{ background: "linear-gradient(180deg, var(--n-700), var(--n-800))" }}
    >
      {url ? (
        <img src={url} alt="" className="h-full w-full object-cover" style={{ opacity: 0.72 }} />
      ) : (
        // Four of seven zones have no map art. Rather than an empty box, give the
        // card a deliberate ground so a missing asset reads as style.
        <div
          className="h-full w-full"
          style={{
            background:
              "radial-gradient(120% 80% at 50% 0%, rgba(255,122,47,0.12), transparent 65%), linear-gradient(180deg, var(--n-700), var(--n-800))",
          }}
        />
      )}
      <div
        className="absolute inset-0"
        style={{ background: "linear-gradient(180deg, transparent 30%, rgba(8,11,17,0.92))" }}
      />
      <div className="absolute inset-x-0 bottom-0 p-3">
        <div className="e-display text-base" style={{ color: "var(--a-100)" }}>
          {name}
        </div>
      </div>
    </div>
  );
}

export function VentureScreen() {
  const { map, travel, explore, lastExplore, quests, setCombatFocusActive } = useGameSession();
  const [busy, setBusy] = useState<"explore" | "travel" | null>(null);
  const [showCombat, setShowCombat] = useState(false);

  const zones = useMemo(() => map?.zones ?? [], [map?.zones]);
  const current = useMemo(() => zones.find((z) => z.is_current) ?? null, [zones]);

  const activeQuests = useMemo(
    () => (quests?.quests ?? []).filter((q) => q.state === "active" || q.state === "in_progress"),
    [quests?.quests],
  );

  async function doExplore() {
    setBusy("explore");
    try {
      const r = await explore();
      const outcome = r?.outcome;
      if (outcome?.type === "enemy" || outcome?.type === "boss") {
        toast.message(`${outcome.emoji ?? "⚔"} ${outcome.name ?? "Something found you"}`);
        setShowCombat(true);
      } else if (r?.reward) {
        const g = Number(r.reward.gold ?? 0);
        const x = Number(r.reward.xp ?? 0);
        toast.success(`Found ${g.toLocaleString()} gold and ${x.toLocaleString()} XP.`);
      } else {
        toast.message("Quiet out there.");
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function doTravel(zoneKey: string) {
    setBusy("travel");
    const r = await travel(zoneKey);
    setBusy(null);
    if (r.ok) toast.success(r.message || "You set out.");
    else toast.error(r.message || "Could not travel.");
  }

  if (showCombat) {
    return (
      <div className="min-h-full">
        <div
          className="flex items-center gap-2 px-4 pb-2"
          style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}
        >
          <button
            type="button"
            onClick={() => {
              setShowCombat(false);
              setCombatFocusActive(false);
            }}
            className="e-pill e-pill--quiet"
          >
            ← Back to the world
          </button>
        </div>
        <CombatTab />
      </div>
    );
  }

  return (
    <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
      <div className="mb-3 flex items-baseline justify-between px-4">
        <span className="e-label">Venture</span>
        {current?.level_min ? (
          <span className="text-[10.5px]" style={{ color: "var(--a-700)" }}>
            level {current.level_min}–{current.level_max}
          </span>
        ) : null}
      </div>

      <div className="space-y-3 px-4">
        {current ? <ZoneArt zoneKey={current.key} name={current.name} /> : null}

        {/* The one primary action out here. */}
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => void doExplore()}
          className="e-btn e-btn--primary w-full text-[15px]"
          style={{ letterSpacing: "0.04em" }}
        >
          {busy === "explore" ? "Searching…" : "Explore"}
        </button>

        <button
          type="button"
          onClick={() => setShowCombat(true)}
          className="e-btn e-btn--ghost w-full"
        >
          Pick a fight
        </button>

        {/* Last thing that happened, kept small — the result matters, the history doesn't. */}
        {lastExplore?.outcome ? (
          <div className="e-card e-card--cold p-3.5">
            <div className="e-label mb-1.5">Last time out</div>
            <p className="text-[13px]" style={{ color: "var(--a-100)" }}>
              {lastExplore.outcome.type === "enemy" || lastExplore.outcome.type === "boss"
                ? `${lastExplore.outcome.emoji ?? "⚔"} ${lastExplore.outcome.name ?? "An enemy"}`
                : lastExplore.outcome.type === "loot"
                  ? "You found something."
                  : "Nothing stirred."}
            </p>
            {lastExplore.reward ? (
              <div className="mt-2 flex gap-2">
                {Number(lastExplore.reward.gold ?? 0) > 0 ? (
                  <span className="e-pill e-pill--gold e-num">
                    🪙 {Number(lastExplore.reward.gold).toLocaleString()}
                  </span>
                ) : null}
                {Number(lastExplore.reward.xp ?? 0) > 0 ? (
                  <span className="e-pill e-pill--quiet e-num">
                    ✦ {Number(lastExplore.reward.xp).toLocaleString()}
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        {/* ── Where else you can go ── */}
        {zones.length > 1 ? (
          <div className="e-card p-4">
            <div className="e-label mb-3">Travel</div>
            <div className="space-y-2">
              {zones
                .filter((z) => !z.is_current)
                .map((z) => (
                  <button
                    key={z.key}
                    type="button"
                    disabled={busy !== null}
                    onClick={() => void doTravel(z.key)}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left"
                    style={{ background: "rgba(0,0,0,0.3)", border: "1px solid var(--n-500)" }}
                  >
                    <span className="text-base" aria-hidden>
                      {z.emoji || "🗺"}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px]" style={{ color: "var(--a-100)" }}>
                        {z.name}
                      </span>
                      <span className="block text-[10.5px]" style={{ color: "var(--a-700)" }}>
                        level {z.level_min}–{z.level_max}
                        {z.boss_alive ? " · world boss up" : ""}
                      </span>
                    </span>
                    {z.boss_alive ? (
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ background: "var(--wound)" }}
                        aria-label="World boss active"
                      />
                    ) : null}
                  </button>
                ))}
            </div>
          </div>
        ) : null}

        {/* ── Quests, as a summary rather than a tab ── */}
        <div className="e-card p-4">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="e-label">Quests</span>
            <span className="e-num text-[10.5px]" style={{ color: "var(--a-500)" }}>
              {activeQuests.length} active
            </span>
          </div>
          {activeQuests.length === 0 ? (
            <p className="text-[12px]" style={{ color: "var(--a-500)" }}>
              Nothing active. Talk to someone out in the world.
            </p>
          ) : (
            <ul className="space-y-2.5">
              {activeQuests.slice(0, 4).map((q) => {
                const cur = Number(q.progress?.current ?? 0);
                const need = Number(q.progress?.needed ?? 0);
                const pct = need > 0 ? Math.min(100, (cur / need) * 100) : 0;
                return (
                  <li key={q.quest_id}>
                    <div className="mb-1 flex items-baseline justify-between gap-2">
                      <span className="min-w-0 flex-1 truncate text-[12.5px]" style={{ color: "var(--a-100)" }}>
                        {q.quest_name || "Quest"}
                      </span>
                      {need > 0 ? (
                        <span className="e-num shrink-0 text-[10.5px]" style={{ color: "var(--a-500)" }}>
                          {cur}/{need}
                        </span>
                      ) : null}
                    </div>
                    {q.objective ? (
                      <p className="mb-1 text-[11px]" style={{ color: "var(--a-700)" }}>
                        {q.objective}
                      </p>
                    ) : null}
                    {need > 0 ? (
                      <div className="e-bar e-bar--xp" style={{ height: 3 }}>
                        <i style={{ width: `${pct}%` }} />
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
