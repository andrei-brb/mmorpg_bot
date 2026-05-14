/** Full-art spec portraits under `public/portraits/characters/{class}_{spec}.png`. */
export const AVAILABLE_SPEC_PORTRAITS = new Set<string>([
  "warrior_arms",
  "warrior_protection",
  "paladin_holy_paladin",
  "paladin_retribution",
  "mage_fire",
  "mage_frost",
  "rogue_assassination",
  "rogue_subtlety",
  "priest_holy_priest",
  "priest_shadow",
  "hunter_beast_mastery",
  "hunter_marksmanship",
]);

export function specPortraitKey(classKey: string, specKey: string | null | undefined): string {
  const c = classKey.trim().toLowerCase().replace(/\s+/g, "_");
  const s = (specKey || "").trim().toLowerCase();
  return s ? `${c}_${s}` : "";
}

export function hasSpecPortrait(classKey: string, specKey: string | null | undefined): boolean {
  const k = specPortraitKey(classKey, specKey);
  return Boolean(k && AVAILABLE_SPEC_PORTRAITS.has(k));
}
