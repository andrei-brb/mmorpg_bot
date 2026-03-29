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

const BAG_SLOTS = 20;

/** Matches `legacy-main.ts` / `.rarity-*` in `style.css`. */
function rarityClassV0(rarity?: string | null): string {
  const v = (rarity || "").toLowerCase();
  if (v === "artifact") return "rarity-artifact";
  if (v === "legendary") return "rarity-legendary";
  if (v === "epic") return "rarity-epic";
  if (v === "rare") return "rarity-rare";
  if (v === "uncommon") return "rarity-uncommon";
  return "rarity-common";
}

export function HeroTab() {
  const {
    inventory,
    refreshInventory,
    itemPost,
    getEnhanceInfo,
    postEnhance,
    buyProtection,
    requestSpecChoice,
  } = useGameSession();

  const [status, setStatus] = useState("");
  const [enhanceItemId, setEnhanceItemId] = useState<string | null>(null);
  const [enhanceInfo, setEnhanceInfo] = useState<Awaited<ReturnType<typeof getEnhanceInfo>> | null>(null);
  const [prot, setProt] = useState<string>("none");
  const [frags, setFrags] = useState(0);
  const [activeInvId, setActiveInvId] = useState<string | null>(null);
  const [blacksmithOpen, setBlacksmithOpen] = useState(false);

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

  const specLine = char?.specialization_name || char?.specialization;
  const enhancableItems = useMemo(
    () => items.filter((i) => Boolean(i.equip_slot)),
    [items],
  );

  return (
    <div id="tab-hero" className="tab-pane space-y-4">
      <div className="hero-stats-card panel v0-panel">
        <div className="hero-stats-head">
          <div>
            <h2>Character Stats</h2>
            {!char ? (
              <p className="hint">
                No character yet — use <code>/character create</code> in Discord.
              </p>
            ) : (
              <p className="hint">
                <strong>{char.name}</strong> · Lv {char.level ?? "?"} · {String(char.class || "?")}
                {specLine ? ` · ${specLine}` : ""}
              </p>
            )}
            {char && (
              <div className="mt-2">
                <button type="button" className="mini-btn" onClick={() => void requestSpecChoice()}>
                  Specialization
                </button>
              </div>
            )}
          </div>
          {char && (
            <div className="hero-gold">
              <span>Gold</span>
              <strong className="hero-gold-amount">{Number(char.gold ?? 0).toLocaleString()}</strong>
            </div>
          )}
        </div>
        {char && (
          <div className="hero-hp-wrap">
            <div className="hero-hp-label-row">
              <span className="hero-hp-label">Hit points</span>
              <span className="hero-hp-numbers">{maxHp > 0 ? `${hp} / ${maxHp}` : "—"}</span>
            </div>
            <div className="hero-hp-bar">
              <div className="hero-hp-fill" style={{ width: `${hpPct}%` }} />
            </div>
          </div>
        )}
        {status ? (
          <p id="hero-action-status" className="hint" style={{ marginTop: "0.5rem" }}>
            {status}
          </p>
        ) : null}
      </div>

      <div className="hero-main-grid">
        <div className="panel v0-panel">
          <h2>Equipment</h2>
          <div className="equip-grid-v0">
            {EQUIP_ORDER.map((slot) => {
              const it = equipped[slot];
              const label = slot.replace("_", " ");
              if (!it) {
                return (
                  <div key={slot} className="equip-slot" data-slot={slot}>
                    {label}
                  </div>
                );
              }
              const enh = Number(it.enhancement_level ?? 0) || 0;
              return (
                <div
                  key={slot}
                  className={`equip-slot filled item-slot ${rarityClassV0(it.rarity)}`}
                  data-slot={slot}
                  data-item-id={it.id}
                >
                  <div className="equip-frame">
                    <span className="slot-icon">
                      <ItemIcon item={it} size={26} />
                    </span>
                    {enh > 0 ? <span className="enh-badge">+{enh}</span> : null}
                  </div>
                  <span className="equip-label">{label}</span>
                  <div className="equip-actions">
                    <button
                      type="button"
                      className="mini-btn act-enhance"
                      onClick={(e) => {
                        e.stopPropagation();
                        void openEnhance(it.id);
                      }}
                    >
                      Enhance
                    </button>
                    <button
                      type="button"
                      className="mini-btn act-unequip"
                      onClick={(e) => {
                        e.stopPropagation();
                        void runAction("/api/game/item/unequip", { slot }, "Unequipped");
                      }}
                    >
                      Unequip
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <button type="button" className="btn w-full mt-3" onClick={() => setBlacksmithOpen(true)}>
            🔨 Open Blacksmith
          </button>
        </div>

        <div className="panel v0-panel">
          <h2>Inventory ({bag.length})</h2>
          <div className="inv-grid">
            {bag.length === 0 ? (
              <p className="hint" style={{ gridColumn: "1 / -1" }}>
                No items in your bag yet.
              </p>
            ) : (
              <>
                {bag.map((it) => {
                  const qty = it.quantity ?? 1;
                  const canEquip = Boolean(it.equip_slot);
                  const canUse =
                    (it.item_type || "").toLowerCase() === "consumable" &&
                    directUse.has((it.effect_type || "").toLowerCase());
                  const enh = Number(it.enhancement_level ?? 0) || 0;
                  const enhSuffix = enh > 0 ? ` +${enh}` : "";
                  const qtyBadge = qty > 1 ? `x${qty}` : "";
                  const active = activeInvId === it.id;
                  return (
                    <div
                      key={it.id}
                      role="button"
                      tabIndex={0}
                      className={`inv-tile ${rarityClassV0(it.rarity)} ${active ? "inv-tile--active" : ""}`}
                      data-item-id={it.id}
                      onClick={() => setActiveInvId((id) => (id === it.id ? null : it.id))}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setActiveInvId((id) => (id === it.id ? null : it.id));
                        }
                      }}
                    >
                      <div className="inv-tile-main">
                        <div className="inv-frame">
                          <span className="inv-icon">
                            <ItemIcon item={it} size={32} />
                          </span>
                          {enh > 0 ? <span className="inv-badge inv-badge-enh">+{enh}</span> : null}
                          {qtyBadge ? <span className="inv-badge inv-badge-qty">{qtyBadge}</span> : null}
                        </div>
                        <span className="inv-tile-name">
                          {it.name}
                          {enhSuffix}
                        </span>
                      </div>
                      <div className="inv-tile-actions">
                        {canUse ? (
                          <button
                            type="button"
                            className="mini-btn act-use"
                            onClick={() => void runAction("/api/game/item/use", { item_id: it.id }, "Used")}
                          >
                            Use
                          </button>
                        ) : null}
                        {canEquip ? (
                          <button
                            type="button"
                            className="mini-btn act-equip"
                            onClick={() => void runAction("/api/game/item/equip", { item_id: it.id }, "Equipped")}
                          >
                            Equip
                          </button>
                        ) : null}
                        {canEquip ? (
                          <button type="button" className="mini-btn act-enhance" onClick={() => void openEnhance(it.id)}>
                            Enhance
                          </button>
                        ) : null}
                        <button
                          type="button"
                          className="mini-btn act-sell"
                          onClick={() => void runAction("/api/game/item/sell", { item_id: it.id }, "Sold")}
                        >
                          Sell
                        </button>
                      </div>
                    </div>
                  );
                })}
                {Array.from({ length: Math.max(0, BAG_SLOTS - bag.length) }).map((_, i) => (
                  <div key={`empty-${i}`} className="inv-tile inv-empty" tabIndex={-1}>
                    <span className="inv-tile-name">Empty slot</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </div>

      <Dialog open={blacksmithOpen} onOpenChange={setBlacksmithOpen}>
        <DialogContent className="max-w-md panel v0-panel border-[#28335d]">
          <DialogHeader>
            <DialogTitle className="font-cinzel">Blacksmith</DialogTitle>
          </DialogHeader>
          <p className="hint text-sm">Choose an item to enhance (same as Enhance on gear).</p>
          <ul className="max-h-64 overflow-y-auto space-y-2">
            {enhancableItems.length === 0 ? (
              <li className="hint text-sm">No gear to enhance.</li>
            ) : (
              enhancableItems.map((it) => (
                <li key={it.id} className="flex items-center justify-between gap-2 border border-[#29325a] rounded-sm p-2">
                  <span className="text-sm truncate">{it.name}</span>
                  <button
                    type="button"
                    className="mini-btn shrink-0"
                    onClick={() => {
                      setBlacksmithOpen(false);
                      void openEnhance(it.id);
                    }}
                  >
                    Enhance
                  </button>
                </li>
              ))
            )}
          </ul>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setBlacksmithOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
                      <SelectItem
                        key={n}
                        value={String(n)}
                        disabled={n > (Number(enhanceInfo.protections?.enhancement_fragment ?? 0) || 0)}
                      >
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
