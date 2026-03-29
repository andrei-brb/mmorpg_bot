import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { InvRow } from "@/lib/apiTypes";
import { publicBaseUrl } from "@/lib/gameApi";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BlacksmithModal } from "@/components/game/modals/BlacksmithModal";

const EQUIP_ORDER = [
  "head",
  "chest",
  "hands",
  "legs",
  "feet",
  "main_hand",
  "off_hand",
  "neck",
  "ring",
  "trinket",
] as const;

const SLOT_ICONS: Record<string, string> = {
  head: "🪖",
  chest: "🛡️",
  hands: "🧤",
  legs: "👖",
  feet: "👢",
  main_hand: "⚔️",
  off_hand: "🛡️",
  neck: "📿",
  ring: "💍",
  trinket: "💎",
};

function rarityBorderColor(rarity?: string | null): string {
  const v = (rarity || "").toLowerCase();
  if (v === "legendary") return "hsl(43 85% 52%)";
  if (v === "epic") return "hsl(268 55% 58%)";
  if (v === "rare") return "hsl(210 65% 52%)";
  if (v === "uncommon") return "hsl(120 38% 46%)";
  return "hsl(228 14% 22%)";
}

function itemImgSrc(it: InvRow): string | null {
  const id = it.template_id?.trim();
  if (!id) return null;
  return `${publicBaseUrl()}assets/items/${encodeURIComponent(id)}.png`;
}

function generateItemImgSrc(it: InvRow): string | null {
  const name = it.name?.trim();
  if (!name) return null;
  return `${publicBaseUrl()}assets/items/generated/${encodeURIComponent(name)}.png`;
}

