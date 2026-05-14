import { useMemo, useState } from "react";
import type { EnhanceInfoPayload } from "@/lib/apiTypes";
import { ItemIcon } from "@/components/game/ItemIcon";
import { WomPanel } from "@/components/wom/WomUi";

interface EnhancableItem {
  id: string;
  name: string;
  template_id?: string | null;
  icon?: string | null;
  rarity: string;
  level: number;
  template_equip_slot?: string | null;
  equip_slot?: string | null;
}

export type BlacksmithProtection = "none" | "blessing" | "charm";

/** Matches `PROTECTION_ITEMS` in `services/blacksmith/blacksmith_service.py` (shop prices). */
const PROTECTION_SHOP: { key: string; label: string; price: number; emoji: string; hint: string }[] = [
  {
    key: "blessing_scroll",
    label: "Blessing Scroll",
    price: 10_000,
    emoji: "📜",
    hint: "Fail → downgrade instead of break",
  },
  {
    key: "safety_charm",
    label: "Safety Charm",
    price: 5_000,
    emoji: "🛡️",
    hint: "Guaranteed success +1–+5",
  },
  {
    key: "enhancement_fragment",
    label: "Enhancement Fragment",
    price: 2_000,
    emoji: "💎",
    hint: "+10% success each (max 3)",
  },
];

interface BlacksmithModalProps {
  item: EnhancableItem;
  /** From GET /api/game/item/enhance/info — real cost, rates, stocks. */
  enhancePayload: EnhanceInfoPayload | null;
  infoLoading: boolean;
  onClose: () => void;
  onEnhance: (protection: BlacksmithProtection, fragments: number) => void | Promise<void>;
  /** POST /api/game/blacksmith/buy-protection — optional; omit to hide shop row. */
  onBuyProtection?: (protectionKey: string, quantity: number) => void | Promise<void>;
}

const MAX_STACK_FRAGMENTS = 3;

function pctFromRate(rate: number | undefined): number {
  if (rate == null || Number.isNaN(rate)) return 0;
  const r = Number(rate);
  return r <= 1 ? Math.round(r * 1000) / 10 : Math.round(r * 10) / 10;
}

