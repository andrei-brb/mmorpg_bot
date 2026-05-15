import { useRef, useState, type ReactNode } from "react";

import { ItemIcon } from "@/components/game/ItemIcon";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import type { InvRow } from "@/lib/apiTypes";
import { itemPopoverStatRows, itemTooltipSubtitle } from "@/lib/itemStatLines";
import { cn } from "@/lib/utils";

type PopoverRarity = "common" | "uncommon" | "rare" | "epic" | "legendary";

const RARITY_STYLES: Record<
  PopoverRarity,
  { ring: string; glow: string; chip: string }
> = {
  common: {
    ring: "ring-muted-foreground/45",
    glow: "shadow-[0_0_20px_-8px_oklch(0.72_0_0/0.45)]",
    chip: "text-muted-foreground",
  },
  uncommon: {
    ring: "ring-emerald-400/50",
    glow: "shadow-[0_0_22px_-8px_oklch(0.72_0.16_150/0.5)]",
    chip: "text-emerald-300",
  },
  rare: {
    ring: "ring-sky-400/50",
    glow: "shadow-[0_0_22px_-8px_oklch(0.72_0.16_230/0.5)]",
    chip: "text-sky-300",
  },
  epic: {
    ring: "ring-fuchsia-400/55",
    glow: "shadow-[0_0_24px_-8px_oklch(0.68_0.22_300/0.5)]",
    chip: "text-fuchsia-300",
  },
  legendary: {
    ring: "ring-[color:var(--gold)]/55",
    glow: "shadow-[0_0_26px_-6px_oklch(0.82_0.14_85/0.55)]",
    chip: "text-[color:var(--gold-bright)]",
  },
};

const RARITY_LABEL: Record<PopoverRarity, string> = {
  common: "Common",
  uncommon: "Uncommon",
  rare: "Rare",
  epic: "Epic",
  legendary: "Legendary",
};

function normalizeRarity(r?: string | null): PopoverRarity {
  const x = (r || "common").toLowerCase();
  if (x === "uncommon" || x === "rare" || x === "epic" || x === "legendary") return x;
  return "common";
}

function ActionBtn({
  label,
  accent,
  onClick,
}: {
  label: string;
  accent?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
      className={cn(
        "relative min-h-[2.5rem] flex-1 py-2 text-[10px] font-display tracking-[0.22em] transition-colors",
        "border-r border-[color:var(--gold)]/20 last:border-r-0",
        accent
          ? "text-[color:var(--gold-bright)] hover:bg-[color:var(--gold)]/10"
          : "text-[color:var(--gold)]/70 hover:bg-[color:var(--gold)]/5 hover:text-[color:var(--gold-bright)]",
      )}
    >
      {label}
    </button>
  );
}

export type ItemPopoverProps = {
  item: InvRow;
  children: ReactNode;
  /** When true, render children only (e.g. salvage selection mode). */
  disabled?: boolean;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  equipped?: boolean;
  compare?: ReactNode;
  onEquip?: () => void;
  onUnequip?: () => void;
  onEnhance?: () => void;
  onSalvage?: () => void;
  onList?: () => void;
  onUse?: () => void;
};

