import type { ReactNode } from "react";

export function ArenaPanel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <div className="relative min-w-0">
      <div className="mb-3 flex min-w-0 items-center gap-2">
        <span className="shrink-0 text-gold-bright">{icon}</span>
        <h3 className="font-display text-[11px] tracking-[0.35em] text-gold-bright sm:tracking-[0.4em]">
          {title.toUpperCase()}
        </h3>
        <div className="h-px min-w-[1rem] flex-1 bg-gradient-to-r from-gold/40 to-transparent" />
      </div>
      {children}
    </div>
  );
}

export function ArenaActionCard({ icon, title, body }: { icon: ReactNode; title: string; body: ReactNode }) {
  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-col hero-forge-edge-gold hero-forge-clip-blade-sm tex-forge p-4 sm:p-5">
      <div className="mb-3 flex shrink-0 items-center gap-2">
        <span className="text-gold-bright">{icon}</span>
        <span className="font-display text-[11px] tracking-[0.35em] text-gold-bright">{title.toUpperCase()}</span>
      </div>
      <div className="min-h-0 min-w-0 flex-1">{body}</div>
    </div>
  );
}

export function ArenaPlayerAvatar({
  name,
  src,
  size = 40,
}: {
  name: string;
  src?: string;
  size?: number;
}) {
  const initial = name.slice(0, 1).toUpperCase();
  return (
    <div
      className="relative flex shrink-0 items-center justify-center overflow-hidden hero-forge-clip-blade-sm tex-parchment border border-gold/40 hero-forge-edge-gold"
      style={{ width: size, height: size }}
      aria-label={`${name} portrait`}
    >
      {src ? (
        <img src={src} alt={name} className="h-full w-full object-cover" />
      ) : (
        <span className="font-display tracking-widest text-gold-bright" style={{ fontSize: Math.round(size * 0.42) }}>
          {initial}
        </span>
      )}
      <div className="pointer-events-none absolute inset-0.5 border border-gold/15" />
    </div>
  );
}
