import React, { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { getBattlefieldBackgroundStackStyle } from "@/components/game/combat/BattleBackground";

export interface CharacterStat {
  label: string;
  value: string | number;
}

export interface CharacterData {
  name: string;
  portraitUrl: string;
  stats: CharacterStat[];
  level?: number;
  class?: string;
  title?: string;
  element?: "fire" | "ice" | "lightning" | "earth" | "dark" | "light";
  isBoss?: boolean;
  weakness?: string;
  indicators?: string[];
}

export interface GridUnit {
  id: string;
  imageUrl?: string;
  label?: string;
  row: number;
  col: number;
}

export interface BattlePreviewData {
  player: CharacterData;
  enemy: CharacterData;
  /**
   * Used when `battlefieldZoneKey` is not set — e.g. a static imported image or `/assets/...` URL.
   * May be empty when `battlefieldZoneKey` is provided.
   */
  backgroundUrl: string;
  /** Same zone art stack as `<BattleBackground />` (png → jpg → gradient). Overrides `backgroundUrl`. */
  battlefieldZoneKey?: string;
  gridRows?: number;
  gridCols?: number;
  units?: GridUnit[];
  buttonLabel?: string;
  onCommence?: () => void;
}

function SafePortraitImage({
  src,
  alt,
  className,
  fallbackCandidates,
}: {
  src: string;
  alt: string;
  className: string;
  fallbackCandidates: string[];
}) {
  const sourceChain = React.useMemo(
    () => [src, ...fallbackCandidates].filter((v, i, arr) => Boolean(v) && arr.indexOf(v) === i),
    [src, fallbackCandidates],
  );
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    setActiveIndex(0);
  }, [sourceChain]);

  return (
    <img
      src={sourceChain[activeIndex]}
      alt={alt}
      className={className}
      loading="lazy"
      onError={() => {
        setActiveIndex((prev) => (prev < sourceChain.length - 1 ? prev + 1 : prev));
      }}
    />
  );
}

function deriveFallbackCandidates(src: string, placeholder: string): string[] {
  const lower = src.toLowerCase();
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) {
    return [src.replace(/\.(jpe?g)$/iu, ".png"), src.replace(/\.(jpe?g)$/iu, ".webp"), placeholder];
  }
  if (lower.endsWith(".png")) {
    return [src.replace(/\.png$/iu, ".jpg"), src.replace(/\.png$/iu, ".webp"), placeholder];
  }
  if (lower.endsWith(".webp")) {
    return [src.replace(/\.webp$/iu, ".jpg"), src.replace(/\.webp$/iu, ".png"), placeholder];
  }
  return [placeholder];
}

type AuraTheme = {
  glow: string;
  icon: string;
  ring: string;
};

const ELEMENT_AURAS: Record<NonNullable<CharacterData["element"]>, AuraTheme> = {
  fire: { glow: "rgba(251, 146, 60, 0.65)", icon: "🔥", ring: "rgba(251, 146, 60, 0.55)" },
  ice: { glow: "rgba(96, 165, 250, 0.65)", icon: "❄️", ring: "rgba(96, 165, 250, 0.55)" },
  lightning: { glow: "rgba(168, 85, 247, 0.65)", icon: "⚡", ring: "rgba(168, 85, 247, 0.55)" },
  earth: { glow: "rgba(74, 222, 128, 0.6)", icon: "🌿", ring: "rgba(74, 222, 128, 0.5)" },
  dark: { glow: "rgba(91, 33, 182, 0.7)", icon: "💀", ring: "rgba(91, 33, 182, 0.55)" },
  light: { glow: "rgba(250, 204, 21, 0.65)", icon: "✨", ring: "rgba(250, 204, 21, 0.55)" },
};

function getAuraTheme(character: CharacterData): AuraTheme {
  if (character.isBoss) {
    return { glow: "rgba(239, 68, 68, 0.75)", icon: "💀", ring: "rgba(239, 68, 68, 0.6)" };
  }
  if (character.element && ELEMENT_AURAS[character.element]) return ELEMENT_AURAS[character.element];
  return { glow: "rgba(250, 204, 21, 0.6)", icon: "✨", ring: "rgba(250, 204, 21, 0.45)" };
}

function EmberParticles({ tint }: { tint: string }) {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {[8, 21, 36, 52, 69, 83].map((left, i) => (
        <span
          key={`${left}-${i}`}
          className="absolute bottom-2 h-1.5 w-1.5 rounded-full animate-pulse"
          style={{
            left: `${left}%`,
            background: tint,
            opacity: 0.55,
            boxShadow: `0 0 10px ${tint}`,
            transform: `translateY(-${(i % 3) * 8}px)`,
            animationDelay: `${i * 120}ms`,
          }}
        />
      ))}
    </div>
  );
}

