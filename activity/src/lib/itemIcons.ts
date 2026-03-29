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

export function itemIconGeneratedSrcs(itemName: string | undefined | null, base: string): string[] {
  const n = (itemName || "").trim();
  if (!n) return [];
  const file = `${encodeURIComponent(n)}.png`;
  return GENERATED_BASES.map((b) => `${base}${b}${file}`);
}

function templateSrc(templateId: string | undefined | null, base: string): string | null {
  const id = templateId?.trim();
  if (!id) return null;
  return `${base}assets/items/${encodeURIComponent(id)}.png`;
}

/** Ordered list of image URLs to try; same order as legacy inventory icons. */
export function itemIconCandidates(item: InvRow): string[] {
  const base = publicBaseUrl();
  const primary = templateSrc(item.template_id, base);
  const generated = itemIconGeneratedSrcs(item.name, base);
  return [primary, ...generated].filter((v): v is string => Boolean(v));
}

export function itemEmojiFallback(item: InvRow, defaultEmoji = "📦"): string {
  const raw = item.icon?.trim() || "";
  if (raw && looksLikeEmoji(raw)) return raw;
  return defaultEmoji;
}
