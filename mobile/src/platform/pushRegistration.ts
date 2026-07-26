import { Capacitor } from "@capacitor/core";
import { PushNotifications } from "@capacitor/push-notifications";
import { apiUrl, authHeaders } from "@/lib/gameApi";

/**
 * Remote push registration.
 *
 * The app already schedules LOCAL notifications (see notifications.ts) for the
 * things the phone can predict on its own — the daily reset, the idle cap
 * filling. Everything that makes a shared game worth returning to is
 * unpredictable from the device: someone whispered you, your guild started a
 * raid, your season ends tonight.
 *
 * This registers the device with Apple and hands the resulting token to our
 * server, which is the only piece the client owns. Whether anything is actually
 * delivered depends on APNs credentials being set on the server — see
 * services/notifications/push.py.
 *
 * Permission is requested LAZILY, not on first launch. A permission prompt
 * before the player knows what the game is gets denied, and iOS only asks once
 * — a denial is close to permanent. `enablePush` is meant to be called from a
 * settings toggle, when the player has decided they want this.
 */

let registeredToken: string | null = null;

function isNative(): boolean {
  return Capacitor.isNativePlatform();
}

/** Whether the platform can do remote push at all. */
export function pushSupported(): boolean {
  return isNative();
}

async function sendTokenToServer(accessToken: string, token: string, guildId?: string): Promise<boolean> {
  try {
    const res = await fetch(apiUrl("/api/game/push/register"), {
      method: "POST",
      headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
      body: JSON.stringify({ token, platform: "ios" }),
    });
    const j = (await res.json()) as { ok?: boolean };
    return j?.ok !== false;
  } catch {
    return false;
  }
}

/**
 * Ask for permission, register with APNs, and send the token up.
 *
 * Returns what actually happened rather than a bare boolean, because "the user
 * said no" and "it failed" need different things said to them.
 */
export async function enablePush(
  accessToken: string,
  guildId?: string,
): Promise<"enabled" | "denied" | "unsupported" | "failed"> {
  if (!isNative()) return "unsupported";

  try {
    let perm = await PushNotifications.checkPermissions();
    if (perm.receive === "prompt" || perm.receive === "prompt-with-rationale") {
      perm = await PushNotifications.requestPermissions();
    }
    if (perm.receive !== "granted") return "denied";

    const token = await new Promise<string | null>((resolve) => {
      // Resolve on whichever fires first; APNs registration can fail silently
      // otherwise and leave a settings toggle spinning forever.
      const timer = setTimeout(() => resolve(null), 10_000);
      void PushNotifications.addListener("registration", (t) => {
        clearTimeout(timer);
        resolve(t.value);
      });
      void PushNotifications.addListener("registrationError", () => {
        clearTimeout(timer);
        resolve(null);
      });
      void PushNotifications.register();
    });

    if (!token) return "failed";
    registeredToken = token;
    return (await sendTokenToServer(accessToken, token, guildId)) ? "enabled" : "failed";
  } catch {
    return "failed";
  }
}

/** Stop remote pushes for this device. */
export async function disablePush(accessToken: string, guildId?: string): Promise<void> {
  if (!registeredToken) return;
  try {
    await fetch(apiUrl("/api/game/push/unregister"), {
      method: "POST",
      headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
      body: JSON.stringify({ token: registeredToken }),
    });
  } catch {
    /* the server prunes dead tokens on its own when Apple reports them gone */
  }
  registeredToken = null;
}

/**
 * Re-send an existing token after sign-in.
 *
 * A device token belongs to the installation, not the account, so when a
 * different player signs in on the same phone the server needs to be told the
 * token has moved — otherwise the previous account keeps getting the pushes.
 */
export async function refreshPushBinding(accessToken: string, guildId?: string): Promise<void> {
  if (!isNative() || !registeredToken) return;
  await sendTokenToServer(accessToken, registeredToken, guildId);
}
