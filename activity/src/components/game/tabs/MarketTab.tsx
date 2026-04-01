import { useState } from "react";
import { toast } from "sonner";

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

interface ShopItem {
  id: string;
  name: string;
  icon: string;
  rarity: string;
  price: number;
  description: string;
  category: "consumable" | "material" | "gear";
}

interface MarketListing {
  id: string;
  name: string;
  icon: string;
  rarity: string;
  price: number;
  seller: string;
  enhanceLevel?: number;
  description: string;
}

const SHOP_ITEMS: ShopItem[] = [
  { id: "hp-pot", name: "Health Potion", icon: "🧪", rarity: "common", price: 25, description: "Restores 50 HP instantly.", category: "consumable" },
  { id: "mana-pot", name: "Mana Elixir", icon: "🔮", rarity: "uncommon", price: 60, description: "Restores 40 Mana over 5s.", category: "consumable" },
  { id: "antidote", name: "Antidote", icon: "💊", rarity: "common", price: 15, description: "Cures poison status.", category: "consumable" },
  { id: "revive", name: "Phoenix Down", icon: "🪶", rarity: "rare", price: 200, description: "Revive with 30% HP.", category: "consumable" },
  { id: "whetstone", name: "Whetstone", icon: "🪨", rarity: "common", price: 40, description: "Enhancement material. +1 weapon level.", category: "material" },
  { id: "armor-kit", name: "Armor Kit", icon: "🛡️", rarity: "common", price: 40, description: "Enhancement material. +1 armor level.", category: "material" },
  { id: "magic-dust", name: "Magic Dust", icon: "✨", rarity: "uncommon", price: 80, description: "Rare enhancement catalyst.", category: "material" },
  { id: "dragon-scale", name: "Dragon Scale", icon: "🐉", rarity: "epic", price: 500, description: "Legendary crafting material.", category: "material" },
  { id: "iron-sword", name: "Iron Sword", icon: "⚔️", rarity: "common", price: 150, description: "+8 ATK. A basic but reliable blade.", category: "gear" },
  { id: "leather-helm", name: "Leather Helm", icon: "🪖", rarity: "common", price: 100, description: "+4 DEF. Light headgear.", category: "gear" },
];

const MARKETPLACE_LISTINGS: MarketListing[] = [
  { id: "m1", name: "Duskblade", icon: "🗡️", rarity: "epic", price: 2800, seller: "DarkKnight99", enhanceLevel: 5, description: "+22 ATK, +5 CRIT" },
  { id: "m2", name: "Shadow Greaves", icon: "🦿", rarity: "rare", price: 950, seller: "ArmorSmith", enhanceLevel: 3, description: "+8 DEF, +3 AGI" },
  { id: "m3", name: "Phoenix Down", icon: "🪶", rarity: "rare", price: 180, seller: "PotionMaster", description: "Revive with 30% HP." },
  { id: "m4", name: "Dragon Scale", icon: "🐉", rarity: "epic", price: 420, seller: "DragonHunter", description: "Legendary crafting material." },
  { id: "m5", name: "Enchanted Gem", icon: "💎", rarity: "rare", price: 300, seller: "GemCollector", description: "Used for high-tier enchants." },
  { id: "m6", name: "Crimson Cloak", icon: "🧥", rarity: "legendary", price: 5500, seller: "LootGoblin", enhanceLevel: 9, description: "+15 DEF, +10 AGI, Stealth Bonus" },
  { id: "m7", name: "Whetstone x10", icon: "🪨", rarity: "common", price: 350, seller: "BulkTrader", description: "Bundle of 10 whetstones." },
  { id: "m8", name: "Magic Dust x5", icon: "✨", rarity: "uncommon", price: 350, seller: "WizardMerch", description: "Bundle of 5 magic dust." },
];

const CATEGORIES = ["All", "Consumable", "Material", "Gear"] as const;

