/**
 * Auth seam: how the game acquires a session, independent of the host.
 *
 * The Discord Activity, a standalone Discord OAuth login, and native
 * (Apple/Google/email) sign-in all implement AuthProvider and return an
 * AuthSession. GameSessionProvider consumes whichever provider it's given,
 * so the shared game UI in activity/src has no knowledge of Discord beyond
 * the DiscordActivityAuth implementation.
 */

export type AuthProviderKind = "discord-activity" | "discord-oauth" | "native";

export type AuthSession = {
  /** Bearer token sent as `Authorization: Bearer <token>`. Either a raw Discord
   *  token (Activity) or our own session JWT (OAuth / native). */
  token: string;
  /** Discord guild id — present only inside the Discord Activity; absent on mobile. */
  guildId?: string;
  /** Discord channel id — parity only; never read by the game. */
  channelId?: string;
  provider: AuthProviderKind;
};

export interface AuthProvider {
  /** Acquire a session. May open an OAuth flow, a native sheet, or read a
   *  stored token. Throws on failure (see error codes below). */
  authenticate(): Promise<AuthSession>;
  /** Optional: refresh/rotate the session when the API returns 401. */
  refresh?(): Promise<AuthSession | null>;
  /** Optional: clear stored credentials (native logout). */
  signOut?(): Promise<void>;
}

/** Error `message` values providers throw so the shell can render the right copy. */
export const AUTH_ERRORS = {
  SDK_READY_TIMEOUT: "sdk_ready_timeout",
  AUTHORIZATION_CANCELLED: "authorization_cancelled",
} as const;
