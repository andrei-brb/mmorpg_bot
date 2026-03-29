import "./style.css";
import { DiscordSDK } from "@discord/embedded-app-sdk";

const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;
/** Empty string = same origin (Activity + API on one host). Set in .env for split deploy. */
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
/** Vite base URL (usually `/`). Item images live under `public/assets/items/{template_id}.png`. */
const publicBase = (() => {
  const b = import.meta.env.BASE_URL || "/";
  return b.endsWith("/") ? b : `${b}/`;
})();

type InvRow = {
  id: string;
  /** Matches `item_templates.id` — use for `/assets/items/{template_id}.png` */
  template_id?: string;
  name: string;
  icon?: string | null;
  quantity?: number | null;
  is_equipped?: boolean | null;
  equip_slot?: string | null;
  rarity?: string | null;
  level_req?: number | null;
  item_type?: string | null;
  s_str?: number | null;
  s_agi?: number | null;
  s_int?: number | null;
  s_spi?: number | null;
  s_sta?: number | null;
  s_armor?: number | null;
  s_dmg_min?: number | null;
  s_dmg_max?: number | null;
  s_haste?: number | null;
  s_lifesteal?: number | null;
  s_resistance?: number | null;
  s_hit_rating?: number | null;
  r_str?: number | null;
  r_agi?: number | null;
  r_int?: number | null;
  r_spi?: number | null;
  r_sta?: number | null;
  r_haste?: number | null;
  r_lifesteal?: number | null;
  r_resistance?: number | null;
  r_hit_rating?: number | null;
  enhancement_level?: number | null;
  effect_type?: string | null;
  effect_value?: number | null;
  effect_duration?: number | null;
};

type EnhanceInfoPayload = {
  ok?: boolean;
  error?: string;
  message?: string;
  info?: {
    current_level?: number;
    next_level?: number | null;
    next_config?: { success_rate?: number; cost?: number; can_break?: boolean; stat_boost?: number } | null;
    item?: { name?: string; rarity?: string; enhancement_level?: number };
  };
  protections?: Record<string, number>;
};

type SpecOption = {
  key: string;
  name: string;
  emoji: string;
  role: string;
  description: string;
  flavor?: string;
  passive_name: string;
  passive_desc: string;
};

type SpecGatePayload = {
  ok?: boolean;
  spec_unlock_level?: number;
  needs_choice?: boolean;
  class?: string;
  specialization?: string | null;
  options?: SpecOption[];
};

type InventoryPayload = {
  discord?: { id?: string; username?: string; global_name?: string | null };
  character: {
    name?: string;
    level?: number;
    class?: string;
    gold?: number;
    specialization?: string | null;
    specialization_name?: string | null;
  } | null;
  items: InvRow[];
};

type CombatEnemy = { key: string; name: string; emoji: string; kind: string };

type CombatAbility = {
  key: string;
  name: string;
  emoji: string;
  cost: number;
  cost_type: string;
  cooldown: number;
  disabled?: string | null;
};

type CombatStatePayload = {
  turn: number;
  player: { name: string; current_hp: number; max_hp: number; current_res: number; max_res: number; res_type: string };
  enemy: { name: string; current_hp: number; max_hp: number };
  log: string[];
  abilities: CombatAbility[];
  can_potion: boolean;
  /** From API: true when character is in a dungeon run — show party strip + sidebar */
  in_dungeon?: boolean;
};

type ProgressAchievement = {
  id?: string;
  name?: string;
  description?: string;
  icon?: string;
  points?: number;
  category?: string;
  earned_at?: string;
};

type ProgressHistory = {
  type?: string;
  outcome?: string;
  zone?: string;
  amount?: number;
  reason?: string;
  source?: string;
  at?: string;
};

type ProgressPayload = {
  character?: {
    name?: string;
    level?: number;
    gold?: number;
    last_combat?: string;
    class?: string;
    specialization?: string | null;
    specialization_name?: string | null;
  };
  stats?: { total_combats?: number; wins?: number; losses?: number; fled?: number; win_rate?: number };
  achievements?: ProgressAchievement[];
  history?: ProgressHistory[];
};

type ExploreZone = {
  key: string;
  name: string;
  emoji: string;
  description?: string;
  level_min?: number;
  level_max?: number;
  faction?: string;
  players?: number;
  boss_alive?: boolean;
  is_current?: boolean;
};

type ExploreMapPayload = {
  current_zone?: string;
  zones?: ExploreZone[];
};

type ExploreNpcPayload = {
  npc_id?: string;
  name?: string;
  title?: string;
  discovery_hint?: string;
  already_met?: boolean;
};

type ExploreOutcome =
  | { type: "enemy" | "boss"; key: string; name: string; emoji?: string }
  | { type: "loot" | "safe" };

type ExploreResultPayload = {
  ok?: boolean;
  error?: string;
  message?: string;
  cooldown_s?: number;
  zone?: { key: string; name: string; emoji: string; level_min?: number; level_max?: number };
  outcome?: ExploreOutcome;
  reward?: { xp?: number; gold?: number };
  npc?: ExploreNpcPayload | null;
  character?: unknown;
};

type QuestLogRow = {
  quest_id?: string;
  state?: string;
  quest_name?: string;
  quest_desc?: string;
  npc_id?: string;
  npc_name?: string;
  npc_title?: string;
  current_step?: number;
  total_steps?: number;
  objective?: string | null;
  completion_check?: { type?: string; value?: string; count?: number } | null;
  progress?: { current?: number; needed?: number } | null;
  expires_at?: string | null;
};

type QuestLogPayload = { ok?: boolean; error?: string; quests?: QuestLogRow[] };

function rarityClass(rarity?: string | null): string {
  const v = (rarity || "").toLowerCase();
  if (v === "artifact") return "rarity-artifact";
  if (v === "legendary") return "rarity-legendary";
  if (v === "epic") return "rarity-epic";
  if (v === "rare") return "rarity-rare";
  if (v === "uncommon") return "rarity-uncommon";
  return "rarity-common";
}

