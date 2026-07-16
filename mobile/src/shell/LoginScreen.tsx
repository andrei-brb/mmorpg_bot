import { useState } from "react";
import { cn } from "@/lib/utils";
import type { AuthProvider } from "@/context/auth/types";
import { nativeLogin, nativeSignup, requestPasswordReset } from "@mobile/platform/authApi";
import type { StoredSession } from "@mobile/platform/sessionStore";

/**
 * The login screen. Mobile only — the Discord Activity authenticates silently
 * against its host and must never see this.
 *
 * Three ways in, all ending in the same place (a session token):
 *   - Sign in with a game account
 *   - Create a game account
 *   - Continue with Discord (the existing OAuth bounce)
 *
 * A game account is offered first, on purpose: the whole point of this work is
 * that Discord is optional.
 */

type Mode = "signin" | "signup" | "forgot";

export function LoginScreen({
  discordAuth,
  onAuthed,
}: {
  /** The existing DiscordOAuthAuth. Absent when VITE_DISCORD_CLIENT_ID isn't set. */
  discordAuth?: AuthProvider;
  onAuthed: (s: StoredSession) => void;
}) {
  const [mode, setMode] = useState<Mode>("signin");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [login, setLogin] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function run(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const submit = () =>
    run(async () => {
      if (mode === "signin") {
        const r = await nativeLogin(login.trim(), password);
        onAuthed({ token: r.token, provider: "native" });
      } else if (mode === "signup") {
        const r = await nativeSignup(username.trim(), email.trim(), password);
        onAuthed({ token: r.token, provider: "native" });
      } else {
        setNotice(await requestPasswordReset(email.trim()));
      }
    });

  const withDiscord = () =>
    run(async () => {
      if (!discordAuth) return;
      const s = await discordAuth.authenticate();
      onAuthed({ token: s.token, provider: "discord-oauth" });
    });

  const field =
    "w-full rounded-xl border border-gold/25 bg-black/40 px-3 py-2.5 text-sm text-foreground " +
    "placeholder:text-muted-foreground/60 focus:border-gold/60 focus:outline-none";

  return (
    <div
      className="flex min-h-[100dvh] flex-col px-6 font-body"
      style={{
        paddingTop: "calc(env(safe-area-inset-top) + 3rem)",
        paddingBottom: "calc(env(safe-area-inset-bottom) + 1.5rem)",
        background:
          "radial-gradient(ellipse at 50% 0%, hsl(271 40% 22%), hsl(264 26% 7%) 62%)",
      }}
    >
      <header className="mb-8 text-center">
        <h1 className="font-display text-3xl tracking-[0.22em] text-gold-bright">EMBERLONE</h1>
        <p className="mt-2 text-[11px] uppercase tracking-[0.3em] text-gold-dim">
          {mode === "signup" ? "Forge a new name" : mode === "forgot" ? "Recover your account" : "Return to the realm"}
        </p>
      </header>

      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        {mode === "signin" ? (
          <input
            className={field}
            placeholder="Username or email"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
            autoComplete="username"
            enterKeyHint="next"
          />
        ) : null}

        {mode === "signup" ? (
          <>
            <input
              className={field}
              placeholder="Username — this is how you sign in"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoCapitalize="none"
              autoCorrect="off"
              autoComplete="username"
            />
            <input
              className={field}
              placeholder="Email — only used to recover your account"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              autoCapitalize="none"
              autoCorrect="off"
              autoComplete="email"
            />
          </>
        ) : null}

        {mode === "forgot" ? (
          <input
            className={field}
            placeholder="Your email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            autoCapitalize="none"
            autoCorrect="off"
            autoComplete="email"
          />
        ) : null}

        {mode !== "forgot" ? (
          <input
            className={field}
            placeholder={mode === "signup" ? "Password — at least 8 characters" : "Password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            enterKeyHint="go"
          />
        ) : null}

        {error ? (
          <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="rounded-lg border border-gold/30 bg-gold/10 px-3 py-2 text-[12px] text-gold-bright">
            {notice}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={busy}
          className={cn(
            "w-full rounded-xl py-3 font-display text-sm tracking-[0.18em] transition-opacity",
            "bg-gradient-to-b from-[#F2D98A] to-[#C9A24B] text-[#221803]",
            "shadow-[0_4px_16px_-4px_rgba(232,197,106,0.55)]",
            busy && "opacity-60",
          )}
        >
          {busy
            ? "…"
            : mode === "signin"
              ? "SIGN IN"
              : mode === "signup"
                ? "CREATE ACCOUNT"
                : "SEND RESET LINK"}
        </button>
      </form>

      <div className="mt-4 flex justify-center gap-4 text-[12px]">
        {mode !== "signin" ? (
          <button type="button" className="text-muted-foreground underline" onClick={() => setMode("signin")}>
            Sign in
          </button>
        ) : null}
        {mode !== "signup" ? (
          <button type="button" className="text-muted-foreground underline" onClick={() => setMode("signup")}>
            Create account
          </button>
        ) : null}
        {mode === "signin" ? (
          <button type="button" className="text-muted-foreground underline" onClick={() => setMode("forgot")}>
            Forgot password
          </button>
        ) : null}
      </div>

      {discordAuth ? (
        <div className="mt-auto pt-8">
          <div className="mb-4 flex items-center gap-3">
            <span className="h-px flex-1 bg-gold/20" />
            <span className="text-[10px] uppercase tracking-[0.28em] text-gold-dim">or</span>
            <span className="h-px flex-1 bg-gold/20" />
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void withDiscord()}
            className={cn(
              "w-full rounded-xl border border-gold/30 py-3 text-sm text-foreground/90 transition-opacity",
              busy && "opacity-60",
            )}
          >
            Continue with Discord
          </button>
          <p className="mt-3 text-center text-[11px] leading-relaxed text-muted-foreground">
            Already play in Discord? Sign in that way and it's the same character — same gold, same gear.
          </p>
        </div>
      ) : null}
    </div>
  );
}
