import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Search,
  Coins,
  Gavel,
  Store,
  Tag,
  Plus,
  ScrollText,
  ShoppingCart,
  Sparkles,
  Info,
  ChevronDown,
  Loader2,
  AlertTriangle,
  X,
  History as HistoryIcon,
  Package,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useGameSession } from "@/context/GameSessionContext";
import { ItemIcon } from "@/components/game/ItemIcon";
import * as api from "@/lib/gameApi";
import type { InvRow, MarketListingRow, ShopCatalogItem } from "@/lib/apiTypes";

const RULES = {
  MAX_LISTINGS_PER_HERO: 10,
  LISTING_DURATION_DAYS: 7,
} as const;

type Rarity = "common" | "uncommon" | "rare" | "epic" | "legendary";
type ItemType = "weapon" | "armor" | "accessory" | "material" | "gear";
type Mode = "auction" | "market" | "supplies";
type SortKey = "newest" | "price-asc" | "price-desc" | "ending-soon";
type View = "browse" | "mine" | "history";

type MarketListingUI = {
  id: string;
  kind: "market";
  name: string;
  description: string;
  rarity: Rarity;
  type: ItemType;
  enhancement_level: number;
  template_equip_slot?: string;
  seller_name: string;
  listed_at: string;
  price: number;
  is_own?: boolean;
  icon?: string | null;
  template_id?: string | null;
};

interface FilterState {
  q: string;
  rarity: Rarity | "all";
  type: ItemType | "all";
  sort: SortKey;
}

const LISTABLE_TYPES = new Set(["weapon", "armor", "accessory", "material", "gear"]);

/** Game shop catalog + blacksmith (same as legacy Market tab). */
const SHOP_RARITY_COLORS: Record<string, string> = {
  common: "text-rarity-common border-rarity-common/40",
  uncommon: "text-rarity-uncommon border-rarity-uncommon/40",
  rare: "text-rarity-rare border-rarity-rare/40",
  epic: "text-rarity-epic border-rarity-epic/40",
  legendary: "text-rarity-legendary border-rarity-legendary/40",
};

const SHOP_RARITY_BG: Record<string, string> = {
  common: "hsl(0 0% 65% / 0.06)",
  uncommon: "hsl(120 38% 46% / 0.06)",
  rare: "hsl(210 65% 52% / 0.06)",
  epic: "hsl(268 55% 58% / 0.06)",
  legendary: "hsl(43 85% 52% / 0.08)",
};

const BLACKSMITH_ITEMS = [
  {
    key: "blessing_scroll",
    name: "Blessing Scroll",
    icon: "🛡️",
    rarity: "rare",
    price: 10_000,
    description: "Prevents item destruction on enhancement failure.",
  },
  {
    key: "safety_charm",
    name: "Safety Charm",
    icon: "✨",
    rarity: "rare",
    price: 5000,
    description: "Guarantees 100% success for enhancements +1 to +5.",
  },
  {
    key: "enhancement_fragment",
    name: "Enhancement Fragment",
    icon: "💎",
    rarity: "uncommon",
    price: 2000,
    description: "Increases success rate by 10% per fragment (max 3 stack).",
  },
] as const;

const RARITY_STYLES: Record<Rarity, { text: string; ring: string; glow: string; label: string }> = {
  common: { text: "text-muted-foreground", ring: "ring-muted/40", glow: "", label: "Common" },
  uncommon: {
    text: "text-emerald-300",
    ring: "ring-emerald-500/40",
    glow: "shadow-[0_0_18px_oklch(0.7_0.18_150/0.25)]",
    label: "Uncommon",
  },
  rare: {
    text: "text-sky-300",
    ring: "ring-sky-500/50",
    glow: "shadow-[0_0_22px_oklch(0.7_0.18_230/0.35)]",
    label: "Rare",
  },
  epic: {
    text: "text-fuchsia-300",
    ring: "ring-fuchsia-500/50",
    glow: "shadow-[0_0_28px_oklch(0.65_0.22_300/0.4)]",
    label: "Epic",
  },
  legendary: {
    text: "text-[color:var(--gold-bright)]",
    ring: "ring-[color:var(--gold)]/70",
    glow: "shadow-[0_0_36px_oklch(0.85_0.18_85/0.55)]",
    label: "Legendary",
  },
};

const fmtGold = (n: number) => n.toLocaleString();

function normalizeRarity(r: string): Rarity {
  const x = (r || "common").toLowerCase();
  if (x === "uncommon" || x === "rare" || x === "epic" || x === "legendary") return x;
  return "common";
}

