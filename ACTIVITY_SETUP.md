# Discord Activity (Embedded App) — Setup & how to open

This repo includes a **web client** in `activity/` that runs **inside Discord** as an **Activity** (iframe). The Python bot remains the source of truth for inventory, combat, and economy; the Activity is the visual shell (we’ll wire APIs next).

## What you need

1. **Same Discord application** as your bot (Developer Portal).
2. **Application ID** (OAuth2 client id) — *not* the bot token.  
   Portal → **General Information** → **Application ID**.
3. A **public HTTPS URL** serving the built files (or **ngrok** for local dev).

## One-time: configure the portal

1. Open [Discord Developer Portal](https://discord.com/developers/applications) → select your app.
2. Go to **Activities** (or **Embedded App** / **Rich Presence** depending on UI).
3. Enable the Activity / Embedded App experience if prompted.
4. Under **URL Mappings** (sometimes “Activity URL”):
   - **Prefix:** `/`
   - **Target URL:** `https://your-deployed-host.example`  
     (no trailing slash; must be HTTPS in production)
5. Save. It can take a minute to propagate.

## Build the web client

```bash
cd activity
cp .env.example .env
# Set VITE_DISCORD_CLIENT_ID to your Application ID
npm ci
npm run build
```

Output is in `activity/dist/`. Upload or deploy that folder to any static host (Vercel, Netlify, Cloudflare Pages, S3+CloudFront, etc.).

### Local testing with ngrok

```bash
cd activity
npm run dev
# In another terminal:
ngrok http 5173
```

Use the **https** URL ngrok prints as the **URL Mapping** target (e.g. `https://abcd.ngrok.io`). Reload Discord after changing mappings.

## How to open the Activity in Discord

1. **Install the bot** in a server (if not already).
2. **Join a voice channel** in that server (Activities launch from voice context).
3. Look for the **rocket / Activities** icon in the voice UI (desktop: near mute/deafen; sometimes in the channel sidebar).
4. Click **Open Activity** / your app name — Discord loads your mapped URL in an iframe.

**Notes**

- If the iframe stays blank: check browser DevTools (hard on mobile); fix mixed content (must be HTTPS); confirm URL mapping matches your deploy URL exactly.
- Opening `index.html` directly in a browser **won’t** complete `discordSdk.ready()` — you need the Discord client iframe (or use ngrok + portal mapping + launch from voice).

## Bot command

Use **`/activity`** in-game (same channel rules as other general commands) for a short checklist and your **Application ID** when available.

## Next steps (development)

- Add **OAuth2 token exchange** + `authenticate` so the Activity can call **your** REST API as the logged-in user.
- Expose read-only **inventory / equipment** JSON from the bot or a small API service.
- Keep **authoritative** combat/economy logic on the server.

See also: [Discord Activities overview](https://discord.com/developers/docs/activities/overview) and [Embedded App SDK](https://discord.com/developers/docs/developer-tools/embedded-app-sdk).
