import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useGameSession } from "@/context/GameSessionContext";
import {
  getLinkStatus,
  linkDiscord,
  LinkConflict,
  resolveLink,
  type CharacterSummary,
  type LinkStatus,
} from "@mobile/platform/authApi";
import type { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";
import type { StoredSession } from "@mobile/platform/sessionStore";

/**
 * Attach a Discord account to the game account you're signed in as (or see
 * what's already attached).
 *
 * The hard case is the conflict: that Discord account already has its own
 * character. Nothing is merged and nothing is deleted — the player picks one,
 * and the other stays exactly as it is, just unreachable by that login. The
 * copy says so, because "abandoned" and "deleted" feel identical in the moment
 * and only one of them is true.
 */

function CharacterCard({
  c,
  label,
  selected,
  onSelect,
}: {
  c: CharacterSummary | null;
  label: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-xl border p-3 text-left transition-colors",
        selected ? "border-gold bg-gold/10" : "border-border bg-black/25",
      )}
    >
      <div className="mb-1 text-[9px] uppercase tracking-[0.24em] text-gold-dim">{label}</div>
      {c ? (
        <>
          <div className="font-display text-sm text-gold-bright">{c.name}</div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            Level {c.level}
            {c.class ? ` · ${String(c.class).replace(/_/g, " ")}` : ""}
          </div>
          <div className="mt-1 text-[11px] tabular-nums text-foreground/80">
            🪙 {c.gold.toLocaleString()}
          </div>
        </>
      ) : (
        <div className="text-[11px] text-muted-foreground">No character yet</div>
      )}
    </button>
  );
}

export function LinkAccountSheet({
  discordAuth,
  onClose,
  onSessionReplaced,
}: {
  discordAuth?: DiscordOAuthAuth;
  onClose: () => void;
  /** keep="other" makes you a different player — the shell must swap the token. */
  onSessionReplaced: (s: StoredSession) => void;
}) {
  const { accessToken } = useGameSession();
  const [status, setStatus] = useState<LinkStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<LinkConflict | null>(null);
  const [keep, setKeep] = useState<"current" | "other">("current");
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void getLinkStatus(accessToken)
      .then((s) => !cancelled && setStatus(s))
      .catch(() => !cancelled && setStatus(null));
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  const startLink = useCallback(async () => {
    if (!accessToken || !discordAuth || busy) return;
    setBusy(true);
    setError(null);
    try {
      // Stop at the code: exchanging it here would sign us in AS the Discord
      // account instead of attaching it.
      const { code, redirectUri } = await discordAuth.authorize();
      await linkDiscord(accessToken, code, redirectUri);
      const s = await getLinkStatus(accessToken);
      setStatus(s);
    } catch (e) {
      if (e instanceof LinkConflict) setConflict(e);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [accessToken, discordAuth, busy]);

  const applyChoice = useCallback(async () => {
    if (!accessToken || !conflict || busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await resolveLink(accessToken, conflict.pickToken, keep);
      if (r.token) {
        // We are literally a different player now.
        onSessionReplaced({ token: r.token, provider: "native" });
        return;
      }
      setConflict(null);
      setConfirming(false);
      setStatus(await getLinkStatus(accessToken));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [accessToken, conflict, keep, busy, onSessionReplaced]);

  const linked = status?.providers?.includes("discord") ?? false;
  const losing = keep === "current" ? conflict?.other : conflict?.current;

  return (
    <>
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
      />
      <div
        className="fixed inset-x-0 bottom-0 z-50 max-h-[80dvh] overflow-y-auto rounded-t-2xl border-t border-gold/40 px-4 pt-3"
        style={{
          background: "linear-gradient(180deg, hsl(265 26% 15%), hsl(264 27% 9%))",
          paddingBottom: "calc(1rem + env(safe-area-inset-bottom))",
        }}
        role="dialog"
        aria-modal="true"
        aria-label="Link a Discord account"
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-gold/30" />

        {!conflict ? (
          <>
            <h2 className="mb-1 font-display text-sm tracking-[0.1em] text-gold-bright">Your account</h2>
            <p className="mb-4 text-[11px] leading-relaxed text-muted-foreground">
              {status?.username ? (
                <>
                  Signed in as <span className="text-foreground">{status.username}</span>.{" "}
                </>
              ) : null}
              {linked
                ? "Discord is linked — you can sign in either way and it's the same character."
                : "Link Discord and you can sign in either way. Same character, same gold, same gear."}
            </p>

            {status && !status.email_verified && status.has_password ? (
              <p className="mb-3 rounded-lg border border-gold/30 bg-gold/5 px-3 py-2 text-[11px] text-gold-bright">
                Your email isn't confirmed yet — until it is, you can't recover this account if you
                forget your password.
              </p>
            ) : null}

            {error ? (
              <p className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-[11px] text-destructive">
                {error}
              </p>
            ) : null}

            {linked ? (
              <div className="rounded-xl border border-border px-3 py-2.5 text-[12px] text-muted-foreground">
                ✓ Discord linked
              </div>
            ) : discordAuth ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void startLink()}
                className={cn(
                  "w-full rounded-xl border border-gold/40 py-3 text-sm text-foreground/90",
                  busy && "opacity-60",
                )}
              >
                {busy ? "Opening Discord…" : "Link Discord"}
              </button>
            ) : (
              <p className="text-[11px] text-muted-foreground">Discord linking isn't configured.</p>
            )}
          </>
        ) : (
          <>
            <h2 className="mb-1 font-display text-sm tracking-[0.1em] text-gold-bright">
              Two characters
            </h2>
            <p className="mb-4 text-[11px] leading-relaxed text-muted-foreground">
              That Discord account already has its own character. Choose which one to keep — the
              other isn't deleted, it just won't be reachable from this login.
            </p>

            <div className="space-y-2">
              <CharacterCard
                c={conflict.current}
                label="This account"
                selected={keep === "current"}
                onSelect={() => setKeep("current")}
              />
              <CharacterCard
                c={conflict.other}
                label="The Discord account"
                selected={keep === "other"}
                onSelect={() => setKeep("other")}
              />
            </div>

            {error ? (
              <p className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-[11px] text-destructive">
                {error}
              </p>
            ) : null}

            {!confirming ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => setConfirming(true)}
                className="mt-4 w-full rounded-xl bg-gradient-to-b from-[#F2D98A] to-[#C9A24B] py-3 font-display text-sm tracking-[0.14em] text-[#221803]"
              >
                KEEP {keep === "current" ? "THIS CHARACTER" : "THE DISCORD CHARACTER"}
              </button>
            ) : (
              <div className="mt-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3">
                <p className="mb-3 text-[11px] leading-relaxed text-foreground">
                  Keeping <span className="text-gold-bright">{(keep === "current" ? conflict.current : conflict.other)?.name ?? "this character"}</span>.
                  {losing ? (
                    <>
                      {" "}
                      <span className="text-destructive">{losing.name}</span> (level {losing.level},{" "}
                      {losing.gold.toLocaleString()} gold) will no longer be reachable.
                    </>
                  ) : null}
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setConfirming(false)}
                    className="flex-1 rounded-lg border border-border py-2 text-[12px] text-muted-foreground"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void applyChoice()}
                    className={cn(
                      "flex-1 rounded-lg bg-destructive py-2 text-[12px] font-semibold text-white",
                      busy && "opacity-60",
                    )}
                  >
                    {busy ? "…" : "Confirm"}
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        <button
          type="button"
          onClick={onClose}
          className="mt-3 w-full rounded-lg border border-border py-2 text-[12px] text-muted-foreground"
        >
          Close
        </button>
      </div>
    </>
  );
}
