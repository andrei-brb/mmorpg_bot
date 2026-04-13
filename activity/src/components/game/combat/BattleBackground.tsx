import { useMemo, type ReactNode } from "react";

const BACKGROUNDS: Record<string, { gradient: string; particles: string; label: string }> = {
  elwynn_forest: {
    gradient: "linear-gradient(180deg, hsl(160 30% 8%) 0%, hsl(140 25% 6%) 40%, hsl(120 20% 4%) 100%)",
    particles: "🍃",
    label: "Elwynn Forest",
  },
  dun_morogh: {
    gradient: "linear-gradient(180deg, hsl(210 20% 12%) 0%, hsl(220 18% 8%) 40%, hsl(228 20% 5%) 100%)",
    particles: "❄️",
    label: "Dun Morogh",
  },
  barrens: {
    gradient: "linear-gradient(180deg, hsl(32 35% 12%) 0%, hsl(22 35% 8%) 45%, hsl(18 30% 5%) 100%)",
    particles: "🌾",
    label: "The Barrens",
  },
  stranglethorn: {
    gradient: "linear-gradient(180deg, hsl(165 35% 10%) 0%, hsl(145 30% 7%) 45%, hsl(120 22% 4%) 100%)",
    particles: "🌿",
    label: "Stranglethorn Vale",
  },
  blackrock_depths: {
    gradient: "linear-gradient(180deg, hsl(15 40% 10%) 0%, hsl(0 50% 8%) 40%, hsl(0 30% 5%) 100%)",
    particles: "🔥",
    label: "Blackrock Depths",
  },
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
  /** Zone key (e.g. `elwynn_forest`). Falls back to themed gradients when no image is present. */
  zone?: string;
  children: ReactNode;
}

export function BattleBackground({ zone = "volcano", children }: Props) {
  const key = String(zone || "volcano").toLowerCase();
  const bg =
    BACKGROUNDS[key] ||
    (key.includes("forest") || key.includes("wood")
      ? BACKGROUNDS.forest
      : key.includes("grave") || key.includes("crypt")
        ? BACKGROUNDS.graveyard
        : key.includes("dungeon") || key.includes("depth") || key.includes("shadow")
          ? BACKGROUNDS.dungeon
          : BACKGROUNDS.volcano);

  // Support both .png and .jpg assets (png preferred). If the png is missing (404),
  // the jpg layer will still render under it.
  const base = import.meta.env.BASE_URL || "/";
  const pngUrl = `${base}battlefields/${key}.png`;
  const jpgUrl = `${base}battlefields/${key}.jpg`;

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
        // Layer order matters: first is "top". We want the image on top, with the
        // gradient as a fallback when no asset exists for a zone.
        backgroundImage: `url('${pngUrl}'), url('${jpgUrl}'), ${bg.gradient}`,
        backgroundSize: "cover, cover, cover",
        backgroundPosition: "center, center, center",
        backgroundRepeat: "no-repeat, no-repeat, no-repeat",
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
