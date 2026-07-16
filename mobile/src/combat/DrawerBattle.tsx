import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { getBattlefieldBackgroundStackStyle } from "@/components/game/combat/BattleBackground";
import type { BattleRendererProps } from "@/context/BattleRenderer";
import type { CharacterData, CharacterStat } from "@/components/BattlePreview";

/**
 * Layout 2 — "The Drawer". Mobile only.
 *
 * The battlefield is the whole screen; your controls live in a sheet at the
 * bottom that can be pulled down to watch the fight.
 *
 * Why a component instead of CSS over BattlePreview: BattlePreview is a
 * three-column desktop arena locked to a 16/9 box by inline styles. Every
 * attempt to override it into a phone layout put elements on top of each other,
 * because `order` and `!important` can move boxes but cannot restructure them.
 * BattlePreview is purely presentational though — CombatEncounterView builds
 * `data` and hands over a ready-made `combatGrid` — so this renders the SAME
 * data and the SAME interactive grid. No combat logic is duplicated, and
 * BattlePreview stays untouched for Discord.
 */

/** HP / Rage / Mana carry bars; Attack Power, Defense, Accuracy are flat numbers. */
function parseVital(v: string | number): { cur: number; max: number } | null {
  const m = String(v).match(/^\s*([\d,]+)\s*\/\s*([\d,]+)\s*$/);
  if (!m) return null;
  const cur = Number(m[1].replace(/,/g, ""));
  const max = Number(m[2].replace(/,/g, ""));
  if (!Number.isFinite(cur) || !Number.isFinite(max) || max <= 0) return null;
  return { cur, max };
}

function isResource(label: string): boolean {
  const l = label.toLowerCase();
  return ["mp", "mana", "energy", "rage", "focus"].some((k) => l.includes(k));
}

type Vital = { label: string; cur: number; max: number; kind: "hp" | "resource" };

function vitalsOf(c: CharacterData): { vitals: Vital[]; flat: CharacterStat[] } {
  const vitals: Vital[] = [];
  const flat: CharacterStat[] = [];
  for (const s of c.stats) {
    const p = parseVital(s.value);
    if (p) vitals.push({ label: s.label, ...p, kind: isResource(s.label) ? "resource" : "hp" });
    else flat.push(s);
  }
  return { vitals, flat };
}

function Bar({ pct, kind }: { pct: number; kind: Vital["kind"] }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-black/70">
      <div
        className="h-full rounded-full transition-[width] duration-300 ease-out"
        style={{
          width: `${Math.max(0, Math.min(100, pct))}%`,
          background:
            kind === "hp"
              ? "linear-gradient(90deg, hsl(146 49% 40%), hsl(146 49% 56%))"
              : "linear-gradient(90deg, hsl(210 53% 38%), hsl(210 65% 60%))",
        }}
      />
    </div>
  );
}

type Tab = "skills" | "bag" | "status";

