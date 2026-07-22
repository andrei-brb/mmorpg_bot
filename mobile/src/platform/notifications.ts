import { LocalNotifications } from "@capacitor/local-notifications";
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";

/**
 * Local (on-device) reminders for the daily loop. No server, no Apple push key.
 *
 * Why local and not remote push: daily quests reset on a known calendar
 * boundary (daily_quest_service.py:58, `CURRENT_DATE`), so "your dailies are
 * ready" is a time the device can compute itself. Remote push (APNs) is only
 * needed for events the phone can't predict — a market sale, a PvP challenge —
 * and that needs an Apple push key + a backend sender. This file is the part
 * that ships with zero credentials.
 *
 * The scheduling trick — reschedule on every foreground:
 * on every app open we cancel the pending reminder and set a new one ~a day
 * out. If the player keeps opening the app, the reminder keeps getting pushed
 * forward and never fires. It only fires after a full day of absence — which is
 * exactly when a "come back" nudge is wanted, and never when it would be noise.
 * This is how streak reminders (Duolingo et al.) avoid nagging active players,
 * and it needs no knowledge of whether they actually played.
 */

const DAILY_REMINDER_ID = 1001;
const PERMISSION_ASKED_KEY = "emberlone.notif.asked";
const ENABLED_KEY = "emberlone.notif.enabled";

// Local hour to nudge at (24h). Early evening is a common play window; a
// midnight-UTC reset time would land at random local hours, so we remind at a
// friendly local time instead of the exact reset instant.
const REMINDER_HOUR = 18;
// Don't let the reminder fire the same evening they were just playing.
const MIN_HOURS_AHEAD = 20;

function isNative(): boolean {
  return Capacitor.isNativePlatform();
}

/** Ask once, ever. iOS only shows the system prompt on the first request; after
 *  that this resolves from the stored decision without re-prompting. */
export async function ensureNotificationPermission(): Promise<boolean> {
  if (!isNative()) return false;
  try {
    const asked = (await Preferences.get({ key: PERMISSION_ASKED_KEY })).value;
    let perm = await LocalNotifications.checkPermissions();
    if (perm.display === "prompt" && !asked) {
      perm = await LocalNotifications.requestPermissions();
      await Preferences.set({ key: PERMISSION_ASKED_KEY, value: "1" });
    }
    const granted = perm.display === "granted";
    // Default enabled when granted, so a fresh install gets reminders without a
    // settings trip. The player can turn them off (setRemindersEnabled).
    if (granted && (await Preferences.get({ key: ENABLED_KEY })).value == null) {
      await Preferences.set({ key: ENABLED_KEY, value: "1" });
    }
    return granted;
  } catch {
    return false;
  }
}

export async function remindersEnabled(): Promise<boolean> {
  if (!isNative()) return false;
  return (await Preferences.get({ key: ENABLED_KEY })).value === "1";
}

export async function setRemindersEnabled(on: boolean): Promise<void> {
  if (!isNative()) return;
  await Preferences.set({ key: ENABLED_KEY, value: on ? "1" : "0" });
  if (on) await scheduleDailyReminder();
  else await cancelDailyReminder();
}

function nextReminderAt(now: Date): Date {
  const t = new Date(now);
  t.setHours(REMINDER_HOUR, 0, 0, 0);
  // Push forward until it's comfortably in the future, so opening the app in
  // the late afternoon doesn't schedule a nudge for an hour later.
  while ((t.getTime() - now.getTime()) / 3_600_000 < MIN_HOURS_AHEAD) {
    t.setDate(t.getDate() + 1);
  }
  return t;
}

/**
 * Cancel the pending daily reminder and set the next one. Safe to call on every
 * app open — that IS the design.
 *
 * `now` is injectable so this is testable; production passes the real time.
 */
export async function scheduleDailyReminder(now: Date = new Date()): Promise<void> {
  if (!isNative()) return;
  if (!(await remindersEnabled())) return;
  try {
    await cancelDailyReminder();
    const at = nextReminderAt(now);
    await LocalNotifications.schedule({
      notifications: [
        {
          id: DAILY_REMINDER_ID,
          title: "Your daily quests have reset",
          body: "New quests and your login reward are waiting in Emberlone.",
          schedule: { at, allowWhileIdle: true },
        },
      ],
    });
  } catch {
    // A scheduling failure is never worth interrupting play over.
  }
}

export async function cancelDailyReminder(): Promise<void> {
  if (!isNative()) return;
  try {
    await LocalNotifications.cancel({ notifications: [{ id: DAILY_REMINDER_ID }] });
  } catch {
    /* ignore */
  }
}
