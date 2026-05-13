import type { InvRow } from "@/lib/apiTypes";
import { publicBaseUrl } from "@/lib/gameApi";

/** Shipped under `public/items/{slot}/` and `public/items/quest/` (world-of-mmo pack). */
const ITEM_ICON_PACK_VERSION = "3";
/** Bump to force Discord/browser to refetch drop-in icons. */
const DROPIN_ITEM_ICON_VERSION = "1";

/** Display-name sprites under `public/assets/items/generated/` (fallback). */
const GENERATED_DIR = "assets/items/generated/";

const ZIP_SLOTS = new Set([
  "head",
  "neck",
  "chest",
  "hands",
  "legs",
  "feet",
  "main_hand",
  "off_hand",
  "ring",
  "trinket",
]);

/** Longest first so `main_hand_*` / `off_hand_*` match before shorter keys. */
const TEMPLATE_ID_SLOT_PREFIXES = [
  "main_hand",
  "off_hand",
  "trinket",
  "neck",
  "chest",
  "head",
  "hands",
  "legs",
  "feet",
  "ring",
] as const;

const RARITY_TOKEN = /_(common|uncommon|rare|epic|legendary)_\d+$/i;

/**
 * `item_templates.id` → path under `items/` for loot / quest gear that has no
 * `{slot}/{name_slug}.png` in the pack (art lives elsewhere or uses a stand-in).
 */
const TEMPLATE_PACK_OVERRIDE: Record<string, string> = {
  corsair_blade: "quest/sun_scorched_scimitar.png",
  jungle_leather_chest: "chest/leather_vest.png",
  necklace_t1: "neck/copper_pendant.png",
};

function isProceduralGearTemplateId(tid: string): boolean {
  return RARITY_TOKEN.test(tid);
}

/**
 * Gear templates in DB look like `head_common_1`, `main_hand_epic_3`.
 * Used when API rows omit `template_equip_slot` / `equip_slot` (e.g. Blacksmith modal stub).
 */
export function equipSlotFromTemplateId(templateId: string | undefined | null): string | null {
  const tid = (templateId || "").trim().toLowerCase();
  if (!tid || !RARITY_TOKEN.test(tid)) return null;
  for (const p of TEMPLATE_ID_SLOT_PREFIXES) {
    if (tid.startsWith(`${p}_`)) return p;
  }
  return null;
}

export function looksLikeEmoji(s: string): boolean {
  const v = (s || "").trim();
  if (!v) return false;
  if (/[A-Za-z0-9_:./\\-]/.test(v)) return false;
  return true;
}

/** Align with server-side display names and `generated/{Name}.png` filenames. */
export function normalizeItemIconName(name: string | undefined | null): string {
  let raw = (name || "").trim();
  raw = raw.replace(/\s*\+\s*\d+\s*$/u, "");
  raw = raw.replace(/Shadowforge/g, "Shadow Forge");
  raw = raw.replace(/\s+Chest$/u, "");
  return raw.trim();
}

/** Snake_case filename stem matching the world-of-mmo item PNG pack. */
export function nameToAssetSlug(name: string | undefined | null): string {
  const n = normalizeItemIconName(name);
  if (!n) return "";
  return n
    .toLowerCase()
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .replace(/['']/g, "")
    .replace(/[^a-z0-9]+/gu, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
}

function packQuery(): string {
  return `?v=${ITEM_ICON_PACK_VERSION}`;
}

function primaryPackIconSrcs(item: InvRow, base: string): string[] {
  const out: string[] = [];
  const slot =
    (item.template_equip_slot || item.equip_slot || "").trim().toLowerCase() ||
    equipSlotFromTemplateId(item.template_id);
  const slug = nameToAssetSlug(item.name);
  const tid = (item.template_id || "").trim().toLowerCase();

  const override = tid ? TEMPLATE_PACK_OVERRIDE[tid] : undefined;
  if (override) {
    out.push(`${base}items/${override}${packQuery()}`);
  }

  if (slot && ZIP_SLOTS.has(slot) && slug) {
    // Named / artifact gear often ships art as `items/quest/{template_id}.png` only.
    if (tid && !isProceduralGearTemplateId(tid) && !override) {
      out.push(`${base}items/quest/${tid}.png${packQuery()}`);
    }
    if (slot === "off_hand" && slug === "eternal_guard") {
      out.push(`${base}items/off_hand/eternal_guard_shield.png${packQuery()}`);
    } else {
      out.push(`${base}items/${slot}/${slug}.png${packQuery()}`);
    }
    return out;
  }

  if (tid) {
    out.push(`${base}items/quest/${tid}.png${packQuery()}`);
  }
  if (slug && slug !== tid) {
    out.push(`${base}items/quest/${slug}.png${packQuery()}`);
  }
  return out;
}

function generatedSrcsForName(itemName: string | undefined | null, base: string): string[] {
  const n = normalizeItemIconName(itemName);
  if (!n) return [];
  const file = encodeURIComponent(n);
  return [
    `${base}${GENERATED_DIR}${file}.png`,
    `${base}${GENERATED_DIR}${file}.jpg`,
    `${base}${GENERATED_DIR}${file}.jpeg`,
  ];
}

/**
 * Hand-painted drops under `public/assets/items/{template_id}.png` (see
 * `public/assets/items/README.md`). Tried after the `public/items/` pack so
 * consumables can match gear art without living under `items/quest/`.
 */
function dropInTemplateIconSrcs(item: InvRow, base: string): string[] {
  const tid = (item.template_id || "").trim();
  if (!tid) return [];
  const enc = encodeURIComponent(tid);
  return [`${base}assets/items/${enc}.png?v=${DROPIN_ITEM_ICON_VERSION}`];
}

/**
 * Primary: `items/{slot}/{slug}.png` or `items/quest/{template_id}.png` (pack under `public/items/`).
 * Then: `assets/items/{template_id}.png` (drop-in, same naming as DB template id).
 * Fallback: `assets/items/generated/{Display Name}.png` / `.jpg` / `.jpeg`.
 */
export function itemIconCandidates(item: InvRow): string[] {
  const base = publicBaseUrl();
  return [...new Set([...primaryPackIconSrcs(item, base), ...dropInTemplateIconSrcs(item, base), ...generatedSrcsForName(item.name, base)])];
}

export function itemEmojiFallback(item: InvRow, defaultEmoji = "📦"): string {
  const raw = item.icon?.trim() || "";
  if (raw && looksLikeEmoji(raw)) return raw;
  return defaultEmoji;
}
