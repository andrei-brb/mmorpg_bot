import { Preferences } from "@capacitor/preferences";

/**
 * Where the session token lives between launches.
 *
 * Until now it lived in a single useState (GameSessionContext.tsx:139) and died
 * with the page — so every cold start re-ran the whole Discord browser consent
 * bounce. That is the single worst thing about the current mobile login, and it
 * is invisible in a dev build where you never fully quit the app.
 *
 * @capacitor/preferences maps to UserDefaults on iOS: it survives app restarts
 * but not deletion of the app. Good enough for a session token that already has
 * a 30-day expiry server-side (session_tokens.py:27).
 *
 * NOT the Keychain. Preferences is not encrypted at rest, so this is unsuitable
 * for a password — which is exactly why nothing here ever stores one. Only the
 * bearer token is kept, and it expires. If we later store credentials for
 * biometric re-auth, that needs a real secure-storage plugin.
 */

const TOKEN_KEY = "emberlone.session.token";
const PROVIDER_KEY = "emberlone.session.provider";

export type StoredSession = {
  token: string;
  provider: "discord-oauth" | "native";
};

export async function loadSession(): Promise<StoredSession | null> {
  try {
    const [{ value: token }, { value: provider }] = await Promise.all([
      Preferences.get({ key: TOKEN_KEY }),
      Preferences.get({ key: PROVIDER_KEY }),
    ]);
    if (!token) return null;
    return { token, provider: provider === "discord-oauth" ? "discord-oauth" : "native" };
  } catch {
    // A storage failure must not lock anyone out — fall through to the login
    // screen rather than crashing the app on boot.
    return null;
  }
}

export async function saveSession(s: StoredSession): Promise<void> {
  try {
    await Promise.all([
      Preferences.set({ key: TOKEN_KEY, value: s.token }),
      Preferences.set({ key: PROVIDER_KEY, value: s.provider }),
    ]);
  } catch {
    // Non-fatal: they stay signed in for this run and log in again next launch.
  }
}

export async function clearSession(): Promise<void> {
  try {
    await Promise.all([
      Preferences.remove({ key: TOKEN_KEY }),
      Preferences.remove({ key: PROVIDER_KEY }),
    ]);
  } catch {
    /* ignore */
  }
}
