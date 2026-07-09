/**
 * DiscordActivityAuth — the embedded Discord Activity login.
 *
 * This is the ONLY file in activity/src that imports the Discord Embedded App
 * SDK. Its behavior is byte-for-byte the original `runDiscordOAuthOnce` flow
 * that used to live inline in GameSessionContext, including the module-level
 * single-flight guard (React 18 Strict Mode dev-mounts twice; a second
 * authorize()+exchange would get invalid_grant on the reused code).
 */

import { DiscordSDK } from "@discord/embedded-app-sdk";
import * as api from "@/lib/gameApi";
import type { AuthProvider, AuthSession } from "./types";
import { AUTH_ERRORS } from "./types";

function runWithTimeout<T>(p: Promise<T>, ms: number): Promise<T | "timeout"> {
  return new Promise((resolve) => {
    const t = setTimeout(() => resolve("timeout"), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (err) => {
        clearTimeout(t);
        console.error(err);
        resolve("timeout");
      },
    );
  });
}

// Single-flight OAuth keyed by clientId — kept at module scope so two provider
// instances (Strict Mode) sharing a clientId await the same in-flight authorize.
let oauthFlight: { clientId: string; promise: Promise<AuthSession> } | null = null;

function runDiscordOAuthOnce(clientId: string): Promise<AuthSession> {
  if (oauthFlight?.clientId === clientId) {
    return oauthFlight.promise;
  }

  // Reserve synchronously before any await — Strict Mode can invoke this twice
  // in the same tick; a second call must see oauthFlight and await the same promise.
  let resolve!: (v: AuthSession) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<AuthSession>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  oauthFlight = { clientId, promise };
  promise.catch(() => {
    oauthFlight = null;
  });

  void (async () => {
    try {
      const sdk = new DiscordSDK(clientId);
      const raced = await runWithTimeout(sdk.ready(), 12000);
      if (raced === "timeout") {
        throw new Error(AUTH_ERRORS.SDK_READY_TIMEOUT);
      }
      let auth: Awaited<ReturnType<DiscordSDK["commands"]["authorize"]>>;
      try {
        auth = await sdk.commands.authorize({
          client_id: clientId,
          response_type: "code",
          state: "",
          prompt: "none",
          scope: ["identify", "applications.commands"],
        });
      } catch (e) {
        console.error(e);
        throw new Error(AUTH_ERRORS.AUTHORIZATION_CANCELLED);
      }
      const token = await api.exchangeToken(auth.code, window.location.origin);
      try {
        await sdk.commands.authenticate({ access_token: token });
      } catch (e) {
        console.warn("authenticate", e);
      }
      resolve({
        token,
        guildId: sdk.guildId ?? undefined,
        channelId: sdk.channelId ?? undefined,
        provider: "discord-activity",
      });
    } catch (e) {
      reject(e);
    }
  })();

  return promise;
}

export class DiscordActivityAuth implements AuthProvider {
  constructor(private readonly clientId: string) {}

  authenticate(): Promise<AuthSession> {
    return runDiscordOAuthOnce(this.clientId);
  }
}
