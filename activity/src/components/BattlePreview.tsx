import React, { type ReactNode } from "react";
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

/* ── HP helpers ── */
function parseHp(val: string | number): { current: number; max: number } | null {
  const m = String(val).match(/^(\d+)\s*\/\s*(\d+)$/);
  if (!m) return null;
  return { current: Number(m[1]), max: Number(m[2]) };
}

function HpBar({ current, max, compact }: { current: number; max: number; compact?: boolean }) {
  const pct = Math.min(100, (current / max) * 100);
  return (
    <div className={cn("w-full rounded-sm overflow-hidden", compact ? "h-1.5" : "h-2.5")} style={{ background: "rgba(0,0,0,0.5)" }}>
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
    <svg className={cn("w-5 h-5 text-amber-700/60", className)} viewBox="0 0 20 20" fill="currentColor">
      <path d="M0 0 L8 0 L0 8 Z" />
      <path d="M4 0 L10 0 L0 10 L0 4 Z" opacity="0.4" />
    </svg>
  );
}

/* ── Stat Panel (bottom bar style) ── */
function StatPanel({ character, compact }: { character: CharacterData; compact?: boolean }) {
  return (
    <div
      className={cn(
        "relative flex flex-col border border-amber-900/40 rounded-sm",
        compact ? "gap-0.5 px-2.5 py-1.5 min-w-0 max-w-[200px] sm:max-w-[220px]" : "gap-1 px-4 py-3 min-w-[240px] max-w-xs",
      )}
      style={{
        background: "linear-gradient(180deg, rgba(20,15,25,0.92) 0%, rgba(30,20,35,0.95) 100%)",
        boxShadow: "inset 0 1px 0 rgba(255,215,0,0.08), 0 4px 20px rgba(0,0,0,0.5)",
      }}
    >
      <PanelOrnament className={cn("absolute top-0 left-0", compact ? "h-3.5 w-3.5" : "h-5 w-5")} />
      <PanelOrnament className={cn("absolute top-0 right-0 -scale-x-100", compact ? "h-3.5 w-3.5" : "h-5 w-5")} />
      <PanelOrnament className={cn("absolute bottom-0 left-0 -scale-y-100", compact ? "h-3.5 w-3.5" : "h-5 w-5")} />
      <PanelOrnament className={cn("absolute bottom-0 right-0 scale-[-1]", compact ? "h-3.5 w-3.5" : "h-5 w-5")} />

      <div className={cn("flex items-center flex-wrap", compact ? "gap-1 mb-0.5" : "gap-2 mb-1")}>
        <h3
          className={cn(
            "font-bold tracking-wider uppercase flex-1 min-w-0",
            compact ? "text-[10px] leading-tight" : "text-sm min-w-[120px]",
          )}
          style={{ color: "#e8dcc8", textShadow: "0 1px 3px rgba(0,0,0,0.8)" }}
        >
          {character.name}
        </h3>
        {character.weakness && (
          <span
            className="text-[10px] font-bold px-1.5 py-0.5 rounded-sm uppercase tracking-wide"
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
            className="text-[10px] font-bold px-1.5 py-0.5 rounded-sm"
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

      <div className={cn("w-full h-px", compact ? "mb-0.5" : "mb-1")} style={{ background: "linear-gradient(90deg, transparent, rgba(180,150,80,0.4), transparent)" }} />

      <div className={cn("flex flex-col", compact ? "gap-0.5" : "gap-1")}>
        {character.stats.map((stat) => {
          const hp = parseHp(stat.value);
          return (
            <div key={stat.label}>
              <div className={cn("flex justify-between items-baseline", compact ? "text-[9px]" : "text-xs")}>
                <span style={{ color: "#9a8e7a" }} className="tracking-wide">
                  {stat.label}
                </span>
                <span
                  className={cn("font-bold tabular-nums", compact ? "text-[9px]" : hp ? "text-sm" : "text-xs")}
                  style={{ color: "#e0d6c2" }}
                >
                  {hp ? `${hp.current} / ${hp.max}` : String(stat.value)}
                </span>
              </div>
              {hp && <HpBar current={hp.current} max={hp.max} compact={compact} />}
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
  compact,
}: {
  rows?: number;
  cols?: number;
  units?: GridUnit[];
  compact?: boolean;
}) {
  const cellRem = compact ? 3.25 : 4.5;
  const cells: React.ReactNode[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const unit = units.find((u) => u.row === r && u.col === c);
      cells.push(
        <div
          key={`${r}-${c}`}
          className={cn("aspect-square flex items-center justify-center text-sm rounded-sm border transition-all duration-300")}
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
              className="w-full h-full object-cover rounded-sm"
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
      className={cn("grid", compact ? "gap-0.5" : "gap-1")}
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
function CommenceBanner({ label, onClick, compact }: { label: string; onClick?: () => void; compact?: boolean }) {
  const inner = (
    <div
      className={cn("relative text-center", compact ? "px-6 py-1.5" : "px-10 py-3")}
      style={{
        background: "linear-gradient(180deg, #5c1a1a 0%, #3d0f0f 60%, #2a0808 100%)",
        border: "2px solid rgba(180,130,50,0.5)",
        borderBottom: "none",
        clipPath: "polygon(0 0, 100% 0, 100% 75%, 50% 100%, 0 75%)",
        paddingBottom: compact ? "1rem" : "1.8rem",
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
        className={cn("relative font-bold tracking-wider uppercase", compact ? "text-[11px]" : "text-base")}
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
  /** Tighter layout for Discord / small viewports so footer actions stay visible. */
  compact = false,
}: {
  data: BattlePreviewData;
  /** When set, replaces the decorative tactical grid (e.g. skill + potion buttons). */
  combatGrid?: ReactNode;
  compact?: boolean;
}) {
  const bgLayerStyle = data.battlefieldZoneKey
    ? getBattlefieldBackgroundStackStyle(data.battlefieldZoneKey)
    : {
        backgroundImage: data.backgroundUrl ? `url(${data.backgroundUrl})` : undefined,
        backgroundSize: "cover",
        backgroundPosition: "center",
      };

  return (
    <div
      className={cn("relative mx-auto w-full max-w-[min(100%,920px)] overflow-visible rounded-lg", compact && "shrink-0")}
      style={
        compact
          ? {
              aspectRatio: "16 / 9",
              maxHeight: "min(38vh, 340px)",
              width: "100%",
            }
          : { aspectRatio: "16/9" }
      }
    >
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

      <div
        className={cn("relative z-10 grid h-full w-full gap-0", compact ? "p-1.5 sm:p-2" : "p-3 sm:p-4")}
        style={{ gridTemplateColumns: "1fr auto 1fr" }}
      >
        <div className={cn("flex min-h-0 flex-col items-center justify-end overflow-hidden", compact ? "gap-0" : "gap-1")}>
          <div className="flex min-h-0 w-full flex-1 items-end justify-center px-0.5">
            {/* Waist-up frame: crop with object-cover + top bias so full-body sources read as bust shots */}
            <div
              className={cn(
                "relative aspect-[3/4] overflow-hidden rounded-sm",
                "shadow-[0_12px_40px_-8px_rgba(0,0,0,0.85)]",
                compact ? "w-[min(88%,200px)] max-h-[72%]" : "w-[min(92%,280px)] max-h-[85%]",
              )}
            >
              <img
                src={data.player.portraitUrl}
                alt={data.player.name}
                className="h-full w-full object-cover object-[center_18%]"
                loading="lazy"
              />
              <div
                className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/50 to-transparent"
                aria-hidden
              />
            </div>
          </div>
          <StatPanel character={data.player} compact={compact} />
        </div>

        <div
          className={cn(
            "z-20 flex min-w-0 flex-col items-center justify-between overflow-visible",
            compact ? "px-1 py-0.5" : "px-4 py-2",
          )}
        >
          <div className={cn("flex w-full justify-center overflow-visible", compact ? "mt-0" : "mt-[4%]")}>
            {combatGrid ?? (
              <GridPreview rows={data.gridRows} cols={data.gridCols} units={data.units} compact={compact} />
            )}
          </div>
          <CommenceBanner label={data.buttonLabel ?? "Commence Battle"} onClick={data.onCommence} compact={compact} />
        </div>

        <div className={cn("flex min-h-0 flex-col items-center justify-end overflow-hidden", compact ? "gap-0" : "gap-1")}>
          <div className="flex min-h-0 w-full flex-1 items-end justify-center px-0.5">
            <div
              className={cn(
                "relative aspect-[3/4] overflow-hidden rounded-sm",
                "shadow-[0_12px_40px_-8px_rgba(0,0,0,0.85)]",
                compact ? "w-[min(88%,200px)] max-h-[72%]" : "w-[min(92%,280px)] max-h-[85%]",
              )}
            >
              <img
                src={data.enemy.portraitUrl}
                alt={data.enemy.name}
                className="h-full w-full object-cover object-[center_18%]"
                loading="lazy"
              />
              <div
                className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/50 to-transparent"
                aria-hidden
              />
            </div>
          </div>
          <StatPanel character={data.enemy} compact={compact} />
        </div>
      </div>
    </div>
  );
}
