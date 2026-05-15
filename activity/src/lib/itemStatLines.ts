import type { InvRow } from "@/lib/apiTypes";

const SLOT_LABEL: Record<string, string> = {
  head: "Head",
  chest: "Chest",
  hands: "Hands",
  legs: "Legs",
  feet: "Feet",
  main_hand: "Main Hand",
  off_hand: "Off Hand",
  neck: "Neck",
  ring: "Ring",
  trinket: "Trinket",
};

export type ItemStatRow = { label: string; value: string };

function capitalizeWord(s: string): string {
  const t = s.trim();
  if (!t) return "";
  return t.charAt(0).toUpperCase() + t.slice(1).toLowerCase();
}

/** Subtitle: "Rare · armor · Head" */
export function itemTooltipSubtitle(item: InvRow): string {
  const parts: string[] = [];
  if (item.rarity) parts.push(capitalizeWord(item.rarity));
  if (item.item_type) parts.push(capitalizeWord(item.item_type));
  const slot = (item.template_equip_slot || item.equip_slot || "").trim();
  if (slot && SLOT_LABEL[slot]) parts.push(SLOT_LABEL[slot]);
  return parts.join(" · ");
}

function hasEquipmentStats(item: InvRow): boolean {
  const n = (v: unknown) => Number(v ?? 0) || 0;
  return (
    n(item.s_str) + n(item.s_agi) + n(item.s_int) + n(item.s_spi) + n(item.s_sta) +
      n(item.s_armor) + n(item.s_dmg_min) + n(item.s_dmg_max) + n(item.s_haste) +
      n(item.s_lifesteal) + n(item.s_resistance) + n(item.s_hit_rating) +
      n(item.r_str) + n(item.r_agi) + n(item.r_int) + n(item.r_spi) + n(item.r_sta) +
      n(item.r_haste) + n(item.r_lifesteal) + n(item.r_resistance) + n(item.r_hit_rating) >
    0
  );
}

function consumableEffectLines(item: InvRow): string[] {
  const et = (item.effect_type || "").trim();
  if (!et) return [];
  const v = Number(item.effect_value ?? 0);
  const d = Number(item.effect_duration ?? 0);
  const dur = d > 0 ? ` · ${d}s` : "";

  switch (et) {
    case "heal_hp":
      return [`Restores ${v} HP`];
    case "boost_sta":
      return [`+${v} Stamina${dur}`];
    case "boost_str":
      return [`+${v} Strength${dur}`];
    case "boost_agi":
      return [`+${v} Agility${dur}`];
    case "boost_int":
      return [`+${v} Intellect${dur}`];
    case "boost_spi":
      return [`+${v} Spirit${dur}`];
    case "boost_max_hp":
      return [`+${v} Max HP${dur}`];
    case "boost_resistance":
      return [`+${v} Resistance${dur}`];
    default:
      return [`${et}: ${v}${dur}`];
  }
}

/**
 * Structured rows for tooltips / popovers — same rules as historical `itemTooltipLines`
 * (+10% per enhancement level on gear stats).
 */
export function itemPopoverDetailRows(item: InvRow): ItemStatRow[] {
  const rows: ItemStatRow[] = [];
  const lvl = Number(item.level_req ?? 0) || 0;
  if (lvl > 0) {
    rows.push({ label: "Requires Level", value: String(lvl) });
  }

  const type = (item.item_type || "").toLowerCase();
  if (type === "consumable") {
    const lines = consumableEffectLines(item);
    if (lines.length === 0) {
      rows.push({ label: "Effect", value: "—" });
    } else {
      for (const line of lines) {
        const idx = line.indexOf(": ");
        if (idx > 0) {
          rows.push({ label: line.slice(0, idx).trim(), value: line.slice(idx + 2).trim() });
        } else {
          rows.push({ label: "Effect", value: line });
        }
      }
    }
    return rows;
  }

  const enhLevel = Math.max(0, Math.min(10, Number(item.enhancement_level ?? 0) || 0));
  const enhMult = 1 + enhLevel * 0.1;

  const pushStat = (label: string, base?: number | null, bonus?: number | null): void => {
    const b = Number(base ?? 0) || 0;
    const r = Number(bonus ?? 0) || 0;
    const preEnh = b + r;
    const total = Math.floor(preEnh * enhMult);
    if (!total) return;
    const bonusTxt = r ? ` (${r > 0 ? "+" : ""}${r} bonus)` : "";
    rows.push({
      label,
      value: `${total > 0 ? "+" : ""}${total}${bonusTxt}`,
    });
  };

  const slot = (item.template_equip_slot || item.equip_slot || "").trim();
  if (slot || hasEquipmentStats(item)) {
    pushStat("STR", item.s_str, item.r_str);
    pushStat("AGI", item.s_agi, item.r_agi);
    pushStat("INT", item.s_int, item.r_int);
    pushStat("SPI", item.s_spi, item.r_spi);
    pushStat("STA", item.s_sta, item.r_sta);
    pushStat("Haste", item.s_haste, item.r_haste);
    pushStat("Lifesteal", item.s_lifesteal, item.r_lifesteal);
    pushStat("Resistance", item.s_resistance, item.r_resistance);
    pushStat("Hit", item.s_hit_rating, item.r_hit_rating);

    const armor = Math.floor((Number(item.s_armor ?? 0) || 0) * enhMult);
    if (armor) {
      rows.push({ label: "Armor", value: `+${armor}` });
    }

    const dMin = Math.floor((Number(item.s_dmg_min ?? 0) || 0) * enhMult);
    const dMax = Math.floor((Number(item.s_dmg_max ?? 0) || 0) * enhMult);
    if (dMin || dMax) {
      rows.push({ label: "Damage", value: `${dMin}–${dMax}` });
    }
  }

  return rows;
}

/**
 * Lines shown in item hovers — equipment stats (with enhancement), consumable effects, level req.
 * Mirrors `legacy-main.ts` `itemStatLines` math (+10% stats per enhancement level).
 */
export function itemTooltipLines(item: InvRow): string[] {
  const rows = itemPopoverDetailRows(item);
  const type = (item.item_type || "").toLowerCase();
  return rows.map((row) => {
    if (row.label === "Requires Level") {
      return `Requires Level ${row.value}`;
    }
    if (type === "consumable" && row.label === "Effect") {
      return row.value;
    }
    return `${row.label}: ${row.value}`;
  });
}
