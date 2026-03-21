# Discord Activity (Embedded App) — Setup & how to open

The **Activity** (`activity/`) is a web UI inside Discord. The **Python bot** stays authoritative for game data; this document covers **OAuth**, the **HTTP API** on the bot process, and **inventory**.

## Architecture

| Piece | Role |
|--------|------|
| `activity/dist` | Static UI (Vite) — icons, inventory grid |
| Bot process (`main.py`) | Discord gateway + **aiohttp** on `PORT`: `POST /api/token`, `GET /api/game/inventory` |
| PostgreSQL | Same DB as slash commands |

When **URL mapping** points at your public bot URL, you can serve **both** the static files and `/api/*` from one host (recommended for Railway).

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

## Local dev (bot + Vite + proxy)

1. **Bot** — set `DISCORD_CLIENT_SECRET`, `DISCORD_APPLICATION_ID`, `DATABASE_URL`, `DISCORD_TOKEN`. HTTP listens on **8080** by default (`ACTIVITY_HTTP_PORT` or `PORT`).
2. **Activity** — `cd activity && npm run dev` (port **5173**). Vite proxies `/api` and `/health` to `http://127.0.0.1:8080` (override with `VITE_DEV_PROXY_TARGET` in `activity/.env`).
3. **ngrok** — `ngrok http 5173` and put the HTTPS URL in **URL mappings** (not 8080), so the iframe loads Vite and `/api` is proxied to your local bot.

## Production (single host, e.g. Railway)

1. Set env vars on the service (including `DISCORD_CLIENT_SECRET`).
2. Build `activity` with the same `VITE_DISCORD_CLIENT_ID` and deploy `activity/dist` next to the bot **or** use the multi-stage **Dockerfile** with build-arg `VITE_DISCORD_CLIENT_ID`.
3. Point **URL mapping** at `https://<your-service>.up.railway.app/` (or your custom domain).
4. `GET https://your-host/health` should return `{"ok": true, ...}`.

## Split UI + API (optional)

- Host **only** `activity/dist` on Vercel/Netlify.
- Set **`VITE_API_BASE_URL`** at build time to your Railway API origin.
- Set **`ACTIVITY_CORS_ORIGINS`** on the bot to your static site origin (e.g. `https://your-app.vercel.app`).
- Set **`ACTIVITY_SERVE_STATIC=0`** on Railway if you don’t copy `dist` there.

## How to open the Activity in Discord

1. Install the bot in a server.
2. **Join a voice channel.**
3. Use the **rocket / Activities** control → launch your app.

Use **`/activity`** in Discord for a short reminder.

## API reference (read-only)

- `POST /api/token` — JSON `{"code": "<oauth code from Embedded App SDK>"}` → `{"access_token": "..."}`.
- `GET /api/game/inventory` — header `Authorization: Bearer <access_token>` → character + items (same data source as `/inventory`).
- `GET /api/game/equipment` — same auth → equipped items by slot.
- `GET /health` — liveness.

## See also

- [Discord Activities overview](https://discord.com/developers/docs/activities/overview)
- [Embedded App SDK](https://discord.com/developers/docs/developer-tools/embedded-app-sdk)
- [discord-embedded-app-sdk-examples](https://github.com/discord/embedded-app-sdk-examples) (token exchange pattern)
