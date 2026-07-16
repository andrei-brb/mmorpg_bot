import { apiUrl } from "@/lib/gameApi";

/**
 * Game-account auth calls. Mobile-only — the Discord Activity has no login
 * screen and never reaches these, so they live here rather than in the shared
 * gameApi.ts.
 *
 * apiUrl() is reused so these resolve exactly like every other call: on a
 * Capacitor page it returns the absolute VITE_API_BASE_URL (gameApi.ts:40-60).
 */

export type AuthResult = { token: string; playerId: string };

type ApiError = { ok?: boolean; error?: string; message?: string; retry_after_s?: number };

async function postAuth(path: string, body: unknown): Promise<Response> {
  return fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Turns a failed response into something worth showing a player. */
async function failure(res: Response): Promise<Error> {
  let j: ApiError = {};
  try {
    j = (await res.json()) as ApiError;
  } catch {
    /* non-JSON body */
  }
  if (res.status === 429) {
    const mins = Math.ceil((j.retry_after_s ?? 900) / 60);
    return new Error(`Too many attempts. Try again in about ${mins} minute${mins === 1 ? "" : "s"}.`);
  }
  // The server writes these for players, not for logs — prefer its wording.
  return new Error(j.message || j.error || `Something went wrong (${res.status}).`);
}

export async function nativeLogin(login: string, password: string): Promise<AuthResult> {
  const res = await postAuth("/api/auth/native/login", { login, password });
  if (!res.ok) throw await failure(res);
  const j = (await res.json()) as { access_token: string; player_id: string };
  return { token: j.access_token, playerId: j.player_id };
}

export async function nativeSignup(
  username: string,
  email: string,
  password: string,
): Promise<AuthResult> {
  const res = await postAuth("/api/auth/native/signup", { username, email, password });
  if (!res.ok) throw await failure(res);
  const j = (await res.json()) as { access_token: string; player_id: string };
  return { token: j.access_token, playerId: j.player_id };
}

export async function requestPasswordReset(email: string): Promise<string> {
  const res = await postAuth("/api/auth/password/forgot", { email });
  if (!res.ok) throw await failure(res);
  const j = (await res.json()) as { message?: string };
  // Deliberately the same answer whether or not the address has an account —
  // see handle_auth_password_forgot.
  return j.message || "If that email has an account, a reset link is on its way.";
}
