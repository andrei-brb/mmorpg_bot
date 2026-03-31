# World of Discord — Activity (Embedded App)

Vite + TypeScript + [`@discord/embedded-app-sdk`](https://www.npmjs.com/package/@discord/embedded-app-sdk).

## Quick start

```bash
cp .env.example .env
# VITE_DISCORD_CLIENT_ID=<Application ID from Developer Portal>
npm install
npm run dev
```

For Discord testing, use ngrok + URL mapping — see **`../ACTIVITY_SETUP.md`**.

```bash
npm run build   # output: dist/
```

## Environment

| Variable | Description |
|----------|-------------|
| `VITE_DISCORD_CLIENT_ID` | Application ID (same app as the bot). Required at build time. |
| `VITE_API_BASE_URL` | Leave **empty** on Vercel when you use **`vercel.json`** to rewrite `/api/*` → Railway (required inside Discord). See **`../ACTIVITY_SETUP.md`**. |
| `VITE_DEV_PROXY_TARGET` | Local dev: where to proxy `/api` (default `http://127.0.0.1:8080`). |

The bot must run with **`DISCORD_CLIENT_SECRET`** so `POST /api/token` works. See **`../ACTIVITY_SETUP.md`**.
