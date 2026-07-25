import { useState } from "react";
import { cn } from "@/lib/utils";
import { ArenaPanel } from "@mobile/v2/parts/ArenaPanel";
import { GuildPanel } from "@mobile/v2/parts/GuildPanel";
import { MarketPanel } from "@mobile/v2/parts/MarketPanel";
import { LinkAccountSheet } from "@mobile/shell/LinkAccountSheet";
import type { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";
import type { StoredSession } from "@mobile/platform/sessionStore";

/**
 * Realm — "I want to deal with people."
 *
 * Guild, market and arena were three separate top-level tabs; they're one
 * intent, so they're one tab with a segment switch.
 *
 * All three are rebuilt in Ember over the real APIs — the everyday 80% of each
 * system. The weekly, officer-gated or rarely-touched parts (auctions, NPC shop,
 * trades; war council, guild tech, raids, hall chat; specific-player challenges
 * and full match history) stay in classic, and each panel says so rather than
 * pretending they don't exist.
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

      <div className="px-4">
        {seg === "guild" ? <GuildPanel /> : null}
        {seg === "market" ? <MarketPanel /> : null}
        {seg === "arena" ? <ArenaPanel /> : null}
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
