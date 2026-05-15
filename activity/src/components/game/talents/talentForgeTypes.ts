import type { LucideIcon } from "lucide-react";

export type TalentTier = "passive" | "minor" | "major" | "keystone";

export type ForgeTalent = {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  maxRank: number;
  tier: TalentTier;
  row: number;
  col: number;
  requires?: string[];
  pointsRequired?: number;
  ranks: string[];
  autoGrant?: boolean;
  /** Server-side allocate gate */
  canAllocate?: boolean;
  lockedReason?: string | null;
  currentRank?: number;
};

export type ForgeTalentTree = {
  id: string;
  name: string;
  flavor: string;
  icon: LucideIcon;
  talents: ForgeTalent[];
};
