/**
 * DiscordOAuthAuth — standalone Discord login for the mobile app (and for the
 * mobile build opened in a plain browser). Unlike the embedded Activity, there's
 * no Discord host here: we run the normal OAuth2 authorization-code flow and
 * exchange the code for our own session token.
 *
 * Native (Capacitor): open the system browser to Discord's authorize page with
 * a deep-link redirect (com.wold.mmo://auth/discord); catch the redirect via the
 * App plugin, pull the `code`, exchange it. Web: redirect round-trip.
 */

import { Capacitor, type PluginListenerHandle } from "@capacitor/core";
import { Browser } from "@capacitor/browser";
import { App } from "@capacitor/app";
import * as api from "@/lib/gameApi";
import type { AuthProvider, AuthSession } from "@/context/auth/types";
import { AUTH_ERRORS } from "@/context/auth/types";

const DISCORD_AUTHORIZE = "https://discord.com/api/oauth2/authorize";

export class DiscordOAuthAuth implements AuthProvider {
  /**
   * @param clientId          Discord application id.
   * @param oauthRedirectUri  The https redirect registered in Discord (Discord
   *                          rejects custom schemes). Sent to authorize AND the
   *                          token exchange — they must match. Its page bounces
   *                          the ?code back into the app via `appDeepLink`.
   * @param appDeepLink       The app's custom-scheme URL the OS routes back to
   *                          (e.g. com.wold.mmo://auth/discord). What we listen for.
   */
  constructor(
    private readonly clientId: string,
    private readonly oauthRedirectUri: string,
    private readonly appDeepLink: string,
  ) {}

  async authenticate(): Promise<AuthSession> {
    const { code } = await this.authorize();
    // Discord validates that the exchange redirect_uri matches the authorize one.
    const token = await api.exchangeDiscordCodeForSession(code, this.oauthRedirectUri);
    return { token, provider: "discord-oauth" };
  }

  /**
   * Run the OAuth flow and stop at the code, without exchanging it for a session.
   *
   * Linking needs this: the player is already signed in as someone, and
   * exchanging here would mint a *Discord* session and silently switch them to
   * that account — the opposite of attaching Discord to the account they have.
   * The code goes to /api/auth/link/discord instead, authenticated as who they
   * already are.
   */
  async authorize(): Promise<{ code: string; redirectUri: string }> {
    const code = Capacitor.isNativePlatform()
      ? await this.nativeCodeFlow()
      : await this.webCodeFlow();
    return { code, redirectUri: this.oauthRedirectUri };
  }

  private buildAuthorizeUrl(): string {
    const params = new URLSearchParams({
      client_id: this.clientId,
      response_type: "code",
      scope: "identify",
      redirect_uri: this.oauthRedirectUri,
      prompt: "consent",
    });
    return `${DISCORD_AUTHORIZE}?${params.toString()}`;
  }

  /** Open the OS browser, wait for the deep-link callback carrying `?code=`. */
  private nativeCodeFlow(): Promise<string> {
    return new Promise<string>((resolve, reject) => {
      let handle: PluginListenerHandle | null = null;
      let settled = false;
      const finish = (run: () => void) => {
        if (settled) return;
        settled = true;
        handle?.remove();
        run();
      };
      const fail = (e: unknown) =>
        finish(() => reject(e instanceof Error ? e : new Error(String(e))));

      void App.addListener("appUrlOpen", ({ url }) => {
        if (!url.startsWith(this.appDeepLink)) return;
        void Browser.close().catch(() => {});
        try {
          const code = new URL(url).searchParams.get("code");
          if (code) finish(() => resolve(code));
          else finish(() => reject(new Error(AUTH_ERRORS.AUTHORIZATION_CANCELLED)));
        } catch (e) {
          fail(e);
        }
      }).then((h) => {
        handle = h;
        if (settled) h.remove(); // callback already fired before the listener resolved
      });

      Browser.open({ url: this.buildAuthorizeUrl() }).catch(fail);
    });
  }

  /** Browser flow: if we returned from Discord with `?code=`, use it; else redirect. */
  private webCodeFlow(): Promise<string> {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("code");
    if (code) {
      url.searchParams.delete("code");
      url.searchParams.delete("state");
      window.history.replaceState({}, "", url.toString());
      return Promise.resolve(code);
    }
    window.location.href = this.buildAuthorizeUrl();
    // The page is navigating away; never resolves on this load.
    return new Promise<string>(() => {});
  }
}
