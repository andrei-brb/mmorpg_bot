import type { InvRow } from "@/lib/apiTypes";
import { publicBaseUrl } from "@/lib/gameApi";

/** Shipped under `public/items/{slot}/` and `public/items/quest/` (world-of-mmo pack). */
const ITEM_ICON_PACK_VERSION = "1";

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
  const slot = (item.template_equip_slot || item.equip_slot || "").trim().toLowerCase();
  const slug = nameToAssetSlug(item.name);
  const tid = (item.template_id || "").trim().toLowerCase();

  if (slot && ZIP_SLOTS.has(slot) && slug) {
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
 * Primary: `items/{slot}/{slug}.png` or `items/quest/{template_id}.png` (pack on CDN).
 * Fallback: `assets/items/generated/{Display Name}.png` / `.jpg` / `.jpeg`.
 */
export function itemIconCandidates(item: InvRow): string[] {
  const base = publicBaseUrl();
  return [...new Set([...primaryPackIconSrcs(item, base), ...generatedSrcsForName(item.name, base)])];
}

export function itemEmojiFallback(item: InvRow, defaultEmoji = "📦"): string {
  const raw = item.icon?.trim() || "";
  if (raw && looksLikeEmoji(raw)) return raw;
  return defaultEmoji;
}
