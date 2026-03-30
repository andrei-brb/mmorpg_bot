/** Bundled PNGs (Vite) — works in Discord iframe even if `/classes` static routes 404. */

function normalizeKey(key: string): string {
  return key.trim().toLowerCase().replace(/\s+/g, "_");
}

function mapByFilename(
  glob: Record<string, string>,
  pattern: RegExp,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [path, url] of Object.entries(glob)) {
    const m = path.match(pattern);
    if (m) out[m[1]] = url;
  }
  return out;
}

const classModules = import.meta.glob<string>("../assets/class-icons/class_*.png", {
  eager: true,
  import: "default",
});

const specModules = import.meta.glob<string>("../assets/spec-icons/spec_*.png", {
  eager: true,
  import: "default",
});

const CLASS_ICON_URLS = mapByFilename(classModules, /class_([a-z_]+)\.png$/);
const SPEC_ICON_URLS = mapByFilename(specModules, /spec_([a-z_]+)\.png$/);

/** Class portrait URL (bundled asset). Unknown keys fall back to warrior. */
export function classIconUrl(classKeyOrName: string): string {
  const key = normalizeKey(classKeyOrName);
  return CLASS_ICON_URLS[key] ?? CLASS_ICON_URLS.warrior;
}

/** Spec icon URL (bundled asset). Returns empty string if unknown. */
export function specIconUrl(specKey: string): string {
  const key = normalizeKey(specKey);
  return SPEC_ICON_URLS[key] ?? "";
}
