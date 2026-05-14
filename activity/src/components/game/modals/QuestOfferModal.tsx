import { useEffect, useMemo, useState } from "react";
import type { QuestOfferPayload } from "@/lib/apiTypes";
import { publicBaseUrl } from "@/lib/gameApi";
import { classIconUrl } from "@/lib/classAndSpecIconUrl";
import { useTypewriter } from "@/hooks/useTypewriter";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

const NPC_FALLBACK_EMOJI = "💬";

function npcPortraitSrc(npcId: string | undefined): string {
  const id = (npcId || "unknown").trim() || "unknown";
  const base = publicBaseUrl();
  return `${base}assets/npcs/${encodeURIComponent(id)}.png?v=3`;
}

function playerInitials(name: string | undefined): string {
  const n = (name || "").trim();
  if (!n) return "?";
  const parts = n.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return n.slice(0, 2).toUpperCase();
}

export function QuestOfferModal({
  offer,
  busy,
  onAccept,
  onIgnore,
  onClose,
  playerAvatarUrl,
  playerName,
  playerClass,
}: {
  offer: QuestOfferPayload;
  busy: boolean;
  onAccept: () => void | Promise<void>;
  onIgnore: () => void | Promise<void>;
  onClose: () => void;
  playerAvatarUrl?: string | null;
  playerName?: string | null;
  playerClass?: string | null;
}) {
  const rewards = offer.rewards || {};
  const objectives = offer.objectives || [];
  const hasRewards =
    Boolean(rewards.xp) ||
    Boolean(rewards.gold) ||
    Boolean(rewards.items?.length) ||
    Boolean(rewards.reputation && Object.keys(rewards.reputation).length);

  const pages = useMemo(() => {
    const out: string[] = [];
    const intro = (offer.intro || "").trim();
    if (intro) out.push(intro);
    const name = (offer.quest_name || "Quest").trim();
    const desc = (offer.quest_desc || "").trim();
    const pitch = [name, desc].filter(Boolean).join("\n\n");
    if (pitch) out.push(pitch);
    if (out.length === 0) out.push("A quest is offered.");
    return out;
  }, [offer.intro, offer.quest_name, offer.quest_desc]);

  const resetKey = `${offer.quest_id || ""}|${offer.npc_id || ""}`;
  const tw = useTypewriter(pages, resetKey, { cps: 34 });

  const [phase, setPhase] = useState<"dialogue" | "briefing">("dialogue");
  const [npcImgFailed, setNpcImgFailed] = useState(false);

  useEffect(() => {
    setPhase("dialogue");
    setNpcImgFailed(false);
  }, [resetKey]);

  useEffect(() => {
    if (tw.allComplete && phase === "dialogue") setPhase("briefing");
  }, [tw.allComplete, phase]);

  const npcLabel = (offer.npc_title ? `${offer.npc_title} ` : "") + (offer.npc_name || "Unknown");
  const classKey = playerClass || "warrior";
  const classIcon = classIconUrl(classKey);

  const actionsEnabled = phase === "briefing" && !busy;

  return (
    <div
      className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto p-2 sm:p-4 sm:items-center"
      style={{ background: "hsl(0 0% 0% / 0.72)", backdropFilter: "blur(4px)" }}
      role="dialog"
      aria-modal="true"
      aria-label="Quest offer"
      onClick={onClose}
    >
      <div
        className={cn(
          "game-panel my-2 flex w-full max-w-[min(96vw,860px)] max-h-[min(94dvh,780px)] flex-col sm:my-4",
          offer.lore_main && "ring-2 ring-violet-500/45 shadow-[0_0_24px_hsl(270_50%_40%/0.25)]",
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="game-panel-header shrink-0 flex items-center justify-between gap-2 flex-wrap">
          <span>{offer.lore_main ? "📜 Main story — Quest offer" : "📜 Quest offer"}</span>
          {offer.lore_main && (
            <span className="text-[9px] font-semibold uppercase tracking-wider text-violet-200/90">Cannot abandon</span>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain [-webkit-overflow-scrolling:touch]">
          <div className="grid grid-cols-[minmax(4.5rem,1fr)_minmax(0,2.6fr)_minmax(4.5rem,1fr)] gap-1.5 p-2 sm:gap-2 sm:p-3">
            {/* NPC column */}
            <aside className="flex min-w-0 flex-col items-center gap-1 border border-border/60 bg-muted/10 p-1.5 sm:p-2">
              {/* Opaque dark matte: many NPC PNGs ship with white / checkerboard “transparency” art — blend into UI. */}
              <div
                className={cn(
                  "relative flex aspect-[3/4] w-full max-w-[120px] items-center justify-center overflow-hidden rounded-sm border border-border",
                  "bg-[hsl(222_28%_8%)] shadow-[inset_0_0_28px_hsl(0_0%_0%/0.55)]",
                )}
              >
                {offer.npc_id && !npcImgFailed ? (
                  <img
                    src={npcPortraitSrc(offer.npc_id)}
                    alt=""
                    className="relative z-[1] max-h-full max-w-full object-contain object-center"
                    onError={() => setNpcImgFailed(true)}
                  />
                ) : (
                  <div className="relative z-[1] flex h-full min-h-[5rem] w-full items-center justify-center text-4xl sm:min-h-[6rem] sm:text-5xl">
                    {NPC_FALLBACK_EMOJI}
                  </div>
                )}
                <div
                  className="pointer-events-none absolute inset-0 z-[2] rounded-[inherit] ring-1 ring-inset ring-white/[0.06]"
                  aria-hidden
                />
              </div>
              <div className="w-full text-center">
                <div className="font-cinzel text-[10px] font-semibold leading-tight text-foreground sm:text-xs">{npcLabel}</div>
              </div>
            </aside>

            {/* Center: dialogue + briefing */}
            <section className="flex min-w-0 flex-col gap-2">
              {phase === "dialogue" && (
                <button
                  type="button"
                  className={cn(
                    "min-h-[8rem] flex-1 rounded-sm border border-border/80 p-2 text-left font-crimson text-xs leading-relaxed text-foreground shadow-sm sm:min-h-[10rem] sm:p-3 sm:text-sm",
                    "cursor-pointer select-none transition-colors hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  )}
                  style={{ background: "hsl(228 18% 12% / 0.65)" }}
                  onClick={() => tw.skipOrAdvance()}
                  aria-label={tw.pageComplete ? "Continue dialogue" : "Show full dialogue text"}
                >
                  <span className="whitespace-pre-wrap">{tw.visibleText}</span>
                  {!tw.pageComplete && (
                    <span className="ml-0.5 inline-block animate-pulse text-violet-300" aria-hidden>
                      ▍
                    </span>
                  )}
                  {tw.pageComplete && tw.pageIndex < tw.pageCount - 1 && (
                    <div className="mt-2 text-[10px] text-muted-foreground">Click to continue…</div>
                  )}
                </button>
              )}

              {phase === "briefing" && (
                <div className="space-y-3 rounded-sm border border-border/60 p-2 sm:p-3" style={{ background: "hsl(228 18% 10% / 0.5)" }}>
                  <div>
                    <div className="text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground">Quest</div>
                    <div className="font-cinzel text-sm font-semibold text-foreground">{offer.quest_name || "Quest"}</div>
                    {offer.quest_desc && (
                      <div className="mt-1 font-crimson text-xs text-muted-foreground whitespace-pre-wrap">{offer.quest_desc}</div>
                    )}
                    <div className="mt-2 font-crimson text-[10px] text-muted-foreground">
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
                        <div className="mb-1.5 text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground">Objectives</div>
                        <ul className="space-y-2">
                          {objectives.map((o, idx) => (
                            <li key={`${idx}`} className="text-xs">
                              <div className="font-crimson text-foreground">
                                <span className="mr-1 text-muted-foreground">{idx + 1}.</span> {o.objective || "—"}
                              </div>
                              {o.hint && <div className="mt-0.5 font-crimson text-[10px] text-muted-foreground">{o.hint}</div>}
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
                        <div className="mb-1.5 text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground">Rewards</div>
                        <div className="space-y-1 font-crimson text-xs text-foreground">
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
              )}
            </section>

            {/* Player column */}
            <aside className="flex min-w-0 flex-col items-center gap-1 border border-border/60 bg-muted/10 p-1.5 sm:p-2">
              <Avatar className="h-[4.5rem] w-[4.5rem] border border-border sm:h-24 sm:w-24">
                {playerAvatarUrl ? <AvatarImage src={playerAvatarUrl} alt="" className="object-cover" /> : null}
                <AvatarFallback className="bg-muted text-lg font-cinzel font-semibold">
                  {playerAvatarUrl ? (
                    playerInitials(playerName || undefined)
                  ) : (
                    <img src={classIcon} alt="" className="h-10 w-10 object-contain sm:h-12 sm:w-12" />
                  )}
                </AvatarFallback>
              </Avatar>
              <div className="w-full text-center">
                <div className="font-cinzel text-[10px] font-semibold leading-tight text-foreground sm:text-xs">
                  {(playerName || "You").trim()}
                </div>
              </div>
            </aside>
          </div>
        </div>

        <div className="shrink-0 space-y-1 border-t border-border p-2 sm:p-3">
          {phase === "dialogue" && (
            <p className="text-center text-[10px] text-muted-foreground">
              Click the dialogue panel to reveal text or continue. Accept and Decline unlock when the briefing appears.
            </p>
          )}
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button type="button" className="game-btn-secondary text-xs" onClick={onClose} disabled={busy}>
              Close
            </button>
            <button
              type="button"
              className="text-xs px-3 py-2 rounded-sm border border-border hover:bg-muted/30 disabled:pointer-events-none disabled:opacity-40"
              onClick={() => void onIgnore()}
              disabled={!actionsEnabled}
              title={!actionsEnabled ? "Finish the dialogue first" : undefined}
            >
              Decline
            </button>
            <button
              type="button"
              className="game-btn-primary text-xs disabled:pointer-events-none disabled:opacity-40"
              onClick={() => void onAccept()}
              disabled={!actionsEnabled}
              title={!actionsEnabled ? "Finish the dialogue first" : undefined}
            >
              Accept
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
