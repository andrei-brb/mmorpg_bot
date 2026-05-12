/** Overworld combat / explore portrait paths (Activity `public/mobs` and `public/bosses`). */

export function isBossKind(kind: string): boolean {
  return String(kind || "").trim().toLowerCase() === "boss";
}

export function enemyPortraitSrc(enemyKey: string, kind: string): string {
  const k = String(enemyKey || "").trim();
  if (!k) return "";
  return isBossKind(kind) ? `/bosses/${k}.png` : `/mobs/${k}.png`;
}