function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${apiBase}${p}`;
}

function authHeaders(accessToken: string, guildId?: string): HeadersInit {
  const h: Record<string, string> = { Authorization: `Bearer ${accessToken}` };
  if (guildId) h["X-Guild-Id"] = String(guildId);
  return h;
}

function el(html: string): HTMLElement {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild as HTMLElement;
}

function escapeHtml(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function itemStatLines(item: InvRow): string[] {
  if (!item.equip_slot) return [];
  const lines: string[] = [];
  const enhLevel = Math.max(0, Math.min(10, Number(item.enhancement_level ?? 0) || 0));
  const enhMult = 1 + enhLevel * 0.1; // mirrors ENHANCEMENT_CONFIG stat_boost (+10% per level)
  const pushStat = (label: string, base?: number | null, bonus?: number | null): void => {
    const b = Number(base ?? 0) || 0;
    const r = Number(bonus ?? 0) || 0;
    const preEnh = b + r;
    const total = Math.floor(preEnh * enhMult);
    if (!total) return;
    const bonusTxt = r ? ` (${r > 0 ? "+" : ""}${r} bonus)` : "";
    lines.push(`${label}: ${total > 0 ? "+" : ""}${total}${bonusTxt}`);
  };

  pushStat("STR", item.s_str, item.r_str);
  pushStat("AGI", item.s_agi, item.r_agi);
  pushStat("INT", item.s_int, item.r_int);
  pushStat("SPI", item.s_spi, item.r_spi);
  pushStat("STA", item.s_sta, item.r_sta);
  pushStat("Haste", item.s_haste, item.r_haste);
  pushStat("Lifesteal", item.s_lifesteal, item.r_lifesteal);
  pushStat("Resistance", item.s_resistance, item.r_resistance);
  pushStat("Hit", item.s_hit_rating, item.r_hit_rating);

  const armor = Math.floor((Number(item.s_armor ?? 0) || 0) * enhMult);
  if (armor) lines.push(`Armor: +${armor}`);
  const dMin = Math.floor((Number(item.s_dmg_min ?? 0) || 0) * enhMult);
  const dMax = Math.floor((Number(item.s_dmg_max ?? 0) || 0) * enhMult);
  if (dMin || dMax) lines.push(`Damage: ${dMin}-${dMax}`);

  return lines;
}

/** PNG path for item art copied from mmorpg-web into `activity/public/assets/items/`. */
function itemIconAssetSrc(templateId: string | undefined | null): string | null {
  const id = templateId?.trim();
  if (!id) return null;
  return `${publicBase}assets/items/${encodeURIComponent(id)}.png`;
}

function itemIconGeneratedSrcs(itemName: string | undefined | null): string[] {
  const n = (itemName || "").trim();
  if (!n) return [];
  const file = `${encodeURIComponent(n)}.png`;
  const bases = [
    // Some icon sets keep files directly under `generated/` (e.g. consumables/materials)
    "assets/items/generated/",
    "assets/items/generated/weapons/",
    "assets/items/generated/armor/",
    "assets/items/generated/off_hand/",
    "assets/items/generated/accessories/",
    "assets/items/generated/characters/",
    "assets/items/generated/maps/",
  ];
  return bases.map((b) => `${publicBase}${b}${file}`);
}

function looksLikeEmoji(s: string): boolean {
  const v = (s || "").trim();
  if (!v) return false;
  // If the DB stored a filename, key, shortcode, etc., prefer a known-good fallback emoji.
  // Heuristic: real emoji are typically not alphanumerics/underscores/colons/dots/slashes.
  if (/[A-Za-z0-9_:./\\-]/.test(v)) return false;
  return true;
}

/** Activity combat enemy name is often `🐺 Forest Wolf` from the server — split for sprite + label. */
function splitLeadingEmojiName(full: string): { emoji: string; rest: string } {
  const t = (full || "").trim();
  const sp = t.indexOf(" ");
  if (sp < 1) return { emoji: "", rest: t };
  const first = t.slice(0, sp);
  if (looksLikeEmoji(first)) {
    const rest = t.slice(sp + 1).trim();
    return { emoji: first, rest: rest || t };
  }
  return { emoji: "", rest: t };
}

/**
 * Inventory / equipment icon: try static image first, fall back to DB emoji (or default).
 */
function renderInvIconHtml(item: InvRow, fallbackEmoji: string): string {
  const raw = item.icon && item.icon.trim() ? item.icon : "";
  const emoji = raw && looksLikeEmoji(raw) ? raw : fallbackEmoji;
  const candidates = [
    itemIconAssetSrc(item.template_id),
    ...itemIconGeneratedSrcs(item.name),
  ].filter((v): v is string => Boolean(v));

  if (candidates.length === 0) {
    return `<span class="inv-icon-emoji">${escapeHtml(emoji)}</span>`;
  }

  const attrs = candidates
    .slice(0, 8)
    .map((src, idx) => ` data-src-${idx}="${src}"`)
    .join("");

  return `<span class="inv-icon-stack" data-icon-fallback="${escapeHtml(emoji)}">
    <img src="${candidates[0]}" alt="" class="inv-icon-img" loading="lazy" decoding="async" width="32" height="32"
      data-src-idx="0"${attrs} />
    <span class="inv-icon-emoji inv-icon-emoji--fallback" style="display:none" aria-hidden="true">${escapeHtml(emoji)}</span>
  </span>`;
}

function wireInvIconFallbacks(scope: ParentNode): void {
  // CSP-safe: attach listeners in JS (Discord blocks inline `onerror=` handlers).
  scope.querySelectorAll<HTMLImageElement>("img.inv-icon-img").forEach((img) => {
    if ((img as unknown as { __wired?: boolean }).__wired) return;
    (img as unknown as { __wired?: boolean }).__wired = true;
    img.addEventListener("error", () => {
      const cur = parseInt(img.getAttribute("data-src-idx") || "0", 10) || 0;
      const nextIdx = cur + 1;
      const next = img.getAttribute(`data-src-${nextIdx}`);
      if (next) {
        img.setAttribute("data-src-idx", String(nextIdx));
        img.src = next;
        return;
      }
      img.style.display = "none";
      const fb = img.nextElementSibling as HTMLElement | null;
      if (fb) fb.style.display = "flex";
    });
  });
}

function renderDisconnected(message: string, extra?: string): void {
  const root = document.getElementById("app");
  if (!root) return;
  root.innerHTML = "";
  root.appendChild(
    el(`
    <div class="shell">
      <h1>World of Discord</h1>
      <p class="sub">Embedded game client</p>
      <div class="status-pill"><span class="dot"></span> Not inside Discord</div>
      <div class="panel">
        <p class="hint">${message}</p>
        ${extra ? `<p class="hint" style="margin-top:0.75rem">${extra}</p>` : ""}
      </div>
      <div class="panel">
        <h2>Local dev</h2>
        <p class="hint">Run the bot with <code>DISCORD_CLIENT_SECRET</code> set, <code>npm run dev</code> in <code>activity/</code> (proxies <code>/api</code> → bot HTTP port), ngrok + URL mapping. See <code>ACTIVITY_SETUP.md</code>.</p>
      </div>
    </div>
  `),
  );
}

function renderLoading(phase: string): void {
  const root = document.getElementById("app");
  if (!root) return;
  root.innerHTML = "";
  root.appendChild(
    el(`
    <div class="shell">
      <h1>World of Discord</h1>
      <p class="sub">${escapeHtml(phase)}</p>
      <div class="status-pill"><span class="dot"></span> Loading…</div>
    </div>
  `),
  );
}

function buildHeroHtml(payload: InventoryPayload): string {
  const char = payload.character;
  const items = payload.items || [];
  const bag = items.filter((i) => !i.is_equipped);
  const bagSlots = 20;
  const emptySlots = Math.max(0, bagSlots - bag.length);
  const hp = Number((char as { current_hp?: number } | null)?.current_hp ?? 0);
  const maxHp = Number((char as { max_hp?: number } | null)?.max_hp ?? 0);
  const hpPct = maxHp > 0 ? Math.max(0, Math.min(100, (hp / maxHp) * 100)) : 100;
  const invTilesHtml = bag.length
    ? bag
        .map((it) => {
          const qty = it.quantity ?? 1;
          const canEquip = Boolean(it.equip_slot);
          const canEnhance = Boolean(it.equip_slot);
          const directUseEffects = new Set([
            "heal_hp",
            "boost_sta",
            "boost_str",
            "boost_agi",
            "boost_int",
            "boost_spi",
            "boost_max_hp",
            "boost_resistance",
          ]);
          const canUse =
            (it.item_type || "").toLowerCase() === "consumable" &&
            directUseEffects.has((it.effect_type || "").toLowerCase());
          const enh = Number((it as any).enhancement_level ?? 0) || 0;
          const enhSuffix = enh > 0 ? ` +${enh}` : "";
          const qtyBadge = qty > 1 ? `x${qty}` : "";
          return `
            <div class="inv-tile ${rarityClass(it.rarity)}" data-item-id="${escapeHtml(it.id)}" title="${escapeHtml(it.name)}" tabindex="0" role="button" aria-label="Inventory item ${escapeHtml(
            it.name,
          )}">
              <div class="inv-tile-main">
                <div class="inv-frame">
                  <span class="inv-icon">${renderInvIconHtml(it, "📦")}</span>
                  ${enh > 0 ? `<span class="inv-badge inv-badge-enh">+${enh}</span>` : ""}
                  ${qtyBadge ? `<span class="inv-badge inv-badge-qty">${escapeHtml(qtyBadge)}</span>` : ""}
                </div>
                <span class="inv-tile-name">${escapeHtml(it.name)}${escapeHtml(enhSuffix)}</span>
              </div>
              <div class="inv-tile-actions">
                ${canUse ? `<button type="button" class="mini-btn act-use" data-item-id="${escapeHtml(it.id)}">Use</button>` : ""}
                ${canEquip ? `<button type="button" class="mini-btn act-equip" data-item-id="${escapeHtml(it.id)}">Equip</button>` : ""}
                ${canEnhance ? `<button type="button" class="mini-btn act-enhance" data-item-id="${escapeHtml(it.id)}">Enhance</button>` : ""}
                <button type="button" class="mini-btn act-sell" data-item-id="${escapeHtml(it.id)}">Sell</button>
              </div>
            </div>
          `.trim();
        })
        .join("") +
      Array.from({ length: emptySlots }, () => `<div class="inv-tile inv-empty" tabindex="-1"><span class="inv-tile-name">Empty slot</span></div>`).join("")
    : `<p class="hint">No items in your bag yet.</p>`;

  const equipOrder = ["head", "chest", "hands", "legs", "feet", "main_hand", "off_hand", "neck", "ring", "trinket"] as const;
  const equipped: Record<string, InvRow | undefined> = {};
  for (const it of items) {
    if (it.is_equipped && it.equip_slot) equipped[it.equip_slot] = it;
  }
  const equipHtml = equipOrder
    .map((slot) => {
      const it = equipped[slot];
      const label = slot.replace("_", " ");
      if (!it) {
        return `<div class="equip-slot" data-slot="${slot}">${label}</div>`;
      }
      return `
        <div class="equip-slot filled item-slot ${rarityClass(it.rarity)}" data-slot="${slot}" data-item-id="${escapeHtml(it.id)}" title="${escapeHtml(it.name)}">
          <div class="equip-frame">
            <span class="slot-icon">${renderInvIconHtml(it, "⚔️")}</span>
            ${((Number((it as any).enhancement_level ?? 0) || 0) > 0) ? `<span class="enh-badge" title="Enhanced">+${escapeHtml(String(Number((it as any).enhancement_level ?? 0) || 0))}</span>` : ""}
          </div>
          <span class="equip-label">${escapeHtml(label)}</span>
          <div class="equip-actions">
            <button type="button" class="mini-btn act-enhance" data-item-id="${escapeHtml(it.id)}">Enhance</button>
            <button type="button" class="mini-btn act-unequip" data-slot="${escapeHtml(slot)}">Unequip</button>
          </div>
        </div>
      `;
    })
    .join("");

  const spec = (char as InventoryPayload["character"])?.specialization_name || (char as InventoryPayload["character"])?.specialization;
  const specPart = spec ? ` · ${escapeHtml(String(spec))}` : "";
  const charLine = char
    ? `<p class="hint"><strong>${escapeHtml(char.name || "?")}</strong> · Lv ${char.level ?? "?"} · ${escapeHtml(String(char.class || "?"))}${specPart}</p>`
    : `<p class="hint">No character yet — use <code>/character create</code> in Discord.</p>`;

  return `
    <div class="panel v0-panel hero-stats-card">
      <div class="hero-stats-head">
        <div>
          <h2>Character Stats</h2>
          ${charLine}
        </div>
        <div class="hero-gold">
          <span>Gold</span>
          <strong class="hero-gold-amount">${char?.gold ?? 0}</strong>
        </div>
      </div>
      <div class="hero-hp-wrap">
        <div class="hero-hp-bar"><div class="hero-hp-fill" style="width:${hpPct}%"></div></div>
        <div class="hint">${maxHp > 0 ? `${hp}/${maxHp} HP` : "HP unavailable"}</div>
      </div>
    </div>
    <div class="hero-main-grid">
      <div class="panel v0-panel">
        <h2>Equipment</h2>
        <div class="equip-grid-v0">${equipHtml}</div>
      </div>
      <div class="panel v0-panel">
        <h2>Inventory (${bag.length})</h2>
        <div class="inv-grid">${invTilesHtml}</div>
      </div>
    </div>
  `;
}

function stripBattleMarkdown(line: string): string {
  return line.replace(/\*\*/g, "").replace(/\s+/g, " ").trim();
}

function lastDamageFromLog(lines: string[]): string | null {
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const raw = lines[i] || "";
    const m = raw.match(/\*\*(\d[\d,]*)\*\*\s*dmg/i) || raw.match(/(\d[\d,]*)\s*dmg/i);
    if (m?.[1]) return m[1];
  }
  return null;
}

/** Sum all `**N** … dmg` / `N dmg` style numbers in the log (approximate “total damage” for UI). */
function totalDamageFromLog(lines: string[]): number {
  let sum = 0;
  for (const line of lines) {
    const re = /\*\*(\d[\d,]*)\*\*[\s\S]*?dmg|(\d[\d,]*)\s*dmg/gi;
    let m: RegExpExecArray | null;
    while ((m = re.exec(line)) !== null) {
      const g = m[1] || m[2];
      if (g) sum += parseInt(g.replace(/,/g, ""), 10) || 0;
    }
  }
  return sum;
}

function formatCombatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

/** Optional UI context for zone bar (Step 3 layout). */
type CombatUiMeta = {
  guildId?: string;
  channelId?: string;
  /** Zone bar title until travel API provides a name */
  zoneLabel?: string;
};

function formatZoneMetaIds(m?: CombatUiMeta): string {
  if (!m) return "";
  const parts: string[] = [];
  if (m.guildId) parts.push(`Guild ${m.guildId}`);
  if (m.channelId) parts.push(`Channel ${m.channelId}`);
  return parts.join(" · ");
}

/** Matches Discord combat labels — warriors use Rage, not mana. */
function resourceUiLabel(resType: string): string {
  const t = (resType || "").toLowerCase();
  if (t === "mana") return "💙 Mana";
  if (t === "energy") return "⚡ Energy";
  if (t === "rage") return "🔴 Rage";
  if (!t || t === "none") return "";
  return resType;
}

function resourceCostLabel(costType: string, cost: number): string {
  if (!cost) return "No cost";
  const t = (costType || "").toLowerCase();
  if (t === "mana") return `${cost} mana`;
  if (t === "energy") return `${cost} energy`;
  if (t === "rage") return `${cost} rage`;
  return `${cost} ${costType}`;
}

/**
 * Combat layout zones B–G (see COMBAT_VISUAL_SPEC_STEP1.md).
 * Step 4: stats row + turn banner + richer placeholder party labels.
 * Skills sit under the battlefield; dungeon “Allies” column has no duplicate hero.
 */
function renderCombatState(state: CombatStatePayload, ui?: CombatUiMeta): string {
  const php = state.player.max_hp ? (100 * state.player.current_hp) / state.player.max_hp : 0;
  const ehp = state.enemy.max_hp ? (100 * state.enemy.current_hp) / state.enemy.max_hp : 0;
  const resLine =
    state.player.max_res > 0
      ? `<p class="hint res-line"><strong>${escapeHtml(resourceUiLabel(state.player.res_type) || state.player.res_type)}</strong> ${state.player.current_res}/${state.player.max_res}</p>`
      : "";

  const logs = state.log || [];
  const logHtml = logs
    .slice(-14)
    .map((line) => `<div class="log-line v0-log-line">${escapeHtml(stripBattleMarkdown(line))}</div>`)
    .join("");
  const latestLine = logs.length ? stripBattleMarkdown(logs[logs.length - 1]) : "Battle started.";
  const floatDmg = lastDamageFromLog(logs);
  const totalDmg = totalDamageFromLog(logs);
  const enemyDisp = splitLeadingEmojiName(state.enemy.name);
  const enemyLabel = enemyDisp.rest || state.enemy.name;
  const enemyShort =
    enemyLabel.length > 22 ? `${escapeHtml(enemyLabel.slice(0, 20))}…` : escapeHtml(enemyLabel);
  const enemySpriteClass = enemyDisp.emoji
    ? "scene-sprite scene-sprite--enemy scene-sprite--emoji"
    : "scene-sprite scene-sprite--enemy";

  const abiHtml = (state.abilities || [])
    .map((a) => {
      const dis = a.disabled ? ` disabled title="${escapeHtml(a.disabled)}"` : "";
      const c = resourceCostLabel(a.cost_type || "", Number(a.cost ?? 0) || 0);
      return `<button type="button" class="skill-btn" data-abi="${escapeHtml(a.key)}"${dis}>
        <span class="skill-name">${escapeHtml(a.emoji)} ${escapeHtml(a.name)}</span>
        <span class="skill-cost">${escapeHtml(c)}</span>
      </button>`;
    })
    .join("");

  const pot =
    state.can_potion ?
      `<button type="button" class="skill-btn alt" data-action="potion">🧪 Potion</button>`
    : "";

  const zoneTitle = ui?.zoneLabel?.trim() ? ui.zoneLabel : "🌲 Current battle";
  const metaIds = formatZoneMetaIds(ui);
  const metaHtml = metaIds ? `<span class="combat-zone-bar__meta">${escapeHtml(metaIds)}</span>` : "";

  /** Dungeon-only: ally column (no duplicate hero — you’re already on the battlefield above). */
  const showPartyUi = Boolean(state.in_dungeon);

  const sidebarRowsAllyOnly = [
    {
      dim: true,
      emoji: "🛡️",
      name: "Slot 2",
      role: "Unlocks with party mode",
      mpPct: 0,
      mpLine: "—",
    },
    {
      dim: true,
      emoji: "🏹",
      name: "Slot 3",
      role: "Unlocks with party mode",
      mpPct: 0,
      mpLine: "—",
    },
  ] as const;

  const sidebarHtml = sidebarRowsAllyOnly
    .map(
      (row) => `
    <div class="party-sidebar-row${row.dim ? " party-sidebar-row--dim" : ""}">
      <div class="party-sidebar-row__portrait${row.dim ? " party-sidebar-row__portrait--dim" : ""}">${row.emoji}</div>
      <div class="party-sidebar-row__main">
        <div class="party-sidebar-row__name">${escapeHtml(row.name)}</div>
        <div class="party-sidebar-row__meta">${escapeHtml(row.role)}</div>
        <div class="party-sidebar-mp"><div style="width:${row.mpPct}%"></div></div>
        <div class="party-sidebar-row__meta">${row.mpLine}</div>
      </div>
    </div>`,
    )
    .join("");

  const skillsHtml = `<div class="skills skills--under-scene" aria-label="Abilities">${abiHtml}${pot}<button type="button" class="skill-btn flee-btn" data-action="flee">🏃 Flee</button></div>`;

  return `
    <div class="combat-compact">
    <div class="combat-zone-bar">
      <div class="combat-zone-bar__left">
        <span class="combat-zone-bar__title">${escapeHtml(zoneTitle)}</span>
        <span class="combat-zone-bar__sub">Turn-based · same rules as <code>/fight</code></span>
      </div>
      <div class="combat-zone-bar__right">
        <span class="combat-zone-bar__turn">Turn ${state.turn}</span>
        ${metaHtml}
      </div>
    </div>
    <div class="scene-wrap">
      <div class="scene">
        <div class="bg-layer"></div>
        <div class="player">
          <div class="scene-sprite" role="img" aria-label="${escapeHtml(state.player.name)}"></div>
          <div class="name">${escapeHtml(state.player.name)}</div>
          <div class="hpbar"><div class="hpfill playerhp" style="width:${php}%"></div></div>
          <div class="hptext">${state.player.current_hp} / ${state.player.max_hp}</div>
          ${resLine}
        </div>
        <div class="enemy">
          <div class="${enemySpriteClass}" role="img" aria-label="${escapeHtml(enemyLabel)}">${enemyDisp.emoji ? escapeHtml(enemyDisp.emoji) : ""}</div>
          <div class="name">${escapeHtml(enemyLabel)}</div>
          <div class="hpbar"><div class="hpfill enemyhp" style="width:${ehp}%"></div></div>
          <div class="hptext">${state.enemy.current_hp} / ${state.enemy.max_hp}</div>
        </div>
        ${floatDmg ? `<div class="damage">-${escapeHtml(floatDmg)}</div>` : ""}
      </div>
    </div>
    ${skillsHtml}
    <div class="combat-mid-band${showPartyUi ? "" : " combat-mid-band--solo"}">
      ${
        showPartyUi
          ? `<div class="combat-mid-band__party">
        <div class="party-sidebar">
          <h3 class="party-sidebar-title">Allies</h3>
          <p class="party-sidebar-hint">You’re on the field above — extra slots for party dungeons.</p>
          ${sidebarHtml}
        </div>
      </div>`
          : ""
      }
      <div class="combat-mid-band__log">
        <div class="combat-log-stack">
          <div class="combat-stats-row" aria-label="Combat summary">
            <div class="combat-stat">
              <span class="combat-stat__k">Turn</span>
              <span class="combat-stat__v">${state.turn}</span>
            </div>
            <div class="combat-stat">
              <span class="combat-stat__k">Total damage</span>
              <span class="combat-stat__v">${formatCombatNumber(totalDmg)}</span>
            </div>
            <div class="combat-stat combat-stat--grow">
              <span class="combat-stat__k">Encounter</span>
              <span class="combat-stat__v combat-stat__v--truncate" title="${escapeHtml(state.enemy.name)}">${enemyShort}</span>
            </div>
          </div>
          <div class="combat-turn-banner" role="status">Your turn — use the skill bar above.</div>
          <div class="log-box log-box--flush">
            <div class="log-highlight">${escapeHtml(latestLine)}</div>
            <div class="combat-log">${logHtml || '<p class="hint">—</p>'}</div>
          </div>
        </div>
      </div>
    </div>
    </div>
  `;
}

function renderOutcome(title: string, lines: string[]): string {
  const body = lines.map((l) => `<p class="hint">${escapeHtml(l)}</p>`).join("");
  return `
    <div class="panel v0-panel outcome-panel">
      <h2>${escapeHtml(title)}</h2>
      ${body}
      <div class="outcome-actions" style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:0.75rem;align-items:center">
        <button type="button" class="btn" data-action="combat-again">Fight again</button>
        <button type="button" class="btn btn-secondary" data-action="combat-rest">💤 Rest</button>
      </div>
      <p class="hint muted-mini" style="margin-top:0.5rem">Rest fully restores HP and your resource (same cooldown as <code>/rest</code>).</p>
    </div>
  `;
}

function renderProgressPanel(payload: InventoryPayload, progress?: ProgressPayload | null): string {
  const char = progress?.character || payload.character || {};
  const stats = progress?.stats || {};
  const achievements = progress?.achievements || [];
  const history = progress?.history || [];
  const level = char?.level ?? 1;
  const gold = char?.gold ?? 0;
  const specName = (char as ProgressPayload["character"])?.specialization_name || (char as ProgressPayload["character"])?.specialization;
  const totalCombats = stats.total_combats ?? 0;
  const wins = stats.wins ?? 0;
  const losses = stats.losses ?? 0;
  const winRate = Number(stats.win_rate ?? 0);
  const historyHtml = history.length
    ? history
        .slice(0, 8)
        .map((h) => {
          const at = h.at ? new Date(h.at).toLocaleString() : "";
          if (h.type === "combat_session") {
            return `<div class="progress-row"><span>⚔️ ${escapeHtml(h.outcome || "unknown")} ${h.zone ? `· ${escapeHtml(h.zone)}` : ""}</span><span class="muted-mini">${escapeHtml(at)}</span></div>`;
          }
          return `<div class="progress-row"><span>🪙 +${h.amount ?? 0} ${escapeHtml(h.reason || "reward")}</span><span class="muted-mini">${escapeHtml(at)}</span></div>`;
        })
        .join("")
    : '<p class="hint">No recent activity yet.</p>';
  const achHtml = achievements.length
    ? achievements
        .slice(0, 8)
        .map(
          (a) =>
            `<div class="progress-row"><span>${escapeHtml(a.icon || "🏆")} ${escapeHtml(a.name || "Achievement")}</span><span class="muted-mini">${a.points ?? 0} pts</span></div>`,
        )
        .join("")
    : '<p class="hint">No achievements earned yet.</p>';
  return `
    <div class="panel v0-panel">
      <h2>Progress</h2>
      <div class="progress-stats">
        <div class="progress-card">
          <span class="progress-k">Level</span>
          <strong class="progress-v">${level}</strong>
        </div>
        <div class="progress-card">
          <span class="progress-k">Specialization</span>
          <strong class="progress-v">${specName ? escapeHtml(String(specName)) : "—"}</strong>
        </div>
        <div class="progress-card">
          <span class="progress-k">Gold</span>
          <strong class="progress-v progress-v--gold">${gold}</strong>
        </div>
        <div class="progress-card">
          <span class="progress-k">Win Rate</span>
          <strong class="progress-v">${(winRate * 100).toFixed(0)}%</strong>
        </div>
        <div class="progress-card">
          <span class="progress-k">Combats</span>
          <strong class="progress-v">${totalCombats}</strong>
        </div>
        <div class="progress-card">
          <span class="progress-k">Record</span>
          <strong class="progress-v">${wins}W / ${losses}L</strong>
        </div>
      </div>
    </div>
    <div class="panel v0-panel">
      <h2>Achievements</h2>
      <div class="progress-list">${achHtml}</div>
    </div>
    <div class="panel v0-panel">
      <h2>History</h2>
      <div class="progress-list">${historyHtml}</div>
    </div>
  `;
}

function mountApp(
  accessToken: string,
  payload: InventoryPayload,
  meta: { guildId?: string; channelId?: string },
): void {
  const root = document.getElementById("app");
  if (!root) return;
  const appRoot = root;

  const guildId = meta.guildId ?? undefined;
  const who = payload.discord?.global_name || payload.discord?.username || "Traveler";

  function combatUiMeta(): CombatUiMeta {
    return {
      guildId: meta.guildId,
      channelId: meta.channelId,
    };
  }

  /** Latest inventory snapshot; updated after combat when loot/gold/bag may change */
  let currentPayload: InventoryPayload = payload;
  let currentProgress: ProgressPayload | null = null;
  let currentMap: ExploreMapPayload | null = null;
  let lastExplore: ExploreResultPayload | null = null;
  let lastEncounterEnemyKey: string | null = null;
  let currentQuestLog: QuestLogPayload | null = null;
  let tooltipEl: HTMLElement | null = null;
  /** Set after DOM mount; specialization prompt at level 10+. */
  let runSpecPrompt: () => Promise<void> = async () => {};

  function hideTooltip(): void {
    if (!tooltipEl) return;
    tooltipEl.classList.remove("visible");
    tooltipEl.style.visibility = "hidden";
  }

  function showTooltip(anchor: HTMLElement, item: InvRow): void {
    if (!tooltipEl) return;
    const raw = item.icon && item.icon.trim() ? item.icon : "";
    const icon = raw && looksLikeEmoji(raw) ? raw : "📦";
    const rarity = item.rarity ? item.rarity.toUpperCase() : "COMMON";
    const qty = item.quantity ?? 1;
    const slot = item.equip_slot ? item.equip_slot.replace("_", " ") : item.is_equipped ? "equipped" : "bag";
    const enh = Number((item as any).enhancement_level ?? 0) || 0;
    const enhSuffix = enh > 0 ? ` +${enh}` : "";
    const lvlReq = Number(item.level_req ?? 0) || 0;
    const statLines = itemStatLines(item);
    const statsHtml = statLines.length
      ? `<div class="item-tip-stats">${statLines.map((l) => `<div class="item-tip-stat">${escapeHtml(l)}</div>`).join("")}</div>`
      : `<div class="item-tip-line">No combat stats</div>`;
    tooltipEl.innerHTML = `
      <div class="item-tip-card ${rarityClass(item.rarity)}">
        <div class="item-tip-title">${escapeHtml(icon)} ${escapeHtml(item.name)}${escapeHtml(enhSuffix)}</div>
        <div class="item-tip-line">${escapeHtml(rarity)} · ${escapeHtml(slot)} · x${qty}</div>
        <div class="item-tip-line">Type: ${escapeHtml(String(item.item_type || "item"))}${lvlReq > 0 ? ` · Req Lv ${lvlReq}` : ""}</div>
        ${statsHtml}
      </div>
    `;
    const rect = anchor.getBoundingClientRect();

    // Measure tooltip before final placement.
    tooltipEl.classList.add("visible");
    tooltipEl.style.visibility = "hidden";
    const tipRect = tooltipEl.getBoundingClientRect();
    const tipW = Math.max(180, tipRect.width || 220);
    const tipH = Math.max(70, tipRect.height || 100);
    const gap = 10;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // User preference: left-side items show tooltip on the left; right-side on the right.
    const anchorCenterX = rect.left + rect.width / 2;
    const preferLeft = anchorCenterX <= vw / 2;

    let left = preferLeft ? rect.left - tipW - gap : rect.right + gap;
    if (left < 8) left = rect.right + gap; // flip
    if (left + tipW > vw - 8) left = rect.left - tipW - gap; // flip back
    if (left < 8) left = 8; // hard clamp

    let top = rect.top + rect.height / 2 - tipH / 2;
    if (top < 8) top = 8;
    if (top + tipH > vh - 8) top = vh - tipH - 8;

    tooltipEl.style.top = `${top}px`;
    tooltipEl.style.left = `${left}px`;
    tooltipEl.style.visibility = "visible";
    tooltipEl.classList.add("visible");
  }

  function wireHeroItems(): void {
    const heroPane = appRoot.querySelector("#tab-hero");
    if (!heroPane) return;
    wireInvIconFallbacks(heroPane);
    heroPane.querySelectorAll<HTMLElement>("[data-item-id]").forEach((n) => {
      const id = n.dataset.itemId;
      if (!id) return;
      const item = currentPayload.items.find((x) => x.id === id);
      if (!item) return;
      n.addEventListener("mouseenter", () => showTooltip(n, item));
      n.addEventListener("focus", () => showTooltip(n, item));
      n.addEventListener("mouseleave", hideTooltip);
      n.addEventListener("blur", hideTooltip);
      n.addEventListener("click", (ev) => {
        if ((ev.target as HTMLElement | null)?.closest(".mini-btn")) return;
        // Tap-to-reveal inventory tiles handle clicks themselves; keep tooltip hover-only for tiles.
        if (n.classList.contains("inv-tile")) return;
        if (tooltipEl?.classList.contains("visible")) hideTooltip();
        else showTooltip(n, item);
      });
    });
  }

  const metaLine =
    meta.guildId || meta.channelId
      ? `<p class="hint">Guild <code>${escapeHtml(meta.guildId ?? "—")}</code> · Channel <code>${escapeHtml(
          meta.channelId ?? "—",
        )}</code></p>`
      : "";

  async function refreshProgressData(): Promise<void> {
    try {
      const res = await fetch(apiUrl("/api/game/progress"), {
        headers: authHeaders(accessToken, guildId),
      });
      if (!res.ok) return;
      currentProgress = (await res.json()) as ProgressPayload;
      const progressPane = appRoot.querySelector("#tab-progress");
      if (progressPane && !progressPane.classList.contains("hidden")) {
        progressPane.innerHTML = renderProgressPanel(currentPayload, currentProgress);
      }
    } catch (e) {
      console.warn("refreshProgressData failed", e);
    }
    void runSpecPrompt();
  }

  function formatExpires(expiresAt?: string | null): string {
    if (!expiresAt) return "";
    const ms = Date.parse(expiresAt);
    if (!Number.isFinite(ms)) return "";
    const delta = ms - Date.now();
    if (delta <= 0) return "Expired";
    const mins = Math.floor(delta / 60000);
    const hrs = Math.floor(mins / 60);
    const remM = mins % 60;
    if (hrs > 0) return `${hrs}h ${remM}m`;
    return `${mins}m`;
  }

  function renderQuestLogPanel(): string {
    const rows = currentQuestLog?.quests || [];
    if (!currentQuestLog) {
      return `<div class="panel v0-panel"><h2>Quest Log</h2><p class="hint">Loading…</p></div>`;
    }
    if (currentQuestLog.error) {
      return `<div class="panel v0-panel"><h2>Quest Log</h2><p class="hint">❌ ${escapeHtml(currentQuestLog.error)}</p></div>`;
    }
    if (!rows.length) {
      return `<div class="panel v0-panel"><h2>Quest Log</h2><p class="hint">No active quests yet. Explore and interact with NPCs to get one.</p></div>`;
    }

    const cards = rows
      .slice(0, 12)
      .map((q) => {
        const npcName = q.npc_name || q.npc_id || "Unknown NPC";
        const title = q.quest_name || q.quest_id || "Quest";
        const step = q.current_step && q.total_steps ? `Step ${q.current_step}/${q.total_steps}` : "";
        const objective = q.objective || "";
        const prog =
          q.progress && typeof q.progress.needed === "number"
            ? `(${q.progress.current ?? 0}/${q.progress.needed})`
            : "";
        const expires = formatExpires(q.expires_at);
        const expiresHtml = expires ? `<span class="quest-pill">${escapeHtml(expires)}</span>` : "";
        const state = (q.state || "").toLowerCase();
        const stateHtml = state ? `<span class="quest-pill">${escapeHtml(state)}</span>` : "";
        const chkType = (q.completion_check?.type || "").toLowerCase();
        const needsNpcTalk = state === "active" && chkType === "talk_to_npc";
        const npcBtn =
          needsNpcTalk && (q.npc_id || q.npc_name)
            ? `<button type="button" class="mini-btn quest-interact" data-npc="${escapeHtml(
                (q.npc_id || (q.npc_name || "").split(" ")[0].toLowerCase()) as string,
              )}">💬 Turn in / Talk</button>`
            : "";

        return `
          <div class="panel v0-panel quest-card">
            <div class="quest-head">
              <div class="quest-title">${escapeHtml(title)}</div>
              <div class="quest-pills">${stateHtml}${expiresHtml}</div>
            </div>
            <div class="hint">From <strong>${escapeHtml(npcName)}</strong>${step ? ` · ${escapeHtml(step)}` : ""}</div>
            <div class="quest-obj">${escapeHtml(objective)} ${escapeHtml(prog)}</div>
            <div class="quest-actions">${npcBtn}</div>
          </div>
        `;
      })
      .join("");

    return `<div class="panel v0-panel"><h2>Quest Log</h2><p class="hint">💬 <strong>Turn in / Talk</strong> only shows when your current step is to speak to an NPC. Kill/explore objectives don’t use this button.</p><div class="quest-grid">${cards}</div></div>`;
  }

  async function refreshQuestLog(): Promise<void> {
    try {
      const res = await fetch(apiUrl("/api/game/quests"), { headers: authHeaders(accessToken, guildId) });
      if (res.status === 401) {
        window.location.reload();
        return;
      }
      if (!res.ok) {
        currentQuestLog = { error: `HTTP ${res.status}` };
        return;
      }
      currentQuestLog = (await res.json()) as QuestLogPayload;
      const pane = appRoot.querySelector("#tab-quests");
      if (pane && !pane.classList.contains("hidden")) pane.innerHTML = renderQuestLogPanel();
    } catch (e) {
      currentQuestLog = { error: e instanceof Error ? e.message : String(e) };
    }
  }

  function renderExplorePanel(): string {
    const char = currentPayload.character as { current_zone?: string; level?: number } | null;
    const zoneKey = (char as { current_zone?: string } | null)?.current_zone || currentMap?.current_zone || "";
    const zones = currentMap?.zones || [];
    const cur = zones.find((z) => z.key === zoneKey) || zones.find((z) => z.is_current) || null;

    const zoneTitle = cur ? `${cur.emoji || "🗺️"} ${cur.name}` : "🗺️ Explore";
    const zoneMeta = cur
      ? `Lv ${cur.level_min ?? "?"}-${cur.level_max ?? "?"} · ${escapeHtml(String(cur.faction || "—"))} · 👥 ${cur.players ?? 0}`
      : "Loading map…";

    const opts = zones.length
      ? zones
          .map((z) => {
            const label = `${z.emoji || "🗺️"} ${z.name} (Lv ${z.level_min ?? "?"}-${z.level_max ?? "?"})`;
            const sel = z.key === zoneKey || z.is_current ? " selected" : "";
            return `<option value="${escapeHtml(z.key)}"${sel}>${escapeHtml(label)}</option>`;
          })
          .join("")
      : `<option value="">Loading…</option>`;

    const exploreBlock = (() => {
      if (!lastExplore) return `<p class="hint">Press <strong>Explore</strong> to roll an encounter, loot, or discover an NPC.</p>`;
      if (lastExplore.error) {
        return `<p class="hint">❌ ${escapeHtml(lastExplore.message || lastExplore.error)}</p>`;
      }
      const out = lastExplore.outcome;
      const reward = lastExplore.reward || {};
      const npc = lastExplore.npc;
      const parts: string[] = [];
      if (out?.type === "enemy" || out?.type === "boss") {
        parts.push(`<div class="panel v0-panel"><h2>Encounter</h2><p class="hint">${escapeHtml(out.emoji || "⚔️")} <strong>${escapeHtml(out.name)}</strong> (${escapeHtml(out.type)})</p><p class="hint">Open the <strong>Combat</strong> tab to fight.</p></div>`);
      } else if (out?.type === "loot") {
        parts.push(`<div class="panel v0-panel"><h2>Discovery</h2><p class="hint">✨ +${reward.xp ?? 0} XP · +${reward.gold ?? 0} 🪙</p></div>`);
      } else if (out?.type === "safe") {
        parts.push(`<div class="panel v0-panel"><h2>Quiet Journey</h2><p class="hint">🌿 +${reward.xp ?? 0} XP</p></div>`);
      }
      if (npc?.npc_id) {
        const name = npc.name || "A Stranger";
        const hint = npc.discovery_hint || (npc.already_met ? "A familiar face." : "Someone approaches…");
        parts.push(`<div class="panel v0-panel"><h2>NPC</h2><p class="hint"><strong>${escapeHtml(name)}</strong></p><p class="hint">${escapeHtml(hint)}</p><div style="margin-top:0.75rem"><button type="button" class="btn" data-action="npc-interact" data-npc="${escapeHtml(name.split(" ")[0].toLowerCase())}">💬 Interact</button></div><p class="hint" style="margin-top:0.5rem">This will DM you the quest offer (if DMs are enabled).</p></div>`);
      }
      if (!parts.length) return `<p class="hint">Done.</p>`;
      return parts.join("");
    })();

    return `
      <div class="panel v0-panel">
        <h2>Explore</h2>
        <p class="hint"><strong>${escapeHtml(zoneTitle)}</strong></p>
        <p class="hint">${zoneMeta}</p>
        <div class="fighters" style="grid-template-columns: 1fr;">
          <div class="v0-fighter-card">
            <label class="select-label">Travel</label>
            <select id="zone-pick" class="enemy-select">${opts}</select>
            <div style="margin-top:0.75rem; display:flex; gap:8px; flex-wrap:wrap">
              <button type="button" class="btn" data-action="travel">🧭 Travel</button>
              <button type="button" class="btn" data-action="explore">🌲 Explore</button>
            </div>
            <div class="hint" style="margin-top:0.5rem">Explore has a cooldown (same as <code>/explore</code>).</div>
          </div>
        </div>
      </div>
      ${exploreBlock}
    `;
  }

  async function refreshMap(): Promise<void> {
    try {
      const res = await fetch(apiUrl("/api/game/map"), { headers: authHeaders(accessToken, guildId) });
      if (res.status === 401) {
        window.location.reload();
        return;
      }
      if (!res.ok) return;
      currentMap = (await res.json()) as ExploreMapPayload;
      const pane = appRoot.querySelector("#tab-explore");
      if (pane && !pane.classList.contains("hidden")) pane.innerHTML = renderExplorePanel();
    } catch (e) {
      console.warn("refreshMap failed", e);
    }
  }

  async function doTravel(): Promise<void> {
    const pane = appRoot.querySelector("#tab-explore");
    const sel = pane?.querySelector("#zone-pick") as HTMLSelectElement | null;
    const zoneKey = sel?.value || "";
    if (!zoneKey) return;
    const res = await fetch(apiUrl("/api/game/travel"), {
      method: "POST",
      headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
      body: JSON.stringify({ zone_key: zoneKey }),
    });
    if (res.status === 401) {
      pane && (pane.innerHTML = `<p class="hint">Session expired — reloading…</p>`);
      window.setTimeout(() => window.location.reload(), 700);
      return;
    }
    const json = (await res.json()) as { ok?: boolean; message?: string; error?: string; character?: unknown };
    if (!res.ok || json.error) {
      lastExplore = { error: json.error || "travel_failed", message: json.message || "Travel failed." };
    }
    await refreshHeroInventory();
    await refreshMap();
    if (pane && !pane.classList.contains("hidden")) pane.innerHTML = renderExplorePanel();
  }

  async function doExplore(): Promise<void> {
    const pane = appRoot.querySelector("#tab-explore");
    lastExplore = { ok: true };
    if (pane && !pane.classList.contains("hidden")) pane.innerHTML = renderExplorePanel();
    const res = await fetch(apiUrl("/api/game/explore"), {
      method: "POST",
      headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (res.status === 401) {
      pane && (pane.innerHTML = `<p class="hint">Session expired — reloading…</p>`);
      window.setTimeout(() => window.location.reload(), 700);
      return;
    }
    const json = (await res.json()) as ExploreResultPayload;
    lastExplore = json;
    if (json.outcome && "key" in (json.outcome as any) && typeof (json.outcome as any).key === "string") {
      lastEncounterEnemyKey = (json.outcome as any).key;
    } else {
      lastEncounterEnemyKey = null;
    }
    await refreshHeroInventory();
    await refreshMap();
    if (pane && !pane.classList.contains("hidden")) pane.innerHTML = renderExplorePanel();
  }

  async function doNpcInteract(npc?: string): Promise<void> {
    const res = await fetch(apiUrl("/api/game/npc/interact"), {
      method: "POST",
      headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
      body: JSON.stringify({ npc }),
    });
    if (res.status === 401) {
      window.location.reload();
      return;
    }
    const json = (await res.json()) as {
      ok?: boolean;
      error?: string;
      message?: string;
      quest_completed?: boolean;
      quest_step_updated?: boolean;
      next_quest_available?: boolean;
      next_quest_auto_offered?: boolean;
      next_quest_blocked?: string;
      rewards?: { xp?: number; gold?: number; items?: string[]; reputation?: Record<string, number> };
    };
    const statusEl = appRoot.querySelector("#hero-action-status");
    if (!res.ok || json.error) {
      lastExplore = { error: json.error || "npc_interact_failed", message: json.message || "Interact failed." };
      if (statusEl) statusEl.textContent = json.message || "Interact failed.";
    } else {
      let msg = json.message || "Sent you a DM.";
      if (json.quest_completed && json.rewards) {
        const parts: string[] = [];
        if (json.rewards.xp) parts.push(`+${json.rewards.xp} XP`);
        if (json.rewards.gold) parts.push(`+${json.rewards.gold} gold`);
        if (json.rewards.items?.length) {
          const items = json.rewards.items.map((i) => i.replace(/_/g, " ")).join(", ");
          parts.push(`items: ${items}`);
        }
        if (json.rewards.reputation && Object.keys(json.rewards.reputation).length) {
          const rep = Object.entries(json.rewards.reputation)
            .map(([k, v]) => `${k.replace(/_/g, " ")} +${v}`)
            .join(", ");
          parts.push(`rep: ${rep}`);
        }
        msg = parts.length ? `Quest complete — ${parts.join(" · ")}` : "Quest complete.";
        if (json.next_quest_auto_offered) {
          msg += " Check your DMs — the next quest offer was sent there.";
        } else if (json.next_quest_available && json.next_quest_blocked === "level_too_low") {
          msg += " A follow-up quest exists but your level is too low — level up and talk to this NPC again.";
        } else if (json.next_quest_available) {
          msg += " NPC has another quest available.";
        }
      }
      lastExplore = { ok: true, message: msg };
      if (statusEl) statusEl.textContent = msg;
    }
    await refreshHeroInventory();
    await refreshProgressData();
    await refreshQuestLog();
    const pane = appRoot.querySelector("#tab-explore");
    if (pane && !pane.classList.contains("hidden")) pane.innerHTML = renderExplorePanel();
  }

  function setTab(next: "hero" | "combat" | "progress" | "explore" | "quests"): void {
    const hBtn = appRoot.querySelector('[data-tab="hero"]');
    const cBtn = appRoot.querySelector('[data-tab="combat"]');
    const pBtn = appRoot.querySelector('[data-tab="progress"]');
    const eBtn = appRoot.querySelector('[data-tab="explore"]');
    const qBtn = appRoot.querySelector('[data-tab="quests"]');
    const hPane = appRoot.querySelector("#tab-hero");
    const cPane = appRoot.querySelector("#tab-combat");
    const pPane = appRoot.querySelector("#tab-progress");
    const ePane = appRoot.querySelector("#tab-explore");
    const qPane = appRoot.querySelector("#tab-quests");
    hBtn?.classList.toggle("active", next === "hero");
    cBtn?.classList.toggle("active", next === "combat");
    pBtn?.classList.toggle("active", next === "progress");
    eBtn?.classList.toggle("active", next === "explore");
    qBtn?.classList.toggle("active", next === "quests");
    hPane?.classList.toggle("hidden", next !== "hero");
    cPane?.classList.toggle("hidden", next !== "combat");
    pPane?.classList.toggle("hidden", next !== "progress");
    ePane?.classList.toggle("hidden", next !== "explore");
    qPane?.classList.toggle("hidden", next !== "quests");
    if (next === "combat") void refreshCombatPanel();
    if (next === "progress") {
      const progressPane = appRoot.querySelector("#tab-progress");
      if (progressPane) {
        progressPane.innerHTML = renderProgressPanel(currentPayload, currentProgress);
      }
      void refreshProgressData();
    }
    if (next === "explore") {
      const pane = appRoot.querySelector("#tab-explore");
      if (pane) pane.innerHTML = renderExplorePanel();
      void refreshMap();
    }
    if (next === "quests") {
      const pane = appRoot.querySelector("#tab-quests");
      if (pane) pane.innerHTML = renderQuestLogPanel();
      void refreshQuestLog();
    }
  }

  async function refreshHeroInventory(): Promise<void> {
    try {
      const invRes = await fetch(apiUrl("/api/game/inventory"), {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!invRes.ok) return;
      const next = (await invRes.json()) as InventoryPayload;
      currentPayload = next;
      const heroPane = appRoot.querySelector("#tab-hero");
      if (heroPane) {
        heroPane.innerHTML = buildHeroHtml(currentPayload);
        wireHeroItems();
      }
      const progressPane = appRoot.querySelector("#tab-progress");
      if (progressPane && !progressPane.classList.contains("hidden")) {
        progressPane.innerHTML = renderProgressPanel(currentPayload, currentProgress);
      }
    } catch (e) {
      console.warn("refreshHeroInventory failed", e);
    }
    void runSpecPrompt();
  }

  async function postCombatRest(): Promise<void> {
    const host = appRoot.querySelector("#combat-mount");
    if (!host) return;
    const restBtn = host.querySelector("[data-action=combat-rest]") as HTMLButtonElement | null;
    if (restBtn) restBtn.disabled = true;
    try {
      const res = await fetch(apiUrl("/api/game/rest"), {
        method: "POST",
        headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
        body: JSON.stringify({ guild_id: guildId ? String(guildId) : undefined }),
      });
      if (res.status === 401) {
        host.innerHTML = `<p class="hint">Session expired — reloading…</p>`;
        window.setTimeout(() => window.location.reload(), 700);
        return;
      }
      const json = (await res.json()) as {
        ok?: boolean;
        error?: string;
        cooldown_s?: number;
        message?: string;
      };
      if (res.status === 429 && json.error === "cooldown") {
        const s = json.cooldown_s ?? 0;
        host.innerHTML = `<div class="panel v0-panel"><p class="hint">⏳ Rest again in <strong>${escapeHtml(String(s))}s</strong>.</p><button type="button" class="btn" data-action="combat-rest-dismiss">OK</button></div>`;
        host.querySelector("[data-action=combat-rest-dismiss]")?.addEventListener("click", () => {
          void refreshCombatPanel();
        });
        return;
      }
      if (!res.ok || !json.ok) {
        const msg = json.message || json.error || "rest_failed";
        host.innerHTML = `<div class="panel v0-panel"><p class="hint">❌ ${escapeHtml(msg)}</p><button type="button" class="btn" data-action="combat-rest-dismiss">OK</button></div>`;
        host.querySelector("[data-action=combat-rest-dismiss]")?.addEventListener("click", () => {
          void refreshCombatPanel();
        });
        return;
      }
      void refreshHeroInventory();
      void refreshProgressData();
      void refreshCombatPanel();
    } catch (e) {
      host.innerHTML = `<div class="panel v0-panel"><p class="hint">❌ ${escapeHtml(e instanceof Error ? e.message : String(e))}</p><button type="button" class="btn" data-action="combat-rest-dismiss">OK</button></div>`;
      host.querySelector("[data-action=combat-rest-dismiss]")?.addEventListener("click", () => {
        void refreshCombatPanel();
      });
    }
  }

  async function refreshCombatPanel(): Promise<void> {
    const host = appRoot.querySelector("#combat-mount");
    if (!host) return;
    host.innerHTML = `<p class="hint">Loading combat…</p>`;

    try {
      const [stRes, enRes] = await Promise.all([
        fetch(apiUrl("/api/game/combat/state"), { headers: authHeaders(accessToken, guildId) }),
        fetch(apiUrl("/api/game/combat/enemies"), { headers: authHeaders(accessToken, guildId) }),
      ]);

      const stJson = (await stRes.json()) as { active?: boolean; state?: CombatStatePayload };
      const enJson = (await enRes.json()) as { enemies?: CombatEnemy[] };

      if (stJson.active && stJson.state) {
        host.innerHTML = renderCombatState(stJson.state, combatUiMeta());
        wireCombatActions(host);
        return;
      }

      // Auto-start the specific enemy we rolled during Explore (tap/click "Combat").
      if (lastEncounterEnemyKey) {
        const enemyKey = lastEncounterEnemyKey;
        // Prevent repeated attempts if the tab rerenders.
        lastEncounterEnemyKey = null;
        const startRes = await fetch(apiUrl("/api/game/combat/start"), {
          method: "POST",
          headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
          body: JSON.stringify({ enemy_key: enemyKey, guild_id: guildId ? String(guildId) : undefined }),
        });
        const startJson = (await startRes.json()) as {
          ok?: boolean;
          error?: string;
          message?: string;
          state?: CombatStatePayload;
        };

        if ((startRes.status === 200 || startRes.status === 409) && startJson.state) {
          host.innerHTML = renderCombatState(startJson.state, combatUiMeta());
          wireCombatActions(host);
          return;
        }
      }

      const enemies = enJson.enemies || [];
      if (enemies.length === 0) {
        host.innerHTML = `<p class="hint">No enemies listed — travel in Discord or create a character.</p>`;
        return;
      }

      const opts = enemies
        .map((e) => `<option value="${escapeHtml(e.key)}">${escapeHtml(e.emoji)} ${escapeHtml(e.name)} (${e.kind})</option>`)
        .join("");

      host.innerHTML = `
        <div class="panel v0-panel">
          <h2>Start a fight</h2>
          <p class="hint">Choose an enemy from your current zone. Same rules as <code>/fight</code>.</p>
          <label class="select-label">Enemy</label>
          <select id="enemy-pick" class="enemy-select">${opts}</select>
          <div style="margin-top:0.75rem;display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center">
            <button type="button" class="btn" data-action="start-fight">⚔️ Start</button>
            <button type="button" class="btn btn-secondary" data-action="combat-rest">💤 Rest</button>
          </div>
          <p class="hint muted-mini" style="margin-top:0.5rem">💤 Rest fully restores HP and your resource (same cooldown as <code>/rest</code>).</p>
        </div>
      `;

      host.querySelector("[data-action=combat-rest]")?.addEventListener("click", () => {
        void postCombatRest();
      });

      host.querySelector("[data-action=start-fight]")?.addEventListener("click", async () => {
        const sel = host.querySelector("#enemy-pick") as HTMLSelectElement | null;
        const enemyKey = sel?.value || "";
        if (!enemyKey) return;
        const startBtn = host.querySelector("[data-action=start-fight]") as HTMLButtonElement | null;
        if (startBtn) {
          startBtn.disabled = true;
          startBtn.textContent = "Starting…";
        }
        host.innerHTML = `<p class="hint">Starting…</p>`;
        try {
          const startRes = await fetch(apiUrl("/api/game/combat/start"), {
            method: "POST",
            headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
            body: JSON.stringify({ enemy_key: enemyKey, guild_id: guildId ? String(guildId) : undefined }),
          });

          if (startRes.status === 401) {
            host.innerHTML = `<p class="hint">Session expired — reloading…</p>`;
            window.setTimeout(() => window.location.reload(), 700);
            return;
          }

          const startJson = (await startRes.json()) as {
            ok?: boolean;
            error?: string;
            message?: string;
            state?: CombatStatePayload;
          };

          if (startRes.status === 409 && startJson.state) {
            host.innerHTML = renderCombatState(startJson.state, combatUiMeta());
            wireCombatActions(host);
            return;
          }

          if (!startRes.ok || startJson.error) {
            const msg = startJson.message || startJson.error || "start_failed";
            host.innerHTML = `<p class="hint">❌ HTTP ${startRes.status}: ${escapeHtml(msg)}</p>`;
            return;
          }

          if (startJson.state) {
            host.innerHTML = renderCombatState(startJson.state, combatUiMeta());
            wireCombatActions(host);
            return;
          }

          host.innerHTML = `<p class="hint">❌ Start succeeded but no combat state returned (HTTP ${startRes.status}).</p>`;
        } catch (e) {
          host.innerHTML = `<p class="hint">❌ Start error: ${escapeHtml(e instanceof Error ? e.message : String(e))}</p>`;
        } finally {
          if (startBtn) startBtn.disabled = false;
        }
      });
    } catch (e) {
      host.innerHTML = `<p class="hint">❌ ${escapeHtml(e instanceof Error ? e.message : String(e))}</p>`;
    }
  }

  async function postAction(body: Record<string, unknown>): Promise<void> {
    const host = appRoot.querySelector("#combat-mount");
    if (!host) return;
    const res = await fetch(apiUrl("/api/game/combat/action"), {
      method: "POST",
      headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, guild_id: guildId ? String(guildId) : undefined }),
    });
    if (res.status === 401) {
      // OAuth bearer can occasionally fail mid-session; reload to force a new token exchange.
      host.innerHTML = `<p class="hint">Session expired — reloading…</p>`;
      window.setTimeout(() => window.location.reload(), 700);
      return;
    }
    const json = (await res.json()) as {
      ok?: boolean;
      ended?: boolean;
      state?: CombatStatePayload;
      outcome?: { type?: string; title?: string; lines?: string[] };
      error?: string;
      message?: string;
    };

    if (!res.ok || json.error) {
      host.innerHTML = `<p class="hint">❌ ${escapeHtml(json.message || json.error || "action_failed")}</p>`;
      return;
    }

    if (json.ended && json.outcome) {
      const title = json.outcome.title || json.outcome.type || "Ended";
      const lines = json.outcome.lines || [];
      host.innerHTML = renderOutcome(title, lines);
      const ot = json.outcome.type;
      if (ot === "victory" || ot === "flee") {
        void refreshHeroInventory();
        void refreshProgressData();
      }
      host.querySelector("[data-action=combat-again]")?.addEventListener("click", () => {
        void refreshCombatPanel();
      });
      host.querySelector("[data-action=combat-rest]")?.addEventListener("click", () => {
        void postCombatRest();
      });
      return;
    }

    if (json.state) {
      host.innerHTML = renderCombatState(json.state, combatUiMeta());
      wireCombatActions(host);
    }
  }

  function wireCombatActions(host: Element): void {
    host.querySelectorAll("[data-abi]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = (btn as HTMLElement).dataset.abi;
        if (!key || (btn as HTMLButtonElement).disabled) return;
        void postAction({ ability: key });
      });
    });
    host.querySelector('[data-action="flee"]')?.addEventListener("click", () => {
      void postAction({ flee: true });
    });
    host.querySelector('[data-action="potion"]')?.addEventListener("click", () => {
      void postAction({ potion: true });
    });
  }

  appRoot.innerHTML = "";
  appRoot.appendChild(
    el(`
    <div class="shell">
      <div class="v0-header-row">
        <div>
          <h1>World of Discord</h1>
          <p class="sub">Welcome, ${escapeHtml(who)}</p>
        </div>
        <button type="button" class="logout-btn" id="logout-btn">Logout</button>
      </div>
      <div class="status-pill"><span class="dot ok"></span> Connected</div>
      ${metaLine}
      <div class="tabs">
        <button type="button" class="tab active" data-tab="hero">Hero</button>
        <button type="button" class="tab" data-tab="explore">Explore</button>
        <button type="button" class="tab" data-tab="quests">Quests</button>
        <button type="button" class="tab" data-tab="combat">Combat</button>
        <button type="button" class="tab" data-tab="progress">Progress</button>
      </div>
      <div id="tab-hero" class="tab-pane">${buildHeroHtml(payload)}</div>
      <div id="tab-explore" class="tab-pane hidden"></div>
      <div id="tab-quests" class="tab-pane hidden"></div>
      <div id="tab-combat" class="tab-pane hidden">
        <div id="combat-mount"><p class="hint">Open this tab to load combat.</p></div>
      </div>
      <div id="tab-progress" class="tab-pane hidden"></div>
      <div id="hero-action-status" class="hint" style="margin-top:0.5rem;"></div>
      <div id="item-tooltip" class="item-tooltip-layer" aria-hidden="true"></div>
      <div id="enhance-modal" class="modal-overlay hidden" role="dialog" aria-modal="true" aria-label="Enhance item"></div>
      <div id="spec-modal" class="modal-overlay modal-overlay--spec hidden" role="dialog" aria-modal="true" aria-label="Choose specialization"></div>
    </div>
  `),
  );

  tooltipEl = appRoot.querySelector("#item-tooltip");
  const statusEl = appRoot.querySelector("#hero-action-status");
  const enhanceModalEl = appRoot.querySelector("#enhance-modal") as HTMLElement | null;
  const specModalEl = appRoot.querySelector("#spec-modal") as HTMLElement | null;
  let pendingEnhanceItemId: string | null = null;

  function closeSpecModal(): void {
    if (!specModalEl) return;
    specModalEl.classList.add("hidden");
    specModalEl.innerHTML = "";
  }

  function closeEnhanceModal(): void {
    pendingEnhanceItemId = null;
    if (!enhanceModalEl) return;
    enhanceModalEl.classList.add("hidden");
    enhanceModalEl.innerHTML = "";
  }

  async function openEnhanceModal(itemId: string): Promise<void> {
    if (!enhanceModalEl) return;
    pendingEnhanceItemId = itemId;
    enhanceModalEl.classList.remove("hidden");
    enhanceModalEl.innerHTML = `<div class="modal-card"><p class="hint">Loading enhancement info…</p></div>`;
    try {
      const res = await fetch(apiUrl(`/api/game/item/enhance/info?item_id=${encodeURIComponent(itemId)}`), {
        headers: authHeaders(accessToken, guildId),
      });
      if (res.status === 401) {
        window.location.reload();
        return;
      }
      const json = (await res.json()) as EnhanceInfoPayload;
      if (!res.ok || !json.ok || !json.info) {
        enhanceModalEl.innerHTML = `<div class="modal-card"><h3>Enhance</h3><p class="hint">❌ ${escapeHtml(
          json.message || json.error || `HTTP ${res.status}`,
        )}</p><div class="modal-actions"><button type="button" class="btn alt" data-enhance-cancel>Close</button></div></div>`;
        return;
      }

      const nextCfg = json.info.next_config || {};
      const protections = json.protections || {};
      const itemName = json.info.item?.name || "Item";
      const cur = Number(json.info.current_level ?? 0) || 0;
      const next = Number(json.info.next_level ?? cur + 1) || cur + 1;
      const baseRate = Number(nextCfg.success_rate ?? 0) || 0;
      const cost = Number(nextCfg.cost ?? 0) || 0;
      const canBreak = Boolean(nextCfg.can_break);
      const haveBless = Number(protections.blessing_scroll ?? 0) || 0;
      const haveCharm = Number(protections.safety_charm ?? 0) || 0;
      const haveFrag = Number(protections.enhancement_fragment ?? 0) || 0;

      enhanceModalEl.innerHTML = `
        <div class="modal-card">
          <h3>Enhance: ${escapeHtml(itemName)} (+${cur} → +${next})</h3>
          <p class="hint">Cost: <strong>${cost.toLocaleString("en-US")}🪙</strong> · Base success: <strong>${(baseRate * 100).toFixed(0)}%</strong></p>
          ${
            canBreak
              ? `<p class="hint"><strong>Risk:</strong> failure can <strong>shatter</strong> the item unless protected.</p>`
              : `<p class="hint">Safe tier: failure won’t destroy the item.</p>`
          }
          <div class="modal-grid">
            <div class="modal-box">
              <div class="modal-box__title">Protection</div>
              <label class="modal-radio"><input type="radio" name="prot" value="" checked /> None</label>
              <label class="modal-radio ${haveBless ? "" : "is-disabled"}"><input type="radio" name="prot" value="blessing_scroll" ${
                haveBless ? "" : "disabled"
              } /> 🛡️ Blessing Scroll (x${haveBless})</label>
              <div class="modal-buy-row">
                <button type="button" class="mini-btn" data-buy-prot="blessing_scroll" data-buy-qty="1">Buy 1</button>
              </div>
              <label class="modal-radio ${haveCharm ? "" : "is-disabled"}"><input type="radio" name="prot" value="safety_charm" ${
                haveCharm ? "" : "disabled"
              } /> ✨ Safety Charm (x${haveCharm})</label>
              <div class="modal-buy-row">
                <button type="button" class="mini-btn" data-buy-prot="safety_charm" data-buy-qty="1">Buy 1</button>
              </div>
            </div>
            <div class="modal-box">
              <div class="modal-box__title">Fragments (+10% each)</div>
              <div class="hint">You have x${haveFrag} (max 3 used)</div>
              <select class="select" id="frag-pick" ${haveFrag ? "" : "disabled"}>
                ${[0, 1, 2, 3]
                  .map((n) => `<option value="${n}" ${n > haveFrag ? "disabled" : ""}>${n}</option>`)
                  .join("")}
              </select>
              <div class="modal-buy-row">
                <button type="button" class="mini-btn" data-buy-prot="enhancement_fragment" data-buy-qty="1">Buy 1</button>
                <button type="button" class="mini-btn" data-buy-prot="enhancement_fragment" data-buy-qty="3">Buy 3</button>
              </div>
            </div>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn alt" data-enhance-cancel>Cancel</button>
            <button type="button" class="btn" data-enhance-confirm>Enhance</button>
          </div>
        </div>
      `;
    } catch (e) {
      enhanceModalEl.innerHTML = `<div class="modal-card"><h3>Enhance</h3><p class="hint">❌ ${
        e instanceof Error ? escapeHtml(e.message) : escapeHtml(String(e))
      }</p><div class="modal-actions"><button type="button" class="btn alt" data-enhance-cancel>Close</button></div></div>`;
    }
  }

  runSpecPrompt = async (): Promise<void> => {
    if (!specModalEl) return;
    if (enhanceModalEl && !enhanceModalEl.classList.contains("hidden")) return;
    if (!specModalEl.classList.contains("hidden")) return;
    try {
      const res = await fetch(apiUrl("/api/game/specializations"), {
        headers: authHeaders(accessToken, guildId),
      });
      if (res.status === 401) return;
      const json = (await res.json()) as SpecGatePayload;
      if (!json.ok || !json.needs_choice || !json.options?.length) {
        closeSpecModal();
        return;
      }
      const lv = json.spec_unlock_level ?? 10;
      const opts = json.options
        .map(
          (o, i) => `
        <label class="spec-option">
          <input type="radio" name="spec-choice" value="${escapeHtml(o.key)}" ${i === 0 ? "checked" : ""} />
          <div class="spec-option__body">
            <div class="spec-option__title">${escapeHtml(o.emoji)} ${escapeHtml(o.name)} <span class="spec-role-pill">${escapeHtml(o.role)}</span></div>
            <p class="spec-option__desc">${escapeHtml(o.description)}</p>
            <p class="spec-option__passive"><strong>${escapeHtml(o.passive_name)}</strong> — ${escapeHtml(o.passive_desc)}</p>
          </div>
        </label>`,
        )
        .join("");
      specModalEl.innerHTML = `
        <div class="modal-card spec-modal-card">
          <h3>Choose your specialization</h3>
          <p class="hint">You reached level <strong>${lv}</strong> — pick your path. This choice is <strong>permanent</strong>.</p>
          <div class="spec-grid">${opts}</div>
          <div class="modal-actions">
            <button type="button" class="btn" data-spec-confirm>Confirm specialization</button>
          </div>
        </div>`;
      specModalEl.classList.remove("hidden");
    } catch (e) {
      console.warn("runSpecPrompt failed", e);
    }
  };

  appRoot.addEventListener("mouseleave", hideTooltip);
  appRoot.addEventListener("click", async (ev) => {
    const target = ev.target as HTMLElement;
    if (!target) return;
    const specConfirm = target.closest("[data-spec-confirm]") as HTMLElement | null;
    if (specConfirm) {
      ev.preventDefault();
      const sel = (appRoot.querySelector('input[name="spec-choice"]:checked') as HTMLInputElement | null)?.value;
      if (!sel) {
        if (statusEl) statusEl.textContent = "Select a specialization first.";
        return;
      }
      try {
        if (statusEl) statusEl.textContent = "Saving specialization…";
        const res = await fetch(apiUrl("/api/game/character/specialization"), {
          method: "POST",
          headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
          body: JSON.stringify({ spec_key: sel }),
        });
        const json = (await res.json()) as { ok?: boolean; message?: string };
        if (statusEl) statusEl.textContent = json.message || (json.ok ? "Specialization saved." : "Failed.");
        if (res.ok && json.ok) {
          closeSpecModal();
          await refreshHeroInventory();
          await refreshProgressData();
        }
      } catch (e) {
        if (statusEl) statusEl.textContent = `Error: ${e instanceof Error ? e.message : String(e)}`;
      }
      return;
    }
    const buyBtn = target.closest("[data-buy-prot]") as HTMLElement | null;
    const enhanceCancel = target.closest("[data-enhance-cancel]") as HTMLElement | null;
    const enhanceConfirm = target.closest("[data-enhance-confirm]") as HTMLElement | null;

    if (buyBtn) {
      const key = buyBtn.getAttribute("data-buy-prot") || "";
      const qty = Number(buyBtn.getAttribute("data-buy-qty") || "1") || 1;
      try {
        if (statusEl) statusEl.textContent = "Buying…";
        const res = await fetch(apiUrl("/api/game/blacksmith/buy-protection"), {
          method: "POST",
          headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
          body: JSON.stringify({ protection_key: key, quantity: qty }),
        });
        const json = (await res.json()) as { ok?: boolean; message?: string };
        if (statusEl) statusEl.textContent = json.message || (json.ok ? "Purchased." : "Purchase failed.");
      } catch (e) {
        if (statusEl) statusEl.textContent = `Buy error: ${e instanceof Error ? e.message : String(e)}`;
      }
      // Refresh hero inventory + gold, then refresh modal counts.
      await refreshHeroInventory();
      await refreshProgressData();
      if (pendingEnhanceItemId) await openEnhanceModal(pendingEnhanceItemId);
      return;
    }

    if (enhanceCancel) {
      closeEnhanceModal();
      return;
    }
    if (enhanceConfirm) {
      const itemId = pendingEnhanceItemId;
      if (!itemId) return;
      const prot = (appRoot.querySelector('input[name="prot"]:checked') as HTMLInputElement | null)?.value || null;
      const fragSel = appRoot.querySelector("#frag-pick") as HTMLSelectElement | null;
      const frag = fragSel ? Number(fragSel.value || "0") || 0 : 0;
      closeEnhanceModal();
      try {
        if (statusEl) statusEl.textContent = "Enhancing...";
        const res = await fetch(apiUrl("/api/game/item/enhance"), {
          method: "POST",
          headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
          body: JSON.stringify({ item_id: itemId, protection_type: prot || null, fragment_count: frag }),
        });
        const json = (await res.json()) as { ok?: boolean; message?: string };
        if (statusEl) statusEl.textContent = json.message || (json.ok ? "Done." : "Enhance failed.");
      } catch (e) {
        if (statusEl) statusEl.textContent = `Enhance error: ${e instanceof Error ? e.message : String(e)}`;
      }
      await refreshHeroInventory();
      await refreshProgressData();
      return;
    }
    const useBtn = target.closest(".act-use") as HTMLElement | null;
    const equipBtn = target.closest(".act-equip") as HTMLElement | null;
    const sellBtn = target.closest(".act-sell") as HTMLElement | null;
    const enhBtn = target.closest(".act-enhance") as HTMLElement | null;
    const unequipBtn = target.closest(".act-unequip") as HTMLElement | null;

    const clickedMini = Boolean(target.closest(".mini-btn"));
    const tileEl = target.closest(".inv-tile") as HTMLElement | null;
    const equipTileEl = target.closest(".equip-slot.filled") as HTMLElement | null;

    // 1) Tap-to-reveal inventory tile
    if (tileEl && !clickedMini && !useBtn && !equipBtn && !sellBtn && !enhBtn && !unequipBtn) {
      if (tileEl.classList.contains("inv-empty")) return;
      appRoot.querySelectorAll<HTMLElement>(".inv-tile.inv-tile--active").forEach((el) => {
        if (el !== tileEl) el.classList.remove("inv-tile--active");
      });
      appRoot.querySelectorAll<HTMLElement>(".equip-slot.equip-slot--active").forEach((el) => el.classList.remove("equip-slot--active"));
      tileEl.classList.toggle("inv-tile--active");
      return;
    }

    // 2) Tap-to-reveal equipment slot actions
    if (equipTileEl && !clickedMini && !useBtn && !equipBtn && !sellBtn && !enhBtn && !unequipBtn) {
      appRoot.querySelectorAll<HTMLElement>(".equip-slot.equip-slot--active").forEach((el) => {
        if (el !== equipTileEl) el.classList.remove("equip-slot--active");
      });
      appRoot.querySelectorAll<HTMLElement>(".inv-tile.inv-tile--active").forEach((el) => el.classList.remove("inv-tile--active"));
      equipTileEl.classList.toggle("equip-slot--active");
      return;
    }

    // 3) If clicked outside tile/action buttons, close any revealed tile.
    if (!useBtn && !equipBtn && !sellBtn && !enhBtn && !unequipBtn && !tileEl && !equipTileEl) {
      appRoot.querySelectorAll<HTMLElement>(".inv-tile.inv-tile--active").forEach((el) => el.classList.remove("inv-tile--active"));
      appRoot.querySelectorAll<HTMLElement>(".equip-slot.equip-slot--active").forEach((el) => el.classList.remove("equip-slot--active"));
      return;
    }

    // 4) Ignore clicks that aren't item actions.
    if (!useBtn && !equipBtn && !sellBtn && !enhBtn && !unequipBtn) return;
    ev.preventDefault();
    ev.stopPropagation();

    let endpoint = "";
    let body: Record<string, unknown> = {};
    if (useBtn) {
      endpoint = "/api/game/item/use";
      const itemId = useBtn.dataset.itemId;
      if (!itemId) return;
      body = { item_id: itemId };
    } else if (equipBtn) {
      endpoint = "/api/game/item/equip";
      const itemId = equipBtn.dataset.itemId;
      if (!itemId) return;
      body = { item_id: itemId };
    } else if (sellBtn) {
      endpoint = "/api/game/item/sell";
      const itemId = sellBtn.dataset.itemId;
      if (!itemId) return;
      body = { item_id: itemId };
    } else if (enhBtn) {
      const itemId = enhBtn.dataset.itemId;
      if (!itemId) return;
      await openEnhanceModal(itemId);
      return;
    } else if (unequipBtn) {
      endpoint = "/api/game/item/unequip";
      const slot = unequipBtn.dataset.slot;
      if (!slot) return;
      body = { slot };
    }
    try {
      if (statusEl) statusEl.textContent = "Processing...";
      const res = await fetch(apiUrl(endpoint), {
        method: "POST",
        headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const json = (await res.json()) as { ok?: boolean; message?: string };
      if (statusEl) statusEl.textContent = json.message || (json.ok ? "Done." : "Action failed.");
      // Always refresh after an item action: enhancement can destroy/downgrade items even on failure.
      await refreshHeroInventory();
      await refreshProgressData();
    } catch (e) {
      if (statusEl) statusEl.textContent = `Action error: ${e instanceof Error ? e.message : String(e)}`;
    }
  });
  wireHeroItems();
  appRoot.querySelector("#logout-btn")?.addEventListener("click", () => window.location.reload());
  appRoot.querySelector('[data-tab="hero"]')?.addEventListener("click", () => setTab("hero"));
  appRoot.querySelector('[data-tab="explore"]')?.addEventListener("click", () => setTab("explore"));
  appRoot.querySelector('[data-tab="quests"]')?.addEventListener("click", () => setTab("quests"));
  appRoot.querySelector('[data-tab="combat"]')?.addEventListener("click", () => setTab("combat"));
  appRoot.querySelector('[data-tab="progress"]')?.addEventListener("click", () => setTab("progress"));

  // Explore actions (delegated)
  appRoot.addEventListener("click", (ev) => {
    const t = ev.target as HTMLElement | null;
    if (!t) return;
    const act = t.closest<HTMLElement>("[data-action]");
    const action = act?.dataset.action || "";
    if (!action) return;
    if (action === "travel") void doTravel();
    if (action === "explore") void doExplore();
    if (action === "npc-interact") void doNpcInteract(act?.dataset.npc);
  });

  appRoot.addEventListener("click", (ev) => {
    const t = ev.target as HTMLElement | null;
    if (!t) return;
    const btn = t.closest<HTMLButtonElement>(".quest-interact");
    if (!btn) return;
    const npc = btn.dataset.npc;
    if (!npc) return;
    void doNpcInteract(npc);
  });

  void runSpecPrompt();
}

async function runWithTimeout<T>(p: Promise<T>, ms: number): Promise<T | "timeout"> {
  return new Promise((resolve) => {
    const t = setTimeout(() => resolve("timeout"), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (err) => {
        clearTimeout(t);
        console.error(err);
        resolve("timeout");
      },
    );
  });
}

async function main(): Promise<void> {
  if (!clientId) {
    renderDisconnected(
      "Missing <code>VITE_DISCORD_CLIENT_ID</code>. Copy <code>activity/.env.example</code> to <code>activity/.env</code> and set your Application ID.",
    );
    return;
  }

  const discordSdk = new DiscordSDK(clientId);

  const raced = await runWithTimeout(discordSdk.ready(), 12000);
  if (raced === "timeout") {
    renderDisconnected(
      "Could not connect to the Discord client. Open this app <strong>inside Discord</strong> as an Activity (voice channel → rocket).",
      "For dev: <code>npm run dev</code> + ngrok + URL mapping.",
    );
    return;
  }

  renderLoading("Connecting to Discord…");

  let code: string;
  try {
    const auth = await discordSdk.commands.authorize({
      client_id: clientId,
      response_type: "code",
      state: "",
      prompt: "none",
      scope: ["identify", "applications.commands"],
    });
    code = auth.code;
  } catch (e) {
    renderDisconnected(
      "Authorization was cancelled or failed.",
      "Try opening the Activity again and approve access when Discord asks.",
    );
    console.error(e);
    return;
  }

  renderLoading("Signing in with your server…");

  const tokenRes = await fetch(apiUrl("/api/token"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });

  if (!tokenRes.ok) {
    const txt = await tokenRes.text();
    renderDisconnected(
      `Token exchange failed (<code>${tokenRes.status}</code>). Is the bot running with <code>DISCORD_CLIENT_SECRET</code> and reachable at <code>${escapeHtml(apiUrl("/api/token"))}</code>?`,
      `<code>${escapeHtml(txt.slice(0, 400))}</code>`,
    );
    return;
  }

  const { access_token: accessToken } = (await tokenRes.json()) as { access_token?: string };
  if (!accessToken) {
    renderDisconnected("No <code>access_token</code> returned from <code>/api/token</code>.");
    return;
  }

  try {
    await discordSdk.commands.authenticate({ access_token: accessToken });
  } catch (e) {
    console.warn("authenticate() warning", e);
  }

  renderLoading("Loading your character…");

  const invRes = await fetch(apiUrl("/api/game/inventory"), {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!invRes.ok) {
    const txt = await invRes.text();
    renderDisconnected(
      `Inventory API error (<code>${invRes.status}</code>).`,
      `<code>${escapeHtml(txt.slice(0, 400))}</code>`,
    );
    return;
  }

  const payload = (await invRes.json()) as InventoryPayload;

  mountApp(accessToken, payload, {
    guildId: discordSdk.guildId ?? undefined,
    channelId: discordSdk.channelId ?? undefined,
  });
}

main().catch((e) => {
  console.error(e);
  renderDisconnected(`Error: ${e instanceof Error ? e.message : String(e)}`);
});
