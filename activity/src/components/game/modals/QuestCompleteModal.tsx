import type { QuestCompletionPayload } from "@/lib/apiTypes";

export function QuestCompleteModal({
  completion,
  busy,
  onContinue,
}: {
  completion: QuestCompletionPayload;
  busy: boolean;
  onContinue: () => void;
}) {
  const rewards = completion.rewards || {};
  const rep = rewards.reputation || {};
  const itemFailures = (rewards.item_failures || []).filter((x) => x?.template_id);
  const hasAny =
    Boolean(rewards.xp) ||
    Boolean(rewards.gold) ||
    Boolean(rewards.items?.length) ||
    Boolean(itemFailures.length) ||
    Boolean(Object.keys(rep).length);
  const items = (rewards.items || []).filter(Boolean);

  const prettyId = (s: string) =>
    String(s)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div
      className="fixed inset-0 z-[95] flex items-start justify-center overflow-y-auto p-3 sm:p-4 sm:items-center"
      style={{ background: "hsl(0 0% 0% / 0.7)", backdropFilter: "blur(4px)" }}
      role="dialog"
      aria-modal="true"
      aria-label="Quest completed"
      onClick={() => {
        if (!busy) onContinue();
      }}
    >
      <div
        className={`game-panel my-4 flex w-full max-w-[540px] max-h-[min(92dvh,640px)] flex-col${
          completion.lore_main ? " ring-2 ring-violet-500/45 shadow-[0_0_24px_hsl(270_50%_40%/0.25)]" : ""
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="game-panel-header shrink-0">
          {completion.lore_main ? "✅ Main story — Completed" : "✅ Quest Completed"}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-0.5 [-webkit-overflow-scrolling:touch]">
          <div className="p-4 space-y-3">
            <div className="text-sm text-foreground font-crimson">{completion.message || "Rewards granted."}</div>

            <div className="ornament-divider" />

            {!hasAny && <div className="text-xs text-muted-foreground font-crimson">No rewards.</div>}

            {hasAny && (
              <div className="space-y-1 text-sm">
                {Boolean(rewards.xp) && (
                  <div className="text-primary font-semibold" style={{ textShadow: "0 0 4px hsl(43 78% 50% / 0.2)" }}>
                    ⭐ +{Number(rewards.xp || 0).toLocaleString()} XP
                  </div>
                )}
                {Boolean(rewards.gold) && <div className="text-gold font-semibold">🪙 +{Number(rewards.gold || 0).toLocaleString()} Gold</div>}
                {Boolean(items.length) && (
                  <div className="text-foreground font-crimson">
                    <div>🎁 Item reward</div>
                    <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                      {items.map((tid) => (
                        <li key={tid}>- {prettyId(tid)}</li>
                      ))}
                    </ul>
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      Tip: check <span className="font-semibold">Hero → Inventory → Consumables & Upgrades</span> for quest items.
                    </div>
                  </div>
                )}
                {Boolean(itemFailures.length) && (
                  <div className="text-destructive font-crimson">
                    <div>⚠ Could not deliver</div>
                    <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                      {itemFailures.map((it, i) => (
                        <li key={`${it.template_id}-${i}`}>
                          - {prettyId(String(it.template_id || ""))}: {it.reason || "could not add"}
                        </li>
                      ))}
                    </ul>
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      Most common cause: inventory full. Free slots, then talk to the NPC again if needed.
                    </div>
                  </div>
                )}
                {Object.keys(rep).map((k) => (
                  <div key={k} className="text-foreground font-crimson">
                    ⭐ +{Number((rep as any)[k] || 0)} {String(k).replace(/_/g, " ")} Rep
                  </div>
                ))}
              </div>
            )}

            {completion.next_quest_available && completion.next_quest_blocked === "level_too_low" && (
              <div className="text-xs text-muted-foreground font-crimson">
                Next quest is available but your level is too low. Level up (Explore/Combat), then press <span className="font-semibold">Talk</span> to the same NPC again.
              </div>
            )}
          </div>
        </div>
        <div className="shrink-0 border-t border-border p-3 flex justify-end">
          <button type="button" className="game-btn-primary text-xs" disabled={busy} onClick={onContinue}>
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}

