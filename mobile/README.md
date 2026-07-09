# Wold of MMO — Mobile App

A thin [Capacitor](https://capacitorjs.com/) shell that runs the **same** React
game UI as the Discord Activity (`../activity/src`, aliased as `@`) and talks to
the **same** backend + database — so mobile and Discord players share one world
(cross-play).

- **No forked UI.** `@` → `../activity/src` (one source of truth). Only mobile-only
  glue lives in `src/` (native auth, secure storage).
- **Auth.** Standalone Discord login now (`src/platform/DiscordOAuthAuth.ts`);
  native Apple/Google/email in Phase 2.

## First-time setup

```bash
cd mobile
npm install
cp .env.example .env      # then fill in the values below
```

`.env`:
- `VITE_API_BASE_URL` — the Railway API base (same backend as Discord). Already
  defaulted to the production URL.
- `VITE_DISCORD_CLIENT_ID` — your Discord application id (same one the Activity uses).
- `VITE_DISCORD_REDIRECT_URI` — `com.wold.mmo://auth/discord` on device, or your
  dev URL (e.g. `http://localhost:5174`) for browser testing.

### Discord Developer Portal (one-time)
Add the redirect to **OAuth2 → Redirects**:
- `com.wold.mmo://auth/discord` (device)
- `http://localhost:5174` (browser testing, optional)

### Backend env (Railway)
- `SESSION_JWT_SECRET` — a long random string. The backend signs mobile session
  tokens with it. (Falls back to a key derived from `DISCORD_CLIENT_SECRET` if
  unset, but set a dedicated one for production.)

## Build

```bash
npm run build          # vite build → dist/
```

## Run on a phone (before any store submission)

### Android (fastest — no store account needed)
```bash
npm install @capacitor/android
npx cap add android
npm run build && npx cap sync android
# Build a debug APK (needs Android Studio / Android SDK + JDK installed):
cd android && ./gradlew assembleDebug
# → android/app/build/outputs/apk/debug/app-debug.apk
# Sideload to a USB-connected phone (USB debugging on):
adb install app/build/outputs/apk/debug/app-debug.apk
```
Or open `android/` in Android Studio and press Run with your phone connected.

### iOS (needs a Mac + Xcode)
```bash
npm install @capacitor/ios
npx cap add ios
npm run build && npx cap sync ios
npx cap open ios       # in Xcode: select your iPhone, set a signing team, Run
```
A free Apple ID runs on your own device (7-day cert). A paid Apple Developer
account ($99/yr) unlocks TestFlight for wider testing.

> The generated `android/` and `ios/` folders are gitignored — they're
> environment-specific and regenerated with `npx cap add`.