function normalizeItemType(t: string | null | undefined): ItemType {
  const x = (t || "gear").toLowerCase();
  if (x === "weapon" || x === "armor" || x === "accessory" || x === "material" || x === "gear") return x;
  return "gear";
}

function formatListedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function rowToMarketUI(row: MarketListingRow, selfId: string | undefined, selfName: string | undefined): MarketListingUI {
  const sid = row.seller_id != null ? String(row.seller_id) : undefined;
  const is_own =
    (!!selfId && sid && selfId === sid) || (!!selfName && row.seller_name === selfName);
  return {
    id: row.id,
    kind: "market",
    name: row.name,
    description: (row.description || "").trim() || "—",
    rarity: normalizeRarity(row.rarity),
    type: normalizeItemType(row.item_type),
    enhancement_level: row.enhancement_level ?? 0,
    template_equip_slot: row.template_equip_slot ?? undefined,
    seller_name: row.seller_name,
    listed_at: formatListedAt(row.listed_at),
    price: row.price,
    is_own,
    icon: row.icon,
    template_id: row.template_id,
  };
}

function isListableItem(it: InvRow): boolean {
  if (it.is_equipped) return false;
  if (it.soulbound) return false;
  if (it.tradeable === false) return false;
  const t = (it.item_type || "").toLowerCase();
  return LISTABLE_TYPES.has(t);
}

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}

function filterAndSortMarket(items: MarketListingUI[], f: FilterState): MarketListingUI[] {
  let out = items.filter((i) => {
    if (f.rarity !== "all" && i.rarity !== f.rarity) return false;
    if (f.type !== "all" && i.type !== f.type) return false;
    if (f.q) {
      const q = f.q.toLowerCase();
      if (!i.name.toLowerCase().includes(q) && !i.seller_name.toLowerCase().includes(q)) return false;
    }
    return true;
  });
  switch (f.sort) {
    case "price-asc":
      out = [...out].sort((a, b) => a.price - b.price);
      break;
    case "price-desc":
      out = [...out].sort((a, b) => b.price - a.price);
      break;
    case "newest":
    default:
      break;
  }
  return out;
}

function GoldPill({ amount, label = "Your Gold" }: { amount: number; label?: string }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-md border border-[color:var(--gold)]/40 bg-black/40 px-3 py-1.5 shadow-[inset_0_0_18px_oklch(0_0_0/0.6)]">
      <Coins className="h-4 w-4 text-[color:var(--gold-bright)]" />
      <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-display">{label}</span>
      <span className="font-display text-sm font-semibold text-[color:var(--gold-bright)] tabular-nums">{fmtGold(amount)}</span>
    </div>
  );
}

function OrnateFrame({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("ornate-frame rounded-lg p-3 sm:p-4", className)}>
      <span className="corner-ornament corner-tl" />
      <span className="corner-ornament corner-tr" />
      <span className="corner-ornament corner-bl" />
      <span className="corner-ornament corner-br" />
      {children}
    </div>
  );
}

function RarityChip({ rarity }: { rarity: Rarity }) {
  const s = RARITY_STYLES[rarity];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-1.5 py-0.5 text-[10px] uppercase tracking-widest font-display ring-1",
        s.text,
        s.ring,
      )}
    >
      {s.label}
    </span>
  );
}

