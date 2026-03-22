import "./style.css";
import { DiscordSDK } from "@discord/embedded-app-sdk";

const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;
/** Empty string = same origin (Activity + API on one host). Set in .env for split deploy. */
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

type InvRow = {
  id: string;
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
};

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
  const slots = bag.slice(0, 20);
  const pad = 20 - slots.length;
  const slotHtml = [
    ...slots.map((it) => {
      const icon = it.icon && it.icon.trim() ? it.icon : "📦";
      const q = (it.quantity ?? 1) > 1 ? ` ×${it.quantity}` : "";
      const title = escapeHtml(`${it.name}${q}`);
      return `<div class="slot filled" title="${title}">${escapeHtml(icon)}</div>`;
    }),
    ...Array.from({ length: Math.max(0, pad) }, () => `<div class="slot" title="Empty">·</div>`),
  ].join("");

  const equipOrder = ["head", "chest", "main_hand", "off_hand", "legs"] as const;
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
      const icon = it.icon && it.icon.trim() ? it.icon : "⚔️";
      return `<div class="equip-slot filled" data-slot="${slot}" title="${escapeHtml(it.name)}">${escapeHtml(icon)}<span class="equip-label">${escapeHtml(label)}</span></div>`;
    })
    .join("");

  const charLine = char
    ? `<p class="hint"><strong>${escapeHtml(char.name || "?")}</strong> · Lv ${char.level ?? "?"} · ${escapeHtml(
        String(char.class || "?"),
      )} · 🪙 ${char.gold ?? 0}</p>`
    : `<p class="hint">No character yet — use <code>/character create</code> in Discord.</p>`;

  return `
    ${charLine}
    <div class="panel">
      <h2>Equipment</h2>
      <div class="equip-row">${equipHtml}</div>
    </div>
    <div class="panel">
      <h2>Inventory (bag)</h2>
      <div class="grid">${slotHtml}</div>
      <p class="hint" style="margin-top:0.75rem">Showing up to <strong>20</strong> unequipped items (same idea as <code>/inventory</code>).</p>
    </div>
  `;
}

function hpBar(pct: number): string {
  const p = Math.max(0, Math.min(100, pct));
  return `<div class="hpbar"><div class="hpbar-fill" style="width:${p}%"></div></div>`;
}

function renderCombatState(state: CombatStatePayload): string {
  const php = state.player.max_hp ? (100 * state.player.current_hp) / state.player.max_hp : 0;
  const ehp = state.enemy.max_hp ? (100 * state.enemy.current_hp) / state.enemy.max_hp : 0;
  const resLine =
    state.player.max_res > 0
      ? `<p class="hint res-line">${escapeHtml(state.player.res_type)} ${state.player.current_res}/${state.player.max_res}</p>`
      : "";

  const logHtml = (state.log || [])
    .slice(-14)
    .map((line) => `<div class="log-line">${escapeHtml(line)}</div>`)
    .join("");

  const abiHtml = (state.abilities || [])
    .map((a) => {
      const dis = a.disabled ? ` disabled title="${escapeHtml(a.disabled)}"` : "";
      return `<button type="button" class="btn abi-btn" data-abi="${escapeHtml(a.key)}"${dis}>${escapeHtml(a.emoji)} ${escapeHtml(a.name)}</button>`;
    })
    .join("");

  const pot =
    state.can_potion ?
      `<button type="button" class="btn btn-secondary" data-action="potion">🧪 Potion</button>`
    : "";

  return `
    <div class="combat-header">
      <p class="hint">Turn <strong>${state.turn}</strong></p>
      <div class="fighters">
        <div>
          <strong>${escapeHtml(state.player.name)}</strong> ${state.player.current_hp}/${state.player.max_hp} HP
          ${hpBar(php)}
          ${resLine}
        </div>
        <div>
          <strong>${escapeHtml(state.enemy.name)}</strong> ${state.enemy.current_hp}/${state.enemy.max_hp} HP
          ${hpBar(ehp)}
        </div>
      </div>
    </div>
    <div class="panel combat-log-panel">
      <h2>Battle log</h2>
      <div class="combat-log">${logHtml || '<p class="hint">—</p>'}</div>
    </div>
    <div class="combat-actions">
      <div class="abi-grid">${abiHtml}</div>
      <div class="row-actions">
        ${pot}
        <button type="button" class="btn btn-secondary" data-action="flee">🏃 Flee</button>
      </div>
    </div>
  `;
}

function renderOutcome(title: string, lines: string[]): string {
  const body = lines.map((l) => `<p class="hint">${escapeHtml(l)}</p>`).join("");
  return `
    <div class="panel outcome-panel">
      <h2>${escapeHtml(title)}</h2>
      ${body}
      <button type="button" class="btn" data-action="combat-again">Fight again</button>
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

  const metaLine =
    meta.guildId || meta.channelId
      ? `<p class="hint">Guild <code>${escapeHtml(meta.guildId ?? "—")}</code> · Channel <code>${escapeHtml(
          meta.channelId ?? "—",
        )}</code></p>`
      : "";

  function setTab(next: "hero" | "combat"): void {
    const hBtn = appRoot.querySelector('[data-tab="hero"]');
    const cBtn = appRoot.querySelector('[data-tab="combat"]');
    const hPane = appRoot.querySelector("#tab-hero");
    const cPane = appRoot.querySelector("#tab-combat");
    hBtn?.classList.toggle("active", next === "hero");
    cBtn?.classList.toggle("active", next === "combat");
    hPane?.classList.toggle("hidden", next !== "hero");
    cPane?.classList.toggle("hidden", next !== "combat");
    if (next === "combat") void refreshCombatPanel();
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
        host.innerHTML = renderCombatState(stJson.state);
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
        <div class="panel">
          <h2>Start a fight</h2>
          <p class="hint">Same zone + rules as <code>/fight</code> in Discord. You cannot run two combats at once.</p>
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
          host.innerHTML = renderCombatState(startJson.state);
          wireCombatActions(host);
          return;
        }

        if (!startRes.ok || startJson.error) {
          const msg = startJson.message || startJson.error || "start_failed";
          host.innerHTML = `<p class="hint">❌ ${escapeHtml(msg)}</p>`;
          return;
        }

        if (startJson.state) {
          host.innerHTML = renderCombatState(startJson.state);
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
      host.querySelector("[data-action=combat-again]")?.addEventListener("click", () => {
        void refreshCombatPanel();
      });
      return;
    }

    if (json.state) {
      host.innerHTML = renderCombatState(json.state);
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
      <h1>World of Discord</h1>
      <p class="sub">Signed in as ${escapeHtml(who)}</p>
      <div class="status-pill"><span class="dot ok"></span> Connected</div>
      ${metaLine}
      <div class="tabs">
        <button type="button" class="tab active" data-tab="hero">Hero</button>
        <button type="button" class="tab" data-tab="combat">Combat</button>
      </div>
      <div id="tab-hero" class="tab-pane">${buildHeroHtml(payload)}</div>
      <div id="tab-combat" class="tab-pane hidden">
        <div id="combat-mount"><p class="hint">Open this tab to load combat.</p></div>
      </div>
    </div>
  `),
  );

  appRoot.querySelector('[data-tab="hero"]')?.addEventListener("click", () => setTab("hero"));
  appRoot.querySelector('[data-tab="combat"]')?.addEventListener("click", () => setTab("combat"));
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
