import { createContext, useContext, type ComponentType, type ReactNode } from "react";
import BattlePreview, { type BattlePreviewData } from "@/components/BattlePreview";

/**
 * Seam for swapping the combat presentation per shell — the same additive
 * pattern as the AuthProvider seam in GameSessionContext.
 *
 * BattlePreview is purely presentational: CombatEncounterView does the work
 * (buildBattlePreviewDataFromCombat) and hands it `data` plus a ready-made
 * `combatGrid`. So an alternative renderer is a pure layout swap — no combat
 * logic is duplicated, and nothing about the fight changes.
 *
 * The default is BattlePreview, so the Discord Activity renders exactly as it
 * did before this file existed. Only the native mobile shell overrides it (with
 * a phone-native layout that a three-column desktop arena cannot be CSS'd into).
 */

export type BattleRendererProps = {
  data: BattlePreviewData;
  combatGrid?: ReactNode;
  /**
   * Flee / Potion. The default layout also renders these in its own row below
   * the arena and ignores this prop; a renderer that places them itself (the
   * mobile drawer) uses it and hides that row. BattlePreview not declaring the
   * prop is fine — a component taking fewer props is still assignable here.
   */
  extraActions?: ReactNode;
};

export type BattleRenderer = ComponentType<BattleRendererProps>;

const BattleRendererContext = createContext<BattleRenderer>(BattlePreview);

export function BattleRendererProvider({
  renderer,
  children,
}: {
  renderer?: BattleRenderer;
  children: ReactNode;
}) {
  return (
    <BattleRendererContext.Provider value={renderer ?? BattlePreview}>
      {children}
    </BattleRendererContext.Provider>
  );
}

export function useBattleRenderer(): BattleRenderer {
  return useContext(BattleRendererContext);
}