function SelectChip({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { v: string; l: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="relative inline-flex items-center">
      <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[10px] uppercase tracking-widest text-muted-foreground font-display pointer-events-none">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none rounded-md border border-[color:var(--gold)]/30 bg-black/40 pl-14 pr-8 py-2 text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-[color:var(--gold)]/50 cursor-pointer max-w-[200px]"
      >
        {options.map((o) => (
          <option key={o.v} value={o.v} className="bg-background">
            {o.l}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
    </label>
  );
}

function FiltersBar({ state, onChange, mode }: { state: FilterState; onChange: (s: FilterState) => void; mode: Mode }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto_auto] gap-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={state.q}
          onChange={(e) => onChange({ ...state, q: e.target.value })}
          placeholder="Search items, materials, sellers…"
          className="pl-8 bg-black/40 border-[color:var(--gold)]/30 focus-visible:ring-[color:var(--gold)]/50"
        />
      </div>
      <SelectChip
        label="Rarity"
        value={state.rarity}
        options={[
          { v: "all", l: "All Rarity" },
          { v: "common", l: "Common" },
          { v: "uncommon", l: "Uncommon" },
          { v: "rare", l: "Rare" },
          { v: "epic", l: "Epic" },
          { v: "legendary", l: "Legendary" },
        ]}
        onChange={(v) => onChange({ ...state, rarity: v as FilterState["rarity"] })}
      />
      <SelectChip
        label="Type"
        value={state.type}
        options={[
          { v: "all", l: "All Types" },
          { v: "weapon", l: "Weapon" },
          { v: "armor", l: "Armor" },
          { v: "accessory", l: "Accessory" },
          { v: "material", l: "Material" },
          { v: "gear", l: "Gear" },
        ]}
        onChange={(v) => onChange({ ...state, type: v as FilterState["type"] })}
      />
      <SelectChip
        label="Sort"
        value={state.sort === "ending-soon" ? "newest" : state.sort}
        options={
          mode === "auction"
            ? [{ v: "newest", l: "Coming soon" }]
            : [
                { v: "newest", l: "Newest" },
                { v: "price-asc", l: "Price Low → High" },
                { v: "price-desc", l: "Price High → Low" },
              ]
        }
        onChange={(v) => onChange({ ...state, sort: v as SortKey })}
      />
    </div>
  );
}

function MarketCard({
  item,
  onBuy,
  gold,
}: {
  item: MarketListingUI;
  onBuy: (i: MarketListingUI) => void;
  gold: number;
}) {
  const cantAfford = gold < item.price;
  const [confirming, setConfirming] = useState(false);
  const iconItem: Partial<InvRow> = {
    id: item.id,
    template_id: item.template_id ?? undefined,
    name: item.name,
    icon: item.icon,
    rarity: item.rarity,
    enhancement_level: item.enhancement_level,
    template_equip_slot: item.template_equip_slot,
    item_type: item.type,
  };

  return (
    <div
      className={cn(
        "group relative rounded-lg border border-[color:var(--gold)]/20 bg-gradient-to-b from-black/40 to-black/20 p-3 transition hover:border-[color:var(--gold)]/60 hover:-translate-y-0.5",
        RARITY_STYLES[item.rarity].glow,
      )}
    >
      <div className="flex gap-3">
        <div
          className={cn(
            "relative h-14 w-14 sm:h-16 sm:w-16 shrink-0 rounded-md ring-2 grid place-items-center bg-gradient-to-br from-black/60 to-black/20",
            RARITY_STYLES[item.rarity].ring,
          )}
        >
          <ItemIcon item={iconItem as InvRow} size={52} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h4 className={cn("font-display text-sm sm:text-base font-semibold leading-tight truncate", RARITY_STYLES[item.rarity].text)}>
              {item.name}
            </h4>
            <RarityChip rarity={item.rarity} />
          </div>
          <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{item.description}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {item.template_equip_slot ? (
              <Badge variant="outline" className="text-[10px] uppercase tracking-wider border-[color:var(--gold)]/30 text-muted-foreground">
                {item.template_equip_slot}
              </Badge>
            ) : null}
            <span className="text-[11px] text-muted-foreground">
              by <span className="text-foreground/80 font-medium">{item.seller_name}</span> · {item.listed_at}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-2 border-t border-[color:var(--gold)]/15 pt-3">
        <div className="inline-flex items-center gap-1.5">
          <Coins className="h-4 w-4 text-[color:var(--gold-bright)]" />
          <span className="font-display text-base font-semibold text-[color:var(--gold-bright)] tabular-nums">{fmtGold(item.price)}</span>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button
            size="sm"
            onClick={() => setConfirming(true)}
            disabled={cantAfford || item.is_own}
            className="bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] text-black hover:brightness-110 font-display tracking-wider"
          >
            <ShoppingCart className="h-3.5 w-3.5" />
            {item.is_own ? "Your listing" : cantAfford ? "Not enough gold" : "Buy"}
          </Button>
        </div>
        <AlertDialog open={confirming} onOpenChange={setConfirming}>
          <AlertDialogContent className="ornate-frame border-[color:var(--gold)]/40 max-w-[min(100vw-2rem,28rem)]">
            <AlertDialogHeader>
              <AlertDialogTitle className="font-display tracking-wider text-[color:var(--gold-bright)]">Confirm purchase</AlertDialogTitle>
              <AlertDialogDescription className="space-y-2">
                <span className="block">
                  Spend <span className="text-[color:var(--gold-bright)] font-display">{fmtGold(item.price)} 🪙</span> for{" "}
                  <span className={cn("font-display", RARITY_STYLES[item.rarity].text)}>{item.name}</span>?
                </span>
                <span className="block text-xs italic">Trade is final. Item is added to your inventory.</span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-[color:var(--gold)]/30">Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => {
                  void onBuy(item);
                  setConfirming(false);
                }}
                className="bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] text-black font-display tracking-wider"
              >
                Confirm Buy
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
}

function SegmentBtn({
  active,
  onClick,
  icon,
  title,
  tag,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  title: string;
  tag: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group relative rounded-md px-3 py-2.5 text-left transition cursor-pointer",
        active
          ? "bg-gradient-to-b from-[color:var(--gold)]/25 to-[color:var(--gold)]/5 ring-1 ring-[color:var(--gold)]/60 shadow-gold"
          : "hover:bg-white/5",
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "grid place-items-center h-7 w-7 rounded-md",
            active ? "bg-[color:var(--gold)]/30 text-[color:var(--gold-bright)]" : "bg-white/5 text-muted-foreground",
          )}
        >
          {icon}
        </span>
        <div className="min-w-0">
          <div className={cn("font-display tracking-wider text-sm", active ? "text-[color:var(--gold-bright)]" : "text-foreground")}>{title}</div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground truncate">{tag}</div>
        </div>
      </div>
    </button>
  );
}

