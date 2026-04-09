import type { QuestOfferPayload } from "@/lib/apiTypes";

export function QuestOfferModal({
  offer,
  busy,
  onAccept,
  onIgnore,
  onClose,
}: {
  offer: QuestOfferPayload;
  busy: boolean;
  onAccept: () => void | Promise<void>;
  onIgnore: () => void | Promise<void>;
  onClose: () => void;
}) {
  const rewards = offer.rewards || {};
  const objectives = offer.objectives || [];
  const hasRewards =
    Boolean(rewards.xp) ||
    Boolean(rewards.gold) ||
    Boolean(rewards.items?.length) ||
    Boolean(rewards.reputation && Object.keys(rewards.reputation).length);

  return (
    <div
      className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto p-3 sm:p-4 sm:items-center"
      style={{ background: "hsl(0 0% 0% / 0.7)", backdropFilter: "blur(4px)" }}
      role="dialog"
      aria-modal="true"
      aria-label="Quest offer"
      onClick={onClose}
    >
      <div
        className={`game-panel my-4 flex w-full max-w-[620px] max-h-[min(92dvh,720px)] flex-col${
          offer.lore_main ? " ring-2 ring-violet-500/45 shadow-[0_0_24px_hsl(270_50%_40%/0.25)]" : ""
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="game-panel-header shrink-0 flex items-center justify-between gap-2 flex-wrap">
          <span>{offer.lore_main ? "📜 Main story — Quest Offer" : "📜 Quest Offer"}</span>
          {offer.lore_main && (
            <span className="text-[9px] font-semibold uppercase tracking-wider text-violet-200/90">Cannot abandon</span>
          )}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-0.5 [-webkit-overflow-scrolling:touch]">
          <div className="p-4 space-y-3">
            <div>
              <div className="text-xs text-muted-foreground font-cinzel uppercase tracking-wider">NPC</div>
              <div className="font-cinzel font-semibold text-foreground">
                {(offer.npc_title ? `${offer.npc_title} ` : "") + (offer.npc_name || "Unknown")}
              </div>
            </div>

            {offer.intro && (
              <div
                className="text-xs p-3 rounded-sm"
                style={{ background: "hsl(228 18% 12% / 0.6)", border: "1px solid hsl(228 16% 22%)" }}
              >
                <div className="text-muted-foreground whitespace-pre-wrap font-crimson">{offer.intro}</div>
              </div>
            )}

            <div className="ornament-divider" />

            <div>
              <div className="text-xs text-muted-foreground font-cinzel uppercase tracking-wider">Quest</div>
              <div className="font-cinzel font-semibold text-foreground">{offer.quest_name || "Quest"}</div>
              {offer.quest_desc && <div className="text-xs text-muted-foreground mt-1 font-crimson">{offer.quest_desc}</div>}
              <div className="text-[10px] text-muted-foreground mt-2">
                {offer.level_req != null && (
                  <span>
                    Requires level <span className="text-foreground font-semibold">{offer.level_req}</span>
                  </span>
                )}
                {offer.time_limit_hours ? (
                  <span>
                    {offer.level_req != null ? " · " : ""}
                    Time limit: <span className="text-foreground font-semibold">{offer.time_limit_hours}h</span>
                  </span>
                ) : null}
              </div>
            </div>

            {objectives.length > 0 && (
              <>
                <div className="ornament-divider" />
                <div>
                  <div className="text-xs text-muted-foreground font-cinzel uppercase tracking-wider mb-2">Objectives</div>
                  <ul className="space-y-2">
                    {objectives.map((o, idx) => (
                      <li key={`${idx}`} className="text-xs">
                        <div className="text-foreground font-crimson">
                          <span className="text-muted-foreground mr-1">{idx + 1}.</span> {o.objective || "—"}
                        </div>
                        {o.hint && <div className="text-[10px] text-muted-foreground font-crimson mt-0.5">{o.hint}</div>}
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            )}

            {hasRewards && (
              <>
                <div className="ornament-divider" />
                <div>
                  <div className="text-xs text-muted-foreground font-cinzel uppercase tracking-wider mb-2">Rewards</div>
                  <div className="text-xs font-crimson text-foreground space-y-1">
                    {Boolean(rewards.xp) && <div>⭐ {Number(rewards.xp || 0).toLocaleString()} XP</div>}
                    {Boolean(rewards.gold) && <div>🪙 {Number(rewards.gold || 0).toLocaleString()} Gold</div>}
                    {Boolean(rewards.items?.length) && <div>🎁 Item reward</div>}
                    {rewards.reputation &&
                      Object.entries(rewards.reputation).map(([k, v]) => (
                        <div key={k}>
                          ⭐ +{v} {k.replace(/_/g, " ")} Rep
                        </div>
                      ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="shrink-0 border-t border-border p-3 flex items-center justify-end gap-2">
          <button type="button" className="game-btn-secondary text-xs" onClick={onClose} disabled={busy}>
            Close
          </button>
          <button
            type="button"
            className="text-xs px-3 py-2 rounded-sm border border-border hover:bg-muted/30"
            onClick={() => void onIgnore()}
            disabled={busy}
          >
            Ignore
          </button>
          <button type="button" className="game-btn-primary text-xs" onClick={() => void onAccept()} disabled={busy}>
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}

