import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { RewardDelivery } from "@/lib/apiTypes";

function GoldCoin({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ display: "inline-block" }} aria-hidden>
      <defs>
        <radialGradient id="reward-coin-grad" cx="35%" cy="35%">
          <stop offset="0%" stopColor="#fff8e1" />
          <stop offset="50%" stopColor="#d4a94e" />
          <stop offset="100%" stopColor="#5d4720" />
        </radialGradient>
      </defs>
      <circle cx="12" cy="12" r="10" fill="url(#reward-coin-grad)" />
    </svg>
  );
}

export type RewardRevealDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  delivery?: RewardDelivery | null;
  extraRows?: Array<{ label: string; value: string }>;
  footnote?: string;
};

export function RewardRevealDialog({
  open,
  onOpenChange,
  title,
  description,
  delivery,
  extraRows,
  footnote,
}: RewardRevealDialogProps) {
  const gold = delivery?.gold ?? 0;
  const xp = delivery?.character_xp ?? 0;
  const gxp = delivery?.guild_xp ?? 0;
  const craftXp = delivery?.crafting_xp ?? 0;
  const items = delivery?.items ?? [];
  const hasBody =
    gold > 0 ||
    xp > 0 ||
    gxp > 0 ||
    craftXp > 0 ||
    items.length > 0 ||
    (extraRows && extraRows.length > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[min(calc(100vw-2rem),24rem)] sm:max-w-md gap-4 p-5 border border-[var(--border-default)] bg-[var(--bg-panel)]">
        <DialogHeader className="space-y-2 text-center sm:text-center">
          <DialogTitle className="text-lg font-cinzel tracking-wide text-[var(--gold-200)]">{title}</DialogTitle>
          {description ? (
            <DialogDescription className="text-sm text-[var(--text-muted)]">{description}</DialogDescription>
          ) : null}
        </DialogHeader>
        {hasBody ? (
          <div className="rounded-sm border border-[var(--border-default)] bg-[var(--bg-panel-raised)] p-4 space-y-3">
            {extraRows?.map((row) => (
              <div key={row.label} className="flex items-center justify-between text-sm">
                <span className="text-[var(--text-muted)]">{row.label}</span>
                <span className="font-mono font-semibold text-[var(--text-primary)]">{row.value}</span>
              </div>
            ))}
            {gold > 0 ? (
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--text-muted)]">Gold</span>
                <span className="inline-flex items-center gap-1.5 font-mono font-semibold text-[var(--gold-200)]">
                  <GoldCoin size={14} />+{gold.toLocaleString()}
                </span>
              </div>
            ) : null}
            {xp > 0 ? (
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--text-muted)]">Character XP</span>
                <span className="font-mono font-semibold text-[var(--text-primary)]">+{xp.toLocaleString()}</span>
              </div>
            ) : null}
            {craftXp > 0 ? (
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--text-muted)]">Forge XP</span>
                <span className="font-mono font-semibold text-[var(--text-primary)]">+{craftXp.toLocaleString()}</span>
              </div>
            ) : null}
            {gxp > 0 ? (
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--text-muted)]">Guild XP</span>
                <span className="font-mono font-semibold text-[var(--text-primary)]">+{gxp.toLocaleString()}</span>
              </div>
            ) : null}
            {items.length > 0 ? (
              <div>
                <div className="text-[10px] uppercase tracking-widest text-[var(--text-muted)] mb-2">Items</div>
                <ul className="space-y-1 text-sm text-[var(--text-primary)]">
                  {items.map((it, i) => (
                    <li key={`${it.template_id}-${i}`} className="font-mono">
                      {it.quantity ?? 1}× {(it.template_id || "item").replace(/_/g, " ")}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {footnote ? (
              <p className="text-[11px] text-center text-[var(--text-muted)] pt-1 border-t border-[var(--border-default)]">
                {footnote}
              </p>
            ) : null}
          </div>
        ) : null}
        <button type="button" className="btn-gold w-full" onClick={() => onOpenChange(false)}>
          Collect
        </button>
      </DialogContent>
    </Dialog>
  );
}
