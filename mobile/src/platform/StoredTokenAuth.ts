import type { AuthProvider, AuthProviderKind, AuthSession } from "@/context/auth/types";
import { clearSession } from "@mobile/platform/sessionStore";

/**
 * An AuthProvider for a token we already hold.
 *
 * The shell resolves the session *before* mounting the game — either from
 * storage or from the login screen — so by the time GameSessionProvider boots
 * there is nothing left to negotiate. This just hands the token over.
 *
 * That ordering is what keeps GameSessionContext untouched: its boot effect
 * still calls authenticate() exactly once and gets a session, exactly as it
 * does for Discord. It never learns that a login screen exists.
 */
export class StoredTokenAuth implements AuthProvider {
  constructor(
    private readonly token: string,
    private readonly kind: AuthProviderKind = "native",
  ) {}

  async authenticate(): Promise<AuthSession> {
    return { token: this.token, provider: this.kind };
  }

  async signOut(): Promise<void> {
    await clearSession();
  }
}