function LevelBadge({ level }: { level?: number }) {
  if (level == null) return null;
  return (
    <div
      className="absolute left-2 top-2 rounded-sm border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
      style={{
        background: "rgba(10, 10, 14, 0.72)",
        borderColor: "rgba(234, 179, 8, 0.5)",
        color: "#fde68a",
      }}
    >
      Lv.{level}
    </div>
  );
}

function BossOverlay({ title }: { title?: string }) {
  return (
    <div
      className="absolute right-2 top-2 rounded-sm border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
      style={{
        background: "rgba(69, 10, 10, 0.78)",
        borderColor: "rgba(248, 113, 113, 0.55)",
        color: "#fecaca",
      }}
    >
      💀 {title || "Boss"}
    </div>
  );
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    const start = performance.now();
    const from = Math.max(0, Math.round(value * 0.4));
    let frame = 0;

    const tick = (ts: number) => {
      const progress = Math.min(1, (ts - start) / 650);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + (value - from) * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return <>{display}</>;
}

/* ── HP helpers ── */
function parseHp(val: string | number): { current: number; max: number } | null {
  const m = String(val).match(/^(\d+)\s*\/\s*(\d+)$/);
  if (!m) return null;
  return { current: Number(m[1]), max: Number(m[2]) };
}

function HpBar({ current, max }: { current: number; max: number }) {
  const pct = Math.min(100, (current / max) * 100);
  return (
    <div className="h-2.5 w-full rounded-sm overflow-hidden" style={{ background: "rgba(0,0,0,0.5)" }}>
      <div
        className="h-full rounded-sm transition-all duration-500"
        style={{
          width: `${pct}%`,
          background:
            pct > 50
              ? "linear-gradient(90deg, #2d8a4e, #4ade80)"
              : pct > 25
                ? "linear-gradient(90deg, #b8860b, #fbbf24)"
                : "linear-gradient(90deg, #b91c1c, #ef4444)",
        }}
      />
    </div>
  );
}

/* ── Ornament SVG for panel corners ── */
function PanelOrnament({ className }: { className?: string }) {
  return (
    <svg className={cn("h-5 w-5 text-amber-700/60", className)} viewBox="0 0 20 20" fill="currentColor">
      <path d="M0 0 L8 0 L0 8 Z" />
      <path d="M4 0 L10 0 L0 10 L0 4 Z" opacity="0.4" />
    </svg>
  );
}

/* ── Stat Panel (bottom bar style) ── */
function StatPanel({ character }: { character: CharacterData }) {
  return (
    <div
      className={cn(
        "relative flex min-w-[240px] max-w-xs flex-col gap-1 rounded-sm border border-amber-900/40 px-4 py-3",
      )}
      style={{
        background: "linear-gradient(180deg, rgba(20,15,25,0.92) 0%, rgba(30,20,35,0.95) 100%)",
        boxShadow: "inset 0 1px 0 rgba(255,215,0,0.08), 0 4px 20px rgba(0,0,0,0.5)",
      }}
    >
      <PanelOrnament className="absolute left-0 top-0" />
      <PanelOrnament className="absolute right-0 top-0 -scale-x-100" />
      <PanelOrnament className="absolute bottom-0 left-0 -scale-y-100" />
      <PanelOrnament className="absolute bottom-0 right-0 scale-[-1]" />

      <div className="mb-1 flex flex-wrap items-center gap-2">
        <h3
          className="min-w-[120px] flex-1 text-sm font-bold uppercase tracking-wider"
          style={{ color: "#e8dcc8", textShadow: "0 1px 3px rgba(0,0,0,0.8)" }}
        >
          {character.name}
        </h3>
        {character.element && !character.isBoss && (
          <span className="rounded-sm border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-100/95">
            {ELEMENT_AURAS[character.element].icon}
          </span>
        )}
        {character.weakness && (
          <span
            className="rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
            style={{
              background: "rgba(180,40,40,0.4)",
              color: "#ff9090",
              border: "1px solid rgba(180,40,40,0.5)",
            }}
          >
            {character.weakness}
          </span>
        )}
        {character.indicators?.map((ind, i) => (
          <span
            key={i}
            className="rounded-sm px-1.5 py-0.5 text-[10px] font-bold"
            style={{
              background: "rgba(140,30,30,0.5)",
              color: "#ff7070",
              border: "1px solid rgba(140,30,30,0.6)",
            }}
          >
            {ind}
          </span>
        ))}
      </div>
      {(character.class || character.title) && (
        <p className="mb-1 text-[10px] uppercase tracking-wider text-amber-200/70">
          {[character.class, character.title].filter(Boolean).join(" · ")}
        </p>
      )}

      <div className="mb-1 h-px w-full" style={{ background: "linear-gradient(90deg, transparent, rgba(180,150,80,0.4), transparent)" }} />

      <div className="flex flex-col gap-1">
        {character.stats.map((stat) => {
          const hp = parseHp(stat.value);
          return (
            <div key={stat.label}>
              <div className="flex items-baseline justify-between text-xs">
                <span style={{ color: "#9a8e7a" }} className="tracking-wide">
                  {stat.label}
                </span>
                <span className={cn("font-bold tabular-nums", hp ? "text-sm" : "text-xs")} style={{ color: "#e0d6c2" }}>
                  {hp
                    ? `${hp.current} / ${hp.max}`
                    : typeof stat.value === "number"
                      ? <AnimatedNumber value={stat.value} />
                      : String(stat.value)}
                </span>
              </div>
              {hp && <HpBar current={hp.current} max={hp.max} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Grid ── */
function GridPreview({
  rows = 3,
  cols = 3,
  units = [],
}: {
  rows?: number;
  cols?: number;
  units?: GridUnit[];
}) {
  const cells: React.ReactNode[] = [];
  const cellRem = 4.5;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const unit = units.find((u) => u.row === r && u.col === c);
      cells.push(
        <div
          key={`${r}-${c}`}
          className={cn("aspect-square flex items-center justify-center rounded-sm border text-sm transition-all duration-300")}
          style={
            unit
              ? {
                  background: "rgba(180,40,40,0.25)",
                  borderColor: "rgba(200,60,60,0.6)",
                  boxShadow: "0 0 12px rgba(200,60,60,0.3), inset 0 0 8px rgba(200,60,60,0.15)",
                }
              : {
                  background: "rgba(40,30,50,0.4)",
                  borderColor: "rgba(100,80,120,0.3)",
                }
          }
        >
          {unit?.imageUrl ? (
            <img
              src={unit.imageUrl}
              alt={unit.label ?? ""}
              className="h-full w-full rounded-sm object-cover"
              loading="lazy"
            />
          ) : unit?.label ? (
            <span style={{ color: "#e0d6c2", textShadow: "0 1px 4px rgba(0,0,0,0.8)" }} className="font-medium">
              {unit.label}
            </span>
          ) : null}
        </div>,
      );
    }
  }

  return (
    <div
      className="grid gap-1"
      style={{
        gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
        width: `${cols * cellRem}rem`,
        maxWidth: "100%",
      }}
    >
      {cells}
    </div>
  );
}

/* ── Commence Banner Button ── */
function CommenceBanner({ label, onClick }: { label: string; onClick?: () => void }) {
  const inner = (
    <div
      className="relative px-10 py-3 text-center"
      style={{
        background: "linear-gradient(180deg, #5c1a1a 0%, #3d0f0f 60%, #2a0808 100%)",
        border: "2px solid rgba(180,130,50,0.5)",
        borderBottom: "none",
        clipPath: "polygon(0 0, 100% 0, 100% 75%, 50% 100%, 0 75%)",
        paddingBottom: "1.8rem",
      }}
    >
      <div
        className="absolute inset-[3px]"
        style={{
          border: "1px solid rgba(180,130,50,0.2)",
          clipPath: "polygon(0 0, 100% 0, 100% 75%, 50% 100%, 0 75%)",
          pointerEvents: "none",
        }}
      />
      <span
        className="relative text-base font-bold uppercase tracking-wider"
        style={{
          color: "#e8dcc8",
          textShadow: "0 1px 4px rgba(0,0,0,0.8), 0 0 20px rgba(180,130,50,0.2)",
        }}
      >
        {label}
      </span>
    </div>
  );

  const shell = onClick ? (
    <button
      type="button"
      onClick={onClick}
      className="group relative cursor-pointer transition-transform duration-200 hover:scale-105 active:scale-95 focus:outline-none"
      style={{ filter: "drop-shadow(0 4px 12px rgba(0,0,0,0.6))" }}
    >
      {inner}
    </button>
  ) : (
    <div className="relative pointer-events-none opacity-95" style={{ filter: "drop-shadow(0 4px 12px rgba(0,0,0,0.6))" }}>
      {inner}
    </div>
  );

  return shell;
}

/* ── Main BattlePreview ── */
export default function BattlePreview({
  data,
  combatGrid,
}: {
  data: BattlePreviewData;
  /** When set, replaces the decorative tactical grid (e.g. skill + potion buttons). */
  combatGrid?: ReactNode;
}) {
  const base = import.meta.env.BASE_URL || "/";
  const portraitPlaceholder = `${base}placeholder.svg`;
  const playerAura = getAuraTheme(data.player);
  const enemyAura = getAuraTheme(data.enemy);
  const bgLayerStyle = data.battlefieldZoneKey
    ? getBattlefieldBackgroundStackStyle(data.battlefieldZoneKey)
    : {
        backgroundImage: data.backgroundUrl ? `url(${data.backgroundUrl})` : undefined,
        backgroundSize: "cover",
        backgroundPosition: "center",
      };

  return (
    <div className="relative w-full overflow-visible rounded-lg" style={{ aspectRatio: "16/9" }}>
      {/* Clip art to rounded rect; UI layer stays overflow-visible so skill tooltips are not clipped */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-lg">
        <div className="absolute inset-0" style={bgLayerStyle} />
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse at center, rgba(0,0,0,0.1) 30%, rgba(0,0,0,0.5) 100%)",
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            background: "linear-gradient(to top, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.1) 40%, transparent 60%)",
          }}
        />
      </div>

      <div className="relative z-10 grid h-full w-full gap-0 p-3 sm:p-4" style={{ gridTemplateColumns: "1fr auto 1fr" }}>
        <div className="flex min-h-0 flex-col items-center justify-end gap-1 overflow-hidden">
          <div className="flex min-h-0 w-full flex-1 items-end justify-center px-1">
            <div
              className={cn(
                "relative aspect-[3/4] max-h-[85%] w-[min(92%,280px)] overflow-hidden rounded-sm",
                "shadow-[0_12px_40px_-8px_rgba(0,0,0,0.85)]",
              )}
              style={{ boxShadow: `0 0 0 1px ${playerAura.ring}, 0 0 26px ${playerAura.glow}, 0 12px 40px -8px rgba(0,0,0,0.85)` }}
            >
              <div className="pointer-events-none absolute inset-0 animate-pulse" style={{ boxShadow: `inset 0 0 40px ${playerAura.glow}` }} />
              <SafePortraitImage
                src={data.player.portraitUrl}
                alt={data.player.name}
                className="h-full w-full object-cover object-[center_18%]"
                fallbackCandidates={deriveFallbackCandidates(data.player.portraitUrl, portraitPlaceholder)}
              />
              <LevelBadge level={data.player.level} />
              <div className="absolute right-2 top-2 rounded-sm bg-black/45 px-1.5 py-0.5 text-xs">{playerAura.icon}</div>
              <EmberParticles tint={playerAura.glow} />
              <div
                className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/50 to-transparent"
                aria-hidden
              />
            </div>
          </div>
          <StatPanel character={data.player} />
        </div>

        <div className="z-20 flex min-w-0 flex-col items-center justify-between overflow-visible px-4 py-2">
          <div className="mt-[4%] flex w-full justify-center overflow-visible">
            {combatGrid ?? <GridPreview rows={data.gridRows} cols={data.gridCols} units={data.units} />}
          </div>
          <CommenceBanner label={data.buttonLabel ?? "Commence Battle"} onClick={data.onCommence} />
        </div>

        <div className="flex min-h-0 flex-col items-center justify-end gap-1 overflow-hidden">
          <div className="flex min-h-0 w-full flex-1 items-end justify-center px-1">
            <div
              className={cn(
                "relative aspect-[3/4] max-h-[85%] w-[min(92%,280px)] overflow-hidden rounded-sm",
                "shadow-[0_12px_40px_-8px_rgba(0,0,0,0.85)]",
              )}
              style={{ boxShadow: `0 0 0 1px ${enemyAura.ring}, 0 0 26px ${enemyAura.glow}, 0 12px 40px -8px rgba(0,0,0,0.85)` }}
            >
              <div className="pointer-events-none absolute inset-0 animate-pulse" style={{ boxShadow: `inset 0 0 40px ${enemyAura.glow}` }} />
              <SafePortraitImage
                src={data.enemy.portraitUrl}
                alt={data.enemy.name}
                className="h-full w-full object-cover object-[center_18%]"
                fallbackCandidates={deriveFallbackCandidates(data.enemy.portraitUrl, portraitPlaceholder)}
              />
              <LevelBadge level={data.enemy.level} />
              {data.enemy.isBoss ? (
                <BossOverlay title={data.enemy.title} />
              ) : (
                <div className="absolute right-2 top-2 rounded-sm bg-black/45 px-1.5 py-0.5 text-xs">{enemyAura.icon}</div>
              )}
              <EmberParticles tint={enemyAura.glow} />
              <div
                className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/50 to-transparent"
                aria-hidden
              />
            </div>
          </div>
          <StatPanel character={data.enemy} />
        </div>
      </div>
    </div>
  );
}