export function DrawerBattle({ data, combatGrid, extraActions }: BattleRendererProps) {
  const [tab, setTab] = useState<Tab>("skills");
  const [open, setOpen] = useState(true);

  const enemy = useMemo(() => vitalsOf(data.enemy), [data.enemy]);
  const player = useMemo(() => vitalsOf(data.player), [data.player]);

  const enemyHp = enemy.vitals.find((v) => v.kind === "hp") ?? null;
  const playerHp = player.vitals.find((v) => v.kind === "hp") ?? null;
  const playerRes = player.vitals.find((v) => v.kind === "resource") ?? null;

  const bg = data.battlefieldZoneKey
    ? getBattlefieldBackgroundStackStyle(data.battlefieldZoneKey)
    : data.backgroundUrl
      ? { backgroundImage: `url('${data.backgroundUrl}')`, backgroundSize: "cover", backgroundPosition: "center" }
      : undefined;

  const items = data.items ?? [];
  const buffs = data.buffs ?? [];

  return (
    <div className="relative flex h-[100dvh] w-full flex-col overflow-hidden bg-[hsl(264_26%_7%)]">
      {/* ── battlefield ── */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        {bg ? <div className="absolute inset-0" style={bg} /> : null}
        <div
          className="absolute inset-0"
          style={{ background: "radial-gradient(ellipse at 50% 34%, transparent 30%, hsl(264 30% 4% / 0.55) 100%)" }}
        />
        <div
          className="absolute inset-0"
          style={{ background: "linear-gradient(180deg, hsl(264 30% 4% / 0.7) 0%, transparent 26%, transparent 52%, hsl(264 30% 4% / 0.85) 100%)" }}
        />
      </div>

      {/* ── enemy HP, pinned top ── */}
      <div className="relative z-10 px-4 pt-[calc(env(safe-area-inset-top)+0.5rem)]">
        <div className="mb-1 flex items-baseline justify-between gap-2">
          <span
            className="truncate font-display text-sm tracking-[0.12em] text-[#FFC9D2]"
            style={{ textShadow: "0 1px 4px hsl(0 0% 0% / 0.9)" }}
          >
            {data.enemy.isBoss ? "💀 " : ""}
            {data.enemy.name.toUpperCase()}
            {data.enemy.level != null ? (
              <span className="ml-1.5 text-[10px] text-white/60">Lv {data.enemy.level}</span>
            ) : null}
          </span>
          {enemyHp ? (
            <span
              className="shrink-0 text-[10px] tabular-nums text-white/85"
              style={{ textShadow: "0 1px 4px hsl(0 0% 0% / 0.9)" }}
            >
              {enemyHp.cur.toLocaleString()} / {enemyHp.max.toLocaleString()}
            </span>
          ) : null}
        </div>
        {enemyHp ? (
          <div className="h-2 w-full overflow-hidden rounded-full bg-black/70 shadow-[0_2px_8px_hsl(0_0%_0%/0.7)]">
            <div
              className="h-full rounded-full transition-[width] duration-300 ease-out"
              style={{
                width: `${(enemyHp.cur / enemyHp.max) * 100}%`,
                background: "linear-gradient(90deg, hsl(345 60% 35%), hsl(350 72% 56%))",
              }}
            />
          </div>
        ) : null}
      </div>

      {/* ── enemy art, standing in the field ── */}
      <div className="relative z-10 flex min-h-0 flex-1 items-center justify-center px-4">
        <img
          src={data.enemy.portraitUrl}
          alt={data.enemy.name}
          className="h-full max-h-full w-auto max-w-[72%] object-contain"
          style={{
            filter: "drop-shadow(0 18px 34px hsl(0 0% 0% / 0.85))",
            WebkitMaskImage: "linear-gradient(180deg, #000 78%, transparent 100%)",
            maskImage: "linear-gradient(180deg, #000 78%, transparent 100%)",
            animation: "portrait-breathe 3s ease-in-out infinite",
          }}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.visibility = "hidden";
          }}
        />
      </div>

      {/* ── the drawer ── */}
      <div
        className={cn(
          "relative z-20 shrink-0 rounded-t-2xl border-t border-gold/40 px-3 pt-1.5",
          "shadow-[0_-14px_30px_-10px_hsl(264_40%_2%/0.9)]",
          "transition-[max-height] duration-300 ease-out",
        )}
        style={{
          background: "linear-gradient(180deg, hsl(265 26% 15%) 0%, hsl(264 27% 9%) 100%)",
          paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))",
          maxHeight: open ? "62dvh" : "calc(6.5rem + env(safe-area-inset-bottom))",
        }}
      >
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="mx-auto mb-2 flex h-5 w-full items-center justify-center"
          aria-label={open ? "Collapse panel" : "Expand panel"}
          aria-expanded={open}
        >
          <span className="h-1 w-9 rounded-full bg-gold/40" />
        </button>

        {/* one-line log (your call: last event only) */}
        {data.centerStatusLine ? (
          <p className="mb-2 truncate text-center text-[11px] text-foreground/80">{data.centerStatusLine}</p>
        ) : null}

        {/* your vitals */}
        <div className="mb-2.5 flex items-center gap-2.5">
          <span className="shrink-0 font-display text-[11px] tracking-[0.1em] text-gold-bright">
            {data.player.name.toUpperCase()}
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            {playerHp ? <Bar pct={(playerHp.cur / playerHp.max) * 100} kind="hp" /> : null}
            {playerRes ? <Bar pct={(playerRes.cur / playerRes.max) * 100} kind="resource" /> : null}
          </div>
          {playerHp ? (
            <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
              {playerHp.cur.toLocaleString()}/{playerHp.max.toLocaleString()}
            </span>
          ) : null}
        </div>

        {/* tabs */}
        <div className="mb-2 flex gap-1.5" role="tablist">
          {([
            ["skills", "Skills"],
            ["bag", `Bag${items.length ? ` · ${items.length}` : ""}`],
            ["status", `Status${buffs.length ? ` · ${buffs.length}` : ""}`],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => {
                setTab(id);
                setOpen(true);
              }}
              className={cn(
                "flex-1 rounded-lg border py-1.5 font-display text-[10px] uppercase tracking-[0.14em] transition-colors",
                tab === id
                  ? "border-gold/50 bg-gold/12 text-gold-bright"
                  : "border-border text-muted-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* panel body */}
        <div className="max-h-[38dvh] overflow-y-auto overscroll-contain">
          {tab === "skills" ? (
            <div className="space-y-2">
              <div className="drawer-grid">{combatGrid}</div>
              {/* Flee / Potion live in the drawer, not in a row underneath the
                  battle — off-screen is not a place to keep an escape hatch. */}
              {extraActions ? <div className="flex gap-2 pb-1">{extraActions}</div> : null}
            </div>
          ) : tab === "bag" ? (
            items.length ? (
              <div className="grid grid-cols-4 gap-1.5 pb-1">
                {items.map((it) => (
                  <div
                    key={it.id}
                    className="flex flex-col items-center gap-1 rounded-lg border border-gold/20 bg-black/35 p-1.5"
                  >
                    <span className="relative text-lg leading-none">
                      {it.icon}
                      {it.quantity > 1 ? (
                        <span className="absolute -right-2 -top-1 rounded-full bg-black/80 px-1 text-[8px] text-gold">
                          ×{it.quantity}
                        </span>
                      ) : null}
                    </span>
                    <span className="line-clamp-2 text-center text-[8.5px] leading-tight text-muted-foreground">
                      {it.name}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-4 text-center text-[11px] text-muted-foreground">Your bag is empty.</p>
            )
          ) : (
            <div className="space-y-2 pb-1">
              {buffs.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {buffs.map((b) => (
                    <span
                      key={b.id}
                      className={cn(
                        "rounded-md border px-2 py-1 text-[10px]",
                        b.type === "buff"
                          ? "border-[hsl(146_49%_51%/0.4)] text-[hsl(146_49%_66%)]"
                          : "border-destructive/40 text-destructive",
                      )}
                    >
                      {b.icon} {b.name}
                      {b.duration ? <span className="ml-1 opacity-60">{b.duration}</span> : null}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="py-2 text-center text-[11px] text-muted-foreground">No active effects.</p>
              )}

              {/* the flat stats hidden from the fight itself live here */}
              <div className="grid grid-cols-2 gap-1.5">
                {player.flat.map((s) => (
                  <div
                    key={s.label}
                    className="flex justify-between rounded-md bg-black/35 px-2 py-1 text-[10px]"
                  >
                    <span className="text-muted-foreground">{s.label}</span>
                    <span className="font-semibold tabular-nums">{String(s.value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DrawerBattle;
