import { useCallback, useMemo, useRef, useState } from "react";
import type { TalentNodeState, TalentTreeSection } from "@/lib/apiTypes";
import { cn } from "@/lib/utils";

const COL_W = 72;
const ROW_H = 76;
const NODE_R = 22;
const PAD = 48;

type Props = {
  tree: TalentTreeSection;
  title?: string;
  dimmed?: boolean;
  onAllocate?: (nodeId: string) => void;
};

function nodePos(node: TalentNodeState): { x: number; y: number } {
  const col = Number(node.column ?? 0);
  const tier = Number(node.tier ?? 0);
  return { x: PAD + col * COL_W, y: PAD + tier * ROW_H };
}

export function TalentTreeCanvas({ tree, title, dimmed, onAllocate }: Props) {
  const nodes = tree.nodes ?? [];
  const nodeById = useMemo(() => {
    const m = new Map<string, TalentNodeState>();
    for (const n of nodes) {
      if (n.id) m.set(String(n.id), n);
    }
    return m;
  }, [nodes]);

  const bounds = useMemo(() => {
    let maxX = PAD + COL_W * 4;
    let maxY = PAD + ROW_H * 6;
    for (const n of nodes) {
      const { x, y } = nodePos(n);
      maxX = Math.max(maxX, x + NODE_R + PAD);
      maxY = Math.max(maxY, y + NODE_R + PAD);
    }
    return { width: maxX, height: maxY };
  }, [nodes]);

  const edges = useMemo(() => {
    const lines: { x1: number; y1: number; x2: number; y2: number; lit: boolean }[] = [];
    for (const n of nodes) {
      const to = nodePos(n);
      for (const pid of n.prereqs ?? []) {
        const p = nodeById.get(String(pid));
        if (!p) continue;
        const from = nodePos(p);
        const lit = (n.ranks ?? 0) > 0 && (p.ranks ?? 0) > 0;
        lines.push({ x1: from.x, y1: from.y, x2: to.x, y2: to.y, lit });
      }
    }
    return lines;
  }, [nodes, nodeById]);

  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const dragRef = useRef<{ x: number; y: number; px: number; py: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.08 : 0.08;
    setZoom((z) => Math.min(1.6, Math.max(0.55, z + delta)));
  }, []);

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if ((e.target as HTMLElement).closest("[data-talent-node]")) return;
      dragRef.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    },
    [pan.x, pan.y],
  );

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragRef.current) return;
    setPan({
      x: dragRef.current.px + (e.clientX - dragRef.current.x),
      y: dragRef.current.py + (e.clientY - dragRef.current.y),
    });
  }, []);

  const onPointerUp = useCallback(() => {
    dragRef.current = null;
  }, []);

  const [tip, setTip] = useState<TalentNodeState | null>(null);

  return (
    <div className={cn("rounded-sm border border-border/50 bg-muted/10", dimmed && "opacity-55")}>
      {title ? (
        <div className="px-3 py-2 border-b border-border/40 text-xs font-cinzel uppercase tracking-wider text-muted-foreground">
          {title}
        </div>
      ) : null}
      <div
        ref={wrapRef}
        className="relative h-[min(52vh,320px)] overflow-hidden touch-none cursor-grab active:cursor-grabbing"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${bounds.width} ${bounds.height}`}
          className="select-none"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
          }}
        >
          {edges.map((e, i) => (
            <line
              key={i}
              x1={e.x1}
              y1={e.y1}
              x2={e.x2}
              y2={e.y2}
              stroke={e.lit ? "hsl(43 78% 50% / 0.75)" : "hsl(0 0% 40% / 0.5)"}
              strokeWidth={e.lit ? 2.5 : 1.5}
            />
          ))}
          {nodes.map((n) => {
            const { x, y } = nodePos(n);
            const ranks = n.ranks ?? 0;
            const max = n.max_ranks ?? 1;
            const glow = n.glow || ranks > 0;
            const can = n.can_allocate && !dimmed;
            const locked = Boolean(n.locked_reason) && ranks < max;
            const desc =
              (n.descriptions && n.descriptions[Math.max(0, ranks - 1)]) ||
              n.descriptions?.[0] ||
              n.name ||
              "";
            return (
              <g
                key={n.id}
                data-talent-node
                transform={`translate(${x}, ${y})`}
                className={cn(can && "cursor-pointer")}
                onClick={() => {
                  if (can && onAllocate && n.id) onAllocate(String(n.id));
                }}
                onMouseEnter={() => setTip(n)}
                onMouseLeave={() => setTip(null)}
              >
                <circle
                  r={NODE_R}
                  fill={glow ? "hsl(43 78% 50% / 0.18)" : "hsl(0 0% 12% / 0.9)"}
                  stroke={glow ? "hsl(43 78% 55%)" : locked ? "hsl(0 0% 35%)" : "hsl(0 0% 50%)"}
                  strokeWidth={glow ? 2.5 : 1.5}
                  filter={glow ? "drop-shadow(0 0 6px hsl(43 78% 50% / 0.45))" : undefined}
                />
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  className="fill-foreground text-[10px] font-semibold pointer-events-none"
                  style={{ fontFamily: "var(--font-cinzel, serif)" }}
                >
                  {ranks > 0 ? `${ranks}/${max}` : max > 1 ? "·" : "+"}
                </text>
                <title>{`${n.name}\n${desc}\n${ranks}/${max}${locked ? ` (${n.locked_reason})` : ""}`}</title>
              </g>
            );
          })}
        </svg>
        {tip ? (
          <div
            className="pointer-events-none absolute bottom-2 left-2 right-2 z-10 rounded-sm border border-primary/30 bg-background/95 px-2 py-1.5 text-[11px] shadow-lg"
            aria-live="polite"
          >
            <div className="font-cinzel text-foreground">{tip.name}</div>
            <div className="text-muted-foreground mt-0.5">
              {(tip.descriptions && tip.descriptions[Math.max(0, (tip.ranks ?? 1) - 1)]) || tip.descriptions?.[0]}
            </div>
            <div className="text-[10px] text-primary/90 mt-0.5 tabular-nums">
              Rank {tip.ranks ?? 0}/{tip.max_ranks ?? 1}
              {tip.can_allocate ? " · click to spend" : ""}
            </div>
          </div>
        ) : null}
        <div className="absolute top-1 right-2 text-[9px] text-muted-foreground font-mono">drag · scroll zoom</div>
      </div>
    </div>
  );
}
