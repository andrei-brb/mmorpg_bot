import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ForgeTalent } from "@/components/game/talents/talentForgeTypes";
import { cn } from "@/lib/utils";

type Status = "active" | "available" | "locked" | "maxed";

type Props = {
  talent: ForgeTalent;
  rank: number;
  status: Status;
  reason?: string;
  disabled?: boolean;
  onClick: (e: React.MouseEvent) => void;
};

const tierSize: Record<ForgeTalent["tier"], string> = {
  passive: "h-12 w-12",
  minor: "h-14 w-14",
  major: "h-16 w-16",
  keystone: "h-20 w-20",
};

const tierShape: Record<ForgeTalent["tier"], string> = {
  passive: "rounded-full",
  minor: "rounded-full",
  major: "rounded-md rotate-45",
  keystone: "rounded-md rotate-45",
};

const iconWrap: Record<ForgeTalent["tier"], string> = {
  passive: "",
  minor: "",
  major: "-rotate-45",
  keystone: "-rotate-45",
};

export function TalentForgeNode({ talent, rank, status, reason, disabled, onClick }: Props) {
  const Icon = talent.icon;
  const isActive = status === "active" || status === "maxed";
  const canClick = !disabled && (status === "available" || status === "active");

  return (
    <Tooltip delayDuration={120}>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={(e) => {
            if (canClick) onClick(e);
          }}
          disabled={!canClick}
          className={cn(
            "relative grid place-items-center border-2 transition-[transform,box-shadow,border-color] duration-200",
            tierSize[talent.tier],
            tierShape[talent.tier],
            canClick && "hover:scale-110 active:scale-95 cursor-pointer",
            status === "locked" && "border-border/40 opacity-50 cursor-not-allowed hover:scale-100",
            status === "available" && "border-gold/50 hover:border-gold hover:shadow-gold",
            status === "active" && "border-gold shadow-gold animate-pulse-gold",
            status === "maxed" && "border-gold-bright shadow-gold",
          )}
          style={{
            background: isActive
              ? "var(--gradient-node-active)"
              : status === "available"
                ? "var(--gradient-node-available)"
                : "var(--gradient-node-locked)",
          }}
        >
          <div className={cn("grid place-items-center w-full h-full", iconWrap[talent.tier])}>
            <Icon
              className={cn(
                "transition-colors",
                talent.tier === "keystone" ? "h-9 w-9" : talent.tier === "major" ? "h-7 w-7" : "h-6 w-6",
                isActive ? "text-background" : status === "available" ? "text-gold" : "text-muted-foreground",
              )}
              strokeWidth={2.2}
            />
          </div>
          {!talent.autoGrant ? (
            <span
              className={cn(
                "absolute -bottom-2 left-1/2 -translate-x-1/2 px-1.5 py-0.5 text-[10px] font-bold font-cinzel rounded border bg-background",
                talent.tier === "major" || talent.tier === "keystone" ? "rotate-[-45deg] -bottom-3" : "",
                isActive ? "border-gold-bright text-gold-bright" : "border-border text-muted-foreground",
              )}
            >
              {rank}/{talent.maxRank}
            </span>
          ) : null}
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        sideOffset={14}
        className="max-w-72 ornate-frame !bg-popover/95 backdrop-blur-md p-0 border-gold/40"
      >
        <div className="relative px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <h4 className="font-cinzel text-base text-gold-bright leading-tight">{talent.name}</h4>
            <span className="text-[10px] font-cinzel uppercase tracking-widest text-gold-dim">{talent.tier}</span>
          </div>
          <p className="mt-1 text-xs text-foreground/80">{talent.description}</p>
          <div className="mt-3 space-y-1">
            {talent.ranks.map((r, i) => (
              <div
                key={i}
                className={cn(
                  "text-[11px] flex items-center gap-2",
                  i < rank ? "text-gold-bright" : i === rank ? "text-foreground" : "text-muted-foreground/70",
                )}
              >
                <span className="font-cinzel w-10 shrink-0">RANK {i + 1}</span>
                <span>{r}</span>
              </div>
            ))}
          </div>
          {reason ? (
            <p className="mt-3 pt-2 border-t border-border/60 text-[11px] text-destructive/90">{reason}</p>
          ) : null}
          {canClick ? (
            <p className="mt-2 text-[10px] text-muted-foreground/70 font-cinzel tracking-wider">CLICK to invest</p>
          ) : null}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
