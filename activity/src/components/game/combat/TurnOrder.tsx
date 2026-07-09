import { useEffect, useState } from "react";

interface Fighter {
  name: string;
  icon: string;
  iconSrc?: string | null;
  isPlayer: boolean;
  isCurrent: boolean;
}

interface Props {
  fighters: Fighter[];
}

/** Portrait with emoji fallback when the image fails to load (e.g. missing mob PNG). */
function FighterIcon({ icon, iconSrc }: { icon: string; iconSrc?: string | null }) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [iconSrc]);

  if (!iconSrc || failed) {
    return <span className="text-sm leading-none">{icon}</span>;
  }
  return (
    <img
      src={iconSrc}
      alt=""
      className="w-[22px] h-[22px] object-contain"
      onError={() => setFailed(true)}
    />
  );
}

export function TurnOrder({ fighters }: Props) {
  return (
    <div
      className="flex items-center gap-1 px-2 py-1.5 rounded-sm"
      style={{
        background: "hsl(228 22% 9% / 0.85)",
        border: "1px solid hsl(228 16% 20%)",
      }}
    >
      <span
        className="text-[8px] font-cinzel font-bold uppercase tracking-widest mr-1"
        style={{ color: "hsl(var(--gold))" }}
      >
        Turn
      </span>
      {fighters.map((f, i) => (
        <div
          key={`${f.name}-${i}`}
          className="relative flex items-center justify-center rounded-sm transition-all overflow-hidden"
          style={{
            width: 28,
            height: 28,
            background: f.isCurrent
              ? "linear-gradient(180deg, hsl(228 18% 16%) 0%, hsl(228 20% 12%) 100%)"
              : "hsl(228 18% 10%)",
            border: f.isCurrent
              ? "1px solid hsl(43 50% 40% / 0.7)"
              : "1px solid hsl(228 16% 18%)",
            boxShadow: f.isCurrent ? "0 0 8px hsl(43 78% 50% / 0.2)" : "none",
          }}
          title={f.name}
        >
          <FighterIcon icon={f.icon} iconSrc={f.iconSrc} />
          {f.isCurrent && (
            <div
              className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full"
              style={{ background: "hsl(var(--gold))", boxShadow: "0 0 4px hsl(var(--gold) / 0.6)" }}
            />
          )}
        </div>
      ))}
    </div>
  );
}
