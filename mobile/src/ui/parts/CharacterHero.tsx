import { useMemo, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { classIconUrl } from "@/lib/classAndSpecIconUrl";
import { publicBaseUrl } from "@/lib/gameApi";
import { hasSpecPortrait, specPortraitKey } from "@/lib/specPortraitCatalog";
import { cn } from "@/lib/utils";

/**
 * Your character, lit by the fire.
 *
 * The classic Hero tab renders the character as a paperdoll — a diagram of
 * equipment slots. That is a *systems* view. This is a *portrait* view: the
 * character is someone you are checking in on, which is the emotional core of a
 * game whose central mechanic is that they keep earning while you're gone.
 *
 * Portrait resolution walks spec art → class icon → nothing, same chain as
 * HeroTab.tsx:228-242. All 12 class/spec portraits exist in public/portraits/
 * characters, so a specced character always has real art.
 */

function titleCase(s?: string | null): string {
  return String(s || "")
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

export function CharacterHero({ compact = false }: { compact?: boolean }) {
  const { inventory } = useGameSession();
  const char = inventory?.character ?? null;
  const [portraitFailed, setPortraitFailed] = useState(false);

  const classKey = String(char?.class || "");
  const specKey = String(char?.specialization || "");

  const portraitUrl = useMemo(() => {
    if (classKey && specKey && hasSpecPortrait(classKey, specKey)) {
      return `${publicBaseUrl()}portraits/characters/${specPortraitKey(classKey, specKey)}.png?v=3`;
    }
    return classKey ? classIconUrl(classKey) : "";
  }, [classKey, specKey]);

  if (!char) return null;

  const hp = Number(char.current_hp ?? 0);
  const hpMax = Number(char.max_hp ?? 0);
  const hpPct = hpMax > 0 ? (hp / hpMax) * 100 : 0;
  const xpIn = Number(char.xp_in_level ?? 0);
  const xpNext = Number(char.xp_to_next ?? 0);
  const xpPct = xpNext > 0 ? (xpIn / xpNext) * 100 : 0;
  const maxed = Number(char.level ?? 0) >= 60 || xpNext === 0;

  return (
    <div className={cn("flex items-center gap-4", compact ? "px-4 py-3" : "px-5 pb-4 pt-2")}>
      {/* Portrait sits in its own pool of light rather than a frame. */}
      <div className="relative shrink-0">
        <div
          aria-hidden
          className="e-glow absolute -inset-3 rounded-full"
          style={{
            background: "radial-gradient(circle, rgba(255,122,47,0.32), transparent 68%)",
            filter: "blur(7px)",
          }}
        />
        <div
          className={cn(
            "relative overflow-hidden rounded-full",
            compact ? "h-14 w-14" : "h-[76px] w-[76px]",
          )}
          style={{ border: "1.5px solid rgba(255,154,92,0.55)", background: "var(--n-700)" }}
        >
          {portraitUrl && !portraitFailed ? (
            <img
              src={portraitUrl}
              alt={String(char.name || "Your character")}
              className="h-full w-full object-cover"
              style={{ objectPosition: "center 22%" }}
              onError={() => setPortraitFailed(true)}
            />
          ) : (
            <div className="grid h-full w-full place-items-center text-2xl">🗡️</div>
          )}
        </div>
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <h1
            className={cn("e-display truncate", compact ? "text-base" : "text-xl")}
            style={{ color: "var(--e-300)" }}
          >
            {char.name || "Adventurer"}
          </h1>
          <span className="e-num shrink-0 text-xs" style={{ color: "var(--a-500)" }}>
            Lv {char.level ?? "—"}
          </span>
        </div>

        <p className="mt-0.5 truncate text-[11px]" style={{ color: "var(--a-500)" }}>
          {titleCase(char.specialization_name || char.specialization) || titleCase(classKey) || "—"}
          {char.specialization && classKey ? ` ${titleCase(classKey)}` : ""}
          {char.guild_name ? ` · ${char.guild_tag ? `[${char.guild_tag}] ` : ""}${char.guild_name}` : ""}
        </p>

        <div className="mt-2 space-y-1.5">
          {hpMax > 0 ? (
            <div>
              <div className="mb-0.5 flex items-baseline justify-between">
                <span className="text-[10px]" style={{ color: "var(--a-500)" }}>
                  Health
                </span>
                <span className="e-num text-[10px]" style={{ color: "var(--a-300)" }}>
                  {hp.toLocaleString()} / {hpMax.toLocaleString()}
                </span>
              </div>
              <div className="e-bar e-bar--hp">
                <i style={{ width: `${Math.max(0, Math.min(100, hpPct))}%` }} />
              </div>
            </div>
          ) : null}

          {!compact ? (
            <div>
              <div className="mb-0.5 flex items-baseline justify-between">
                <span className="text-[10px]" style={{ color: "var(--a-500)" }}>
                  {maxed ? "Experience" : "To next level"}
                </span>
                <span className="e-num text-[10px]" style={{ color: "var(--a-300)" }}>
                  {maxed ? "Max level" : `${(xpNext - xpIn).toLocaleString()} XP`}
                </span>
              </div>
              <div className="e-bar e-bar--xp" style={{ height: 4 }}>
                <i style={{ width: `${maxed ? 100 : Math.max(0, Math.min(100, xpPct))}%` }} />
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
