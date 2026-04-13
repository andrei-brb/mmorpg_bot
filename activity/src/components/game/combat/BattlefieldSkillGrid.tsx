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
  const cellRem = 4.5;

  return (
    <div
      className={cn(
        "grid gap-1 overflow-visible",
        "[grid-template-columns:repeat(3,minmax(0,1fr))]",
      )}
      style={{
        width: `${COLS * cellRem}rem`,
        maxWidth: "100%",
      }}
    >
      {cells.map((cell, i) => (
        <div
          key={i}
          className={cn(
            "aspect-square min-h-0 rounded-sm border transition-all duration-300",
            cell.kind === "empty"
              ? "border-[rgba(100,80,120,0.3)] bg-[rgba(40,30,50,0.4)]"
              : "border-[rgba(200,60,60,0.45)] bg-[rgba(180,40,40,0.22)] shadow-[inset_0_0_8px_rgba(200,60,60,0.12)]",
          )}
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
