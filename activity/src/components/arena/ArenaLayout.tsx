import type { ReactNode } from "react";
import { Swords, ScrollText } from "lucide-react";

export type ArenaHubSubTab = "stats" | "history";

type ArenaLayoutProps = {
  activeSub: ArenaHubSubTab;
  onSubChange: (sub: ArenaHubSubTab) => void;
  children: ReactNode;
};

/**
 * Coliseum shell (matches desktop `arena-pvp` reference) — sub-tabs drive hub vs history.
 */
export function ArenaLayout({ activeSub, onSubChange, children }: ArenaLayoutProps) {
  return (
    <div className="relative w-full min-w-0 tex-forge hero-forge-edge-gold-strong p-[2px]">
      <span className="corner-ornament corner-tl" aria-hidden />
      <span className="corner-ornament corner-tr" aria-hidden />
      <span className="corner-ornament corner-bl" aria-hidden />
      <span className="corner-ornament corner-br" aria-hidden />

      <div className="relative w-full min-w-0 bg-black/60 border border-gold/30">
        <div className="relative">
          <div className="hero-forge-clip-banner flex items-center justify-center gap-3 bg-gradient-to-r from-gold-dim via-gold-200 to-gold-dim px-6 py-2.5 text-background sm:px-8">
            <Swords className="h-4 w-4 shrink-0" />
            <span className="font-display text-center text-xs font-bold tracking-[0.35em] sm:tracking-[0.4em]">
              ARENA · COLISEUM OF KINGS
            </span>
            <Swords className="h-4 w-4 shrink-0" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-px border-b border-gold/30 bg-gold/20">
          <ArenaSubTab
            active={activeSub === "stats"}
            onClick={() => onSubChange("stats")}
            icon={<Swords className="h-4 w-4" />}
            label="PVP Stats"
          />
          <ArenaSubTab
            active={activeSub === "history"}
            onClick={() => onSubChange("history")}
            icon={<ScrollText className="h-4 w-4" />}
            label="Match History"
          />
        </div>

        <div className="tex-leather w-full min-w-0 p-4 sm:p-6">{children}</div>
      </div>
    </div>
  );
}

function ArenaSubTab({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex min-w-0 items-center justify-center gap-2 py-3 font-display text-[11px] tracking-[0.3em] transition-colors ${
        active ? "tex-forge text-gold-bright" : "bg-black/40 text-gold-dim hover:text-gold"
      }`}
    >
      <span className="shrink-0">{icon}</span>
      <span className="truncate">{label.toUpperCase()}</span>
      {active && (
        <span className="absolute -bottom-px left-6 right-6 h-px bg-gradient-to-r from-transparent via-gold-200 to-transparent" />
      )}
    </button>
  );
}
