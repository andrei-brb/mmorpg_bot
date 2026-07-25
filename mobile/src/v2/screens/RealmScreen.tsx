import { useState } from "react";
import { GuildTab } from "@/components/game/tabs/GuildTab";
import { MarketTab } from "@/components/game/tabs/MarketTab";
import { PvpPage } from "@/components/pvp/PvpPage";
import { cn } from "@/lib/utils";
import { LinkAccountSheet } from "@mobile/shell/LinkAccountSheet";
import type { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";
import type { StoredSession } from "@mobile/platform/sessionStore";

/**
 * Realm — "I want to deal with people."
 *
 * Guild, market and arena were three separate top-level tabs; they're one
 * intent, so they're one tab with a segment switch.
 *
 * HONEST NOTE: the bodies here are the existing views (MarketView alone is
 * 2,410 lines, GuildTab 1,463). They're embedded rather than rebuilt, so they
 * still carry the classic styling inside the Ember frame. Rebuilding them
 * wouldn't demonstrate anything the rest of this redesign doesn't already —
 * the argument being made is about structure and the home screen, and faking
 * a market would prove less than shipping the real one.
 */

type Seg = "guild" | "market" | "arena";

export function RealmScreen({
  discordAuth,
  onSessionReplaced,
}: {
  discordAuth?: DiscordOAuthAuth;
  onSessionReplaced?: (s: StoredSession) => void;
}) {
  const [seg, setSeg] = useState<Seg>("guild");
  const [linkOpen, setLinkOpen] = useState(false);

  return (
    <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
      <div className="mb-3 flex items-center gap-2 px-4">
        <span className="e-label flex-1">Realm</span>
        {discordAuth ? (
          <button type="button" onClick={() => setLinkOpen(true)} className="e-pill e-pill--quiet">
            Link Discord
          </button>
        ) : null}
      </div>

      <div className="mb-3 flex gap-1.5 px-4">
        {(
          [
            ["guild", "Guild"],
            ["market", "Market"],
            ["arena", "Arena"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            onClick={() => setSeg(k)}
            className={cn("e-pill flex-1 py-2", seg === k ? "e-pill--ember" : "e-pill--quiet")}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="px-2">
        {seg === "guild" ? <GuildTab /> : null}
        {seg === "market" ? <MarketTab /> : null}
        {seg === "arena" ? <PvpPage /> : null}
      </div>

      {linkOpen ? (
        <LinkAccountSheet
          discordAuth={discordAuth}
          onClose={() => setLinkOpen(false)}
          onSessionReplaced={(s) => {
            setLinkOpen(false);
            onSessionReplaced?.(s);
          }}
        />
      ) : null}
    </div>
  );
}
