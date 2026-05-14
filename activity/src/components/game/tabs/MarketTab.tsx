import { useState, useEffect } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { ItemIcon } from "@/components/game/ItemIcon";
import * as api from "@/lib/gameApi";
import type { ShopCatalogItem, InvRow, MarketListingRow } from "@/lib/apiTypes";
import { WomPanel } from "@/components/wom/WomUi";

type MarketSection = "shop" | "marketplace";

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

const BLACKSMITH_ITEMS = [
  { key: "blessing_scroll", name: "Blessing Scroll", icon: "🛡️", rarity: "rare", price: 10000, description: "Prevents item destruction on enhancement failure." },
  { key: "safety_charm", name: "Safety Charm", icon: "✨", rarity: "rare", price: 5000, description: "Guarantees 100% success for enhancements +1 to +5." },
  { key: "enhancement_fragment", name: "Enhancement Fragment", icon: "💎", rarity: "uncommon", price: 2000, description: "Increases success rate by 10% per fragment (max 3 stack)." },
];

const CATEGORIES = ["All", "Consumable", "Material", "Gear"] as const;

export function MarketTab() {
  const { inventory, buyProtection, buyShopItem, marketListings, refreshMarketListings, refreshInventory, accessToken, guildId } =
    useGameSession();
  const [section, setSection] = useState<MarketSection>("shop");
  const [shopCategory, setShopCategory] = useState<string>("All");
  const [shopCatalog, setShopCatalog] = useState<ShopCatalogItem[]>([]);
  const [loadingShop, setLoadingShop] = useState(false);
  const [loadingMarket, setLoadingMarket] = useState(false);

  const playerGold = inventory?.character?.gold ?? 0;

  // Load shop catalog on mount
  useEffect(() => {
    const loadShop = async () => {
      if (!accessToken) return;
      setLoadingShop(true);
      try {
        const r = await api.getShopCatalog(accessToken, guildId);
        setShopCatalog(r.items || []);
      } catch (e) {
        console.error("Failed to load shop catalog:", e);
        toast.error("Failed to load shop items");
      } finally {
        setLoadingShop(false);
      }
    };
    void loadShop();
  }, [accessToken, guildId]);

  // Load market listings on mount
  useEffect(() => {
    const loadMarket = async () => {
      setLoadingMarket(true);
      try {
        await refreshMarketListings();
      } catch (e) {
        console.error("Failed to load market listings:", e);
      } finally {
        setLoadingMarket(false);
      }
    };
    void loadMarket();
  }, [refreshMarketListings]);

  const filteredShop = shopCategory === "All"
    ? shopCatalog
    : shopCatalog.filter((i) => {
      const itype = i.description?.toLowerCase() || "";
      return shopCategory === "Consumable";
    });

  const handleBuy = async (item: ShopCatalogItem) => {
    if (playerGold < item.vendor_buy) {
      toast.error("Not enough gold!", { description: `You need ${item.vendor_buy} 🪙 but only have ${playerGold} 🪙` });
      return;
    }
    try {
      const res = await buyShopItem(item.id, 1);
      if (res.ok) {
        toast.success(`Purchased ${item.name}!`, { description: `−${item.vendor_buy} 🪙` });
      } else {
        toast.error(res.message || "Purchase failed");
      }
    } catch (e) {
      toast.error("Purchase failed", { description: String(e) });
    }
  };

  const handleBuyBlacksmith = async (key: string, price: number, name: string) => {
    if (playerGold < price) {
      toast.error("Not enough gold!", { description: `You need ${price} 🪙 but only have ${playerGold} 🪙` });
      return;
    }
    try {
      const res = await buyProtection(key, 1);
      if (res.ok) {
        toast.success(`Purchased ${name}!`, { description: `−${price} 🪙` });
      } else {
        toast.error(res.message || "Purchase failed");
      }
    } catch (e) {
      toast.error("Purchase failed", { description: String(e) });
    }
  };

  const handleBuyListing = async (listing: MarketListingRow) => {
    if (!accessToken) return;
    if (playerGold < listing.price) {
      toast.error("Not enough gold!", { description: `You need ${listing.price} 🪙 but only have ${playerGold} 🪙` });
      return;
    }
    try {
      const res = await api.postMarketBuy(accessToken, listing.id, guildId);
      if (res.ok) {
        toast.success(`Purchased ${listing.name}!`, { description: res.message || `−${listing.price.toLocaleString()} 🪙` });
        await refreshInventory();
        await refreshMarketListings();
      } else {
        toast.error(res.message || "Purchase failed");
      }
    } catch (e) {
      toast.error("Purchase failed", { description: String(e) });
    }
  };

  return (
    <div className="space-y-4">
      {/* Section toggle */}
      <WomPanel glow className="p-0 overflow-hidden">
        <div className="flex">
          <button
            onClick={() => setSection("shop")}
            className={`flex-1 py-3 text-xs font-cinzel font-semibold uppercase tracking-widest transition-all ${
              section === "shop"
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
            style={section === "shop" ? {
              background: 'linear-gradient(180deg, hsl(228 18% 16%) 0%, hsl(228 20% 12%) 100%)',
              boxShadow: 'inset 0 2px 0 hsl(43 78% 50% / 0.5), inset 0 -1px 0 hsl(228 18% 8%)',
              textShadow: '0 0 8px hsl(43 78% 50% / 0.3)',
            } : {}}
          >
            🏪 Game Shop
          </button>
          <div style={{ width: '1px', background: 'hsl(228 16% 20%)' }} />
          <button
            onClick={() => setSection("marketplace")}
            className={`flex-1 py-3 text-xs font-cinzel font-semibold uppercase tracking-widest transition-all ${
              section === "marketplace"
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
            style={section === "marketplace" ? {
              background: 'linear-gradient(180deg, hsl(228 18% 16%) 0%, hsl(228 20% 12%) 100%)',
              boxShadow: 'inset 0 2px 0 hsl(43 78% 50% / 0.5), inset 0 -1px 0 hsl(228 18% 8%)',
              textShadow: '0 0 8px hsl(43 78% 50% / 0.3)',
            } : {}}
          >
            🏛️ Player Market
          </button>
        </div>
      </WomPanel>

      {/* ════════════ GAME SHOP ════════════ */}
      {section === "shop" && (
        <>
          {/* Consumables Section */}
          <div className="space-y-3">
            <h3 className="text-sm font-cinzel font-semibold text-primary px-1">Consumables</h3>
            {loadingShop ? (
              <div className="text-xs text-muted-foreground text-center py-4">Loading shop...</div>
            ) : shopCatalog.length === 0 ? (
              <div className="text-xs text-muted-foreground text-center py-4">No items available</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {shopCatalog.map((item) => {
                  const iconItem: Partial<InvRow> = {
                    id: item.id,
                    template_id: item.id,
                    name: item.name,
                    icon: item.icon,
                    rarity: item.rarity,
                  };
                  return (
                  <WomPanel key={item.id} bracket={false} glow={false} className="p-3 flex items-start gap-3">
                    <div className="shrink-0 w-12 h-12 rounded-sm flex items-center justify-center slot-filled"
                      style={{ background: RARITY_BG[item.rarity] || "hsl(0 0% 65% / 0.06)" }}>
                      <ItemIcon item={iconItem as InvRow} size={46} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className={`text-sm font-cinzel font-semibold ${RARITY_COLORS[item.rarity] || ""}`}>
                            {item.name}
                          </h3>
                          <p className="text-[10px] text-muted-foreground mt-0.5 leading-snug">
                            {item.description || "..."}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-xs font-cinzel font-bold text-primary"
                          style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.2)' }}>
                          {item.vendor_buy} 🪙
                        </span>
                        <button
                          onClick={() => void handleBuy(item)}
                          className="game-btn-primary text-[10px] px-3 py-1"
                        >
                          Buy
                        </button>
                      </div>
                    </div>
                  </WomPanel>
                  );
                })}
              </div>
            )}
          </div>

          {/* Blacksmith Section */}
          <div className="space-y-3">
            <h3 className="text-sm font-cinzel font-semibold text-primary px-1">⚒️ Blacksmith</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {BLACKSMITH_ITEMS.map((item) => {
                const iconItem: Partial<InvRow> = {
                  id: item.key,
                  template_id: item.key,
                  name: item.name,
                  icon: item.icon,
                  rarity: item.rarity,
                };
                return (
                <WomPanel key={item.key} bracket={false} glow={false} className="p-3 flex items-start gap-3">
                  <div className="shrink-0 w-12 h-12 rounded-sm flex items-center justify-center slot-filled"
                    style={{ background: RARITY_BG[item.rarity] }}>
                    <ItemIcon item={iconItem as InvRow} size={46} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className={`text-sm font-cinzel font-semibold ${RARITY_COLORS[item.rarity]}`}>
                          {item.name}
                        </h3>
                        <p className="text-[10px] text-muted-foreground mt-0.5 leading-snug">
                          {item.description}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs font-cinzel font-bold text-primary"
                        style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.2)' }}>
                        {item.price.toLocaleString()} 🪙
                      </span>
                      <button
                        onClick={() => void handleBuyBlacksmith(item.key, item.price, item.name)}
                        className="game-btn-primary text-[10px] px-3 py-1"
                      >
                        Buy
                      </button>
                    </div>
                  </div>
                </WomPanel>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* ════════════ PLAYER MARKETPLACE ════════════ */}
      {section === "marketplace" && (
        <>
          <WomPanel glow className="p-3">
            <p className="text-xs text-muted-foreground font-crimson text-center italic">
              Browse items listed by other players. Enhanced items keep their upgrades!
            </p>
          </WomPanel>

          {loadingMarket ? (
            <div className="text-xs text-muted-foreground text-center py-8">Loading listings...</div>
          ) : marketListings.length === 0 ? (
            <WomPanel glow className="p-8 text-center">
              <p className="text-sm font-cinzel font-semibold text-foreground mb-2">
                📭 No Listings Yet
              </p>
              <p className="text-xs text-muted-foreground font-crimson mb-4">
                Be the first to sell an item! Use <span className="font-mono text-foreground">/market sell</span> in Discord to list an item.
              </p>
            </WomPanel>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {marketListings.map((listing) => {
                const iconItem: Partial<InvRow> = {
                  id: listing.id,
                  template_id: listing.template_id ?? undefined,
                  name: listing.name,
                  icon: listing.icon,
                  rarity: listing.rarity,
                  enhancement_level: listing.enhancement_level,
                  template_equip_slot: listing.template_equip_slot,
                };
                return (
                <WomPanel key={listing.id} bracket={false} glow={false} className="p-3 flex items-start gap-3">
                  <div className="shrink-0 w-12 h-12 rounded-sm flex items-center justify-center slot-filled relative"
                    style={{ background: RARITY_BG[listing.rarity] || "hsl(0 0% 65% / 0.06)" }}>
                    <ItemIcon item={iconItem as InvRow} size={46} />
                    {listing.enhancement_level && listing.enhancement_level > 0 && (
                      <span className="absolute bottom-0 right-0 text-[8px] text-primary font-bold leading-none bg-black/60 px-1 rounded-tl"
                        style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.4)' }}>
                        +{listing.enhancement_level}
                      </span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div>
                      <h3 className={`text-sm font-cinzel font-semibold ${RARITY_COLORS[listing.rarity] || ""}`}>
                        {listing.name}
                        {listing.enhancement_level && listing.enhancement_level > 0 && (
                          <span className="text-primary ml-1">+{listing.enhancement_level}</span>
                        )}
                      </h3>
                      <p className="text-[10px] text-muted-foreground mt-0.5 leading-snug">
                        {listing.description || "..."}
                      </p>
                    </div>
                    <div className="flex items-center justify-between mt-2">
                      <div>
                        <span className="text-xs font-cinzel font-bold text-primary"
                          style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.2)' }}>
                          {listing.price.toLocaleString()} 🪙
                        </span>
                        <span className="text-[9px] text-muted-foreground ml-2">
                          by <span className="text-foreground">{listing.seller_name}</span>
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleBuyListing(listing)}
                        className="game-btn-primary text-[10px] px-3 py-1"
                      >
                        Buy
                      </button>
                    </div>
                  </div>
                </WomPanel>
                );
              })}
            </div>
          )}

          <div className="ornament-divider" />

          {/* Sell your own items button */}
          <WomPanel glow className="p-4 text-center">
            <p className="text-sm font-cinzel font-semibold text-foreground mb-2">
              Want to sell your items?
            </p>
            <p className="text-[10px] text-muted-foreground mb-3 font-crimson">
              Use the Discord command <span className="font-mono text-foreground">/market sell</span> to list items from your inventory on the Player Market.
            </p>
            <p className="text-[9px] text-muted-foreground font-crimson">
              Listings expire after 7 days. A 5% fee is charged when you sell.
            </p>
          </WomPanel>
        </>
      )}

      {/* Gold display */}
      <WomPanel glow className="p-3 text-center border-t border-border/40">
        <p className="text-xs text-muted-foreground">Your Gold</p>
        <p className="text-lg font-cinzel font-bold text-primary mt-1"
          style={{ textShadow: '0 0 8px hsl(43 78% 50% / 0.3)' }}>
          {playerGold.toLocaleString()} 🪙
        </p>
      </WomPanel>
    </div>
  );
}
