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
    <svg className={cn("w-5 h-5 text-amber-700/60", className)} viewBox="0 0 20 20" fill="currentColor">
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
        "relative flex flex-col gap-1 px-4 py-3 min-w-[240px] max-w-xs",
        "border border-amber-900/40 rounded-sm",
      )}
      style={{
        background: "linear-gradient(180deg, rgba(20,15,25,0.92) 0%, rgba(30,20,35,0.95) 100%)",
        boxShadow: "inset 0 1px 0 rgba(255,215,0,0.08), 0 4px 20px rgba(0,0,0,0.5)",
      }}
    >
      <PanelOrnament className="absolute top-0 left-0" />
      <PanelOrnament className="absolute top-0 right-0 -scale-x-100" />
      <PanelOrnament className="absolute bottom-0 left-0 -scale-y-100" />
      <PanelOrnament className="absolute bottom-0 right-0 scale-[-1]" />

      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <h3
          className="text-sm font-bold tracking-wider uppercase flex-1 min-w-[120px]"
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

      <div className="w-full h-px mb-1" style={{ background: "linear-gradient(90deg, transparent, rgba(180,150,80,0.4), transparent)" }} />

      <div className="flex flex-col gap-1">
        {character.stats.map((stat) => {
          const hp = parseHp(stat.value);
          return (
            <div key={stat.label}>
              <div className="flex justify-between items-baseline text-xs">
                <span style={{ color: "#9a8e7a" }} className="tracking-wide">
                  {stat.label}
                </span>
                <span className={cn("font-bold tabular-nums", hp ? "text-sm" : "text-xs")} style={{ color: "#e0d6c2" }}>
                  {hp ? `${hp.current} / ${hp.max}` : String(stat.value)}
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
      className="grid gap-1"
      style={{
        gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
        width: `${cols * 4.5}rem`,
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
        className="relative text-base font-bold tracking-wider uppercase"
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

      <div className="relative z-10 w-full h-full grid gap-0 p-3 sm:p-4" style={{ gridTemplateColumns: "1fr auto 1fr" }}>
        <div className="flex flex-col items-center justify-end gap-1 min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 flex w-full items-end justify-center px-1">
            {/* Waist-up frame: crop with object-cover + top bias so full-body sources read as bust shots */}
            <div
              className={cn(
                "relative w-[min(92%,280px)] max-h-[85%] aspect-[3/4]",
                "overflow-hidden rounded-sm",
                "shadow-[0_12px_40px_-8px_rgba(0,0,0,0.85)]",
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
          <StatPanel character={data.player} />
        </div>

        <div className="flex flex-col items-center justify-between py-2 px-4 min-w-0 overflow-visible z-20">
          <div className="mt-[4%] w-full flex justify-center overflow-visible">
            {combatGrid ?? (
              <GridPreview rows={data.gridRows} cols={data.gridCols} units={data.units} />
            )}
          </div>
          <CommenceBanner label={data.buttonLabel ?? "Commence Battle"} onClick={data.onCommence} />
        </div>

        <div className="flex flex-col items-center justify-end gap-1 min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 flex w-full items-end justify-center px-1">
            <div
              className={cn(
                "relative w-[min(92%,280px)] max-h-[85%] aspect-[3/4]",
                "overflow-hidden rounded-sm",
                "shadow-[0_12px_40px_-8px_rgba(0,0,0,0.85)]",
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
          <StatPanel character={data.enemy} />
        </div>
      </div>
    </div>
  );
}
