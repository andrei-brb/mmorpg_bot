import { publicBaseUrl } from "./gameApi";

function normalizeKey(key: string): string {
  return key.trim().toLowerCase().replace(/\s+/g, "_");
}

/** Static icon shipped in `public/classes/class_<key>.png` (matches `config/settings.py` class keys). */
export function classIconUrl(classKeyOrName: string): string {
  const key = normalizeKey(classKeyOrName);
  return `${publicBaseUrl()}classes/class_${encodeURIComponent(key)}.png`;
}

/** Static icon shipped in `public/specs/spec_<key>.png` (matches `config/settings.py` specialization keys). */
export function specIconUrl(specKey: string): string {
  const key = normalizeKey(specKey);
  return `${publicBaseUrl()}specs/spec_${encodeURIComponent(key)}.png`;
}

