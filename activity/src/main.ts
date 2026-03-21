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

function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${apiBase}${p}`;
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

function renderGame(payload: InventoryPayload, meta: { guildId?: string; channelId?: string }): void {
  const root = document.getElementById("app");
  if (!root) return;

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

  const who = payload.discord?.global_name || payload.discord?.username || "Traveler";
  const charLine = char
    ? `<p class="hint"><strong>${escapeHtml(char.name || "?")}</strong> · Lv ${char.level ?? "?"} · ${escapeHtml(
        String(char.class || "?"),
      )} · 🪙 ${char.gold ?? 0}</p>`
    : `<p class="hint">No character yet — use <code>/character create</code> in Discord.</p>`;

  const metaLine =
    meta.guildId || meta.channelId
      ? `<p class="hint">Guild <code>${escapeHtml(meta.guildId ?? "—")}</code> · Channel <code>${escapeHtml(
          meta.channelId ?? "—",
        )}</code></p>`
      : "";

  root.innerHTML = "";
  root.appendChild(
    el(`
    <div class="shell">
      <h1>World of Discord</h1>
      <p class="sub">Signed in as ${escapeHtml(who)}</p>
      <div class="status-pill"><span class="dot ok"></span> Live inventory</div>
      ${charLine}
      ${metaLine}
      <div class="panel">
        <h2>Equipment</h2>
        <div class="equip-row">${equipHtml}</div>
      </div>
      <div class="panel">
        <h2>Inventory (bag)</h2>
        <div class="grid">${slotHtml}</div>
        <p class="hint" style="margin-top:0.75rem">Showing up to <strong>20</strong> unequipped items (same idea as <code>/inventory</code>).</p>
      </div>
    </div>
  `),
  );
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

  renderLoading("Loading your inventory…");

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

  renderGame(payload, {
    guildId: discordSdk.guildId ?? undefined,
    channelId: discordSdk.channelId ?? undefined,
  });
}

main().catch((e) => {
  console.error(e);
  renderDisconnected(`Error: ${e instanceof Error ? e.message : String(e)}`);
});
