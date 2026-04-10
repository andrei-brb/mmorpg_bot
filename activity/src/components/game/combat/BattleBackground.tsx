import { useMemo, type ReactNode } from "react";

const BACKGROUNDS: Record<string, { gradient: string; particles: string; label: string }> = {
  forest: {
    gradient: "linear-gradient(180deg, hsl(160 30% 8%) 0%, hsl(140 25% 6%) 40%, hsl(120 20% 4%) 100%)",
    particles: "🍃",
    label: "Darkwood Forest",
  },
  volcano: {
    gradient: "linear-gradient(180deg, hsl(15 40% 10%) 0%, hsl(0 50% 8%) 40%, hsl(0 30% 5%) 100%)",
    particles: "🔥",
    label: "Ashveil Crater",
  },
  dungeon: {
    gradient: "linear-gradient(180deg, hsl(260 25% 8%) 0%, hsl(250 20% 6%) 40%, hsl(240 18% 4%) 100%)",
    particles: "✨",
    label: "Shadow Depths",
  },
  graveyard: {
    gradient: "linear-gradient(180deg, hsl(220 20% 10%) 0%, hsl(230 18% 7%) 40%, hsl(228 20% 4%) 100%)",
    particles: "💀",
    label: "Cursed Grounds",
  },
};

interface Props {
  zone?: string;
  children: ReactNode;
}

export function BattleBackground({ zone = "volcano", children }: Props) {
  const bg = BACKGROUNDS[zone] || BACKGROUNDS.volcano;

  const floatingParticles = useMemo(() => {
    return Array.from({ length: 6 }, (_, i) => ({
      id: i,
      left: `${10 + Math.random() * 80}%`,
      delay: `${Math.random() * 4}s`,
      duration: `${3 + Math.random() * 3}s`,
      size: `${8 + Math.random() * 6}px`,
    }));
  }, []);

  return (
    <div
      className="relative rounded-sm overflow-hidden"
      style={{
        background: bg.gradient,
        border: "1px solid hsl(228 16% 20%)",
        boxShadow: "inset 0 0 60px hsl(0 0% 0% / 0.6), 0 4px 20px hsl(0 0% 0% / 0.4)",
        minHeight: 220,
      }}
    >
      {/* Particle layer */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        {floatingParticles.map((p) => (
          <span
            key={p.id}
            className="absolute animate-float-particle opacity-30"
            style={{
              left: p.left,
              bottom: "-10px",
              fontSize: p.size,
              animationDelay: p.delay,
              animationDuration: p.duration,
            }}
          >
            {bg.particles}
          </span>
        ))}
      </div>

      {/* Ground line */}
      <div
        className="absolute bottom-0 left-0 right-0 h-[2px]"
        style={{
          background: "linear-gradient(90deg, transparent, hsl(var(--frame-highlight) / 0.3), transparent)",
        }}
      />

      {/* Content */}
      <div className="relative z-10">{children}</div>
    </div>
  );
}