function SubTabBtn({
  active,
  onClick,
  icon,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-xs font-display tracking-wider transition cursor-pointer",
        active
          ? "bg-[color:var(--gold)]/20 text-[color:var(--gold-bright)] ring-1 ring-[color:var(--gold)]/50"
          : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
      )}
    >
      {icon}
      <span className="truncate">{label}</span>
      {count != null && count > 0 ? (
        <Badge className="bg-[color:var(--gold)]/25 text-[color:var(--gold-bright)] border-0 px-1.5 py-0 text-[10px]">{count}</Badge>
      ) : null}
    </button>
  );
}

function EmptyState({ title, hint, cta }: { title: string; hint: string; cta: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-[color:var(--gold)]/30 bg-black/20 p-10 text-center">
      <Sparkles className="h-6 w-6 text-[color:var(--gold)] mx-auto mb-3 opacity-60" />
      <h3 className="font-display text-lg text-[color:var(--gold-bright)]">{title}</h3>
      <p className="text-xs text-muted-foreground mt-1 mb-4">{hint}</p>
      {cta}
    </div>
  );
}

function Rule({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-md border border-[color:var(--gold)]/15 bg-black/30 p-3">
      <div className="flex items-center gap-1.5 text-[color:var(--gold-bright)] font-display text-xs uppercase tracking-widest">
        {icon} {title}
      </div>
      <p className="mt-1 leading-relaxed text-xs text-muted-foreground">{body}</p>
    </div>
  );
}

function ModalShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto"
      role="presentation"
      onClick={onClose}
    >
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg my-auto">
        <OrnateFrame className="bg-black/80">
          <div className="flex items-center justify-between gap-2 mb-3">
            <h3 className="font-display text-lg text-[color:var(--gold-bright)] tracking-wider">{title}</h3>
            <Button size="icon" variant="ghost" type="button" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="divider-ornate mb-4" />
          {children}
        </OrnateFrame>
      </div>
    </div>
  );
}