export function MarketTab() {
  const [section, setSection] = useState<MarketSection>("shop");
  const [shopCategory, setShopCategory] = useState<string>("All");
  const [playerGold] = useState(1247);

  const filteredShop = shopCategory === "All"
    ? SHOP_ITEMS
    : SHOP_ITEMS.filter((i) => i.category === shopCategory.toLowerCase());

  const handleBuy = (name: string, price: number) => {
    if (price > playerGold) {
      toast.error("Not enough gold!", { description: `You need ${price} 🪙 but only have ${playerGold} 🪙` });
    } else {
      toast.success(`Purchased ${name}!`, { description: `−${price} 🪙` });
    }
  };

  const handleListingBuy = (listing: MarketListing) => {
    if (listing.price > playerGold) {
      toast.error("Not enough gold!", { description: `You need ${listing.price} 🪙` });
    } else {
      toast.success(`Bought ${listing.name} from ${listing.seller}!`, { description: `−${listing.price} 🪙` });
    }
  };

  return (
    <div className="space-y-4">
      {/* Section toggle */}
      <div className="game-panel p-0">
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
      </div>

      {/* ════════════ GAME SHOP ════════════ */}
      {section === "shop" && (
        <>
          {/* Category filter */}
          <div className="flex gap-2 flex-wrap">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setShopCategory(cat)}
                className={`text-[10px] px-3 py-1.5 rounded-sm font-cinzel font-semibold uppercase tracking-wider transition-all ${
                  shopCategory === cat ? "game-btn-primary" : "game-btn-secondary"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Shop grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {filteredShop.map((item) => (
              <div key={item.id} className="game-panel p-3 flex items-start gap-3">
                <div
                  className={`shrink-0 w-12 h-12 rounded-sm flex items-center justify-center text-2xl slot-filled ${RARITY_COLORS[item.rarity]}`}
                  style={{ background: RARITY_BG[item.rarity] }}
                >
                  {item.icon}
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
                      {item.price} 🪙
                    </span>
                    <button
                      onClick={() => handleBuy(item.name, item.price)}
                      className="game-btn-primary text-[10px] px-3 py-1"
                    >
                      Buy
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ════════════ PLAYER MARKETPLACE ════════════ */}
      {section === "marketplace" && (
        <>
          <div className="game-panel p-3">
            <p className="text-xs text-muted-foreground font-crimson text-center italic">
              Browse items listed by other players. Enhanced items keep their upgrades!
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {MARKETPLACE_LISTINGS.map((listing) => (
              <div key={listing.id} className="game-panel p-3 flex items-start gap-3">
                <div
                  className={`shrink-0 w-12 h-12 rounded-sm flex items-center justify-center text-2xl slot-filled ${RARITY_COLORS[listing.rarity]}`}
                  style={{ background: RARITY_BG[listing.rarity] }}
                >
                  <div className="flex flex-col items-center">
                    <span>{listing.icon}</span>
                    {listing.enhanceLevel && listing.enhanceLevel > 0 && (
                      <span className="text-[8px] text-primary font-bold leading-none"
                        style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.4)' }}>
                        +{listing.enhanceLevel}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div>
                    <h3 className={`text-sm font-cinzel font-semibold ${RARITY_COLORS[listing.rarity]}`}>
                      {listing.name}
                      {listing.enhanceLevel && listing.enhanceLevel > 0 && (
                        <span className="text-primary ml-1">+{listing.enhanceLevel}</span>
                      )}
                    </h3>
                    <p className="text-[10px] text-muted-foreground mt-0.5 leading-snug">
                      {listing.description}
                    </p>
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <div>
                      <span className="text-xs font-cinzel font-bold text-primary"
                        style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.2)' }}>
                        {listing.price.toLocaleString()} 🪙
                      </span>
                      <span className="text-[9px] text-muted-foreground ml-2">
                        by <span className="text-foreground">{listing.seller}</span>
                      </span>
                    </div>
                    <button
                      onClick={() => handleListingBuy(listing)}
                      className="game-btn-primary text-[10px] px-3 py-1"
                    >
                      Buy
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="ornament-divider" />

          {/* Sell your own items button */}
          <div className="game-panel p-4 text-center">
            <p className="text-sm font-cinzel font-semibold text-foreground mb-2">
              Want to sell your items?
            </p>
            <p className="text-[10px] text-muted-foreground mb-3 font-crimson">
              List items from your inventory on the Player Market for other adventurers to buy.
            </p>
            <button
              onClick={() => toast("Sell feature coming soon!", { description: "List your items on the marketplace." })}
              className="game-btn-secondary text-xs px-6 py-2"
            >
              📦 List an Item
            </button>
          </div>
        </>
      )}
    </div>
  );
}