export function BlacksmithModal({
  item,
  enhancePayload,
  infoLoading,
  onClose,
  onEnhance,
  onBuyProtection,
}: BlacksmithModalProps) {
  const [protection, setProtection] = useState<BlacksmithProtection>("none");
  const [fragments, setFragments] = useState(0);
  const [enhancePending, setEnhancePending] = useState(false);
  const [buyPendingKey, setBuyPendingKey] = useState<string | null>(null);

  const info = enhancePayload?.info;
  const curLevel = info?.current_level ?? item.level;
  const nextLevel = info?.next_level;
  const nc = info?.next_config;
  const isMaxed = curLevel >= 10 || nextLevel == null || !nc;
  const charmUsable = nextLevel != null && nextLevel <= 5;

  const prot = enhancePayload?.protections ?? {};
  const blessingStock = prot.blessing_scroll ?? 0;
  const charmStock = prot.safety_charm ?? 0;
  const fragmentStock = prot.enhancement_fragment ?? 0;

  const canShatter = Boolean(nc?.can_break);

  const baseSuccessPct = useMemo(() => pctFromRate(nc?.success_rate), [nc?.success_rate]);

  const finalSuccessPct = useMemo(() => {
    if (protection === "charm" && charmUsable) return 100;
    let v = baseSuccessPct + fragments * 10;
    return Math.min(100, Math.round(v * 10) / 10);
  }, [baseSuccessPct, fragments, protection, charmUsable]);

  const handleEnhance = async () => {
    if (isMaxed || !nc || enhancePending || infoLoading) return;
    setEnhancePending(true);
    try {
      await Promise.resolve(onEnhance(protection, fragments));
    } finally {
      setEnhancePending(false);
    }
  };

  const handleBuy = async (key: string) => {
    if (!onBuyProtection || buyPendingKey || enhancePending || infoLoading) return;
    setBuyPendingKey(key);
    try {
      await Promise.resolve(onBuyProtection(key, 1));
    } finally {
      setBuyPendingKey(null);
    }
  };

  const loadError = enhancePayload && enhancePayload.ok === false;
  const cost = nc?.cost;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-3 sm:p-4 sm:items-center"
      style={{ background: "hsl(0 0% 0% / 0.7)", backdropFilter: "blur(4px)" }}
    >
      <WomPanel
        glow
        className="my-4 flex w-full max-w-[540px] max-h-[min(92dvh,680px)] flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="game-panel-header shrink-0">🔨 Blacksmith — Enhance</div>

        {infoLoading && (
          <p className="shrink-0 py-6 text-center text-sm text-muted-foreground">Loading enhancement data…</p>
        )}

        {!infoLoading && loadError && (
          <p className="shrink-0 py-4 text-sm text-destructive">{enhancePayload?.message || enhancePayload?.error || "Could not load enhancement info."}</p>
        )}

        {!infoLoading && !loadError && (
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-0.5 [-webkit-overflow-scrolling:touch]">
            <div className="flex items-center gap-3 mb-4">
              <div
                className="slot-filled w-12 h-12 text-2xl shrink-0"
                style={{ filter: "drop-shadow(0 1px 3px hsl(0 0% 0% / 0.5))" }}
              >
                {item.template_id ? (
                  <ItemIcon
                    item={{
                      // Minimal fields used by itemIcons helpers
                      id: item.id,
                      template_id: item.template_id,
                      name: item.name,
                      icon: item.icon ?? undefined,
                      template_equip_slot: item.template_equip_slot,
                      equip_slot: item.equip_slot,
                    } as any}
                    size={40}
                    className="mx-auto my-auto"
                  />
                ) : (
                  <span aria-hidden>{item.icon || "⚔️"}</span>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-cinzel font-semibold text-foreground">
                  {item.name} {curLevel > 0 && <span className="text-primary">+{curLevel}</span>}
                </div>
                {!isMaxed && nextLevel != null && (
                  <div className="text-xs text-muted-foreground mt-0.5">
                    <span className="text-foreground">+{curLevel}</span>
                    <span className="mx-1.5">→</span>
                    <span className="text-primary font-semibold">+{nextLevel}</span>
                  </div>
                )}
                {isMaxed && (
                  <div className="text-xs text-primary font-semibold mt-0.5">Maximum enhancement reached</div>
                )}
              </div>
            </div>

            {!isMaxed && nc && (
              <>
                <div className="flex gap-4 mb-3 text-xs flex-wrap">
                  <div>
                    <span className="text-muted-foreground">Cost: </span>
                    <span className="text-gold font-semibold">{cost != null ? cost.toLocaleString() : "—"} 🪙</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Base success: </span>
                    <span
                      className={`font-semibold ${
                        baseSuccessPct >= 70
                          ? "text-rarity-uncommon"
                          : baseSuccessPct >= 40
                            ? "text-primary"
                            : "text-destructive"
                      }`}
                    >
                      {baseSuccessPct}%
                    </span>
                  </div>
                </div>

                <div
                  className="text-xs mb-4 p-2 rounded-sm"
                  style={{
                    background: canShatter ? "hsl(0 60% 15% / 0.3)" : "hsl(120 40% 15% / 0.2)",
                    border: `1px solid ${canShatter ? "hsl(0 50% 30% / 0.4)" : "hsl(120 40% 30% / 0.3)"}`,
                  }}
                >
                  {canShatter ? (
                    <span className="text-destructive">
                      ⚠️ Failure may <strong>shatter</strong> the item unless protected (Blessing Scroll).
                    </span>
                  ) : (
                    <span className="text-rarity-uncommon">✓ Safe tier — failure will not destroy the item.</span>
                  )}
                </div>

                <div className="ornament-divider mb-4" />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                  <div>
                    <div className="text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground mb-2">
                      Protection
                    </div>
                    <div className="space-y-2">
                      <label
                        className={`flex items-start gap-2 p-2 rounded-sm cursor-pointer transition-all ${protection === "none" ? "bg-muted/60" : ""}`}
                        style={{
                          border: `1px solid ${protection === "none" ? "hsl(43 50% 35% / 0.5)" : "hsl(228 16% 20%)"}`,
                        }}
                      >
                        <input
                          type="radio"
                          name="protection"
                          checked={protection === "none"}
                          onChange={() => setProtection("none")}
                          className="mt-0.5 accent-[hsl(43,78%,50%)]"
                        />
                        <div>
                          <div className="text-xs text-foreground font-semibold">None</div>
                          <div className="text-[10px] text-muted-foreground">No protection applied</div>
                        </div>
                      </label>

                      <label
                        className={`flex items-start gap-2 p-2 rounded-sm cursor-pointer transition-all ${protection === "blessing" ? "bg-muted/60" : ""} ${blessingStock === 0 ? "opacity-50" : ""}`}
                        style={{
                          border: `1px solid ${protection === "blessing" ? "hsl(43 50% 35% / 0.5)" : "hsl(228 16% 20%)"}`,
                        }}
                      >
                        <input
                          type="radio"
                          name="protection"
                          checked={protection === "blessing"}
                          onChange={() => blessingStock > 0 && setProtection("blessing")}
                          disabled={blessingStock === 0}
                          className="mt-0.5 accent-[hsl(43,78%,50%)]"
                        />
                        <div className="flex-1">
                          <div className="text-xs text-foreground font-semibold">📜 Blessing Scroll</div>
                          <div className="text-[10px] text-muted-foreground">On fail when item can break → downgrade by 1 instead</div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-muted-foreground">
                              In inventory: <span className="text-foreground">{blessingStock}</span>
                            </span>
                            {onBuyProtection && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.preventDefault();
                                  void handleBuy("blessing_scroll");
                                }}
                                disabled={Boolean(buyPendingKey) || enhancePending}
                                className="text-[9px] px-1.5 py-0.5 rounded bg-primary/20 hover:bg-primary/30 text-primary border border-primary/40 transition"
                              >
                                {buyPendingKey === "blessing_scroll" ? "…" : "10,000 🪙"}
                              </button>
                            )}
                          </div>
                        </div>
                      </label>

                      <label
                        className={`flex items-start gap-2 p-2 rounded-sm cursor-pointer transition-all ${protection === "charm" ? "bg-muted/60" : ""} ${!charmUsable || charmStock === 0 ? "opacity-50" : ""}`}
                        style={{
                          border: `1px solid ${protection === "charm" ? "hsl(43 50% 35% / 0.5)" : "hsl(228 16% 20%)"}`,
                        }}
                      >
                        <input
                          type="radio"
                          name="protection"
                          checked={protection === "charm"}
                          onChange={() => charmUsable && charmStock > 0 && setProtection("charm")}
                          disabled={!charmUsable || charmStock === 0}
                          className="mt-0.5 accent-[hsl(43,78%,50%)]"
                        />
                        <div className="flex-1">
                          <div className="text-xs text-foreground font-semibold">🛡️ Safety Charm</div>
                          <div className="text-[10px] text-muted-foreground">Guarantees success (tiers +1–+5 only)</div>
                          {!charmUsable && <div className="text-[10px] text-destructive mt-0.5">Not usable at this tier</div>}
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-muted-foreground">
                              In inventory: <span className="text-foreground">{charmStock}</span>
                            </span>
                            {onBuyProtection && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.preventDefault();
                                  void handleBuy("safety_charm");
                                }}
                                disabled={Boolean(buyPendingKey) || enhancePending}
                                className="text-[9px] px-1.5 py-0.5 rounded bg-primary/20 hover:bg-primary/30 text-primary border border-primary/40 transition"
                              >
                                {buyPendingKey === "safety_charm" ? "…" : "5,000 🪙"}
                              </button>
                            )}
                          </div>
                        </div>
                      </label>
                    </div>
                  </div>

                  <div>
                    <div className="text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground mb-2">
                      Enhancement Fragments
                    </div>
                    <WomPanel bracket={false} glow={false} className="p-3">
                      <div className="text-xs text-muted-foreground mb-2">
                        Each fragment adds <span className="text-primary font-semibold">+10%</span> success (max {MAX_STACK_FRAGMENTS}).
                      </div>
                      <div className="mb-3">
                        <label className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider block mb-1">
                          Fragments to use
                        </label>
                        <select
                          value={fragments}
                          onChange={(e) =>
                            setFragments(Math.min(Number(e.target.value), Math.min(MAX_STACK_FRAGMENTS, fragmentStock)))
                          }
                          className="game-select"
                        >
                          {[0, 1, 2, 3].map((n) => (
                            <option key={n} value={n} disabled={n > fragmentStock || n > MAX_STACK_FRAGMENTS}>
                              {n} fragment{n !== 1 ? "s" : ""} (+{n * 10}%)
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">
                          In inventory: <span className="text-foreground">{fragmentStock}</span>
                        </span>
                        {onBuyProtection && (
                          <button
                            type="button"
                            onClick={() => void handleBuy("enhancement_fragment")}
                            disabled={Boolean(buyPendingKey) || enhancePending}
                            className="text-[9px] px-1.5 py-0.5 rounded bg-primary/20 hover:bg-primary/30 text-primary border border-primary/40 transition"
                          >
                            {buyPendingKey === "enhancement_fragment" ? "…" : "2,000 🪙"}
                          </button>
                        )}
                      </div>
                    </WomPanel>

                    <div
                      className="mt-3 p-2 rounded-sm text-center"
                      style={{
                        background: "linear-gradient(180deg, hsl(228 18% 14%) 0%, hsl(228 20% 10%) 100%)",
                        border: "1px solid hsl(228 16% 20%)",
                      }}
                    >
                      <div className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider mb-1">
                        Final success rate
                      </div>
                      <div
                        className={`text-xl font-cinzel font-bold ${
                          finalSuccessPct >= 70
                            ? "text-rarity-uncommon"
                            : finalSuccessPct >= 40
                              ? "text-primary"
                              : "text-destructive"
                        }`}
                        style={{ textShadow: "0 0 6px currentColor" }}
                      >
                        {finalSuccessPct}%
                      </div>
                    </div>
                  </div>
                </div>

                <div className="ornament-divider mb-4" />
              </>
            )}
          </div>
        )}

        <div
          className="mt-auto flex shrink-0 flex-wrap justify-end gap-2 border-t border-border/60 bg-background/95 py-3 pt-3 supports-[backdrop-filter]:backdrop-blur-sm"
          style={{ boxShadow: "0 -8px 24px hsl(0 0% 0% / 0.25)" }}
        >
          <button type="button" onClick={onClose} disabled={enhancePending} className="game-btn-secondary text-xs">
            Cancel
          </button>
          {!infoLoading && !isMaxed && nc && (
            <button
              type="button"
              onClick={() => void handleEnhance()}
              disabled={enhancePending || loadError}
              className="game-btn-primary text-xs"
            >
              {enhancePending ? "…" : "🔨 Enhance"}
            </button>
          )}
        </div>
      </WomPanel>
    </div>
  );
}
