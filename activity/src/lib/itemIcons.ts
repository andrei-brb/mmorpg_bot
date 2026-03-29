import type { InvRow } from "@/lib/apiTypes";
import { publicBaseUrl } from "@/lib/gameApi";
import itemIconManifest from "@/data/itemIconManifest.json";

/** Built by `scripts/generate-item-icon-manifest.mjs` from `public/assets/items/icons/*`. */
const manifest = itemIconManifest as Record<string, string[]>;

export function looksLikeEmoji(s: string): boolean {
  const v = (s || "").trim();
  if (!v) return false;
  if (/[A-Za-z0-9_:./\\-]/.test(v)) return false;
  return true;
}

/** Match server-side naming / inventory display. */
export function normalizeItemIconName(name: string | undefined | null): string {
  let raw = (name || "").trim();
  raw = raw.replace(/\s*\+\s*\d+\s*$/u, "");
  raw = raw.replace(/Shadowforge/g, "Shadow Forge");
  raw = raw.replace(/\s+Chest$/u, "");
  return raw.trim();
}

/** Slug for manifest keys (`icons/{slug}_{rarity}.png`). */
export function slugifyItemNameForIconPack(name: string | undefined | null): string {
  const n = normalizeItemIconName(name);
  if (!n) return "";
  return n
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/** Prefer exact tier, then other tiers — art pack often has one file per item line. */
const PACK_RARITY_FALLBACK = ["uncommon", "common", "rare", "epic", "legendary"] as const;

function pickPackFile(files: string[] | undefined, rarity: string | undefined | null): string | null {
  if (!files?.length) return null;
  const r = (rarity || "common").trim().toLowerCase() || "common";
  const order = [r, ...PACK_RARITY_FALLBACK.filter((x) => x !== r)];
  for (const tier of order) {
    const hit = files.find((f) => {
      const lower = f.toLowerCase();
      return (
        lower.endsWith(`_${tier}.png`) ||
        lower.endsWith(`_${tier}.jpg`) ||
        lower.endsWith(`_${tier}.jpeg`) ||
        lower.endsWith(`_${tier}.webp`)
      );
    });
    if (hit) return hit;
  }
  if (files.length === 1) return files[0];
  return files[0] ?? null;
}

/**
 * Single URL from bundled `icons/` art only (see `itemIconManifest.json`). No legacy `generated/` or
 * `template_id` images — avoids wrong art and long 404 chains.
 */
export function itemIconCandidates(item: InvRow): string[] {
  const slug = slugifyItemNameForIconPack(item.name);
  if (!slug) return [];
  const files = manifest[slug];
  const file = pickPackFile(files, item.rarity);
  if (!file) return [];
  const base = publicBaseUrl();
  return [`${base}assets/items/icons/${file}`];
}

export function itemEmojiFallback(item: InvRow, defaultEmoji = "📦"): string {
  const raw = item.icon?.trim() || "";
  if (raw && looksLikeEmoji(raw)) return raw;
  return defaultEmoji;
}
