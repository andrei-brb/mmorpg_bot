import "./style.css";
import { DiscordSDK } from "@discord/embedded-app-sdk";

const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;

function el(html: string): HTMLElement {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild as HTMLElement;
}

function renderDisconnected(message: string, extra?: string): void {
  const root = document.getElementById("app");
  if (!root) return;
  root.innerHTML = "";
  root.appendChild(
    el(`
    <div class="shell">
      <h1>World of Discord</h1>
      <p class="sub">Embedded game client (preview)</p>
      <div class="status-pill"><span class="dot"></span> Not inside Discord</div>
      <div class="panel">
        <p class="hint">${message}</p>
        ${extra ? `<p class="hint" style="margin-top:0.75rem">${extra}</p>` : ""}
      </div>
      <div class="panel">
        <h2>Local dev</h2>
        <p class="hint">Run <code>npm run dev</code>, expose with ngrok, set URL mapping in the Developer Portal, then launch the Activity from a voice channel (see <code>ACTIVITY_SETUP.md</code>).</p>
      </div>
    </div>
  `),
  );
}

function renderApp(ctx: {
  mode: "discord" | "dev";
  guildId?: string;
  channelId?: string;
  userLabel?: string;
}): void {
  const root = document.getElementById("app");
  if (!root) return;

  const status =
    ctx.mode === "discord"
      ? `<div class="status-pill"><span class="dot ok"></span> Connected in Discord</div>`
      : `<div class="status-pill"><span class="dot ok"></span> SDK ready (dev)</div>`;

  const meta =
    ctx.guildId || ctx.channelId
      ? `<p class="hint">Guild: <code>${ctx.guildId ?? "—"}</code> · Channel: <code>${ctx.channelId ?? "—"}</code></p>`
      : "";

  const userLine = ctx.userLabel
    ? `<p class="hint">${ctx.userLabel}</p>`
    : `<p class="hint">Sign-in to show your Discord name: add a token endpoint (see docs) — inventory sync comes next.</p>`;

  // Placeholder grid (real data will come from your API + bot DB)
  const slots = Array.from({ length: 20 }, (_, i) =>
    i < 3
      ? `<div class="slot filled" title="Slot ${i + 1}">📦</div>`
      : `<div class="slot" title="Empty">·</div>`,
  ).join("");

  root.innerHTML = "";
  root.appendChild(
    el(`
    <div class="shell">
      <h1>World of Discord</h1>
      <p class="sub">Inventory & equipment (visual shell — data hooks next)</p>
      ${status}
      ${meta}
      ${userLine}
      <div class="panel">
        <h2>Equipment</h2>
        <div class="equip-row">
          <div class="equip-slot">Head</div>
          <div class="equip-slot">Chest</div>
          <div class="equip-slot">Weapon</div>
          <div class="equip-slot">Off-hand</div>
        </div>
      </div>
      <div class="panel">
        <h2>Inventory</h2>
        <div class="grid">${slots}</div>
        <p class="hint" style="margin-top:0.75rem">Placeholder slots — next step: REST API on the bot + OAuth to load real items.</p>
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
      () => {
        clearTimeout(t);
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

  const raced = await runWithTimeout(discordSdk.ready(), 8000);
  if (raced === "timeout") {
    renderDisconnected(
      "Could not connect to the Discord client. This page only fully works when opened <strong>inside Discord</strong> as an Activity (iframe).",
      "Use <code>npm run dev</code> + ngrok + Developer Portal URL mapping, then launch from a voice channel.",
    );
    return;
  }

  const guildId = discordSdk.guildId;
  const channelId = discordSdk.channelId;

  renderApp({
    mode: "discord",
    guildId: guildId ?? undefined,
    channelId: channelId ?? undefined,
  });
}

main().catch((e) => {
  console.error(e);
  renderDisconnected(`Error: ${e instanceof Error ? e.message : String(e)}`);
});
