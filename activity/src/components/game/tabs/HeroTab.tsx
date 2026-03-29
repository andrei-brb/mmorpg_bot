import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { InvRow } from "@/lib/apiTypes";
import { ItemIcon } from "@/components/game/ItemIcon";
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

function rarityClass(rarity?: string | null): string {
  const v = (rarity || "").toLowerCase();
  if (v === "legendary") return "text-rarity-legendary border-rarity-legendary/40";
  if (v === "epic") return "text-rarity-epic border-rarity-epic/40";
  if (v === "rare") return "text-rarity-rare border-rarity-rare/40";
  if (v === "uncommon") return "text-rarity-uncommon border-rarity-uncommon/40";
  return "text-rarity-common border-rarity-common/40";
}

export function HeroTab() {
  const {
    inventory,
    refreshInventory,
    itemPost,
    getEnhanceInfo,
    postEnhance,
    buyProtection,
  } = useGameSession();

  const [status, setStatus] = useState("");
  const [enhanceItemId, setEnhanceItemId] = useState<string | null>(null);
  const [enhanceInfo, setEnhanceInfo] = useState<Awaited<ReturnType<typeof getEnhanceInfo>> | null>(null);
  const [prot, setProt] = useState<string>("none");
  const [frags, setFrags] = useState(0);

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

  return (
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">Character</div>
        {!char ? (
          <p className="text-sm text-muted-foreground">
            No character — use <code className="text-xs">/character create</code> in Discord.
          </p>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-cinzel font-semibold">{char.name}</span>
              <span className="text-primary text-xs font-mono">Lv {char.level ?? "?"}</span>
              <span className="text-muted-foreground">{char.class}</span>
              {(char.specialization_name || char.specialization) && (
                <span className="text-xs italic text-accent-foreground">
                  · {char.specialization_name || char.specialization}
                </span>
              )}
              <span className="ml-auto text-primary font-cinzel">{Number(char.gold ?? 0).toLocaleString()} 🪙</span>
            </div>
            <div>
              <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
                <span>HP</span>
                <span>
                  {hp}/{maxHp || "—"}
                </span>
              </div>
              <div className="hp-bar-track">
                <div className="hp-bar-fill" style={{ width: `${hpPct}%` }} />
              </div>
            </div>
          </div>
        )}
        {status && <p className="text-xs text-muted-foreground mt-2">{status}</p>}
      </div>

      <div className="game-panel">
        <div className="game-panel-header">Equipment</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {EQUIP_ORDER.map((slot) => {
            const it = equipped[slot];
            const label = slot.replace("_", " ");
            if (!it) {
              return (
                <div key={slot} className="rounded-sm border border-dashed border-border p-2 text-[10px] text-muted-foreground capitalize">
                  {label}
                </div>
              );
            }
            return (
              <div key={slot} className={`rounded-sm border p-2 ${rarityClass(it.rarity)}`}>
                <div className="text-[10px] capitalize text-muted-foreground mb-1">{label}</div>
                <div className="flex items-center gap-2">
                  <ItemIcon item={it} size={32} className="shrink-0 w-8 h-8" />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold truncate">{it.name}</div>
                    {Number(it.enhancement_level ?? 0) > 0 && (
                      <div className="text-[10px] text-primary">+{it.enhancement_level}</div>
                    )}
                  </div>
                </div>
                <div className="flex gap-1 mt-2">
                  <Button size="sm" variant="secondary" className="h-7 text-[10px]" type="button" onClick={() => openEnhance(it.id)}>
                    Enhance
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-[10px]"
                    type="button"
                    onClick={() => runAction("/api/game/item/unequip", { slot }, "Unequipped")}
                  >
                    Unequip
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="game-panel">
        <div className="game-panel-header">Inventory ({bag.length})</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {bag.length === 0 && <p className="text-xs text-muted-foreground">Empty bag.</p>}
          {bag.map((it) => {
            const canEquip = Boolean(it.equip_slot);
            const canUse =
              (it.item_type || "").toLowerCase() === "consumable" &&
              directUse.has((it.effect_type || "").toLowerCase());
            return (
              <div key={it.id} className={`rounded-sm border p-2 ${rarityClass(it.rarity)}`}>
                <div className="flex gap-2 items-center">
                  <ItemIcon item={it} size={36} className="shrink-0 w-9 h-9" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold truncate">
                      {it.name}
                      {Number(it.quantity ?? 1) > 1 ? ` ×${it.quantity}` : ""}
                    </div>
                    {Number(it.enhancement_level ?? 0) > 0 && (
                      <div className="text-[10px] text-primary">+{it.enhancement_level}</div>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {canUse && (
                    <Button
                      size="sm"
                      className="h-7 text-[10px]"
                      type="button"
                      onClick={() => runAction("/api/game/item/use", { item_id: it.id }, "Used")}
                    >
                      Use
                    </Button>
                  )}
                  {canEquip && (
                    <Button
                      size="sm"
                      variant="secondary"
                      className="h-7 text-[10px]"
                      type="button"
                      onClick={() => runAction("/api/game/item/equip", { item_id: it.id }, "Equipped")}
                    >
                      Equip
                    </Button>
                  )}
                  {canEquip && (
                    <Button size="sm" variant="outline" className="h-7 text-[10px]" type="button" onClick={() => openEnhance(it.id)}>
                      Enhance
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-[10px]"
                    type="button"
                    onClick={() => runAction("/api/game/item/sell", { item_id: it.id }, "Sold")}
                  >
                    Sell
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

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
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => void buyProtection("blessing_scroll", 1)}
                  >
                    Buy blessing
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => void buyProtection("safety_charm", 1)}>
                    Buy charm
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => void buyProtection("enhancement_fragment", 3)}
                  >
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
