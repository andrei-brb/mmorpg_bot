import { cn } from "@/lib/utils";
import type { CombatAbility } from "@/lib/apiTypes";
import { CombatPotionGridButton, CombatSkillGridButton } from "@/components/game/combat/CombatSkillButton";

const COLS = 3;
const CELLS = COLS * COLS;
const POTION_INDEX = CELLS - 1;

type Cell =
  | { kind: "ability"; ability: CombatAbility }
  | { kind: "potion" }
  | { kind: "empty" };

function buildCells(
  abilities: CombatAbility[],
  options: { reservePotionSlot: boolean },
): Cell[] {
  const { reservePotionSlot } = options;
  const maxSkills = reservePotionSlot ? CELLS - 1 : CELLS;
  const skills = abilities.slice(0, maxSkills);
  const out: Cell[] = Array.from({ length: CELLS }, () => ({ kind: "empty" as const }));
  for (let i = 0; i < skills.length; i++) {
    if (reservePotionSlot && i === POTION_INDEX) break;
    out[i] = { kind: "ability", ability: skills[i] };
  }
  if (reservePotionSlot) {
    out[POTION_INDEX] = { kind: "potion" };
  }
  return out;
}

export function BattlefieldSkillGrid({
  abilities,
  loading,
  canAct,
  onAbility,
  showPotionButton,
  canPotion,
  onPotion,
}: {
  abilities: CombatAbility[];
  loading: boolean;
  canAct: boolean;
  onAbility: (key: string) => void;
  showPotionButton: boolean;
  canPotion: boolean;
  onPotion: () => void;
}) {
  const reservePotionSlot = Boolean(showPotionButton && canPotion);
  const cells = buildCells(abilities, { reservePotionSlot });

  return (
    <div
      className={cn(
        "mx-auto grid w-full max-w-md gap-1.5 overflow-visible sm:max-w-lg sm:gap-2",
        "[grid-template-columns:repeat(3,minmax(0,1fr))]",
      )}
    >
      {cells.map((cell, i) => (
        <div
          key={i}
          className={cn(
            "aspect-square min-h-0 overflow-hidden rounded-sm border transition-all duration-300",
            cell.kind === "empty"
              ? "border-[rgba(80,120,180,0.22)] shadow-[inset_0_0_12px_rgba(40,80,140,0.08)]"
              : "border-[rgba(200,60,60,0.35)] bg-[rgba(18,14,22,0.35)] shadow-[inset_0_0_10px_rgba(200,60,60,0.08)]",
          )}
          style={
            cell.kind === "empty"
              ? {
                  backgroundColor: "rgba(25,18,35,0.45)",
                  backgroundImage: [
                    "linear-gradient(rgba(80,140,220,0.07) 1px, transparent 1px)",
                    "linear-gradient(90deg, rgba(80,140,220,0.07) 1px, transparent 1px)",
                  ].join(", "),
                  backgroundSize: "10px 10px",
                }
              : undefined
          }
        >
          {cell.kind === "ability" ? (
            <CombatSkillGridButton
              ability={cell.ability}
              loading={loading}
              canAct={canAct}
              onUse={onAbility}
            />
          ) : cell.kind === "potion" ? (
            <CombatPotionGridButton
              loading={loading}
              canAct={canAct}
              canPotion={canPotion}
              onUse={onPotion}
            />
          ) : null}
        </div>
      ))}
    </div>
  );
}
