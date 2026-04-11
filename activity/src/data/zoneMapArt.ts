const MAP_DIR = "/assets/items/generated/maps/";

/** Zone key → filename in `activity/public/assets/items/generated/maps/`. */
const ZONE_MAP_FILES: Partial<Record<string, string>> = {
  elwynn_forest: "ELWYNN FOREST.png",
  dun_morogh: "DUN MOROGH.png",
  barrens: "THE BARRENS.png",
  /** No jungle map on disk yet — use other in-repo painted map as stand-in. */
  stranglethorn: "SHADOWMOON VALLEY.png",
  /** No volcanic map on disk yet — use other in-repo painted map as stand-in. */
  blackrock_depths: "Plaguelands.png",
};

/** Public URL for the hand-painted zone map, if one exists for this zone. */
export function zoneMapImageUrl(zoneKey: string): string | undefined {
  const file = ZONE_MAP_FILES[zoneKey];
  if (!file) return undefined;
  return `${MAP_DIR}${encodeURIComponent(file)}`;
}
