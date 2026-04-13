import { useState } from "react";
import type { CombatAbility } from "@/lib/apiTypes";
import { getSkillByKey } from "@/data/skills";
import { skillIconUrl } from "@/lib/skillIconUrl";

function formatResourceLine(cost: number, costType: string): string {
  if (costType === "none" || cost === 0) return "Free";
  if (costType === "mana") return `${cost} MP`;
  if (costType === "energy") return `${cost} Energy`;
  if (costType === "rage") return `${cost} Rage`;
  return `${cost} ${costType}`;
}

function abilityMetaLine(a: CombatAbility): string | null {
  const parts: string[] = [];
  if (a.dmg_min != null && a.dmg_max != null) {
    parts.push(`DMG: ${a.dmg_min}–${a.dmg_max}`);
  }
  if (a.heal_estimate != null) {
    parts.push(`Heal: ~${a.heal_estimate}`);
  }
  if (a.crit_pct != null) {
    parts.push(`Crit: ${a.crit_pct}%`);
  }
  if (a.is_aoe) parts.push("AoE");
  return parts.length ? parts.join(" · ") : null;
}

export function CombatSkillButton({
  ability: a,
  loading,
  canAct,
  onUse,
}: {
  ability: CombatAbility;
  loading: boolean;
  canAct: boolean;
  onUse: (key: string) => void;
}) {
  const disabled = Boolean(a.disabled) || loading || !canAct;
  const meta = abilityMetaLine(a);
  const desc =
    (a.description || "").trim() || (getSkillByKey(a.key)?.description ?? "").trim();
  const cd = a.cooldown > 0 ? a.cooldown : 0;

  return (
    <div className="combat-skill-slot relative min-w-0">
      <button
        type="button"
        aria-disabled={disabled}
        tabIndex={disabled ? -1 : undefined}
        className="skill-btn w-full min-h-[4.5rem] border border-[hsl(43_50%_35%_/_0.45)]"
        onClick={() => {
          if (disabled) return;
          void onUse(a.key);
        }}
      >
        <CombatSkillIcon abilityKey={a.key} emoji={a.emoji} />
        <span className="text-foreground font-semibold text-[10px] leading-tight line-clamp-2">{a.name}</span>
        <span className="text-muted-foreground text-[9px]">{formatResourceLine(a.cost, a.cost_type)}</span>
      </button>

      <div
        className="combat-skill-tooltip"
        role="tooltip"
        aria-hidden
      >
        <div className="relative z-[1] space-y-1.5">
          <div className="font-cinzel font-bold text-[10px] tracking-widest text-foreground uppercase leading-tight">
            {a.name}
          </div>
          {desc ? (
            <p className="text-[10px] leading-snug text-muted-foreground font-crimson">{desc}</p>
          ) : null}
          {meta ? (
            <p
              className="text-[10px] font-cinzel font-semibold leading-snug"
              style={{ color: "hsl(var(--gold))", textShadow: "0 0 6px hsl(var(--gold) / 0.25)" }}
            >
              {meta}
            </p>
          ) : null}
          <div className="text-[9px] text-muted-foreground space-y-0.5 border-t border-[hsl(var(--frame-mid)_/_0.5)] pt-1.5 mt-1">
            <div>{formatResourceLine(a.cost, a.cost_type)}</div>
            {cd > 0 ? <div>Cooldown: {cd} turn{cd === 1 ? "" : "s"}</div> : null}
            {a.disabled ? <div className="text-amber-200/90">{a.disabled}</div> : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function CombatSkillIcon({ abilityKey, emoji }: { abilityKey: string; emoji: string }) {
  const [useEmoji, setUseEmoji] = useState(false);
  if (useEmoji) {
    return (
      <span className="text-2xl leading-none" style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))" }}>
        {emoji}
      </span>
    );
  }
  return (
    <img
      src={skillIconUrl(abilityKey)}
      alt=""
      width={32}
      height={32}
      className="w-8 h-8 object-contain shrink-0"
      style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))" }}
      onError={() => setUseEmoji(true)}
    />
  );
}

function CombatSkillIconSmall({ abilityKey, emoji }: { abilityKey: string; emoji: string }) {
  const [useEmoji, setUseEmoji] = useState(false);
  if (useEmoji) {
    return (
      <span className="text-lg leading-none shrink-0" style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))" }}>
        {emoji}
      </span>
    );
  }
  return (
    <img
      src={skillIconUrl(abilityKey)}
      alt=""
      width={24}
      height={24}
      className="w-6 h-6 object-contain shrink-0"
      style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))" }}
      onError={() => setUseEmoji(true)}
    />
  );
}

