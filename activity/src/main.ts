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
};

type InventoryPayload = {
  discord?: { id?: string; username?: string; global_name?: string | null };
  character: { name?: string; level?: number; class?: string; gold?: number } | null;
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
  character?: { name?: string; level?: number; gold?: number; last_combat?: string };
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

function rarityClass(rarity?: string | null): string {
  const v = (rarity || "").toLowerCase();
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
          return `
            <div class="inv-tile ${rarityClass(it.rarity)}" data-item-id="${escapeHtml(it.id)}" title="${escapeHtml(it.name)}" tabindex="0" role="button" aria-label="Inventory item ${escapeHtml(
            it.name,
          )}">
              <div class="inv-tile-main">
                <span class="inv-icon">${renderInvIconHtml(it, "📦")}</span>
                <span class="inv-tile-name">${escapeHtml(it.name)}</span>
                <span class="inv-tile-meta">x${qty}</span>
              </div>
              <div class="inv-tile-actions">
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
          <span class="slot-icon">${renderInvIconHtml(it, "⚔️")}</span>
          <span class="equip-label">${escapeHtml(label)}</span>
          <div class="equip-actions">
            <button type="button" class="mini-btn act-enhance" data-item-id="${escapeHtml(it.id)}">Enhance</button>
            <button type="button" class="mini-btn act-unequip" data-slot="${escapeHtml(slot)}">Unequip</button>
          </div>
        </div>
      `;
    })
    .join("");

  const charLine = char
    ? `<p class="hint"><strong>${escapeHtml(char.name || "?")}</strong> · Lv ${char.level ?? "?"} · ${escapeHtml(String(char.class || "?"))}</p>`
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
          <strong>🪙 ${char?.gold ?? 0}</strong>
        </div>
      </div>
      <div class="hero-hp-wrap">
        <div class="hero-hp-bar"><div class="hero-hp-fill" style="width:${hpPct}%"></div></div>
        <div class="hint">${maxHp > 0 ? `${hp}/${maxHp} HP` : "HP unavailable"}</div>
      </div>
    </div>
    <div class="panel v0-panel">
      <h2>Equipment</h2>
      <div class="equip-grid-v0">${equipHtml}</div>
    </div>
    <div class="panel v0-panel">
      <h2>Inventory (${bag.length})</h2>
      <div class="inv-grid">${invTilesHtml}</div>
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
      ? `<p class="hint res-line">${escapeHtml(state.player.res_type)} ${state.player.current_res}/${state.player.max_res}</p>`
      : "";

  const logs = state.log || [];
  const logHtml = logs
    .slice(-14)
    .map((line) => `<div class="log-line v0-log-line">${escapeHtml(stripBattleMarkdown(line))}</div>`)
    .join("");
  const latestLine = logs.length ? stripBattleMarkdown(logs[logs.length - 1]) : "Battle started.";
  const floatDmg = lastDamageFromLog(logs);
  const totalDmg = totalDamageFromLog(logs);
  const enemyShort =
    state.enemy.name.length > 22
      ? `${escapeHtml(state.enemy.name.slice(0, 20))}…`
      : escapeHtml(state.enemy.name);

  const abiHtml = (state.abilities || [])
    .map((a) => {
      const dis = a.disabled ? ` disabled title="${escapeHtml(a.disabled)}"` : "";
      const c = a.cost > 0 ? `${a.cost} ${a.cost_type}` : "No cost";
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
          <div class="scene-sprite" role="img" aria-label="${escapeHtml(state.player.name)}">⚔️</div>
          <div class="name">${escapeHtml(state.player.name)}</div>
          <div class="hpbar"><div class="hpfill playerhp" style="width:${php}%"></div></div>
          <div class="hptext">${state.player.current_hp} / ${state.player.max_hp}</div>
          ${resLine}
        </div>
        <div class="enemy">
          <div class="scene-sprite scene-sprite--enemy" role="img" aria-label="${escapeHtml(state.enemy.name)}">🐻</div>
          <div class="name">${escapeHtml(state.enemy.name)}</div>
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
  `;
}

function renderOutcome(title: string, lines: string[]): string {
  const body = lines.map((l) => `<p class="hint">${escapeHtml(l)}</p>`).join("");
  return `
    <div class="panel v0-panel outcome-panel">
      <h2>${escapeHtml(title)}</h2>
      ${body}
      <button type="button" class="btn" data-action="combat-again">Fight again</button>
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
          <span class="progress-k">Gold</span>
          <strong class="progress-v">🪙 ${gold}</strong>
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
  let tooltipEl: HTMLElement | null = null;

  function hideTooltip(): void {
    tooltipEl?.classList.remove("visible");
  }

  function showTooltip(anchor: HTMLElement, item: InvRow): void {
    if (!tooltipEl) return;
    const raw = item.icon && item.icon.trim() ? item.icon : "";
    const icon = raw && looksLikeEmoji(raw) ? raw : "📦";
    const rarity = item.rarity ? item.rarity.toUpperCase() : "COMMON";
    const qty = item.quantity ?? 1;
    const slot = item.equip_slot ? item.equip_slot.replace("_", " ") : item.is_equipped ? "equipped" : "bag";
    tooltipEl.innerHTML = `
      <div class="item-tip-card ${rarityClass(item.rarity)}">
        <div class="item-tip-title">${escapeHtml(icon)} ${escapeHtml(item.name)}</div>
        <div class="item-tip-line">${escapeHtml(rarity)} · ${escapeHtml(slot)} · x${qty}</div>
      </div>
    `;
    const rect = anchor.getBoundingClientRect();
    const top = rect.top + window.scrollY - 10;
    const left = rect.left + window.scrollX + rect.width / 2;
    tooltipEl.style.top = `${Math.max(12, top)}px`;
    tooltipEl.style.left = `${left}px`;
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
    const json = (await res.json()) as ExploreResultPayload;
    lastExplore = json;
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
    const json = (await res.json()) as { ok?: boolean; error?: string; message?: string };
    if (!res.ok || json.error) {
      lastExplore = { error: json.error || "npc_interact_failed", message: json.message || "Interact failed." };
    } else {
      lastExplore = { ok: true, message: json.message || "Sent you a DM." };
    }
    const pane = appRoot.querySelector("#tab-explore");
    if (pane && !pane.classList.contains("hidden")) pane.innerHTML = renderExplorePanel();
  }

  function setTab(next: "hero" | "combat" | "progress" | "explore"): void {
    const hBtn = appRoot.querySelector('[data-tab="hero"]');
    const cBtn = appRoot.querySelector('[data-tab="combat"]');
    const pBtn = appRoot.querySelector('[data-tab="progress"]');
    const eBtn = appRoot.querySelector('[data-tab="explore"]');
    const hPane = appRoot.querySelector("#tab-hero");
    const cPane = appRoot.querySelector("#tab-combat");
    const pPane = appRoot.querySelector("#tab-progress");
    const ePane = appRoot.querySelector("#tab-explore");
    hBtn?.classList.toggle("active", next === "hero");
    cBtn?.classList.toggle("active", next === "combat");
    pBtn?.classList.toggle("active", next === "progress");
    eBtn?.classList.toggle("active", next === "explore");
    hPane?.classList.toggle("hidden", next !== "hero");
    cPane?.classList.toggle("hidden", next !== "combat");
    pPane?.classList.toggle("hidden", next !== "progress");
    ePane?.classList.toggle("hidden", next !== "explore");
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
          <div style="margin-top:0.75rem">
            <button type="button" class="btn" data-action="start-fight">⚔️ Start</button>
          </div>
        </div>
      `;

      host.querySelector("[data-action=start-fight]")?.addEventListener("click", async () => {
        const sel = host.querySelector("#enemy-pick") as HTMLSelectElement | null;
        const enemyKey = sel?.value || "";
        if (!enemyKey) return;
        host.innerHTML = `<p class="hint">Starting…</p>`;
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

        if (startRes.status === 409 && startJson.state) {
          host.innerHTML = renderCombatState(startJson.state, combatUiMeta());
          wireCombatActions(host);
          return;
        }

        if (!startRes.ok || startJson.error) {
          const msg = startJson.message || startJson.error || "start_failed";
          host.innerHTML = `<p class="hint">❌ ${escapeHtml(msg)}</p>`;
          return;
        }

        if (startJson.state) {
          host.innerHTML = renderCombatState(startJson.state, combatUiMeta());
          wireCombatActions(host);
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
        <button type="button" class="tab" data-tab="combat">Combat</button>
        <button type="button" class="tab" data-tab="progress">Progress</button>
      </div>
      <div id="tab-hero" class="tab-pane">${buildHeroHtml(payload)}</div>
      <div id="tab-explore" class="tab-pane hidden"></div>
      <div id="tab-combat" class="tab-pane hidden">
        <div id="combat-mount"><p class="hint">Open this tab to load combat.</p></div>
      </div>
      <div id="tab-progress" class="tab-pane hidden"></div>
      <div id="hero-action-status" class="hint" style="margin-top:0.5rem;"></div>
      <div id="item-tooltip" class="item-tooltip-layer" aria-hidden="true"></div>
    </div>
  `),
  );

  tooltipEl = appRoot.querySelector("#item-tooltip");
  const statusEl = appRoot.querySelector("#hero-action-status");
  appRoot.addEventListener("mouseleave", hideTooltip);
  appRoot.addEventListener("click", async (ev) => {
    const target = ev.target as HTMLElement;
    if (!target) return;
    const equipBtn = target.closest(".act-equip") as HTMLElement | null;
    const sellBtn = target.closest(".act-sell") as HTMLElement | null;
    const enhBtn = target.closest(".act-enhance") as HTMLElement | null;
    const unequipBtn = target.closest(".act-unequip") as HTMLElement | null;

    const clickedMini = Boolean(target.closest(".mini-btn"));
    const tileEl = target.closest(".inv-tile") as HTMLElement | null;

    // 1) Tap-to-reveal inventory tile
    if (tileEl && !clickedMini && !equipBtn && !sellBtn && !enhBtn && !unequipBtn) {
      if (tileEl.classList.contains("inv-empty")) return;
      appRoot.querySelectorAll<HTMLElement>(".inv-tile.inv-tile--active").forEach((el) => {
        if (el !== tileEl) el.classList.remove("inv-tile--active");
      });
      tileEl.classList.toggle("inv-tile--active");
      return;
    }

    // 2) If clicked outside tile/action buttons, close any revealed tile.
    if (!equipBtn && !sellBtn && !enhBtn && !unequipBtn && !tileEl) {
      appRoot.querySelectorAll<HTMLElement>(".inv-tile.inv-tile--active").forEach((el) => el.classList.remove("inv-tile--active"));
      return;
    }

    // 3) Ignore clicks that aren't item actions.
    if (!equipBtn && !sellBtn && !enhBtn && !unequipBtn) return;
    ev.preventDefault();
    ev.stopPropagation();

    let endpoint = "";
    let body: Record<string, unknown> = {};
    if (equipBtn) {
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
      endpoint = "/api/game/item/enhance";
      const itemId = enhBtn.dataset.itemId;
      if (!itemId) return;
      body = { item_id: itemId };
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
      if (json.ok) {
        await refreshHeroInventory();
        await refreshProgressData();
      }
    } catch (e) {
      if (statusEl) statusEl.textContent = `Action error: ${e instanceof Error ? e.message : String(e)}`;
    }
  });
  wireHeroItems();
  appRoot.querySelector("#logout-btn")?.addEventListener("click", () => window.location.reload());
  appRoot.querySelector('[data-tab="hero"]')?.addEventListener("click", () => setTab("hero"));
  appRoot.querySelector('[data-tab="explore"]')?.addEventListener("click", () => setTab("explore"));
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