function SuppliesPanel({ playerGold }: { playerGold: number }) {
  const { accessToken, guildId, buyShopItem, buyProtection } = useGameSession();
  const [shopCatalog, setShopCatalog] = useState<ShopCatalogItem[]>([]);
  const [loadingShop, setLoadingShop] = useState(false);

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

  const handleBuyShop = async (item: ShopCatalogItem) => {
    if (playerGold < item.vendor_buy) {
      toast.error("Not enough gold!", {
        description: `You need ${item.vendor_buy} 🪙 but only have ${playerGold} 🪙`,
      });
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

  return (
    <div className="space-y-4">
      <OrnateFrame>
        <h3 className="text-sm font-display font-semibold text-[color:var(--gold-bright)] px-1 mb-3 tracking-wider uppercase">
          Consumables
        </h3>
        {loadingShop ? (
          <div className="text-xs text-muted-foreground text-center py-8">Loading shop…</div>
        ) : shopCatalog.length === 0 ? (
          <div className="text-xs text-muted-foreground text-center py-8">No items available</div>
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
              const bg = SHOP_RARITY_BG[item.rarity] || SHOP_RARITY_BG.common;
              const col = SHOP_RARITY_COLORS[item.rarity] || "";
              return (
                <div
                  key={item.id}
                  className="rounded-lg border border-[color:var(--gold)]/20 bg-gradient-to-b from-black/40 to-black/20 p-3 flex items-start gap-3"
                >
                  <div
                    className="shrink-0 w-12 h-12 rounded-sm flex items-center justify-center slot-filled"
                    style={{ background: bg }}
                  >
                    <ItemIcon item={iconItem as InvRow} size={46} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className={cn("text-sm font-display font-semibold leading-tight", col)}>{item.name}</h4>
                    <p className="text-[10px] text-muted-foreground mt-0.5 leading-snug">{item.description || "…"}</p>
                    <div className="flex items-center justify-between mt-2 gap-2">
                      <span className="text-xs font-display font-bold text-[color:var(--gold-bright)] tabular-nums">
                        {item.vendor_buy.toLocaleString()} 🪙
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void handleBuyShop(item)}
                        className="bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] text-black hover:brightness-110 font-display text-[10px] tracking-wider h-8"
                      >
                        Buy
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </OrnateFrame>

      <OrnateFrame>
        <h3 className="text-sm font-display font-semibold text-[color:var(--gold-bright)] px-1 mb-3 tracking-wider uppercase">
          Blacksmith
        </h3>
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
              <div
                key={item.key}
                className="rounded-lg border border-[color:var(--gold)]/20 bg-gradient-to-b from-black/40 to-black/20 p-3 flex items-start gap-3"
              >
                <div
                  className="shrink-0 w-12 h-12 rounded-sm flex items-center justify-center slot-filled"
                  style={{ background: SHOP_RARITY_BG[item.rarity] }}
                >
                  <ItemIcon item={iconItem as InvRow} size={46} />
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className={cn("text-sm font-display font-semibold leading-tight", SHOP_RARITY_COLORS[item.rarity])}>
                    {item.name}
                  </h4>
                  <p className="text-[10px] text-muted-foreground mt-0.5 leading-snug">{item.description}</p>
                  <div className="flex items-center justify-between mt-2 gap-2">
                    <span className="text-xs font-display font-bold text-[color:var(--gold-bright)] tabular-nums">
                      {item.price.toLocaleString()} 🪙
                    </span>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => void handleBuyBlacksmith(item.key, item.price, item.name)}
                      className="bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] text-black hover:brightness-110 font-display text-[10px] tracking-wider h-8"
                    >
                      Buy
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </OrnateFrame>
    </div>
  );
}

function ListMarketModal({
  onClose,
  items,
  currentListCount,
  onListed,
}: {
  onClose: () => void;
  items: InvRow[];
  currentListCount: number;
  onListed: () => void;
}) {
  const { listItemOnMarket } = useGameSession();
  const eligible = useMemo(() => items.filter(isListableItem), [items]);
  const [selectedId, setSelectedId] = useState<string>(eligible[0]?.id ?? "");
  const sel = eligible.find((i) => i.id === selectedId);
  const suggested = sel ? api.calculateMarketPrice(sel, sel.vendor_sell ?? undefined) : 100;
  const [price, setPrice] = useState(suggested);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (eligible.length && !eligible.some((e) => e.id === selectedId)) {
      setSelectedId(eligible[0].id);
    }
  }, [eligible, selectedId]);

  useEffect(() => {
    setPrice(suggested);
  }, [suggested, sel?.id]);

  const overCap = currentListCount >= RULES.MAX_LISTINGS_PER_HERO;
  const tooLow = price < suggested * 0.5;
  const tooHigh = price > suggested * 3;
  const invalid = !sel || price < 1 || overCap;

  const handleList = async () => {
    if (!sel || invalid || submitting) return;
    setSubmitting(true);
    try {
      const j = await listItemOnMarket(sel.id, price);
      if (j.ok !== false) {
        toast.success("Item listed!", { description: j.message || `${fmtGold(price)} 🪙` });
        onListed();
        onClose();
      } else {
        toast.error("Listing failed", { description: j.message || "Could not list item." });
      }
    } catch (e) {
      toast.error("Listing failed", { description: String(e) });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title="List on Player Market" onClose={onClose}>
      {overCap ? (
        <div className="mb-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-300 flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5" />
          Limit of {RULES.MAX_LISTINGS_PER_HERO} active listings reached.
        </div>
      ) : null}

      <label className="text-[11px] uppercase tracking-widest text-muted-foreground font-display">Tradeable inventory</label>
      <div className="mt-1.5 grid grid-cols-2 gap-2 max-h-44 overflow-y-auto pr-1">
        {eligible.length === 0 ? (
          <div className="col-span-2 rounded-md border border-dashed border-[color:var(--gold)]/30 p-4 text-center text-xs text-muted-foreground">
            Nothing to list — unequip gear, avoid soulbound items, and use weapon/armor/accessory/material/gear types only.
          </div>
        ) : (
          eligible.map((it) => {
            const active = it.id === selectedId;
            const r = normalizeRarity(it.rarity || "common");
            return (
              <button
                type="button"
                key={it.id}
                onClick={() => setSelectedId(it.id)}
                className={cn(
                  "flex items-center gap-2 rounded-md border p-2 text-left transition cursor-pointer",
                  active
                    ? "border-[color:var(--gold)] bg-[color:var(--gold)]/10 shadow-gold"
                    : "border-[color:var(--gold)]/20 bg-black/30 hover:border-[color:var(--gold)]/50",
                )}
              >
                <div className={cn("h-11 w-11 shrink-0 rounded ring-1 grid place-items-center", RARITY_STYLES[r].ring)}>
                  <ItemIcon item={it} size={40} />
                </div>
                <div className="min-w-0">
                  <div className={cn("text-xs font-display font-semibold truncate", RARITY_STYLES[r].text)}>{it.name}</div>
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {RARITY_STYLES[r].label} · {normalizeItemType(it.item_type)}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-[11px] uppercase tracking-widest text-muted-foreground font-display">Your asking price</label>
          <div className="flex gap-1">
            {[
              { l: "−25%", v: Math.round(suggested * 0.75) },
              { l: "Suggested", v: suggested },
              { l: "+25%", v: Math.round(suggested * 1.25) },
            ].map((q) => (
              <Button
                key={q.l}
                type="button"
                size="sm"
                variant="outline"
                className="h-6 px-2 text-[10px] border-[color:var(--gold)]/30"
                onClick={() => setPrice(q.v)}
              >
                {q.l}
              </Button>
            ))}
          </div>
        </div>
        <div className="relative">
          <Coins className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[color:var(--gold-bright)]" />
          <Input
            type="number"
            value={price}
            onChange={(e) => setPrice(Number(e.target.value || 0))}
            className="pl-8 bg-black/40 border-[color:var(--gold)]/30 font-display text-base tabular-nums"
          />
        </div>
        {(tooLow || tooHigh) && (
          <div className="mt-2 flex items-start gap-1.5 text-xs text-amber-400">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>{tooLow ? "Price is very low versus suggested." : "Price is very high — may be slow to sell."}</span>
          </div>
        )}
      </div>

      <div className="mt-4 rounded-md border border-[color:var(--gold)]/20 bg-black/30 p-3 text-xs space-y-1.5 text-muted-foreground">
        <div className="flex justify-between">
          <span>Listing duration</span>
          <span className="font-display text-foreground">{RULES.LISTING_DURATION_DAYS} days</span>
        </div>
        <div className="flex justify-between">
          <span>Upfront fee (Activity)</span>
          <span className="font-display text-emerald-300/90">None</span>
        </div>
        <div className="flex justify-between">
          <span>Active listings</span>
          <span className="font-display tabular-nums text-foreground">
            {currentListCount}/{RULES.MAX_LISTINGS_PER_HERO}
          </span>
        </div>
        <p className="text-[10px] italic pt-1 border-t border-[color:var(--gold)]/10">
          Discord <span className="font-mono">/market sell</span> may charge a separate listing fee; sales credit gold to the seller.
        </p>
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onClose} className="border-[color:var(--gold)]/30">
          Cancel
        </Button>
        <Button
          type="button"
          onClick={() => void handleList()}
          disabled={invalid || submitting}
          className="bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] text-black font-display tracking-wider min-w-[140px]"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Listing…
            </>
          ) : (
            <>
              <Tag className="h-4 w-4" /> List Item
            </>
          )}
        </Button>
      </div>
    </ModalShell>
  );
}

export function MarketView() {
  const {
    inventory,
    marketListings,
    refreshMarketListings,
    refreshInventory,
    accessToken,
    guildId,
  } = useGameSession();

  const [mode, setMode] = useState<Mode>("market");
  const [marketViewTab, setMarketViewTab] = useState<"browse" | "mine">("browse");
  const [filters, setFilters] = useState<FilterState>({ q: "", rarity: "all", type: "all", sort: "newest" });
  const debouncedQ = useDebounced(filters.q, 200);
  const effectiveFilters = useMemo(() => ({ ...filters, q: debouncedQ }), [filters, debouncedQ]);

  const [showListModal, setShowListModal] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const [historyTab, setHistoryTab] = useState(false);

  useEffect(() => {
    if (mode !== "market") setHistoryTab(false);
  }, [mode]);

  /** browse | mine | history — flatten sub-nav */
  const view: View = historyTab ? "history" : marketViewTab;

  const gold = inventory?.character?.gold ?? 0;
  const charId = inventory?.character?.id ? String(inventory.character.id) : undefined;
  const charName = inventory?.character?.name ?? undefined;

  const mappedMarket = useMemo(
    () => marketListings.map((row) => rowToMarketUI(row, charId, charName)),
    [marketListings, charId, charName],
  );

  const myMarketCount = useMemo(() => mappedMarket.filter((m) => m.is_own).length, [mappedMarket]);

  const filteredMarketBase = useMemo(() => {
    if (marketViewTab === "browse") return mappedMarket.filter((m) => !m.is_own);
    return mappedMarket.filter((m) => m.is_own);
  }, [mappedMarket, marketViewTab]);

  const visibleMarket = useMemo(() => filterAndSortMarket(filteredMarketBase, effectiveFilters), [filteredMarketBase, effectiveFilters]);

  const refreshAll = useCallback(async () => {
    await refreshMarketListings();
    await refreshInventory();
  }, [refreshMarketListings, refreshInventory]);

  useEffect(() => {
    if (!accessToken) return;
    void refreshMarketListings();
  }, [accessToken, refreshMarketListings]);

  const handleBuy = useCallback(
    async (item: MarketListingUI) => {
      if (!accessToken) return;
      try {
        const res = await api.postMarketBuy(accessToken, item.id, guildId);
        if (res.ok) {
          toast.success(`Purchased ${item.name}!`, { description: res.message || `−${fmtGold(item.price)} 🪙` });
          await refreshAll();
        } else {
          toast.error(res.message || "Purchase failed.");
        }
      } catch (e) {
        toast.error("Purchase failed", { description: String(e) });
      }
    },
    [accessToken, guildId, refreshAll],
  );

  const setModeSafe = (m: Mode) => {
    setMode(m);
    if (m === "auction") {
      setFilters((f) => ({ ...f, sort: "newest" }));
    }
  };

  return (
    <div className="realm-market space-y-4 min-h-0 flex flex-col">
      <OrnateFrame>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[color:var(--gold)]" />
              <span className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground font-display">Realm · Commerce</span>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl text-shimmer mt-1">Market — Exchange of the Realm</h1>
            <p className="text-xs sm:text-sm text-muted-foreground mt-1">
              Listings last {RULES.LISTING_DURATION_DAYS} days. Enhanced gear keeps{" "}
              <span className="text-[color:var(--gold-bright)]">+levels</span> and rolls.
            </p>
          </div>
          <GoldPill amount={gold} />
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-2 rounded-lg border border-[color:var(--gold)]/30 bg-black/40 p-1">
          <SegmentBtn
            active={mode === "auction"}
            onClick={() => setModeSafe("auction")}
            icon={<Gavel className="h-4 w-4" />}
            title="Auction House"
            tag="Coming soon — timed bids"
          />
          <SegmentBtn
            active={mode === "market"}
            onClick={() => setModeSafe("market")}
            icon={<Store className="h-4 w-4" />}
            title="Player Market"
            tag="Buy now — fixed prices"
          />
          <SegmentBtn
            active={mode === "supplies"}
            onClick={() => setModeSafe("supplies")}
            icon={<Package className="h-4 w-4" />}
            title="Supplies"
            tag="NPC shop · Blacksmith"
          />
        </div>

        {mode === "market" ? (
          <div className="mt-3 grid grid-cols-3 gap-1 rounded-md border border-[color:var(--gold)]/20 bg-black/30 p-1">
            <SubTabBtn
              active={!historyTab && marketViewTab === "browse"}
              onClick={() => {
                setHistoryTab(false);
                setMarketViewTab("browse");
              }}
              icon={<Search className="h-3.5 w-3.5" />}
              label="Browse"
            />
            <SubTabBtn
              active={!historyTab && marketViewTab === "mine"}
              onClick={() => {
                setHistoryTab(false);
                setMarketViewTab("mine");
              }}
              icon={<ScrollText className="h-3.5 w-3.5" />}
              label="My Listings"
              count={myMarketCount}
            />
            <SubTabBtn
              active={historyTab}
              onClick={() => setHistoryTab(true)}
              icon={<HistoryIcon className="h-3.5 w-3.5" />}
              label="History"
            />
          </div>
        ) : null}
      </OrnateFrame>

      {mode === "supplies" ? (
        <ScrollArea className="max-h-[60vh] pr-2 flex-1 min-h-[200px]">
          <div className="pb-4">
            <SuppliesPanel playerGold={gold} />
          </div>
        </ScrollArea>
      ) : mode === "auction" ? (
        <EmptyState
          title="Auction House — in development"
          hint="Timed auctions, bids, and buyouts require new server APIs. Use Player Market for listings or Supplies for the NPC shop."
          cta={
            <div className="flex flex-wrap gap-2 justify-center">
              <Button type="button" onClick={() => setModeSafe("market")} className="bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] text-black font-display">
                <Store className="h-4 w-4" /> Player Market
              </Button>
              <Button type="button" variant="outline" onClick={() => setModeSafe("supplies")} className="border-[color:var(--gold)]/40 font-display">
                <Package className="h-4 w-4" /> Supplies
              </Button>
            </div>
          }
        />
      ) : view === "history" ? (
        <EmptyState
          title="Trade history"
          hint="A unified buy/sell/bid ledger will appear here once the backend exposes it."
          cta={null}
        />
      ) : (
        <>
          <OrnateFrame>
            <FiltersBar state={filters} onChange={setFilters} mode={mode} />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <div className="text-[11px] text-muted-foreground">
                Showing <span className="text-foreground font-semibold">{visibleMarket.length}</span> listings ·{" "}
                <span className="italic">Instant buy with gold.</span>
              </div>
              <Button
                type="button"
                size="sm"
                onClick={() => setShowListModal(true)}
                disabled={myMarketCount >= RULES.MAX_LISTINGS_PER_HERO}
                className="bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] text-black font-display tracking-wider"
              >
                <Plus className="h-3.5 w-3.5" /> Sell / List
                <Badge className="ml-1 bg-black/30 text-[color:var(--gold-bright)] border-0">{myMarketCount}/{RULES.MAX_LISTINGS_PER_HERO}</Badge>
              </Button>
            </div>
          </OrnateFrame>

          <ScrollArea className="max-h-[60vh] pr-2 flex-1 min-h-[200px]">
            {visibleMarket.length === 0 ? (
              <EmptyState
                title={marketViewTab === "mine" ? "No listings" : "No listings match"}
                hint={
                  marketViewTab === "mine"
                    ? "List a tradeable item from your inventory."
                    : "Try adjusting filters — or open Sell / List to put gear up."
                }
                cta={
                  marketViewTab === "mine" ? (
                    <Button type="button" onClick={() => setShowListModal(true)} className="bg-gradient-to-b from-[color:var(--gold-bright)] to-[color:var(--gold-dim)] text-black font-display">
                      <Plus className="h-4 w-4" /> Sell an Item
                    </Button>
                  ) : null
                }
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pb-4">
                {visibleMarket.map((it) => (
                  <MarketCard key={it.id} item={it} gold={gold} onBuy={(i) => void handleBuy(i)} />
                ))}
              </div>
            )}
          </ScrollArea>
        </>
      )}

      <OrnateFrame>
        <button type="button" onClick={() => setShowRules((s) => !s)} className="w-full flex items-center justify-between gap-2 cursor-pointer">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-[color:var(--gold)]" />
            <span className="font-display tracking-wider uppercase text-sm text-[color:var(--gold-bright)]">Codex of the Exchange</span>
          </div>
          <ChevronDown className={cn("h-4 w-4 transition-transform", showRules && "rotate-180")} />
        </button>
        {showRules ? (
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <Rule
              icon={<Store className="h-3.5 w-3.5" />}
              title="Player Market"
              body={`Fixed-price, instant purchase. Up to ${RULES.MAX_LISTINGS_PER_HERO} active listings each. Soulbound / equipped gear cannot be listed. Activity listing has no upfront fee.`}
            />
            <Rule
              icon={<Package className="h-3.5 w-3.5" />}
              title="Supplies"
              body="Official catalog consumables plus blacksmith enhancement helpers (Blessing Scroll, Safety Charm, Fragment). Priced in gold."
            />
            <Rule
              icon={<Gavel className="h-3.5 w-3.5" />}
              title="Auction House"
              body="Scheduled for a future update — bidding, escrow, and anti-sniping need new API endpoints."
            />
          </div>
        ) : null}
      </OrnateFrame>

      {showListModal && (
        <ListMarketModal
          onClose={() => setShowListModal(false)}
          items={inventory?.items ?? []}
          currentListCount={myMarketCount}
          onListed={() => void refreshAll()}
        />
      )}
    </div>
  );
}
