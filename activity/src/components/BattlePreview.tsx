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

export interface Skill {
  id: string;
  name: string;
  icon: string;
  element?: CharacterData["element"];
  damage?: number;
  manaCost?: number;
  cooldown?: number;
  level?: number;
  description: string;
  keybind?: string;
  isReady?: boolean;
}

export interface Item {
  id: string;
  name: string;
  icon: string;
  quantity: number;
  description: string;
}

export interface BuffDebuff {
  id: string;
  name: string;
  icon: string;
  type: "buff" | "debuff";
  duration?: string;
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
  /** Shown on the center action button (combat uses “Your Turn”, demos may use “Combat History”). */
  buttonLabel?: string;
  /** Overrides `buttonLabel` for the center button text when both are set in demos. */
  centerActionLabel?: string;
  /** Small line above the skill grid (e.g. “Your Turn — 8s”) while the button stays “Combat History”. */
  centerStatusLine?: string;
  onCommence?: () => void;
  /** Optional mock / preview skills (used when `combatGrid` is not passed). */
  playerSkills?: Skill[];
  enemySkills?: Skill[];
  items?: Item[];
  buffs?: BuffDebuff[];
  /** When true, shows Items/Status panel even if empty. When undefined, panel shows only if items or buffs exist. */
  showRpgPanel?: boolean;
  /** Called when the user picks a skill cell in `playerSkills` grid (optional). */
  onSelectPlayerSkill?: (skillId: string) => void;
}

