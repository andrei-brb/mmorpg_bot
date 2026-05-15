import type { TalentNodeState, TalentTreeSection, TalentsStatePayload } from "@/lib/apiTypes";
import {
  CLASS_FOUNDATION_FLAVOR,
  CLASS_LABELS,
  SPEC_META,
} from "@/components/game/talents/talentForgeMeta";
import type { ForgeTalent, ForgeTalentTree, TalentTier } from "@/components/game/talents/talentForgeTypes";
import {
  Crown,
  Flame,
  Hammer,
  Sparkles,
  Star,
  Sword,
  Zap,
  type LucideIcon,
} from "lucide-react";

function nodeTypeToTier(nodeType: string | undefined, maxRanks: number): TalentTier {
  const t = nodeType || "stat";
  if (t === "capstone") return "keystone";
  if (t === "spec_passive") return maxRanks <= 1 ? "keystone" : "major";
  if (t === "starter" || t === "preview") return "minor";
  if (t === "proc" || t === "utility") return "minor";
  return maxRanks <= 1 ? "major" : "minor";
}

function iconForNode(node: TalentNodeState, treeIcon?: LucideIcon): LucideIcon {
  if (node.auto_grant) return Crown;
  const t = node.node_type || "stat";
  if (t === "preview") return Sparkles;
  if (t === "spec_passive") return Star;
  if (t === "proc") return Flame;
  if (t === "utility") return Hammer;
  if (t === "capstone") return Crown;
  return treeIcon || Sword;
}

function mapNode(node: TalentNodeState, treeIcon?: LucideIcon): ForgeTalent {
  const maxRank = Math.max(1, Number(node.max_ranks ?? 1));
  const descriptions = node.descriptions?.length
    ? node.descriptions
    : [node.name || "Talent"];
  return {
    id: String(node.id),
    name: String(node.name || node.id),
    description: descriptions[0] || "",
    icon: iconForNode(node, treeIcon),
    maxRank,
    tier: nodeTypeToTier(node.node_type, maxRank),
    row: Number(node.tier ?? 0),
    col: Number(node.column ?? 0),
    requires: node.prereqs?.map(String),
    ranks: descriptions,
    autoGrant: Boolean(node.auto_grant),
    canAllocate: node.can_allocate,
    lockedReason: node.locked_reason,
    currentRank: Number(node.ranks ?? 0),
  };
}

function mapSection(
  section: TalentTreeSection,
  treeId: string,
  name: string,
  flavor: string,
  icon: LucideIcon,
): ForgeTalentTree {
  return {
    id: treeId,
    name,
    flavor,
    icon,
    talents: (section.nodes || []).map((n) => mapNode(n, icon)),
  };
}

export function buildForgeTreesFromApi(state: TalentsStatePayload): {
  foundation: ForgeTalentTree | null;
  specs: ForgeTalentTree[];
} {
  const classKey = String(state.class_key || "warrior");
  const classLabel = CLASS_LABELS[classKey] || classKey;

  const foundation = state.foundation
    ? mapSection(
        state.foundation,
        "foundation",
        "Class Foundation",
        CLASS_FOUNDATION_FLAVOR[classKey] ||
          `Forge your ${classLabel} before choosing a specialization.`,
        Crown,
      )
    : null;

  const specs = (state.spec_trees || []).map((section) => {
    const sk = String(section.spec_key || "");
    const meta = SPEC_META[sk];
    return mapSection(
      section,
      sk,
      meta?.name || sk.replace(/_/g, " "),
      meta?.tagline || section.passive_name || "",
      meta?.icon || Sword,
    );
  });

  return { foundation, specs };
}

export function ranksFromTalentsState(state: TalentsStatePayload): Record<string, number> {
  const alloc = state.allocations || {};
  const out: Record<string, number> = { ...alloc };
  const walk = (section?: TalentTreeSection | null) => {
    for (const n of section?.nodes || []) {
      if (!n.id) continue;
      const id = String(n.id);
      if (n.ranks != null) out[id] = Math.max(out[id] ?? 0, Number(n.ranks));
    }
  };
  walk(state.foundation);
  for (const t of state.spec_trees || []) walk(t);
  return out;
}

export function pointsInTree(tree: ForgeTalentTree, ranks: Record<string, number>): number {
  return tree.talents.reduce((sum, t) => {
    if (t.autoGrant) return sum;
    return sum + (ranks[t.id] ?? 0);
  }, 0);
}

export function lockedReasonLabel(reason?: string | null): string | undefined {
  if (!reason) return undefined;
  const map: Record<string, string> = {
    need_spec: "Choose your specialization at level 10.",
    other_spec: "This branch belongs to your other specialization.",
    prereq: "Prerequisites not met.",
    locked: "Cannot allocate here.",
  };
  return map[reason] || reason;
}
