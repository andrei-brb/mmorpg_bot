import { useId, type ReactNode, type ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

type WomPanelProps = ComponentPropsWithoutRef<"div"> & {
  children: ReactNode;
  glow?: boolean;
  bracket?: boolean;
};

export function WomPanel({
  children,
  className = "",
  glow = false,
  bracket = true,
  ...rest
}: WomPanelProps) {
  return (
    <div
      className={cn("wom-game-panel game-panel relative", glow && "wom-game-panel-glow", className)}
      {...rest}
    >
      {bracket ? (
        <>
          <span className="pointer-events-none absolute -left-[2px] -top-[2px] h-4 w-4 border-l-[1.5px] border-t-[1.5px] border-[var(--gold-500)]" />
          <span className="pointer-events-none absolute -right-[2px] -top-[2px] h-4 w-4 border-r-[1.5px] border-t-[1.5px] border-[var(--gold-500)]" />
          <span className="pointer-events-none absolute -bottom-[2px] -left-[2px] h-4 w-4 border-b-[1.5px] border-l-[1.5px] border-[var(--gold-500)]" />
          <span className="pointer-events-none absolute -bottom-[2px] -right-[2px] h-4 w-4 border-b-[1.5px] border-r-[1.5px] border-[var(--gold-500)]" />
        </>
      ) : null}
      {children}
    </div>
  );
}

export function WomSectionHeader({
  title,
  kicker,
  right,
}: {
  title: string;
  kicker?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {kicker ? <div className="text-label mb-1 text-[var(--gold-600)]">{kicker}</div> : null}
        <h2 className="font-display text-xl font-bold uppercase leading-none tracking-wider text-[var(--gold-200)] sm:text-2xl md:text-3xl">
          {title}
        </h2>
        <div className="mt-2 h-0.5 w-16 bg-gradient-to-r from-[var(--gold-400)] to-transparent" />
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
}

export function WomOrnateDivider({ label }: { label?: string }) {
  return (
    <div className="my-3 flex w-full items-center gap-3">
      <div className="min-w-0 flex-1 divider-ornate" />
      <div className="diamond-divider" />
      {label ? (
        <>
          <span className="font-display whitespace-nowrap text-[11px] uppercase tracking-[0.32em] text-[var(--gold-400)]">
            {label}
          </span>
          <div className="diamond-divider" />
        </>
      ) : null}
      <div className="min-w-0 flex-1 divider-ornate" />
    </div>
  );
}

const pillTones = {
  default: "border-[var(--border-default)] text-[var(--text-secondary)] bg-[var(--bg-panel-raised)]",
  gold: "border-[var(--gold-600)] text-[var(--gold-200)] bg-[rgba(184,151,88,0.08)]",
  crimson: "border-[var(--crimson-500)] text-[var(--crimson-400)] bg-[rgba(176,32,32,0.08)]",
  arcane: "border-[#3b82f6]/60 text-[var(--arcane)] bg-[rgba(95,168,255,0.08)]",
  success: "border-[#22c55e]/60 text-[var(--verdant)] bg-[rgba(110,227,110,0.08)]",
} as const;

export function WomPill({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: keyof typeof pillTones;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${pillTones[tone]}`}
    >
      {children}
    </span>
  );
}

export function WomStatBar({
  value,
  max,
  variant = "gold",
  small,
}: {
  value: number;
  max: number;
  variant?: "gold" | "crimson" | "arcane";
  small?: boolean;
}) {
  const pct = Math.min(100, Math.max(0, max > 0 ? (value / max) * 100 : 0));
  return (
    <div className={`bar-track ${small ? "!h-[5px]" : ""}`}>
      <div className={`bar-fill ${variant}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function WomGoldCoin({ size = 14, className = "" }: { size?: number; className?: string }) {
  const gid = useId().replace(/:/g, "");
  const gradId = `wom-coin-grad-${gid}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={`inline-block align-middle ${className}`.trim()}
      aria-hidden
    >
      <defs>
        <radialGradient id={gradId} cx="35%" cy="35%">
          <stop offset="0%" stopColor="#fff8e1" />
          <stop offset="50%" stopColor="#d4a94e" />
          <stop offset="100%" stopColor="#5d4720" />
        </radialGradient>
      </defs>
      <circle cx="12" cy="12" r="10" fill={`url(#${gradId})`} />
      <circle cx="12" cy="12" r="7" fill="none" stroke="#5d4720" strokeWidth="0.8" />
      <path
        d="M12 7 L13.4 10.2 L17 10.6 L14.3 13.1 L15 16.6 L12 14.9 L9 16.6 L9.7 13.1 L7 10.6 L10.6 10.2 Z"
        fill="#5d4720"
        opacity="0.6"
      />
    </svg>
  );
}