function SafePortraitImage({
  src,
  alt,
  className,
  fallbackCandidates,
  style,
}: {
  src: string;
  alt: string;
  className: string;
  fallbackCandidates: string[];
  style?: React.CSSProperties;
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
      style={style}
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

type ElementKey = NonNullable<CharacterData["element"]>;

const ELEMENT_THEME: Record<
  ElementKey,
  { glow: string; icon: string; ring: string; shadow: string }
> = {
  fire: {
    glow: "rgba(251, 146, 60, 0.65)",
    icon: "🔥",
    ring: "rgba(251, 146, 60, 0.55)",
    shadow: "rgba(251, 80, 0, 0.4)",
  },
  ice: {
    glow: "rgba(96, 165, 250, 0.65)",
    icon: "❄️",
    ring: "rgba(96, 165, 250, 0.55)",
    shadow: "rgba(80, 160, 255, 0.4)",
  },
  lightning: {
    glow: "rgba(168, 85, 247, 0.65)",
    icon: "⚡",
    ring: "rgba(168, 85, 247, 0.55)",
    shadow: "rgba(180, 140, 255, 0.4)",
  },
  earth: {
    glow: "rgba(74, 222, 128, 0.6)",
    icon: "🌿",
    ring: "rgba(74, 222, 128, 0.5)",
    shadow: "rgba(100, 160, 60, 0.4)",
  },
  dark: {
    glow: "rgba(91, 33, 182, 0.7)",
    icon: "💀",
    ring: "rgba(91, 33, 182, 0.55)",
    shadow: "rgba(120, 40, 180, 0.45)",
  },
  light: {
    glow: "rgba(250, 204, 21, 0.65)",
    icon: "✨",
    ring: "rgba(250, 204, 21, 0.55)",
    shadow: "rgba(255, 220, 100, 0.4)",
  },
};

type AuraVisual = { glow: string; icon: string; ring: string; shadow: string };

function getAuraTheme(character: CharacterData): AuraVisual {
  if (character.isBoss) {
    return {
      glow: "rgba(239, 68, 68, 0.75)",
      icon: "💀",
      ring: "rgba(239, 68, 68, 0.6)",
      shadow: "rgba(200, 40, 40, 0.45)",
    };
  }
  if (character.element && ELEMENT_THEME[character.element]) return ELEMENT_THEME[character.element];
  return {
    glow: "rgba(250, 204, 21, 0.6)",
    icon: "✨",
    ring: "rgba(250, 204, 21, 0.45)",
    shadow: "rgba(0, 0, 0, 0.5)",
  };
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
      className="absolute left-2 top-2 z-20 flex h-9 min-w-[2.25rem] items-center justify-center rounded-full border px-1.5 text-[9px] font-bold tabular-nums leading-none"
      style={{
        background: "linear-gradient(145deg, rgba(30,22,12,0.95) 0%, rgba(12,10,8,0.98) 100%)",
        borderColor: "rgba(234, 179, 8, 0.55)",
        color: "#fde68a",
        boxShadow: "0 0 10px rgba(234, 179, 8, 0.2), inset 0 1px 0 rgba(255,255,255,0.08)",
      }}
    >
      Lv.{level}
    </div>
  );
}

function BossOverlay({ title }: { title?: string }) {
  return (
    <div
      className="absolute right-2 top-2 z-20 flex items-center justify-center rounded-full border p-1.5 text-sm leading-none"
      style={{
        background: "rgba(10, 10, 14, 0.75)",
        borderColor: "rgba(248, 250, 252, 0.45)",
        color: "#f8fafc",
        boxShadow: "0 0 12px rgba(239, 68, 68, 0.35)",
      }}
      title={title || "Boss"}
    >
      💀
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

const KEYFRAMES_CSS = `
@keyframes ember-float {
  0% { transform: translateY(0) scale(1); opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 0.3; }
  100% { transform: translateY(-400px) scale(0.3); opacity: 0; }
}
@keyframes pulse-glow {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.05); }
}
@keyframes portrait-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
}
@keyframes shimmer-sweep {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@keyframes skill-pulse {
  0%, 100% { box-shadow: 0 0 4px rgb(var(--bp-gold-bright-rgb) / 0.2); }
  50% { box-shadow: 0 0 12px rgb(var(--bp-gold-bright-rgb) / 0.5), 0 0 20px rgb(var(--bp-gold-bright-rgb) / 0.15); }
}
@keyframes tab-fade-in {
  0% { opacity: 0; transform: translateY(6px); }
  100% { opacity: 1; transform: translateY(0); }
}
`;

let keyframesInjected = false;
function useInjectKeyframes() {
  useEffect(() => {
    if (keyframesInjected) return;
    keyframesInjected = true;
    const style = document.createElement("style");
    style.setAttribute("data-battle-preview-keyframes", "true");
    style.textContent = KEYFRAMES_CSS;
    document.head.appendChild(style);
  }, []);
}

function parseHp(val: string | number): { current: number; max: number } | null {
  const m = String(val).match(/^(\d+)\s*\/\s*(\d+)$/);
  if (!m) return null;
  return { current: Number(m[1]), max: Number(m[2]) };
}

function HpBar({ current, max, isMp }: { current: number; max: number; isMp?: boolean }) {
  const pct = Math.min(100, (current / max) * 100);
  const gradient = isMp
    ? "linear-gradient(90deg, #1a5fb4, #62a0ea)"
    : pct > 50
      ? "linear-gradient(90deg, #2d8a4e, #4ade80)"
      : pct > 25
        ? "linear-gradient(90deg, #b8860b, #fbbf24)"
        : "linear-gradient(90deg, #b91c1c, #ef4444)";

  return (
    <div className="relative h-2.5 w-full overflow-hidden rounded-sm" style={{ background: "rgba(0,0,0,0.5)" }}>
      <div className="h-full rounded-sm transition-all duration-500" style={{ width: `${pct}%`, background: gradient }} />
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)",
          backgroundSize: "200% 100%",
          animation: "shimmer-sweep 3s ease-in-out infinite",
        }}
      />
    </div>
  );
}

function PanelOrnament({ className }: { className?: string }) {
  return (
    <svg className={cn("h-5 w-5 text-amber-700/60", className)} viewBox="0 0 20 20" fill="currentColor">
      <path d="M0 0 L8 0 L0 8 Z" />
      <path d="M4 0 L10 0 L0 10 L0 4 Z" opacity="0.4" />
    </svg>
  );
}

