import type { InvRow } from "@/lib/apiTypes";
import { publicBaseUrl } from "@/lib/gameApi";

/** Same paths as legacy `main.ts` / mmorpg-web exports. */
const GENERATED_BASES = [
  "assets/items/generated/",
  "assets/items/generated/weapons/",
  "assets/items/generated/armor/",
  "assets/items/generated/off_hand/",
  "assets/items/generated/accessories/",
  "assets/items/generated/characters/",
  "assets/items/generated/maps/",
];

export function looksLikeEmoji(s: string): boolean {
  const v = (s || "").trim();
  if (!v) return false;
  if (/[A-Za-z0-9_:./\\-]/.test(v)) return false;
  return true;
}

/** Match server-side `icon_url_for_item_name` / inventory display so filenames align with `generated/*.png`. */
export function normalizeItemIconName(name: string | undefined | null): string {
  let raw = (name || "").trim();
  raw = raw.replace(/\s*\+\s*\d+\s*$/u, "");
  raw = raw.replace(/Shadowforge/g, "Shadow Forge");
  raw = raw.replace(/\s+Chest$/u, "");
  return raw.trim();
}

export function itemIconGeneratedSrcs(itemName: string | undefined | null, base: string): string[] {
  const n = normalizeItemIconName(itemName);
  if (!n) return [];
  const file = `${encodeURIComponent(n)}.png`;
  return GENERATED_BASES.map((b) => `${base}${b}${file}`);
}

function templateSrc(templateId: string | undefined | null, base: string): string | null {
  const id = templateId?.trim();
  if (!id) return null;
  return `${base}assets/items/${encodeURIComponent(id)}.png`;
}

/**
 * Ordered URLs to try. PNGs in this repo are almost all under `generated/{display name}.png`, while
 * `template_id` is often tiered (`chest_common_4`) — only a few ids match flat `assets/items/{id}.png`
 * via the server fallback. Prefer display-name paths first so armor/gloves match `Scale Cuirass.png`,
 * `Steel Grips.png`, etc.
 */
export function itemIconCandidates(item: InvRow): string[] {
  const base = publicBaseUrl();
  const generated = itemIconGeneratedSrcs(item.name, base);
  const primary = templateSrc(item.template_id, base);
  const ordered = [...generated, primary].filter((v): v is string => Boolean(v));
  return [...new Set(ordered)];
}

export function itemEmojiFallback(item: InvRow, defaultEmoji = "📦"): string {
  const raw = item.icon?.trim() || "";
  if (raw && looksLikeEmoji(raw)) return raw;
  return defaultEmoji;
}
