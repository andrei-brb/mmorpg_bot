import { useMemo } from "react";
import { TalentForgeNode } from "@/components/game/talents/TalentForgeNode";
import { lockedReasonLabel } from "@/components/game/talents/talentForgeAdapter";
import type { ForgeTalent, ForgeTalentTree } from "@/components/game/talents/talentForgeTypes";
import { cn } from "@/lib/utils";

const COL_W = 110;
const ROW_H = 110;
const PAD_X = 60;
const PAD_Y = 60;

type NodeStatus = "active" | "available" | "locked" | "maxed";

type Props = {
  tree: ForgeTalentTree;
  ranks: Record<string, number>;
  pointsInTree: number;
  canSpend: boolean;
  lockedReason?: string;
  onInvest: (talentId: string) => void;
  active?: boolean;
  subtitle?: React.ReactNode;
  busy?: boolean;
};

export function TalentForgePanel({
  tree,
  ranks,
  pointsInTree,
  canSpend,
  lockedReason,
  onInvest,
  active = true,
  subtitle,
  busy = false,
}: Props) {
  const Icon = tree.icon;

  const { width, height } = useMemo(() => {
    const cols = Math.max(1, ...tree.talents.map((t) => t.col)) + 1;
    const rows = Math.max(1, ...tree.talents.map((t) => t.row)) + 1;
    return {
      width: cols * COL_W + PAD_X * 2,
      height: rows * ROW_H + PAD_Y * 2,
    };
  }, [tree]);

  const nodePos = (row: number, col: number) => ({
    x: PAD_X + col * COL_W + COL_W / 2,
    y: PAD_Y + row * ROW_H + ROW_H / 2,
  });

  const getStatus = (talent: ForgeTalent): { status: NodeStatus; reason?: string } => {
    const rank = ranks[talent.id] ?? 0;
    if (!active) return { status: "locked", reason: lockedReason ?? "Tree locked." };
    if (talent.autoGrant) return rank > 0 ? { status: "maxed" } : { status: "active" };
    if (rank >= talent.maxRank) return { status: "maxed" };
    if (talent.pointsRequired && pointsInTree < talent.pointsRequired) {
      return { status: "locked", reason: `Requires ${talent.pointsRequired} points spent in ${tree.name}.` };
    }
    if (talent.requires?.length) {
      const missing = talent.requires.filter((r) => (ranks[r] ?? 0) === 0);
      if (missing.length) {
        const names = missing
          .map((id) => tree.talents.find((t) => t.id === id)?.name)
          .filter(Boolean)
          .join(", ");
        return { status: "locked", reason: `Requires: ${names}` };
      }
    }
    if (talent.canAllocate === false) {
      if (rank > 0) return { status: "active" };
      return { status: "locked", reason: lockedReasonLabel(talent.lockedReason) };
    }
    if (rank > 0) return { status: "active" };
    if (!canSpend) return { status: "available", reason: "No talent points to spend." };
    return { status: "available" };
  };

  return (
    <section className={cn("ornate-frame rounded-md p-4 sm:p-6 relative", !active && "opacity-80")}>
      <span className="corner-ornament corner-tl" aria-hidden />
      <span className="corner-ornament corner-tr" aria-hidden />
      <span className="corner-ornament corner-bl" aria-hidden />
      <span className="corner-ornament corner-br" aria-hidden />

      <header className="relative flex items-end justify-between gap-4 mb-2">
        <div className="flex items-center gap-3 sm:gap-4 min-w-0">
          <div
            className={cn(
              "h-12 w-12 sm:h-14 sm:w-14 grid place-items-center rounded border-2 shrink-0",
              active ? "border-gold shadow-gold" : "border-border",
            )}
            style={{ background: active ? "var(--gradient-node-active)" : "var(--gradient-node-locked)" }}
          >
            <Icon className={cn("h-6 w-6 sm:h-7 sm:w-7", active ? "text-background" : "text-muted-foreground")} strokeWidth={2.2} />
          </div>
          <div className="min-w-0">
            <h3 className="font-cinzel text-xl sm:text-2xl text-gold-bright tracking-widest uppercase truncate">{tree.name}</h3>
            <p className="text-xs text-muted-foreground italic line-clamp-2">{tree.flavor}</p>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="font-cinzel text-lg sm:text-xl text-gold">
            {pointsInTree}
            <span className="text-muted-foreground"> spent</span>
          </div>
          {subtitle ? <div className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</div> : null}
        </div>
      </header>

      <div className="divider-ornate my-4" />

      <div className="relative w-full overflow-x-auto">
        <div
          className="relative mx-auto"
          style={{
            width,
            height,
            backgroundImage: "radial-gradient(circle, oklch(0.78 0.14 78 / 0.05) 1px, transparent 1px)",
            backgroundSize: "22px 22px",
          }}
        >
          <svg className="absolute inset-0 pointer-events-none" width={width} height={height}>
            <defs>
              <linearGradient id={`line-active-${tree.id}`} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="oklch(0.88 0.16 88)" stopOpacity="0.9" />
                <stop offset="100%" stopColor="oklch(0.55 0.1 75)" stopOpacity="0.9" />
              </linearGradient>
            </defs>
            {tree.talents.flatMap((talent) =>
              (talent.requires ?? []).map((reqId) => {
                const req = tree.talents.find((t) => t.id === reqId);
                if (!req) return null;
                const from = nodePos(req.row, req.col);
                const to = nodePos(talent.row, talent.col);
                const isOn = (ranks[reqId] ?? 0) > 0 && active;
                return (
                  <line
                    key={`${reqId}-${talent.id}`}
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke={isOn ? `url(#line-active-${tree.id})` : "oklch(0.4 0.04 70)"}
                    strokeWidth={isOn ? 3 : 1.5}
                    strokeOpacity={isOn ? 1 : 0.35}
                    strokeDasharray={isOn ? "0" : "5 4"}
                  />
                );
              }),
            )}
          </svg>

          {tree.talents.map((talent) => {
            const pos = nodePos(talent.row, talent.col);
            const { status, reason } = getStatus(talent);
            return (
              <div
                key={talent.id}
                className="absolute -translate-x-1/2 -translate-y-1/2"
                style={{ left: pos.x, top: pos.y }}
              >
                <TalentForgeNode
                  talent={talent}
                  rank={ranks[talent.id] ?? 0}
                  status={status}
                  reason={reason}
                  disabled={busy}
                  onClick={() => {
                    if (status === "available" || status === "active") onInvest(talent.id);
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>

      {!active && lockedReason ? (
        <div className="absolute inset-0 grid place-items-center bg-background/60 backdrop-blur-[2px] rounded-md pointer-events-none">
          <div className="ornate-frame px-6 py-3 rounded">
            <p className="font-cinzel text-gold tracking-widest uppercase text-sm text-center">{lockedReason}</p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
