import { Preferences } from "@capacitor/preferences";

/**
 * Which UI the player is running.
 *
 * "classic" is the shipped game and stays the default — this redesign is an
 * alternative to look at, not a replacement. The switch lives in Settings and
 * takes effect immediately (no reinstall), so the two can be compared
 * side-by-side on the same character and the same live data.
 */

export type UiMode = "classic" | "ember";

const KEY = "emberlone.ui.mode";

export async function loadUiMode(): Promise<UiMode> {
  try {
    const { value } = await Preferences.get({ key: KEY });
    return value === "ember" ? "ember" : "classic";
  } catch {
    return "classic";
  }
}

export async function saveUiMode(mode: UiMode): Promise<void> {
  try {
    await Preferences.set({ key: KEY, value: mode });
  } catch {
    /* non-fatal — they keep the mode for this run */
  }
}

/**
 * Stamped on <html> so ember.css can scope every rule to [data-ui="ember"].
 * The classic UI carries no attribute, so it cannot be touched by any of it.
 */
export function applyUiMode(mode: UiMode): void {
  if (mode === "ember") document.documentElement.dataset.ui = "ember";
  else delete document.documentElement.dataset.ui;
}
