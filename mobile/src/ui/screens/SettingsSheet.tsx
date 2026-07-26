import { useEffect, useState } from "react";
import { remindersEnabled, setRemindersEnabled } from "@mobile/platform/notifications";
import { disablePush, enablePush, pushSupported } from "@mobile/platform/pushRegistration";
import { useGameSession } from "@/context/GameSessionContext";
import { toast } from "sonner";

/**
 * Settings, including the way back to the classic UI.
 *
 * The switch is intentionally prominent and framed as an experiment rather than
 * a preference — this design is something to look at and judge, not the shipped
 * game.
 */

function Row({
  title,
  detail,
  right,
  onClick,
}: {
  title: string;
  detail?: string;
  right?: React.ReactNode;
  onClick?: () => void;
}) {
  const Cmp = onClick ? "button" : "div";
  return (
    <Cmp
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className="e-card flex w-full items-center gap-3 p-3.5 text-left"
    >
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-semibold" style={{ color: "var(--a-100)" }}>
          {title}
        </div>
        {detail ? (
          <div className="mt-0.5 text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
            {detail}
          </div>
        ) : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </Cmp>
  );
}

export function SettingsSheet({
  onClose,
  onSignOut,
}: {
  onClose: () => void;
  onSignOut?: () => void;
}) {
  const [remind, setRemind] = useState(false);
  const { accessToken, guildId } = useGameSession();
  // Remote push. The permission prompt is deliberately deferred to this toggle:
  // iOS asks once, and a prompt shown before the player knows what the game is
  // gets denied close to permanently.
  const [pushOn, setPushOn] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);

  async function togglePush() {
    if (!accessToken || pushBusy) return;
    setPushBusy(true);
    try {
      if (pushOn) {
        await disablePush(accessToken, guildId);
        setPushOn(false);
        return;
      }
      const r = await enablePush(accessToken, guildId);
      if (r === "enabled") {
        setPushOn(true);
        toast.success("Alerts on.");
      } else if (r === "denied") {
        toast.error("iOS is blocking notifications for this app — turn them on in Settings.");
      } else if (r === "unsupported") {
        toast.error("Alerts only work in the installed app.");
      } else {
        toast.error("Could not turn alerts on. Try again in a moment.");
      }
    } finally {
      setPushBusy(false);
    }
  }

  useEffect(() => {
    void remindersEnabled().then(setRemind);
  }, []);

  return (
    <>
      <button
        type="button"
        aria-label="Close settings"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
      />
      <div
        className="e-sheet e-scroll fixed inset-x-0 bottom-0 z-50 max-h-[82dvh] px-4"
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
      >
        <div className="e-grabber" />
        <h2 className="e-display mb-4 text-base" style={{ color: "var(--e-300)" }}>
          Settings
        </h2>

        <div className="space-y-4">
          <section>
            <div className="e-label mb-2">Notifications</div>
            <Row
              title="Daily reminder"
              detail="A nudge when your dailies reset — only if you've been away a day."
              right={
                <button
                  type="button"
                  onClick={() => {
                    const next = !remind;
                    setRemind(next);
                    void setRemindersEnabled(next);
                  }}
                  className="e-pill"
                  style={{
                    background: remind ? "rgba(255,122,47,0.18)" : "var(--n-700)",
                    border: `1px solid ${remind ? "rgba(255,122,47,0.5)" : "var(--n-500)"}`,
                    color: remind ? "var(--e-300)" : "var(--a-500)",
                  }}
                >
                  {remind ? "On" : "Off"}
                </button>
              }
            />
          </section>

          {pushSupported() ? (
            <section>
              <div className="e-label mb-2">Alerts</div>
              <Row
                title="Whispers and guild news"
                detail="Reach you even when the app is closed. Asked for only when you turn it on."
                right={
                  <button
                    type="button"
                    disabled={pushBusy}
                    onClick={() => void togglePush()}
                    className="e-pill"
                    style={{
                      background: pushOn ? "rgba(255,122,47,0.18)" : "var(--n-700)",
                      border: `1px solid ${pushOn ? "rgba(255,122,47,0.5)" : "var(--n-500)"}`,
                      color: pushOn ? "var(--e-300)" : "var(--a-500)",
                    }}
                  >
                    {pushBusy ? "…" : pushOn ? "On" : "Off"}
                  </button>
                }
              />
            </section>
          ) : null}

          {onSignOut ? (
            <section>
              <div className="e-label mb-2">Account</div>
              <button type="button" onClick={onSignOut} className="e-btn e-btn--quiet w-full">
                Sign out
              </button>
            </section>
          ) : null}
        </div>

        <button type="button" onClick={onClose} className="e-btn e-btn--quiet mt-4 w-full">
          Close
        </button>
      </div>
    </>
  );
}
