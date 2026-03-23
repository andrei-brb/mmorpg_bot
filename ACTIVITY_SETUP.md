# Discord Activity (Embedded App) — Setup & how to open

The **Activity** (`activity/`) is a web UI inside Discord. The **Python bot** stays authoritative for game data; this document covers **OAuth**, the **HTTP API** on the bot process, **inventory**, and **combat** (same engine as `/fight`).

## Architecture

| Piece | Role |
|--------|------|
| `activity/dist` | Static UI (Vite) — icons, inventory grid |
| Bot process (`main.py`) | Discord gateway + **aiohttp** on `PORT`: `POST /api/token`, `GET /api/game/inventory`, `GET/POST /api/game/combat/*` |
| PostgreSQL | Same DB as slash commands |

When **URL mapping** points at your public bot URL, you can serve **both** the static files and `/api/*` from one host (recommended for Railway).

## Combat API (Embedded App)

Iframe combat uses **in-memory** sessions keyed by Discord user id (`services/combat/activity_combat.py`). You **cannot** run Discord `/fight` and Activity combat for the same character at the same time.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/game/combat/enemies` | `Authorization: Bearer` | Enemies/bosses available in your **current zone** |
| `GET` | `/api/game/combat/state` | Bearer | Resume UI if a session exists |
| `POST` | `/api/game/combat/start` | Bearer | JSON `{ "enemy_key": "kobold", "guild_id": "<optional>", "force": false }` — `409` if already fighting (includes `state`) |
| `POST` | `/api/game/combat/action` | Bearer | JSON `{ "ability": "auto_attack" }` or `{ "flee": true }` or `{ "potion": true }` — optional `guild_id` for milestones/loot scaling |

Optional header **`X-Guild-Id`** (or `guild_id` in JSON) should match the guild the Activity is opened in so **server milestones** and **server_config** multipliers apply like `/fight`.

## Environment variables (bot / `.env`)

| Variable | Required for Activity API | Description |
|----------|---------------------------|-------------|
| `DISCORD_TOKEN` | Yes (bot) | Bot token |
| `DATABASE_URL` | Yes | PostgreSQL |
| `DISCORD_CLIENT_SECRET` | **Yes** for `/api/token` | Developer Portal → **OAuth2** → Client Secret |
| `DISCORD_APPLICATION_ID` | Recommended | Same as **Application ID** (General Information). Used if the bot’s `application_id` is not ready at startup. |
| `DISCORD_OAUTH_REDIRECT_URI` | Rarely | Only if Discord returns `redirect_uri` errors — must match a URI under **OAuth2 → Redirects** exactly. |
| `PORT` / `ACTIVITY_HTTP_PORT` | Optional | HTTP listen port (default **8080**). **Railway** sets `PORT` automatically. |
| `ACTIVITY_CORS_ORIGINS` | Optional | Comma-separated origins if the Activity is on another domain than the API (e.g. Vercel → Railway). |
| `ACTIVITY_SERVE_STATIC` | Optional | `1` (default): serve `activity/dist` when present. Set `0` if you only host the API. |
| `ACTIVITY_STATIC_DIR` | Optional | Override path to built static files |

Frontend build (`activity/.env`):

| Variable | Description |
|----------|-------------|
| `VITE_DISCORD_CLIENT_ID` | Application ID (same app as the bot) |
| `VITE_API_BASE_URL` | Empty = same origin. Set to your API base if UI and API differ (e.g. `https://your-bot.up.railway.app`). |

## Developer Portal checklist

1. **General Information** — copy **Application ID** → `VITE_DISCORD_CLIENT_ID` and `DISCORD_APPLICATION_ID`.
2. **OAuth2** — copy **Client Secret** → `DISCORD_CLIENT_SECRET`.
3. **OAuth2 → Redirects** — add the URL where your Activity is served, e.g. `https://your-public-host/` (no path mismatch). If token exchange fails with redirect errors, set `DISCORD_OAUTH_REDIRECT_URI` to that **exact** string and retry.
4. **Activities → URL mappings** — prefix `/` → target `https://your-public-host` (same host as above if you use one service).

## Build the web client

```bash
cd activity
cp .env.example .env
# VITE_DISCORD_CLIENT_ID=...   (Application ID)
npm ci
npm run build
```

Output: `activity/dist/`.

### Item icons (shared with mmorpg-web)

You can copy PNGs from **mmorpg-web** into `activity/public/assets/items/` named `{template_id}.png` (UUID from `item_templates.id`). The Hero inventory uses them automatically; if a file is missing, the DB emoji is shown. See `activity/public/assets/items/README.md`.

## Local dev (bot + Vite + proxy)

1. **Bot** — set `DISCORD_CLIENT_SECRET`, `DISCORD_APPLICATION_ID`, `DATABASE_URL`, `DISCORD_TOKEN`. HTTP listens on **8080** by default (`ACTIVITY_HTTP_PORT` or `PORT`).
2. **Activity** — `cd activity && npm run dev` (port **5173**). Vite proxies `/api` and `/health` to `http://127.0.0.1:8080` (override with `VITE_DEV_PROXY_TARGET` in `activity/.env`).
3. **ngrok** — `ngrok http 5173` and put the HTTPS URL in **URL mappings** (not 8080), so the iframe loads Vite and `/api` is proxied to your local bot.

