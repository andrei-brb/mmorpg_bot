import { useState } from "react";
import { toast } from "sonner";

interface EnhancableItem {
  name: string;
  icon: string;
  rarity: string;
  level: number; // current +N
}

interface BlacksmithModalProps {
  item: EnhancableItem;
  onClose: () => void;
  onEnhance: (newLevel: number) => void;
}

const MAX_ENHANCEMENT = 10;
const SHATTER_THRESHOLD = 6; // +6 and above can shatter

const TIER_DATA: Record<number, { cost: number; baseChance: number }> = {
  1: { cost: 50, baseChance: 95 },
  2: { cost: 120, baseChance: 90 },
  3: { cost: 250, baseChance: 85 },
  4: { cost: 500, baseChance: 75 },
  5: { cost: 1000, baseChance: 65 },
  6: { cost: 2000, baseChance: 50 },
  7: { cost: 4000, baseChance: 40 },
  8: { cost: 7500, baseChance: 30 },
  9: { cost: 12000, baseChance: 20 },
  10: { cost: 20000, baseChance: 10 },
};

type ProtectionType = "none" | "blessing" | "charm";

export function BlacksmithModal({ item, onClose, onEnhance }: BlacksmithModalProps) {
  const [protection, setProtection] = useState<ProtectionType>("none");
  const [fragments, setFragments] = useState(0);
  const [blessingStock, setBlessingStock] = useState(2);
  const [charmStock, setCharmStock] = useState(1);
  const [fragmentStock, setFragmentStock] = useState(5);

  const nextLevel = item.level + 1;
  const tier = TIER_DATA[nextLevel];
  const isMaxed = item.level >= MAX_ENHANCEMENT;
  const canShatter = nextLevel >= SHATTER_THRESHOLD;
  const charmUsable = nextLevel <= 5;
  const successChance = Math.min(100, tier?.baseChance + fragments * 10);

  const handleEnhance = () => {
    if (isMaxed || !tier) return;

    // Use up protection / fragments
    if (protection === "blessing" && blessingStock > 0) setBlessingStock((s) => s - 1);
    if (protection === "charm" && charmStock > 0) setCharmStock((s) => s - 1);
    if (fragments > 0) setFragmentStock((s) => Math.max(0, s - fragments));

    const roll = Math.random() * 100;
    if (roll < successChance) {
      toast("✨ Enhancement Success!", {
        description: `${item.name} is now +${nextLevel}!`,
      });
      onEnhance(nextLevel);
    } else {
      if (canShatter && protection === "none") {
        toast("💥 Item Shattered!", {
          description: `${item.name} was destroyed in the attempt.`,
        });
        onClose();
      } else if (canShatter && protection === "blessing") {
        const downgraded = Math.max(0, item.level - 1);
        toast("🛡️ Blessing Activated — Downgraded", {
          description: `${item.name} dropped to +${downgraded} instead of shattering.`,
        });
        onEnhance(downgraded);
      } else {
        toast("❌ Enhancement Failed", {
          description: `${item.name} remains at +${item.level}. No damage done.`,
        });
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'hsl(0 0% 0% / 0.7)', backdropFilter: 'blur(4px)' }}>
      <div className="game-panel w-full max-w-[540px]" onClick={(e) => e.stopPropagation()}>
        <div className="game-panel-header">🔨 Blacksmith — Enhance</div>

        {/* Item info */}
        <div className="flex items-center gap-3 mb-4">
          <div className="slot-filled w-12 h-12 text-2xl shrink-0"
            style={{ filter: 'drop-shadow(0 1px 3px hsl(0 0% 0% / 0.5))' }}>
            {item.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-cinzel font-semibold text-foreground">
              {item.name} {item.level > 0 && <span className="text-primary">+{item.level}</span>}
            </div>
            {!isMaxed && (
              <div className="text-xs text-muted-foreground mt-0.5">
                <span className="text-foreground">+{item.level}</span>
                <span className="mx-1.5">→</span>
                <span className="text-primary font-semibold">+{nextLevel}</span>
              </div>
            )}
            {isMaxed && (
              <div className="text-xs text-primary font-semibold mt-0.5">Maximum enhancement reached</div>
            )}
          </div>
        </div>

        {!isMaxed && tier && (
          <>
            {/* Cost & chance */}
            <div className="flex gap-4 mb-3 text-xs">
              <div>
                <span className="text-muted-foreground">Cost: </span>
                <span className="text-gold font-semibold">{tier.cost.toLocaleString()} 🪙</span>
              </div>
              <div>
                <span className="text-muted-foreground">Success: </span>
                <span className={`font-semibold ${successChance >= 70 ? 'text-rarity-uncommon' : successChance >= 40 ? 'text-primary' : 'text-destructive'}`}>
                  {successChance}%
                </span>
              </div>
            </div>

            {/* Risk line */}
            <div className="text-xs mb-4 p-2 rounded-sm"
              style={{
                background: canShatter
                  ? 'hsl(0 60% 15% / 0.3)'
                  : 'hsl(120 40% 15% / 0.2)',
                border: `1px solid ${canShatter ? 'hsl(0 50% 30% / 0.4)' : 'hsl(120 40% 30% / 0.3)'}`,
              }}>
              {canShatter ? (
                <span className="text-destructive">⚠️ Failure may <strong>shatter</strong> the item unless protected.</span>
              ) : (
                <span className="text-rarity-uncommon">✓ Safe tier — failure will not destroy the item.</span>
              )}
            </div>

            <div className="ornament-divider mb-4" />

            {/* Two columns: Protection + Fragments */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              {/* Protection */}
              <div>
                <div className="text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground mb-2">Protection</div>
                <div className="space-y-2">
                  {/* None */}
                  <label className={`flex items-start gap-2 p-2 rounded-sm cursor-pointer transition-all ${protection === 'none' ? 'bg-muted/60' : ''}`}
                    style={{ border: `1px solid ${protection === 'none' ? 'hsl(43 50% 35% / 0.5)' : 'hsl(228 16% 20%)'}` }}>
                    <input type="radio" name="protection" checked={protection === 'none'} onChange={() => setProtection('none')}
                      className="mt-0.5 accent-[hsl(43,78%,50%)]" />
                    <div>
                      <div className="text-xs text-foreground font-semibold">None</div>
                      <div className="text-[10px] text-muted-foreground">No protection applied</div>
                    </div>
                  </label>

                  {/* Blessing Scroll */}
                  <label className={`flex items-start gap-2 p-2 rounded-sm cursor-pointer transition-all ${protection === 'blessing' ? 'bg-muted/60' : ''} ${blessingStock === 0 ? 'opacity-50' : ''}`}
                    style={{ border: `1px solid ${protection === 'blessing' ? 'hsl(43 50% 35% / 0.5)' : 'hsl(228 16% 20%)'}` }}>
                    <input type="radio" name="protection" checked={protection === 'blessing'}
                      onChange={() => blessingStock > 0 && setProtection('blessing')}
                      disabled={blessingStock === 0}
                      className="mt-0.5 accent-[hsl(43,78%,50%)]" />
                    <div className="flex-1">
                      <div className="text-xs text-foreground font-semibold">📜 Blessing Scroll</div>
                      <div className="text-[10px] text-muted-foreground">On shatter → downgrade by 1 instead</div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] text-muted-foreground">Stock: <span className="text-foreground">{blessingStock}</span></span>
                        <button onClick={(e) => { e.preventDefault(); setBlessingStock(s => s + 1); toast("Purchased Blessing Scroll (fake)"); }}
                          className="text-[9px] text-primary hover:underline">Buy 1</button>
                      </div>
                    </div>
                  </label>

                  {/* Safety Charm */}
                  <label className={`flex items-start gap-2 p-2 rounded-sm cursor-pointer transition-all ${protection === 'charm' ? 'bg-muted/60' : ''} ${!charmUsable || charmStock === 0 ? 'opacity-50' : ''}`}
                    style={{ border: `1px solid ${protection === 'charm' ? 'hsl(43 50% 35% / 0.5)' : 'hsl(228 16% 20%)'}` }}>
                    <input type="radio" name="protection" checked={protection === 'charm'}
                      onChange={() => charmUsable && charmStock > 0 && setProtection('charm')}
                      disabled={!charmUsable || charmStock === 0}
                      className="mt-0.5 accent-[hsl(43,78%,50%)]" />
                    <div className="flex-1">
                      <div className="text-xs text-foreground font-semibold">🛡️ Safety Charm</div>
                      <div className="text-[10px] text-muted-foreground">Guarantees success (+1 – +5 only)</div>
                      {!charmUsable && <div className="text-[10px] text-destructive mt-0.5">Not usable at this tier</div>}
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] text-muted-foreground">Stock: <span className="text-foreground">{charmStock}</span></span>
                        <button onClick={(e) => { e.preventDefault(); setCharmStock(s => s + 1); toast("Purchased Safety Charm (fake)"); }}
                          className="text-[9px] text-primary hover:underline">Buy 1</button>
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              {/* Fragments */}
              <div>
                <div className="text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground mb-2">Enhancement Fragments</div>
                <div className="game-panel p-3">
                  <div className="text-xs text-muted-foreground mb-2">Each fragment adds <span className="text-primary font-semibold">+10%</span> success (max 3).</div>
                  <div className="mb-3">
                    <label className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider block mb-1">Fragments to use</label>
                    <select value={fragments}
                      onChange={(e) => setFragments(Math.min(Number(e.target.value), fragmentStock))}
                      className="game-select">
                      {[0, 1, 2, 3].map((n) => (
                        <option key={n} value={n} disabled={n > fragmentStock}>
                          {n} fragment{n !== 1 ? 's' : ''} (+{n * 10}%)
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                    <span>Stock: <span className="text-foreground">{fragmentStock}</span></span>
                    <button onClick={() => { setFragmentStock(s => s + 1); toast("Purchased 1 fragment (fake)"); }}
                      className="text-primary hover:underline">Buy 1</button>
                    <button onClick={() => { setFragmentStock(s => s + 3); toast("Purchased 3 fragments (fake)"); }}
                      className="text-primary hover:underline">Buy 3</button>
                  </div>
                </div>

                {/* Success preview */}
                <div className="mt-3 p-2 rounded-sm text-center"
                  style={{
                    background: 'linear-gradient(180deg, hsl(228 18% 14%) 0%, hsl(228 20% 10%) 100%)',
                    border: '1px solid hsl(228 16% 20%)',
                  }}>
                  <div className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider mb-1">Final Success Rate</div>
                  <div className={`text-xl font-cinzel font-bold ${successChance >= 70 ? 'text-rarity-uncommon' : successChance >= 40 ? 'text-primary' : 'text-destructive'}`}
                    style={{ textShadow: '0 0 6px currentColor' }}>
                    {protection === 'charm' && charmUsable ? '100' : successChance}%
                  </div>
                </div>
              </div>
            </div>

            <div className="ornament-divider mb-4" />
          </>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="game-btn-secondary text-xs">Cancel</button>
          {!isMaxed && (
            <button onClick={handleEnhance} className="game-btn-primary text-xs">
              🔨 Enhance
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
