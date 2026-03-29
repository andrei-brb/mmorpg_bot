import type { InvRow } from "@/lib/apiTypes";
import { publicBaseUrl } from "@/lib/gameApi";

/** Display-name sprites shipped under `public/assets/items/generated/` only. */
const GENERATED_DIR = "assets/items/generated/";

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
 * URLs under `assets/items/generated/` only (`{Display Name}.png` / `.jpg` / `.jpeg`).
 * Same item name at every rarity shares one sprite.
 */
export function itemIconCandidates(item: InvRow): string[] {
  const base = publicBaseUrl();
  return [...new Set(generatedSrcsForName(item.name, base))];
}

export function itemEmojiFallback(item: InvRow, defaultEmoji = "📦"): string {
  const raw = item.icon?.trim() || "";
  if (raw && looksLikeEmoji(raw)) return raw;
  return defaultEmoji;
}