function StatPanel({ character }: { character: CharacterData }) {
  return (
    <div
      className={cn("relative flex w-full min-w-0 max-w-xs flex-col gap-1 rounded-sm border border-amber-900/40 px-2.5 py-3 sm:min-w-[240px] sm:px-4")}
      style={{
        background: "linear-gradient(180deg, rgba(20,15,25,0.92) 0%, rgba(30,20,35,0.95) 100%)",
        boxShadow: "inset 0 1px 0 rgb(var(--bp-gold-bright-rgb) / 0.08), 0 4px 20px rgba(0,0,0,0.5)",
      }}
    >
      <PanelOrnament className="absolute left-0 top-0" />
      <PanelOrnament className="absolute right-0 top-0 -scale-x-100" />
      <PanelOrnament className="absolute bottom-0 left-0 -scale-y-100" />
      <PanelOrnament className="absolute bottom-0 right-0 scale-[-1]" />

      <div className="mb-1 flex flex-wrap items-center gap-2">
        {character.element && (
          <span className="text-sm" title={character.element}>
            {ELEMENT_THEME[character.element].icon}
          </span>
        )}
        <h3
          className="min-w-0 flex-1 truncate text-sm font-bold uppercase tracking-wider sm:min-w-[120px]"
          style={{ color: "var(--bp-ink-bright)", textShadow: "0 1px 3px rgba(0,0,0,0.8)" }}
          title={character.name}
        >
          {character.name}
        </h3>
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
          {[character.class, character.title].filter(Boolean).join(" — ")}
        </p>
      )}

      <div className="mb-1 h-px w-full" style={{ background: "linear-gradient(90deg, transparent, rgba(180,150,80,0.4), transparent)" }} />

      <div className="flex flex-col gap-1">
        {character.stats.map((stat) => {
          const hp = parseHp(stat.value);
          const isMp =
            stat.label.toLowerCase().includes("mp") ||
            stat.label.toLowerCase().includes("mana") ||
            stat.label.toLowerCase().includes("energy") ||
            stat.label.toLowerCase().includes("rage");
          return (
            <div key={stat.label}>
              <div className="flex items-baseline justify-between text-xs">
                <span style={{ color: "var(--bp-ink-muted)" }} className="tracking-wide">
                  {stat.label}
                </span>
                <span className={cn("font-bold tabular-nums", hp ? "text-sm" : "text-xs")} style={{ color: "var(--bp-ink)" }}>
                  {hp ? (
                    <>
                      <AnimatedNumber value={hp.current} /> / {hp.max}
                    </>
                  ) : typeof stat.value === "number" ? (
                    <AnimatedNumber value={stat.value} />
                  ) : (
                    String(stat.value)
                  )}
                </span>
              </div>
              {hp && <HpBar current={hp.current} max={hp.max} isMp={isMp} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

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
            <span style={{ color: "var(--bp-ink)", textShadow: "0 1px 4px rgba(0,0,0,0.8)" }} className="font-medium">
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

function SkillGrid({
  rows = 3,
  cols = 3,
  skills = [],
  selectedSkillId,
  onSelectSkill,
}: {
  rows?: number;
  cols?: number;
  skills?: Skill[];
  selectedSkillId?: string;
  onSelectSkill?: (id: string) => void;
}) {
  const cells: React.ReactNode[] = [];
  const cellRem = 4.5;
  const total = rows * cols;
  for (let i = 0; i < total; i++) {
    const skill = skills[i];
    const isSelected = skill && selectedSkillId === skill.id;
    const elem = skill?.element ? ELEMENT_THEME[skill.element] : null;
    const isReady = skill ? skill.isReady !== false : true;

    cells.push(
      <button
        key={skill?.id ?? `empty-${i}`}
        type="button"
        onClick={skill ? () => onSelectSkill?.(skill.id) : undefined}
        className={cn(
          "group/cell relative aspect-square rounded-sm border text-sm transition-all duration-300",
          skill ? "cursor-pointer hover:scale-105" : "cursor-default",
          "flex items-center justify-center",
        )}
        style={
          skill
            ? {
                background: isSelected ? "rgb(var(--bp-gold-bright-rgb) / 0.15)" : "rgba(30,20,15,0.7)",
                borderColor: isSelected
                  ? "rgb(var(--bp-gold-bright-rgb) / 0.7)"
                  : elem
                    ? elem.glow.replace("0.65", "0.4").replace("0.6", "0.35")
                    : "rgb(var(--bp-gold-rgb) / 0.35)",
                boxShadow: isSelected
                  ? "0 0 12px rgb(var(--bp-gold-bright-rgb) / 0.3), inset 0 0 8px rgb(var(--bp-gold-bright-rgb) / 0.1)"
                  : isReady
                    ? `0 0 6px ${elem ? elem.glow.replace("0.65", "0.15").replace("0.6", "0.12") : "rgb(var(--bp-gold-rgb) / 0.1)"}`
                    : "none",
                animation: isReady && !isSelected ? "skill-pulse 2.5s ease-in-out infinite" : undefined,
              }
            : {
                background: "rgba(40,30,50,0.3)",
                borderColor: "rgba(100,80,120,0.2)",
              }
        }
      >
        {skill && (
          <>
            {elem && isReady && (
              <div
                className="pointer-events-none absolute inset-0 rounded-sm"
                style={{
                  background: `radial-gradient(circle, ${elem.glow.replace("0.65", "0.12").replace("0.6", "0.12")} 0%, transparent 70%)`,
                }}
              />
            )}
            <span
              className="relative z-10 text-lg"
              style={{ filter: isReady ? "none" : "grayscale(0.8) brightness(0.5)" }}
            >
              {skill.icon}
            </span>
            {!isReady && skill.cooldown != null && (
              <div
                className="absolute inset-0 z-20 flex items-center justify-center rounded-sm"
                style={{ background: "rgba(0,0,0,0.55)" }}
              >
                <span className="text-[10px] font-bold" style={{ color: "#ff9090" }}>
                  {skill.cooldown}s
                </span>
              </div>
            )}
            {skill.keybind && (
              <span
                className="absolute right-0 top-0 z-20 rounded-bl-sm px-0.5 text-[7px] font-bold"
                style={{ background: "rgb(var(--bp-panel-rgb) / 0.85)", color: "var(--bp-ink-dim)" }}
              >
                {skill.keybind}
              </span>
            )}
            {skill.manaCost != null && (
              <span
                className="absolute bottom-0 left-0 z-20 rounded-tr-sm px-0.5 text-[7px] font-bold"
                style={{ background: "rgba(15,30,60,0.85)", color: "#62a0ea" }}
              >
                {skill.manaCost}
              </span>
            )}
            <div
              className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 hidden min-w-[170px] -translate-x-1/2 group-hover/cell:block"
            >
              <div
                className="rounded-sm px-3 py-2 text-left"
                style={{
                  background: "linear-gradient(180deg, rgba(30,22,12,0.97) 0%, rgb(var(--bp-panel-rgb) / 0.98) 100%)",
                  border: "1px solid rgb(var(--bp-gold-rgb) / 0.4)",
                  boxShadow: "0 4px 20px rgba(0,0,0,0.7)",
                }}
              >
                <div className="mb-1 flex items-center gap-1.5">
                  <span className="text-sm">{skill.icon}</span>
                  <span className="text-xs font-bold" style={{ color: "var(--bp-ink-bright)" }}>
                    {skill.name}
                  </span>
                  {skill.level != null && (
                    <span className="ml-auto text-[9px]" style={{ color: "var(--bp-ink-faint)" }}>
                      Lv.{skill.level}
                    </span>
                  )}
                </div>
                {skill.element && (
                  <span
                    className="mb-1 inline-block rounded-sm px-1.5 py-0.5 text-[9px]"
                    style={{
                      background: ELEMENT_THEME[skill.element].glow.replace("0.65", "0.15").replace("0.6", "0.12"),
                      color: "var(--bp-ink)",
                      border: `1px solid ${ELEMENT_THEME[skill.element].glow.replace("0.65", "0.28")}`,
                    }}
                  >
                    {skill.element}
                  </span>
                )}
                <p className="mt-1 text-[10px] leading-tight" style={{ color: "var(--bp-ink-muted)" }}>
                  {skill.description}
                </p>
                <div className="mt-1.5 flex gap-3" style={{ color: "var(--bp-ink-dim)" }}>
                  {skill.damage != null && (
                    <span className="text-[9px]">⚔️ {skill.damage}</span>
                  )}
                  {skill.manaCost != null && (
                    <span className="text-[9px]">💧 {skill.manaCost}</span>
                  )}
                  {skill.cooldown != null && (
                    <span className="text-[9px]">⏱️ {skill.cooldown}s</span>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </button>,
    );
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

function RPGTab({ label, isActive, onClick }: { label: string; isActive: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="relative cursor-pointer px-5 py-2 text-xs font-bold uppercase tracking-wider transition-all duration-200"
      style={{
        background: isActive
          ? "linear-gradient(180deg, rgba(50,35,15,0.95) 0%, rgba(30,20,10,0.98) 100%)"
          : "linear-gradient(180deg, rgba(25,18,10,0.9) 0%, rgba(15,10,5,0.95) 100%)",
        color: isActive ? "#ffd700" : "var(--bp-ink-faint)",
        borderTop: `2px solid ${isActive ? "rgb(var(--bp-gold-bright-rgb) / 0.6)" : "rgb(var(--bp-gold-rgb) / 0.2)"}`,
        borderLeft: "1px solid rgb(var(--bp-gold-rgb) / 0.2)",
        borderRight: "1px solid rgb(var(--bp-gold-rgb) / 0.2)",
        borderBottom: isActive ? "2px solid transparent" : "2px solid rgb(var(--bp-gold-rgb) / 0.2)",
        boxShadow: isActive ? "0 -4px 12px rgb(var(--bp-gold-bright-rgb) / 0.15)" : "none",
      }}
    >
      {label}
      {isActive && (
        <div
          className="absolute bottom-0 left-2 right-2 h-[2px]"
          style={{ background: "linear-gradient(90deg, transparent, rgb(var(--bp-gold-bright-rgb) / 0.6), transparent)" }}
        />
      )}
    </button>
  );
}

function ItemsTabContent({ items }: { items: Item[] }) {
  if (items.length === 0) {
    return (
      <p className="p-4 text-center text-[11px] text-muted-foreground" style={{ animation: "tab-fade-in 0.3s ease-out" }}>
        No items.
      </p>
    );
  }
  return (
    <div className="grid grid-cols-4 gap-2 p-3 sm:grid-cols-6" style={{ animation: "tab-fade-in 0.3s ease-out" }}>
      {items.map((item) => (
        <div
          key={item.id}
          className="group/item relative flex cursor-pointer flex-col items-center rounded-sm p-2 transition-all duration-200 hover:scale-105"
          style={{
            background: "linear-gradient(180deg, rgba(25,18,10,0.95) 0%, rgba(18,12,8,0.98) 100%)",
            border: "1px solid rgb(var(--bp-gold-rgb) / 0.25)",
          }}
        >
          <span className="text-xl">{item.icon}</span>
          <span className="mt-1 w-full truncate text-center text-[9px]" style={{ color: "var(--bp-ink-dim)" }}>
            {item.name}
          </span>
          <span
            className="absolute right-0.5 top-0.5 rounded-sm px-1 text-[8px] font-bold"
            style={{
              background: "rgba(30,20,10,0.9)",
              color: "var(--bp-ink)",
              border: "1px solid rgb(var(--bp-gold-rgb) / 0.3)",
            }}
          >
            x{item.quantity}
          </span>
          <div className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 hidden min-w-[120px] -translate-x-1/2 group-hover/item:block">
            <div
              className="rounded-sm px-2 py-1.5 text-center"
              style={{
                background: "rgba(25,18,10,0.97)",
                border: "1px solid rgb(var(--bp-gold-rgb) / 0.4)",
                boxShadow: "0 4px 16px rgba(0,0,0,0.6)",
              }}
            >
              <span className="block text-[10px] font-bold" style={{ color: "var(--bp-ink-bright)" }}>
                {item.name}
              </span>
              <span className="text-[9px]" style={{ color: "var(--bp-ink-muted)" }}>
                {item.description}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function StatusTabContent({ character, buffs }: { character: CharacterData; buffs: BuffDebuff[] }) {
  const elem = character.element ? ELEMENT_THEME[character.element] : null;
  return (
    <div className="space-y-3 p-3" style={{ animation: "tab-fade-in 0.3s ease-out" }}>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        {character.stats.map((stat) => (
          <div
            key={stat.label}
            className="flex justify-between rounded-sm px-1.5 py-1 text-[11px]"
            style={{ background: "rgb(var(--bp-panel-rgb) / 0.6)" }}
          >
            <span style={{ color: "var(--bp-ink-muted)" }}>{stat.label}</span>
            <span className="font-bold" style={{ color: "var(--bp-ink)" }}>
              {String(stat.value)}
            </span>
          </div>
        ))}
        {character.element && (
          <div className="flex justify-between rounded-sm px-1.5 py-1 text-[11px]" style={{ background: "rgb(var(--bp-panel-rgb) / 0.6)" }}>
            <span style={{ color: "var(--bp-ink-muted)" }}>Element</span>
            <span className="font-bold" style={{ color: "var(--bp-ink)" }}>
              {elem?.icon} {character.element}
            </span>
          </div>
        )}
        {character.class && (
          <div className="flex justify-between rounded-sm px-1.5 py-1 text-[11px]" style={{ background: "rgb(var(--bp-panel-rgb) / 0.6)" }}>
            <span style={{ color: "var(--bp-ink-muted)" }}>Class</span>
            <span className="font-bold" style={{ color: "var(--bp-ink)" }}>
              {character.class}
            </span>
          </div>
        )}
      </div>
      {buffs.length > 0 && (
        <div>
          <div className="mb-1.5 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--bp-ink-faint)" }}>
            Active Effects
          </div>
          <div className="flex flex-wrap gap-1.5">
            {buffs.map((b) => (
              <div
                key={b.id}
                className="flex items-center gap-1 rounded-sm px-2 py-1 text-[10px]"
                style={{
                  background: b.type === "buff" ? "rgba(40,80,40,0.4)" : "rgba(80,30,30,0.4)",
                  border: `1px solid ${b.type === "buff" ? "rgba(80,180,80,0.4)" : "rgba(180,60,60,0.4)"}`,
                  color: b.type === "buff" ? "#80e080" : "#ff8080",
                }}
              >
                <span>{b.icon}</span>
                <span className="font-bold">{b.name}</span>
                {b.duration && <span style={{ color: "var(--bp-ink-muted)" }}>{b.duration}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BattleTabPanel({ data }: { data: BattlePreviewData }) {
  const [activeTab, setActiveTab] = useState<"items" | "status">("items");
  const items = data.items ?? [];
  const buffs = data.buffs ?? [];

  return (
    <div
      className="relative mt-3 w-full overflow-hidden rounded-sm"
      style={{
        background: "linear-gradient(180deg, rgb(var(--bp-panel-rgb) / 0.95) 0%, rgba(15,10,6,0.98) 100%)",
        border: "1px solid rgb(var(--bp-gold-rgb) / 0.25)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.5)",
      }}
    >
      <PanelOrnament className="absolute left-0 top-0 z-10" />
      <PanelOrnament className="absolute right-0 top-0 z-10 -scale-x-100" />
      <PanelOrnament className="absolute bottom-0 left-0 z-10 -scale-y-100" />
      <PanelOrnament className="absolute bottom-0 right-0 z-10 scale-[-1]" />

      <div className="flex border-b" style={{ borderColor: "rgb(var(--bp-gold-rgb) / 0.2)" }}>
        <RPGTab label="🎒 Items" isActive={activeTab === "items"} onClick={() => setActiveTab("items")} />
        <RPGTab label="📊 Status" isActive={activeTab === "status"} onClick={() => setActiveTab("status")} />
      </div>

      <div className="min-h-[120px]">
        {activeTab === "items" && <ItemsTabContent items={items} />}
        {activeTab === "status" && <StatusTabContent character={data.player} buffs={buffs} />}
      </div>
    </div>
  );
}

export default function BattlePreview({
  data,
  combatGrid,
}: {
  data: BattlePreviewData;
  combatGrid?: ReactNode;
}) {
  useInjectKeyframes();
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

  const [selectedSkill, setSelectedSkill] = useState<string | undefined>();
  const rows = data.gridRows ?? 3;
  const cols = data.gridCols ?? 3;

  const centerGrid =
    combatGrid ??
    (data.playerSkills && data.playerSkills.length > 0 ? (
      <SkillGrid
        rows={rows}
        cols={cols}
        skills={data.playerSkills}
        selectedSkillId={selectedSkill}
        onSelectSkill={(id) => {
          setSelectedSkill(id);
          data.onSelectPlayerSkill?.(id);
        }}
      />
    ) : (
      <GridPreview rows={rows} cols={cols} units={data.units} />
    ));

  const centerButtonLabel = data.centerActionLabel ?? data.buttonLabel ?? "⚔️ Combat History";
  const centerStatusLine = data.centerStatusLine?.trim();
  const showRpgPanel =
    data.showRpgPanel === true ||
    (data.showRpgPanel !== false && ((data.items?.length ?? 0) > 0 || (data.buffs?.length ?? 0) > 0));

  return (
    <div className="flex w-full flex-col">
      <div className="relative w-full overflow-visible rounded-lg" style={{ aspectRatio: "16/9" }}>
        <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-lg">
          <div className="absolute inset-0" style={bgLayerStyle} />
          <div
            className="absolute inset-0"
            style={{
              background: "radial-gradient(ellipse at center, rgba(0,0,0,0.02) 28%, rgba(0,0,0,0.34) 100%)",
            }}
          />
          <div
            className="absolute inset-0"
            style={{
              background: "linear-gradient(to top, rgba(0,0,0,0.38) 0%, rgba(0,0,0,0.04) 42%, transparent 64%)",
            }}
          />
        </div>

        <div
          className="relative z-10 grid h-full w-full gap-0 p-3 sm:p-4"
          style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1.35fr) minmax(0,1fr)" }}
        >
          <div className="flex min-h-0 flex-col items-center justify-end gap-1 overflow-hidden">
            <div className="flex min-h-0 w-full flex-1 items-end justify-center px-1">
              <div
                className={cn(
                  "relative aspect-[3/4] max-h-[85%] w-[min(92%,280px)] overflow-hidden rounded-sm",
                  "shadow-[0_12px_40px_-8px_rgba(0,0,0,0.85)]",
                )}
                style={{
                  boxShadow: `0 0 0 1px ${playerAura.ring}, 0 0 26px ${playerAura.glow}, 0 12px 40px -8px rgba(0,0,0,0.85)`,
                }}
              >
                <div
                  className="pointer-events-none absolute inset-0 animate-pulse"
                  style={{ boxShadow: `inset 0 0 40px ${playerAura.glow}` }}
                />
                <SafePortraitImage
                  src={data.player.portraitUrl}
                  alt={data.player.name}
                  className="relative z-10 h-full w-full object-cover"
                  style={{ animation: "portrait-breathe 3s ease-in-out infinite", objectPosition: "center bottom" }}
                  fallbackCandidates={deriveFallbackCandidates(data.player.portraitUrl, portraitPlaceholder)}
                />
                <LevelBadge level={data.player.level} />
                <div className="absolute right-2 top-2 z-20 rounded-sm bg-black/45 px-1.5 py-0.5 text-xs">{playerAura.icon}</div>
                <EmberParticles tint={playerAura.glow} />
                <div
                  className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/50 to-transparent"
                  aria-hidden
                />
              </div>
            </div>
            <StatPanel character={data.player} />
          </div>

          <div className="z-20 flex min-h-0 min-w-0 flex-1 flex-col items-center justify-center overflow-visible px-2 py-2 sm:px-4">
            <div className="flex w-full min-h-0 flex-1 flex-col items-center justify-center gap-2 overflow-visible">
              {centerStatusLine ? (
                <div
                  className="max-w-full truncate px-2 text-center text-[10px] font-semibold uppercase tracking-wider"
                  style={{ color: "#d4c4a8", textShadow: "0 1px 2px rgba(0,0,0,0.75)" }}
                >
                  {centerStatusLine}
                </div>
              ) : null}
              <div className="flex w-full justify-center overflow-visible">{centerGrid}</div>
            </div>
            {data.onCommence ? (
              <button
                type="button"
                onClick={data.onCommence}
                className="mt-1 shrink-0 rounded px-4 py-1.5 text-xs font-bold uppercase tracking-wider transition-all duration-200 hover:scale-105 active:scale-95"
                style={{
                  background: "linear-gradient(135deg, #991b1b 0%, #dc2626 50%, #991b1b 100%)",
                  color: "#fde8e8",
                  border: "1px solid rgba(239,68,68,0.5)",
                  boxShadow: "0 0 12px rgba(239,68,68,0.3), inset 0 1px 0 rgba(255,255,255,0.15)",
                  textShadow: "0 1px 2px rgba(0,0,0,0.5)",
                }}
              >
                {centerButtonLabel}
              </button>
            ) : (
              <div
                className="mt-1 shrink-0 rounded px-4 py-1.5 text-center text-xs font-bold uppercase tracking-wider opacity-95"
                style={{
                  background: "linear-gradient(135deg, #991b1b 0%, #dc2626 50%, #991b1b 100%)",
                  color: "#fde8e8",
                  border: "1px solid rgba(239,68,68,0.5)",
                  boxShadow: "0 0 12px rgba(239,68,68,0.3), inset 0 1px 0 rgba(255,255,255,0.15)",
                  textShadow: "0 1px 2px rgba(0,0,0,0.5)",
                }}
              >
                {centerButtonLabel}
              </div>
            )}
          </div>

          <div className="flex min-h-0 flex-col items-center justify-end gap-1 overflow-hidden">
            <div className="flex min-h-0 w-full flex-1 items-end justify-center px-1">
              <div
                className={cn(
                  "relative aspect-[3/4] max-h-[85%] w-[min(92%,280px)] overflow-hidden rounded-sm",
                  "shadow-[0_12px_40px_-8px_rgba(0,0,0,0.85)]",
                )}
                style={{
                  boxShadow: `0 0 0 1px ${enemyAura.ring}, 0 0 26px ${enemyAura.glow}, 0 12px 40px -8px rgba(0,0,0,0.85)`,
                }}
              >
                <div
                  className="pointer-events-none absolute inset-0 animate-pulse"
                  style={{ boxShadow: `inset 0 0 40px ${enemyAura.glow}` }}
                />
                <SafePortraitImage
                  src={data.enemy.portraitUrl}
                  alt={data.enemy.name}
                  className="relative z-10 h-full w-full object-cover"
                  style={{ animation: "portrait-breathe 3s ease-in-out infinite", objectPosition: "center bottom" }}
                  fallbackCandidates={deriveFallbackCandidates(data.enemy.portraitUrl, portraitPlaceholder)}
                />
                <LevelBadge level={data.enemy.level} />
                {data.enemy.isBoss ? (
                  <BossOverlay title={data.enemy.title} />
                ) : (
                  <div className="absolute right-2 top-2 z-20 rounded-sm bg-black/45 px-1.5 py-0.5 text-xs">{enemyAura.icon}</div>
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

      {showRpgPanel && <BattleTabPanel data={data} />}
    </div>
  );
}