## Production (single host, e.g. Railway)

1. Set env vars on the service (including `DISCORD_CLIENT_SECRET`).
2. Build `activity` with the same `VITE_DISCORD_CLIENT_ID` and deploy `activity/dist` next to the bot **or** use the multi-stage **Dockerfile** with build-arg `VITE_DISCORD_CLIENT_ID`.
3. Point **URL mapping** at `https://<your-service>.up.railway.app/` (or your custom domain).
4. `GET https://your-host/health` should return `{"ok": true, ...}`.
5. `GET https://your-host/` should load the **game UI**, not an “Index of /” directory listing. The bot serves `index.html` at `/` and `/assets/*` from Vite’s `dist/` (rebuild if you only see a file list).

### Railway + Docker: build-time `VITE_DISCORD_CLIENT_ID` (required)

The **Dockerfile** runs `npm run build` in stage `activity-build`. Vite needs **`VITE_DISCORD_CLIENT_ID`** at **build** time (same value as **Application ID**).

If you see a placeholder page like *“Rebuild with Docker build-arg VITE_DISCORD_CLIENT_ID”*, the image was built **without** that variable.

**Fix:**

1. Railway → your **worker** service → **Variables**.
2. Add **`VITE_DISCORD_CLIENT_ID`** = your Application ID (e.g. `1473559227569279159`).
3. Enable it for **Build** (Railway: toggle “Available at Build Time” / **Build** scope — exact UI varies).
4. **Redeploy** so Docker rebuilds with `npm run build` and produces real `activity/dist/assets/*`.

Without this, the container only contains a stub `index.html` and the Activity UI will not load.

## Split UI + API (optional)

- Host **only** `activity/dist` on Vercel/Netlify.
- Set **`VITE_API_BASE_URL`** at build time to your Railway API origin.
- Set **`ACTIVITY_CORS_ORIGINS`** on the bot to your static site origin (e.g. `https://your-app.vercel.app`).
- Set **`ACTIVITY_SERVE_STATIC=0`** on Railway if you don’t copy `dist` there.

## How to open the Activity in Discord

**Easiest (recommended):** In a text channel, run slash command **`/open_game`**.  
The bot answers with Discord’s **`LAUNCH_ACTIVITY`** response so the client opens your Embedded App (no App Launcher “Launch” entry required).

Other options:

1. Install the bot in a server.
2. **Join a voice channel** and use the **rocket / Activities** control (your app may not appear in search).
3. **App Launcher** (`/` in the message box) — only if Discord created a default Entry Point command.

Use **`/activity`** for setup notes if something fails.

## API reference (read-only)

- `POST /api/token` — JSON `{"code": "<oauth code from Embedded App SDK>"}` → `{"access_token": "..."}`.
- `GET /api/game/inventory` — header `Authorization: Bearer <access_token>` → character + items (same data source as `/inventory`).
- `GET /api/game/equipment` — same auth → equipped items by slot.
- `GET /health` — liveness.

## Troubleshooting: `50234` / “does not have the EMBEDDED flag”

When using **`/open_game`** (or `LAUNCH_ACTIVITY`), Discord may return:

`Cannot use this interaction callback if the application does not have the EMBEDDED flag`

**Meaning:** Embedded Activities are **not enabled** for that application in the Developer Portal.

**Fix:**

1. [Developer Portal](https://discord.com/developers/applications) → **the same application** as your bot (`DISCORD_APPLICATION_ID`).
2. **Activities** → **Settings** (not only URL Mappings).
3. Turn **Enable Activities** on (exact label may vary). You typically need **URL Mappings** configured first.
4. Save, wait a short time, try **`/open_game`** again.

Without this, OAuth and Railway can still work, but **launching** the Activity from an interaction will fail.

## Troubleshooting: “invalid redirect URI”

Discord compares three things:

1. **OAuth2 → Redirects** in the Developer Portal (allowed list).
2. The URL your **Activity iframe** loads (URL mapping / public HTTPS URL).
3. The **`redirect_uri`** your server sends in `POST https://discord.com/api/oauth2/token` (we send what you set in env, plus slash variants, then try without).

**Fix:**

1. Copy your **exact** public Activity URL from the browser bar when the iframe is open (e.g. `https://something.up.railway.app/` or without trailing slash — pick one style).
2. In **OAuth2 → Redirects**, add **that exact string**. If unsure, add **both** `https://host` and `https://host/`.
3. On Railway, set **`DISCORD_OAUTH_REDIRECT_URI`** (or **`ACTIVITY_PUBLIC_URL`**) to the **same** string as one of the entries in step 2 (character-for-character: `https`, no wrong port, same slash).
4. Redeploy and try again.

If you still see the error, check Railway logs for `OAuth token exchange` lines — they show which `redirect_uri` was attempted.

## See also

- [Discord Activities overview](https://discord.com/developers/docs/activities/overview)
- [Embedded App SDK](https://discord.com/developers/docs/developer-tools/embedded-app-sdk)
- [discord-embedded-app-sdk-examples](https://github.com/discord/embedded-app-sdk-examples) (token exchange pattern)