export function ItemPopover({
  item,
  children,
  disabled = false,
  side = "right",
  align = "center",
  equipped = false,
  compare,
  onEquip,
  onUnequip,
  onEnhance,
  onSalvage,
  onList,
  onUse,
}: ItemPopoverProps) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const rarity = normalizeRarity(item.rarity);
  const r = RARITY_STYLES[rarity];
  const stats = itemPopoverStatRows(item);
  const enh = Number(item.enhancement_level ?? 0) || 0;

  const cancel = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  const onEnter = () => {
    cancel();
    setOpen(true);
  };

  const onLeave = () => {
    if (pinned) return;
    cancel();
    closeTimer.current = window.setTimeout(() => setOpen(false), 120);
  };

  const closePopover = () => {
    cancel();
    setPinned(false);
    setOpen(false);
  };

  if (disabled) return <>{children}</>;

  const flavor = itemTooltipSubtitle(item) || "Forged for the realm—handle with ambition.";

  const visible: Array<{ label: string; accent?: boolean; onClick?: () => void }> = [];
  if (onUse) visible.push({ label: "Use", accent: true, onClick: () => { closePopover(); onUse(); } });
  if (onUnequip) visible.push({ label: "Unequip", onClick: () => { closePopover(); onUnequip(); } });
  else if (onEquip) visible.push({ label: "Equip", onClick: () => { closePopover(); onEquip(); } });
  if (onEnhance) visible.push({ label: "Enhance", accent: true, onClick: () => { closePopover(); onEnhance(); } });
  if (onSalvage) visible.push({ label: "Salvage", onClick: () => { closePopover(); onSalvage(); } });
  if (onList) visible.push({ label: "List", onClick: () => { closePopover(); onList(); } });

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          cancel();
          setPinned(false);
          setOpen(false);
        }
      }}
    >
      <PopoverAnchor asChild>
        <div
          className="block"
          onMouseEnter={onEnter}
          onMouseLeave={onLeave}
          onClick={(e) => {
            e.stopPropagation();
            if (pinned) {
              setPinned(false);
              setOpen(false);
              cancel();
            } else {
              setPinned(true);
              setOpen(true);
              cancel();
            }
          }}
        >
          {children}
        </div>
      </PopoverAnchor>
      <PopoverContent
        side={side}
        align={align}
        sideOffset={6}
        collisionPadding={8}
        onMouseEnter={onEnter}
        onMouseLeave={onLeave}
        onOpenAutoFocus={(e) => e.preventDefault()}
        className={cn(
          "w-72 p-0 rounded-md",
          "border border-[color:var(--gold)]/45 bg-black/95 backdrop-blur-md shadow-2xl",
          "text-foreground",
        )}
      >
        <div className="flex items-center gap-3 border-b border-[color:var(--gold)]/25 bg-gradient-to-b from-black/90 to-black/95 px-3 py-2.5">
          <div
            className={cn(
              "relative flex h-12 w-12 shrink-0 items-center justify-center bg-black/60 ring-1",
              r.ring,
              r.glow,
            )}
          >
            <ItemIcon item={item} size={36} />
            {enh > 0 ? (
              <span className="absolute -right-1.5 -top-1.5 border border-[color:var(--gold)]/60 bg-background px-1 py-px font-display text-[9px] tracking-wider text-[color:var(--gold-bright)]">
                +{enh}
              </span>
            ) : null}
          </div>
          <div className="min-w-0">
            <div className={cn("truncate font-display text-sm leading-tight tracking-[0.12em]", r.chip)}>{item.name}</div>
            <div className="mt-1 text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
              {RARITY_LABEL[rarity]}
              {equipped ? " · Equipped" : ""}
            </div>
          </div>
        </div>

        <div className="divide-y divide-[color:var(--gold)]/15 px-3">
          {stats.map((s) => (
            <div
              key={`${s.label}-${s.value}`}
              className="flex min-h-[1.75rem] items-baseline justify-between gap-3 py-2 text-[11px] first:pt-3 last:pb-3"
            >
              <span className="shrink-0 uppercase tracking-[0.18em] text-muted-foreground">{s.label}</span>
              <span className="min-w-0 text-right font-display tabular-nums text-[color:var(--gold-bright)]">
                {s.value}
              </span>
            </div>
          ))}
        </div>

        {compare ? (
          <div className="border-t border-[color:var(--gold)]/25 bg-black/25 px-3 py-2.5 text-[10px] leading-snug text-muted-foreground">
            {compare}
          </div>
        ) : null}

        <div className="px-3 pb-3">
          <div className="h-px bg-gradient-to-r from-transparent via-[color:var(--gold)]/35 to-transparent" />
          <p className="mt-2 text-center text-[10px] italic leading-relaxed text-muted-foreground">{flavor}</p>
        </div>

        {visible.length > 0 ? (
          <div
            className="grid gap-px border-t border-[color:var(--gold)]/25 bg-black/60"
            style={{ gridTemplateColumns: `repeat(${visible.length}, minmax(0, 1fr))` }}
          >
            {visible.map((a) => (
              <ActionBtn key={a.label} label={a.label} accent={a.accent} onClick={a.onClick} />
            ))}
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
