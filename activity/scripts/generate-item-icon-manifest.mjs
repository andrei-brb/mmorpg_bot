/**
 * Scans public/assets/items/icons and writes src/data/itemIconManifest.json
 * (slug -> filenames). Run on build/dev so the Activity only resolves icons that exist.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RARITIES = new Set(["common", "uncommon", "rare", "epic", "legendary"]);

const iconsDir = path.join(__dirname, "../public/assets/items/icons");
const outFile = path.join(__dirname, "../src/data/itemIconManifest.json");

function parseFileName(filename) {
  const m = filename.match(/^(.+)\.(png|jpe?g|webp)$/i);
  if (!m) return null;
  const base = m[1];
  const parts = base.split("_");
  const last = parts[parts.length - 1].toLowerCase();
  if (parts.length >= 2 && RARITIES.has(last)) {
    return { slug: parts.slice(0, -1).join("_"), file: filename };
  }
  return { slug: base, file: filename };
}

function main() {
  if (!fs.existsSync(iconsDir)) {
    console.warn("generate-item-icon-manifest: missing", iconsDir, "(skip)");
    fs.mkdirSync(path.dirname(outFile), { recursive: true });
    fs.writeFileSync(outFile, "{}\n");
    return;
  }

  /** @type {Record<string, string[]>} */
  const manifest = {};
  const names = fs.readdirSync(iconsDir);
  for (const name of names) {
    const parsed = parseFileName(name);
    if (!parsed) continue;
    if (!manifest[parsed.slug]) manifest[parsed.slug] = [];
    if (!manifest[parsed.slug].includes(parsed.file)) manifest[parsed.slug].push(parsed.file);
  }
  for (const k of Object.keys(manifest)) {
    manifest[k].sort();
  }

  fs.mkdirSync(path.dirname(outFile), { recursive: true });
  fs.writeFileSync(outFile, JSON.stringify(manifest, null, 0) + "\n");
  const n = Object.keys(manifest).length;
  console.log(`generate-item-icon-manifest: ${n} slug(s) -> ${outFile}`);
}

main();
