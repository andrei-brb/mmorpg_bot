import { useEffect, useState } from "react";

export interface DamageEvent {
  id: number;
  value: number;
  isCrit: boolean;
  isHeal: boolean;
  side: "player" | "enemy";
}

interface Props {
  events: DamageEvent[];
}

function hslWithAlpha(color: string, alpha: string): string {
  if (color.endsWith(")")) return `${color.slice(0, -1)} / ${alpha})`;
  return color;
}

export function DamageNumbers({ events }: Props) {
  return (
    <div className="absolute inset-0 pointer-events-none z-20 overflow-hidden">
      {events.map((evt) => (
        <FloatingNumber key={evt.id} event={evt} />
      ))}
    </div>
  );
}

function FloatingNumber({ event }: { event: DamageEvent }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setVisible(false), 1200);
    return () => clearTimeout(t);
  }, []);

  if (!visible) return null;

  const color = event.isHeal
    ? "hsl(120 60% 55%)"
    : event.isCrit
      ? "hsl(43 85% 55%)"
      : "hsl(0 75% 60%)";

  const x = event.side === "player" ? "25%" : "75%";
  const offset = `${-20 + Math.random() * 40}px`;

  return (
    <span
      className="absolute animate-damage-float font-pixel font-bold"
      style={{
        left: x,
        top: "30%",
        marginLeft: offset,
        color,
        fontSize: event.isCrit ? "18px" : "14px",
        textShadow: `0 2px 4px hsl(0 0% 0% / 0.8), 0 0 8px ${hslWithAlpha(color, "0.5")}`,
      }}
    >
      {event.isHeal ? "+" : "-"}
      {event.value}
      {event.isCrit && <span className="text-[9px] ml-0.5">CRIT!</span>}
    </span>
  );
}
