import { useState, useCallback, useMemo } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { ItemIcon } from "../ItemIcon";
import { calculateMarketPrice } from "@/lib/gameApi";
import type { InvRow } from "@/lib/apiTypes";

const RARITY_COLORS: Record<string, string> = {
  common: "text-rarity-common border-rarity-common/40",
  uncommon: "text-rarity-uncommon border-rarity-uncommon/40",
  rare: "text-rarity-rare border-rarity-rare/40",
  epic: "text-rarity-epic border-rarity-epic/40",
  legendary: "text-rarity-legendary border-rarity-legendary/40",
};

const RARITY_BG: Record<string, string> = {
  common: "hsl(0 0% 65% / 0.06)",
  uncommon: "hsl(120 38% 46% / 0.06)",
  rare: "hsl(210 65% 52% / 0.06)",
  epic: "hsl(268 55% 58% / 0.06)",
  legendary: "hsl(43 85% 52% / 0.08)",
};

const RARITY_MULTIPLIERS: Record<string, number> = {
  common: 3.0,
  uncommon: 4.5,
  rare: 7.0,
  epic: 10.0,
  legendary: 15.0,
};

interface ListItemModalProps {
  item: InvRow;
  onClose: () => void;
  onSuccess: () => void;
}

export function ListItemModal({ item, onClose, onSuccess }: ListItemModalProps) {
  const { listItemOnMarket } = useGameSession();
  const [listPrice, setListPrice] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(false);

  const rarity = (item.rarity || "common").toLowerCase();
  const rarityMult = RARITY_MULTIPLIERS[rarity] || 3.0;
  const enhancement = 1.0 + ((item.enhancement_level || 0) * 0.15);

  // Calculate suggested price
  // Use a base of 50g for items without vendor_buy info
  const basePrice = 50;
  const suggestedPrice = Math.round(basePrice * rarityMult * enhancement);

  // Initialize with suggested price on first render
  useMemo(() => {
    if (listPrice === 0) {
      setListPrice(suggestedPrice);
    }
  }, []);

  const priceWarning = useMemo(() => {
    if (listPrice <= 0) return "Price must be greater than 0";
    if (listPrice < suggestedPrice * 0.5) return "Price is very low (below 50% of suggested)";
    if (listPrice > suggestedPrice * 3) return "Price is very high (above 300% of suggested)";
    return "";
  }, [listPrice, suggestedPrice]);

  const handleList = useCallback(async () => {
    if (listPrice <= 0) {
      toast.error("Invalid price", { description: "Price must be greater than 0" });
      return;
    }

    setIsLoading(true);
    try {
      const res = await listItemOnMarket(item.id, listPrice);
      if (res.ok) {
        toast.success("Item listed!", { description: `Listed for ${listPrice}g` });
        onSuccess();
      } else {
        toast.error("Listing failed", { description: res.message || "Unknown error" });
      }
    } catch (e) {
      toast.error("Error", { description: String(e) });
    } finally {
      setIsLoading(false);
    }
  }, [item.id, listPrice, listItemOnMarket, onSuccess]);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      style={{ background: "hsl(0 0% 0% / 0.7)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="game-panel w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="game-panel-header">List Item on Marketplace</div>

        {/* Item Display */}
        <div className="mb-4 p-3 border border-border/40 rounded-sm flex gap-3">
          <div
            className="shrink-0 w-16 h-16 rounded-sm flex items-center justify-center"
            style={{ background: RARITY_BG[rarity] || "hsl(0 0% 65% / 0.06)" }}
          >
            <ItemIcon item={item} size={46} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className={`text-sm font-cinzel font-semibold ${RARITY_COLORS[rarity] || ""}`}>
              {item.name}
              {(item.enhancement_level ?? 0) > 0 && (
                <span className="text-primary ml-1">+{item.enhancement_level}</span>
              )}
            </h3>
            <p className="text-xs text-muted-foreground mt-1 capitalize">{rarity}</p>
            {(item.enhancement_level ?? 0) > 0 && (
              <p className="text-xs text-primary mt-1">
                Enhancement: +{item.enhancement_level} (+{Math.round(item.enhancement_level * 15)}%)
              </p>
            )}
          </div>
        </div>

        {/* Price Calculation Breakdown */}
        <div className="mb-4 p-3 bg-muted/30 rounded-sm space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Base price:</span>
            <span className="font-semibold">{basePrice}g</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Rarity multiplier ({rarity}):</span>
            <span className="font-semibold">{rarityMult.toFixed(1)}x</span>
          </div>
          {(item.enhancement_level ?? 0) > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Enhancement bonus:</span>
              <span className="font-semibold">{enhancement.toFixed(2)}x</span>
            </div>
          )}
          <div className="border-t border-border/40 pt-2 flex justify-between">
            <span className="text-foreground font-semibold">Suggested price:</span>
            <span className="text-primary font-bold">{suggestedPrice}g</span>
          </div>
        </div>

        {/* Price Input */}
        <div className="mb-4">
          <label className="block text-xs font-cinzel font-semibold mb-2">Your Asking Price</label>
          <div className="flex gap-2">
            <input
              type="number"
              min="1"
              value={listPrice}
              onChange={(e) => setListPrice(Math.max(0, parseInt(e.target.value) || 0))}
              className="flex-1 px-3 py-2 bg-muted border border-border rounded-sm text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Enter price"
              disabled={isLoading}
            />
            <span className="flex items-center text-sm font-semibold text-foreground">🪙</span>
          </div>

          {/* Price Warning */}
          {priceWarning && (
            <p className="mt-2 text-xs text-yellow-500/80">⚠️ {priceWarning}</p>
          )}

          {/* Price Adjustment Helper */}
          <div className="mt-2 flex gap-1.5">
            <button
              type="button"
              onClick={() => setListPrice(Math.round(suggestedPrice * 0.75))}
              className="flex-1 px-2 py-1 text-[10px] bg-muted border border-border/40 rounded hover:bg-muted/80 transition"
              disabled={isLoading}
            >
              -25%
            </button>
            <button
              type="button"
              onClick={() => setListPrice(suggestedPrice)}
              className="flex-1 px-2 py-1 text-[10px] bg-primary/20 border border-primary/40 rounded hover:bg-primary/30 transition font-semibold"
              disabled={isLoading}
            >
              Suggested
            </button>
            <button
              type="button"
              onClick={() => setListPrice(Math.round(suggestedPrice * 1.25))}
              className="flex-1 px-2 py-1 text-[10px] bg-muted border border-border/40 rounded hover:bg-muted/80 transition"
              disabled={isLoading}
            >
              +25%
            </button>
          </div>
        </div>

        {/* Listing Summary */}
        {listPrice > 0 && (
          <div className="mb-4 p-3 bg-primary/10 border border-primary/20 rounded-sm text-sm">
            <p className="text-foreground font-semibold">
              You will receive: <span className="text-primary">{listPrice}g</span>
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Listed for 7 days or until sold
            </p>
          </div>
        )}

        {/* Buttons */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 game-btn-secondary text-xs py-2"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleList}
            className="flex-1 game-btn-primary text-xs py-2"
            disabled={isLoading || listPrice <= 0}
          >
            {isLoading ? "Listing..." : "List Item"}
          </button>
        </div>
      </div>
    </div>
  );
}
