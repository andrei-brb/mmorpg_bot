/** Mirrors `services/crafting/crafting_service.py` `crafting_xp_to_next_level`. */
export function craftingXpToNextLevel(level: number): number {
  const lv = Math.max(1, Math.min(98, Math.floor(level)));
  return Math.min(8000, 50 + (lv - 1) * 55);
}