/** Square cell for 3×3 battle grid — same tooltip pipeline as {@link CombatSkillButton}. */
export function CombatSkillGridButton({
  ability: a,
  loading,
  canAct,
  onUse,
}: {
  ability: CombatAbility;
  loading: boolean;
  canAct: boolean;
  onUse: (key: string) => void;
}) {
  const disabled = Boolean(a.disabled) || loading || !canAct;
  const meta = abilityMetaLine(a);
  const desc =
    (a.description || "").trim() || (getSkillByKey(a.key)?.description ?? "").trim();
  const cd = a.cooldown > 0 ? a.cooldown : 0;

  return (
    <div className="combat-skill-slot relative h-full w-full min-w-0 flex flex-col">
      <button
        type="button"
        aria-disabled={disabled}
        title={a.name}
        tabIndex={disabled ? -1 : undefined}
        className="skill-btn flex h-full min-h-0 w-full flex-col items-center justify-center gap-0.5 border border-[hsl(43_50%_35%_/_0.45)] px-0.5 py-1 text-center"
        onClick={() => {
          if (disabled) return;
          void onUse(a.key);
        }}
      >
        <CombatSkillIconSmall abilityKey={a.key} emoji={a.emoji} />
        <span className="w-full break-words text-[8px] font-semibold leading-tight text-foreground line-clamp-2">
          {a.name}
        </span>
      </button>

      <div className="combat-skill-tooltip combat-skill-tooltip--grid" role="tooltip" aria-hidden>
        <div className="relative z-[1] space-y-1.5">
          <div className="font-cinzel font-bold text-[10px] tracking-widest text-foreground uppercase leading-tight">{a.name}</div>
          {desc ? <p className="text-[10px] leading-snug text-muted-foreground font-crimson">{desc}</p> : null}
          {meta ? (
            <p
              className="font-cinzel text-[10px] font-semibold leading-snug"
              style={{ color: "hsl(var(--gold))", textShadow: "0 0 6px hsl(var(--gold) / 0.25)" }}
            >
              {meta}
            </p>
          ) : null}
          <div className="space-y-0.5 border-t border-[hsl(var(--frame-mid)_/_0.5)] pt-1.5 text-[9px] text-muted-foreground mt-1">
            <div>{formatResourceLine(a.cost, a.cost_type)}</div>
            {cd > 0 ? <div>Cooldown: {cd} turn{cd === 1 ? "" : "s"}</div> : null}
            {a.disabled ? <div className="text-amber-200/90">{a.disabled}</div> : null}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Bottom-right style potion cell — matches grid tooltip behavior. */
export function CombatPotionGridButton({
  loading,
  canAct,
  canPotion,
  onUse,
}: {
  loading: boolean;
  canAct: boolean;
  canPotion: boolean;
  onUse: () => void;
}) {
  const disabled = loading || !canAct || !canPotion;

  return (
    <div className="combat-skill-slot relative h-full w-full min-w-0 flex flex-col">
      <button
        type="button"
        aria-disabled={disabled}
        title="Potion"
        tabIndex={disabled ? -1 : undefined}
        className="skill-btn flex h-full min-h-0 w-full flex-col items-center justify-center gap-0.5 border border-[hsl(43_50%_35%_/_0.45)] px-0.5 py-1 text-center"
        onClick={() => {
          if (disabled) return;
          void onUse();
        }}
      >
        <span className="text-xl leading-none" aria-hidden>
          🧪
        </span>
        <span className="w-full text-[8px] font-semibold leading-tight text-foreground">Potion</span>
      </button>
      <div className="combat-skill-tooltip combat-skill-tooltip--grid" role="tooltip" aria-hidden>
        <div className="relative z-[1] space-y-1.5">
          <div className="font-cinzel font-bold text-[10px] tracking-widest text-foreground uppercase leading-tight">Health potion</div>
          <p className="text-[10px] leading-snug text-muted-foreground font-crimson">
            Drink to restore health. Consumes one charge for this encounter when available.
          </p>
          {!canPotion ? <p className="text-[9px] text-amber-200/90">No potion charges left.</p> : null}
          {!canAct ? <p className="text-[9px] text-muted-foreground">Not your turn.</p> : null}
        </div>
      </div>
    </div>
  );
}
