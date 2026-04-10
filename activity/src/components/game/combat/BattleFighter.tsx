import { useEffect, useState } from "react";

interface Props {
  name: string;
  icon: string;
  /** When set, shows an image instead of the emoji `icon`. */
  iconSrc?: string | null;
  hp: number;
  maxHp: number;
  mp?: number;
  maxMp?: number;
  /** Label for the resource bar (e.g. MP, Rage). */
  resourceLabel?: string;
  level: number;
  isPlayer?: boolean;
  isHit?: boolean;
  isAttacking?: boolean;
}

function hslWithAlpha(color: string, alpha: string): string {
  if (color.endsWith(")")) return `${color.slice(0, -1)} / ${alpha})`;
  return color;
}

export function BattleFighter({
  name,
  icon,
  iconSrc,
  hp,
  maxHp,
  mp,
  maxMp,
  resourceLabel = "MP",
  level,
  isPlayer = false,
  isHit = false,
  isAttacking = false,
}: Props) {
  const hpPercent = Math.max(0, (hp / maxHp) * 100);
  const mpPercent = mp && maxMp ? Math.max(0, (mp / maxMp) * 100) : 0;
  const [displayHp, setDisplayHp] = useState(hp);

  // Animate HP drain
  useEffect(() => {
    const diff = displayHp - hp;
    if (diff === 0) return;
    const step = Math.ceil(Math.abs(diff) / 12);
    const timer = setInterval(() => {
      setDisplayHp((prev) => {
        const next = prev > hp ? prev - step : prev + step;
        if ((prev > hp && next <= hp) || (prev < hp && next >= hp)) {
          clearInterval(timer);
          return hp;
        }
        return next;
      });
    }, 30);
    return () => clearInterval(timer);
  }, [hp]);

  const hpBarColor =
    hpPercent > 50
      ? "hsl(120 50% 40%)"
      : hpPercent > 25
        ? "hsl(45 80% 45%)"
        : "hsl(0 65% 45%)";

  const hitClass = isHit ? "animate-fighter-hit" : "";
  const attackClass = isAttacking
    ? isPlayer
      ? "animate-fighter-attack-right"
      : "animate-fighter-attack-left"
    : "";

  return (
    <div className={`flex flex-col items-center ${hitClass} ${attackClass}`}>
      {/* Sprite container */}
      <div
        className="relative mb-2"
        style={{
          width: 72,
          height: 72,
          background: "radial-gradient(ellipse, hsl(0 0% 0% / 0.4) 0%, transparent 70%)",
        }}
      >
        {iconSrc ? (
          <img
            src={iconSrc}
            alt=""
            width={56}
            height={56}
            className="absolute inset-0 m-auto object-contain select-none"
            style={{
              filter: "drop-shadow(0 4px 8px hsl(0 0% 0% / 0.7))",
              transform: isPlayer ? "scaleX(1)" : "scaleX(-1)",
            }}
          />
        ) : (
          <span
            className="absolute inset-0 flex items-center justify-center text-5xl select-none"
            style={{
              filter: "drop-shadow(0 4px 8px hsl(0 0% 0% / 0.7))",
              transform: isPlayer ? "scaleX(1)" : "scaleX(-1)",
            }}
          >
            {icon}
          </span>
        )}

        {/* Hit flash overlay */}
        {isHit && (
          <div
            className="absolute inset-0 rounded-full animate-hit-flash pointer-events-none"
            style={{
              background: "radial-gradient(circle, hsl(0 80% 60% / 0.5) 0%, transparent 70%)",
            }}
          />
        )}
      </div>

      {/* Name plate */}
      <div
        className="w-full max-w-[120px] rounded-sm px-2 py-1 text-center"
        style={{
          background: "hsl(228 22% 9% / 0.9)",
          border: "1px solid hsl(228 16% 20%)",
          boxShadow: "0 2px 8px hsl(0 0% 0% / 0.5)",
        }}
      >
        <div className="flex items-center justify-between mb-1">
          <span
            className="text-[9px] font-cinzel font-bold uppercase tracking-wider"
            style={{ color: "hsl(var(--gold))", textShadow: "0 0 4px hsl(var(--gold) / 0.3)" }}
          >
            Lv.{level}
          </span>
          <span className="text-[10px] font-cinzel font-semibold text-foreground truncate ml-1">
            {name}
          </span>
        </div>

        {/* HP bar */}
        <div className="mb-1">
          <div
            className="h-[6px] rounded-sm overflow-hidden"
            style={{
              background: "hsl(0 0% 0% / 0.6)",
              border: "1px solid hsl(228 16% 20% / 0.5)",
            }}
          >
            <div
              className="h-full rounded-sm transition-all duration-500 relative"
              style={{
                width: `${hpPercent}%`,
                background: `linear-gradient(180deg, ${hpBarColor}, ${hpBarColor.replace("40%", "28%")})`,
                boxShadow: `0 0 4px ${hslWithAlpha(hpBarColor, "0.5")}`,
              }}
            >
              <div
                className="absolute inset-0 rounded-sm"
                style={{
                  background: "linear-gradient(180deg, hsl(0 0% 100% / 0.15) 0%, transparent 60%)",
                }}
              />
            </div>
          </div>
          <div className="flex justify-between mt-0.5">
            <span className="text-[8px] text-muted-foreground">HP</span>
            <span className="text-[8px] text-foreground tabular-nums">
              {displayHp}/{maxHp}
            </span>
          </div>
        </div>

        {/* MP bar (player only) */}
        {mp !== undefined && maxMp !== undefined && (
          <div>
            <div
              className="h-[4px] rounded-sm overflow-hidden"
              style={{
                background: "hsl(0 0% 0% / 0.6)",
                border: "1px solid hsl(228 16% 20% / 0.5)",
              }}
            >
              <div
                className="h-full rounded-sm transition-all duration-300"
                style={{
                  width: `${mpPercent}%`,
                  background: "linear-gradient(180deg, hsl(210 65% 52%), hsl(210 60% 38%))",
                  boxShadow: "0 0 4px hsl(210 65% 48% / 0.5)",
                }}
              />
            </div>
            <div className="flex justify-between mt-0.5">
              <span className="text-[8px] text-muted-foreground truncate max-w-[3.5rem]">{resourceLabel}</span>
              <span className="text-[8px] text-foreground tabular-nums">
                {mp}/{maxMp}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