export function HeroTab() {
  const {
    inventory,
    refreshInventory,
    itemPost,
    getEnhanceInfo,
    postEnhance,
    buyProtection,
    specModal,
    requestSpecChoice,
  } = useGameSession();

  const [status, setStatus] = useState("");
  const [enhanceItemId, setEnhanceItemId] = useState<string | null>(null);
  const [enhanceInfo, setEnhanceInfo] = useState<Awaited<ReturnType<typeof getEnhanceInfo>> | null>(null);
  const [prot, setProt] = useState<string>("none");
  const [frags, setFrags] = useState(0);
  const [showBlacksmith, setShowBlacksmith] = useState(false);
  const [selectedBagItem, setSelectedBagItem] = useState<string | null>(null);

  const char = inventory?.character;
  const items = inventory?.items || [];
  const bag = useMemo(() => items.filter((i) => !i.is_equipped), [items]);
  const equipped = useMemo(() => {
    const m: Record<string, InvRow> = {};
    for (const it of items) {
      if (it.is_equipped && it.equip_slot) m[it.equip_slot] = it;
    }
    return m;
  }, [items]);

  const hp = Number(char?.current_hp ?? 0);
  const maxHp = Number(char?.max_hp ?? 0);
  const hpPct = maxHp > 0 ? Math.min(100, (hp / maxHp) * 100) : 100;

  const runAction = useCallback(
    async (endpoint: string, body: Record<string, unknown>, msg: string) => {
      try {
        setStatus("…");
        const res = await itemPost(endpoint, body);
        const j = (await res.json()) as { ok?: boolean; message?: string };
        setStatus(j.message || (j.ok ? msg : "Failed"));
        toast(j.message || msg);
        await refreshInventory();
      } catch (e) {
        setStatus(String(e));
        toast.error(String(e));
      }
    },
    [itemPost, refreshInventory],
  );

  const openEnhance = async (itemId: string) => {
    setEnhanceItemId(itemId);
    setProt("none");
    setFrags(0);
    try {
      const info = await getEnhanceInfo(itemId);
      setEnhanceInfo(info);
    } catch (e) {
      toast.error(String(e));
      setEnhanceItemId(null);
    }
  };

  const directUse = new Set([
    "heal_hp",
    "boost_sta",
    "boost_str",
    "boost_agi",
    "boost_int",
    "boost_spi",
    "boost_max_hp",
    "boost_resistance",
  ]);

  const ItemImg = ({ item, size = "w-10 h-10" }: { item: InvRow; size?: string }) => {
    const src = itemImgSrc(item) || generateItemImgSrc(item);
    if (src) {
      return (
        <img
          src={src}
          alt={item.name}
          className={`${size} object-contain`}
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
            const next = (e.target as HTMLElement).nextElementSibling;
            if (next) (next as HTMLElement).style.display = "";
          }}
        />
      );
    }
    return <span className="text-xl opacity-60">{SLOT_ICONS[item.equip_slot || ""] || "📦"}</span>;
  };

  return (
    <div className="space-y-4">
      {/* CHARACTER STATS */}
      <div className="game-panel">
        <div className="game-panel-header">Character Stats</div>
        {!char ? (
          <p className="text-sm text-muted-foreground">
            No character — use <code className="text-xs">/character create</code> in Discord.
          </p>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-cinzel font-bold uppercase tracking-wide">{char.name}</span>
              <span className="text-primary text-xs font-cinzel font-semibold">Lv {char.level ?? "?"}</span>
              <span className="text-muted-foreground text-xs lowercase">{char.class}</span>
              {(char.specialization_name || char.specialization) && (
                <>
                  <span className="text-muted-foreground text-xs">|</span>
                  <span className="text-xs italic text-accent-foreground">
                    {char.specialization_name || char.specialization}
                  </span>
                </>
              )}
              <span className="ml-auto text-primary font-cinzel font-semibold">
                {Number(char.gold ?? 0).toLocaleString()} 🪙
              </span>
            </div>

            <div>
              <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
                <span className="font-cinzel uppercase tracking-wider font-semibold">Hit Points</span>
                <span className="tabular-nums">
                  {hp} / {maxHp || "—"}
                </span>
              </div>
              <div className="hp-bar-track">
                <div className="hp-bar-fill" style={{ width: `${hpPct}%` }} />
              </div>
            </div>

            {!char.specialization && !char.specialization_name && (
              <button
                type="button"
                className="game-btn-secondary w-full text-xs py-2"
                onClick={() => void requestSpecChoice?.()}
              >
                ✨ Specialization
              </button>
            )}
          </div>
        )}
        {status && <p className="text-xs text-muted-foreground mt-2">{status}</p>}
      </div>

      {/* EQUIPMENT + INVENTORY side by side */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* EQUIPMENT */}
        <div className="game-panel">
          <div className="game-panel-header">Equipment</div>
          <div className="grid grid-cols-5 gap-1.5">
            {EQUIP_ORDER.map((slot) => {
              const it = equipped[slot];
              const label = slot.replace(/_/g, " ");
              return (
                <div key={slot} className="flex flex-col items-center gap-1">
                  <div
                    className={`relative w-full aspect-square ${it ? "slot-filled" : "slot-empty"}`}
                    style={it ? { borderColor: rarityBorderColor(it.rarity) } : undefined}
                    title={it ? `${it.name}${Number(it.enhancement_level ?? 0) > 0 ? ` +${it.enhancement_level}` : ""}` : label}
                  >
                    {it ? (
                      <ItemImg item={it} size="w-7 h-7" />
                    ) : (
                      <span className="text-sm opacity-30">{SLOT_ICONS[slot]}</span>
                    )}
                    {it && Number(it.enhancement_level ?? 0) > 0 && (
                      <span
                        className="absolute -bottom-0.5 -right-0.5 text-[8px] font-bold px-1 rounded-sm"
                        style={{
                          background: "hsl(228 22% 9%)",
                          color: "hsl(43 78% 50%)",
                          border: "1px solid hsl(43 50% 35% / 0.5)",
                        }}
                      >
                        +{it.enhancement_level}
                      </span>
                    )}
                  </div>
                  <span className="text-[8px] text-muted-foreground capitalize leading-none text-center">
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* INVENTORY */}
        <div className="game-panel">
          <div className="game-panel-header">Inventory</div>
          <div className="grid grid-cols-5 gap-1.5">
            {bag.length === 0 && (
              <>
                {Array.from({ length: 10 }).map((_, i) => (
                  <div key={i} className="slot-empty w-full aspect-square" />
                ))}
              </>
            )}
            {bag.map((it) => (
              <button
                key={it.id}
                type="button"
                className={`relative slot-filled w-full aspect-square transition-all ${
                  selectedBagItem === it.id ? "ring-1 ring-[hsl(43_78%_50%)]" : ""
                }`}
                style={{ borderColor: rarityBorderColor(it.rarity) }}
                title={`${it.name}${Number(it.quantity ?? 1) > 1 ? ` ×${it.quantity}` : ""}`}
                onClick={() => setSelectedBagItem(selectedBagItem === it.id ? null : it.id)}
              >
                <ItemImg item={it} size="w-7 h-7" />
                {Number(it.quantity ?? 1) > 1 && (
                  <span
                    className="absolute bottom-0 right-0.5 text-[8px] font-bold"
                    style={{ color: "hsl(38 25% 82%)", textShadow: "0 1px 2px hsl(0 0% 0% / 0.8)" }}
                  >
                    ×{it.quantity}
                  </span>
                )}
              </button>
            ))}
            {bag.length > 0 &&
              bag.length < 10 &&
              Array.from({ length: 10 - bag.length }).map((_, i) => (
                <div key={`empty-${i}`} className="slot-empty w-full aspect-square" />
              ))}
          </div>

          {/* Selected item actions */}
          {selectedBagItem && (() => {
            const it = bag.find((b) => b.id === selectedBagItem);
            if (!it) return null;
            const canEquip = Boolean(it.equip_slot);
            const canUse =
              (it.item_type || "").toLowerCase() === "consumable" &&
              directUse.has((it.effect_type || "").toLowerCase());
            return (
              <div className="mt-3 pt-3" style={{ borderTop: "1px solid hsl(228 16% 20%)" }}>
                <div className="flex items-center gap-2 mb-2">
                  <ItemImg item={it} size="w-6 h-6" />
                  <span className="text-xs font-semibold truncate">{it.name}</span>
                  {Number(it.enhancement_level ?? 0) > 0 && (
                    <span className="text-[10px] text-primary">+{it.enhancement_level}</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1">
                  {canUse && (
                    <button
                      className="game-btn-primary text-[10px] px-2 py-1"
                      type="button"
                      onClick={() => void runAction("/api/game/item/use", { item_id: it.id }, "Used")}
                    >
                      Use
                    </button>
                  )}
                  {canEquip && (
                    <button
                      className="game-btn-secondary text-[10px] px-2 py-1"
                      type="button"
                      onClick={() => void runAction("/api/game/item/equip", { item_id: it.id }, "Equipped")}
                    >
                      Equip
                    </button>
                  )}
                  {canEquip && (
                    <button
                      className="game-btn-secondary text-[10px] px-2 py-1"
                      type="button"
                      onClick={() => openEnhance(it.id)}
                    >
                      Enhance
                    </button>
                  )}
                  <button
                    className="game-btn-danger text-[10px] px-2 py-1"
                    type="button"
                    onClick={() => void runAction("/api/game/item/sell", { item_id: it.id }, "Sold")}
                  >
                    Sell
                  </button>
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* OPEN BLACKSMITH CTA */}
      <button
        type="button"
        className="game-btn-primary w-full py-3 text-sm"
        onClick={() => setShowBlacksmith(true)}
      >
        🔨 Open Blacksmith
      </button>

      {/* BLACKSMITH MODAL */}
      {showBlacksmith && (
        <BlacksmithModal
          item={{
            name: "Select an item",
            icon: "🔨",
            rarity: "common",
            level: 0,
          }}
          onClose={() => setShowBlacksmith(false)}
          onEnhance={() => {
            setShowBlacksmith(false);
            void refreshInventory();
          }}
        />
      )}

      {/* ENHANCE DIALOG (real API) */}
      <Dialog open={Boolean(enhanceItemId)} onOpenChange={(o) => !o && setEnhanceItemId(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              Enhance {enhanceInfo?.info?.item?.name ?? "item"}{" "}
              {enhanceInfo?.info?.current_level != null ? `(+${enhanceInfo.info.current_level})` : ""}
            </DialogTitle>
          </DialogHeader>
          {!enhanceInfo?.ok && enhanceInfo && (
            <p className="text-sm text-destructive">{enhanceInfo.message || enhanceInfo.error || "Cannot enhance."}</p>
          )}
          {enhanceInfo?.ok && enhanceInfo.info && (
            <div className="space-y-3 text-sm">
              <p>
                Next: +{enhanceInfo.info.next_level ?? "?"}{" "}
                {enhanceInfo.info.next_config && (
                  <>
                    · Cost <strong>{enhanceInfo.info.next_config.cost ?? 0}</strong> 🪙 · Base{" "}
                    {((enhanceInfo.info.next_config.success_rate ?? 0) * 100).toFixed(0)}% success
                  </>
                )}
              </p>
              {enhanceInfo.info.next_config?.can_break && (
                <p className="text-xs text-amber-600">Failure can destroy this item unless protected.</p>
              )}
              <div>
                <Label className="text-xs">Protection</Label>
                <RadioGroup value={prot} onValueChange={setProt} className="mt-1 space-y-1">
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="none" id="p-none" />
                    <Label htmlFor="p-none">None</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem
                      value="blessing_scroll"
                      id="p-bs"
                      disabled={(Number(enhanceInfo.protections?.blessing_scroll ?? 0) || 0) < 1}
                    />
                    <Label htmlFor="p-bs">
                      Blessing scroll (×{enhanceInfo.protections?.blessing_scroll ?? 0})
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem
                      value="safety_charm"
                      id="p-sc"
                      disabled={(Number(enhanceInfo.protections?.safety_charm ?? 0) || 0) < 1}
                    />
                    <Label htmlFor="p-sc">Safety charm (×{enhanceInfo.protections?.safety_charm ?? 0})</Label>
                  </div>
                </RadioGroup>
                <div className="flex gap-2 mt-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => void buyProtection("blessing_scroll", 1)}>
                    Buy blessing
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => void buyProtection("safety_charm", 1)}>
                    Buy charm
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => void buyProtection("enhancement_fragment", 3)}>
                    Buy fragments
                  </Button>
                </div>
              </div>
              <div>
                <Label className="text-xs">Fragments (+10% each, max 3)</Label>
                <Select
                  value={String(frags)}
                  onValueChange={(v) => setFrags(Number(v))}
                  disabled={(Number(enhanceInfo.protections?.enhancement_fragment ?? 0) || 0) < 1}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[0, 1, 2, 3].map((n) => (
                      <SelectItem key={n} value={String(n)} disabled={n > (Number(enhanceInfo.protections?.enhancement_fragment ?? 0) || 0)}>
                        {n}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setEnhanceItemId(null)}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={async () => {
                if (!enhanceItemId) return;
                const j = await postEnhance(enhanceItemId, prot === "none" ? null : prot, frags);
                toast(j.message || (j.ok ? "Enhanced" : "Failed"));
                setEnhanceItemId(null);
                setEnhanceInfo(null);
              }}
            >
              Enhance
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
