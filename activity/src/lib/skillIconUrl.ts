import { publicBaseUrl } from "./gameApi";

/** Static icon shipped in `public/skills/skill_<key>.png` (matches combat ability keys). */
export function skillIconUrl(key: string): string {
  return `${publicBaseUrl()}skills/skill_${encodeURIComponent(key)}.png`;
}
