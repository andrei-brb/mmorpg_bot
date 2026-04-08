import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { EnhanceInfoPayload, InvRow } from "@/lib/apiTypes";
import { classIconUrl, specIconUrl } from "@/lib/classAndSpecIconUrl";
import { BlacksmithModal, type BlacksmithProtection } from "../modals/BlacksmithModal";
import { ListItemModal } from "../modals/ListItemModal";
import { ItemIcon } from "../ItemIcon";
import { ItemTooltipPanel } from "../ItemTooltipPanel";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";

const EQUIP_ORDER = [
  "head", "chest", "hands", "legs", "feet",
  "main_hand", "off_hand", "neck", "ring", "trinket",
] as const;

const SLOT_LABELS: Record<string, string> = {
  head: "Head", chest: "Chest", hands: "Hands", legs: "Legs", feet: "Feet",
  main_hand: "Main Hand", off_hand: "Off Hand", neck: "Neck", ring: "Ring", trinket: "Trinket",
};

const SLOT_ICONS: Record<string, string> = {
  head: "🪖", chest: "🛡️", hands: "🧤", legs: "🦿", feet: "👢",
  main_hand: "⚔️", off_hand: "🛡️", neck: "📿", ring: "💍", trinket: "💎",
};

const RARITY_COLORS: Record<string, string> = {
  common: "text-rarity-common border-rarity-common/40",
  uncommon: "text-rarity-uncommon border-rarity-uncommon/40",
  rare: "text-rarity-rare border-rarity-rare/40",
  epic: "text-rarity-epic border-rarity-epic/40",
  legendary: "text-rarity-legendary border-rarity-legendary/40",
};

function rarityKey(rarity?: string | null) {
  return (rarity || "common").toLowerCase();
}

/** Template slot for icons / actions; `equip_slot` alone was overwritten by SQL before `template_equip_slot` existed. */
function gearSlot(it: InvRow): string | null {
  const s = (it.template_equip_slot || it.equip_slot || "").trim();
  return s || null;
}

function isProtectionTemplate(it: InvRow): boolean {
  return (it.template_id || "").toLowerCase().startsWith("protection_");
}

function isEnhanceableGear(it: InvRow): boolean {
  if (!gearSlot(it) || isProtectionTemplate(it)) return false;
  const t = (it.item_type || "").toLowerCase();
  if (t === "consumable") return false;
  return true;
}

type StatKey =
  | "STR"
  | "AGI"
  | "INT"
  | "SPI"
  | "STA"
  | "Armor"
  | "Haste"
  | "Lifesteal"
  | "Resistance"
  | "Hit"
  | "DamageMin"
  | "DamageMax";

function itemEffectiveStats(item: InvRow): Partial<Record<StatKey, number>> {
  const out: Partial<Record<StatKey, number>> = {};
  const type = (item.item_type || "").toLowerCase();
  if (type === "consumable") return out;

  const enhLevel = Math.max(0, Math.min(10, Number(item.enhancement_level ?? 0) || 0));
  const enhMult = 1 + enhLevel * 0.1;
  const n = (v: unknown) => Number(v ?? 0) || 0;

  const sum = (base: unknown, bonus: unknown) => n(base) + n(bonus);
  const push = (k: StatKey, v: number) => {
    if (!v) return;
    out[k] = v;
  };

  push("STR", Math.floor(sum(item.s_str, item.r_str) * enhMult));
  push("AGI", Math.floor(sum(item.s_agi, item.r_agi) * enhMult));
  push("INT", Math.floor(sum(item.s_int, item.r_int) * enhMult));
  push("SPI", Math.floor(sum(item.s_spi, item.r_spi) * enhMult));
  push("STA", Math.floor(sum(item.s_sta, item.r_sta) * enhMult));
  push("Haste", Math.floor(sum(item.s_haste, item.r_haste) * enhMult));
  push("Lifesteal", Math.floor(sum(item.s_lifesteal, item.r_lifesteal) * enhMult));
  push("Resistance", Math.floor(sum(item.s_resistance, item.r_resistance) * enhMult));
  push("Hit", Math.floor(sum(item.s_hit_rating, item.r_hit_rating) * enhMult));
  push("Armor", Math.floor(n(item.s_armor) * enhMult));
  push("DamageMin", Math.floor(n(item.s_dmg_min) * enhMult));
  push("DamageMax", Math.floor(n(item.s_dmg_max) * enhMult));

  return out;
}

function statLabel(k: string): string {
  if (k === "DamageMin") return "Damage (min)";
  if (k === "DamageMax") return "Damage (max)";
  return k;
}

export function HeroTab() {
  const {
    inventory, refreshInventory, itemPost,
    getEnhanceInfo, postEnhance, buyProtection, requestSpecChoice,
  } = useGameSession();

  /** Hover: stats only. Click: `pinnedKey` keeps actions open until outside click or same slot toggled. */
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const [pinnedKey, setPinnedKey] = useState<string | null>(null);
  const [enhanceItemId, setEnhanceItemId] = useState<string | null>(null);
  const [enhancePayload, setEnhancePayload] = useState<EnhanceInfoPayload | null>(null);
  const [enhanceInfoLoading, setEnhanceInfoLoading] = useState(false);
  const [blacksmithPickerOpen, setBlacksmithPickerOpen] = useState(false);
  const [listItemId, setListItemId] = useState<string | null>(null);

  const char = inventory?.character;
  const items = inventory?.items || [];
  const bag = useMemo(() => items.filter((i) => !i.is_equipped), [items]);
  const equipped = useMemo(() => {
    const m: Record<string, InvRow> = {};
    for (const it of items) if (it.is_equipped && it.equip_slot) m[it.equip_slot] = it;
    return m;
  }, [items]);

  const runAction = useCallback(
    async (endpoint: string, body: Record<string, unknown>, msg: string) => {
      try {
        const res = await itemPost(endpoint, body);
        const j = (await res.json()) as { ok?: boolean; message?: string };
        toast(j.message || msg);
        await refreshInventory();
        if (res.ok && j.ok !== false) setPinnedKey(null);
      } catch (e) {
        toast.error(String(e));
      }
    },
    [itemPost, refreshInventory],
  );

  useEffect(() => {
    if (!pinnedKey) return;
    const onDown = (e: MouseEvent) => {
      const el = document.querySelector(`[data-item-slot="${CSS.escape(pinnedKey)}"]`);
      if (el && e.target instanceof Node && el.contains(e.target)) return;
      setPinnedKey(null);
    };
    document.addEventListener("mousedown", onDown, true);
    return () => document.removeEventListener("mousedown", onDown, true);
  }, [pinnedKey]);

  useEffect(() => {
    if (!enhanceItemId) {
      setEnhancePayload(null);
      setEnhanceInfoLoading(false);
      return;
    }
    let cancelled = false;
    setEnhancePayload(null);
    setEnhanceInfoLoading(true);
    void getEnhanceInfo(enhanceItemId)
      .then((p) => {
        if (!cancelled) setEnhancePayload(p);
      })
      .catch((e) => {
        if (!cancelled) setEnhancePayload({ ok: false, message: String(e) });
      })
      .finally(() => {
        if (!cancelled) setEnhanceInfoLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [enhanceItemId, getEnhanceInfo]);

  const equipmentSlots = EQUIP_ORDER.map((slot) => ({
    id: slot,
    label: SLOT_LABELS[slot],
    item: equipped[slot] || null,
  }));

  const blacksmithCandidates = useMemo(() => {
    const out: InvRow[] = [];
    const eq: Record<string, InvRow> = {};
    for (const it of items) {
      if (it.is_equipped && it.equip_slot) eq[it.equip_slot] = it;
    }
    for (const slot of EQUIP_ORDER) {
      const it = eq[slot];
      if (it && isEnhanceableGear(it)) out.push(it);
    }
    for (const it of items) {
      if (it.is_equipped) continue;
      if (isEnhanceableGear(it)) out.push(it);
    }
    return out;
  }, [items]);

  const EMPTY_SLOTS = 20;
  const invSlots = [
    ...bag.map((it) => ({ id: it.id, name: it.name, icon: it.icon || SLOT_ICONS[gearSlot(it) || ""] || "📦", rarity: rarityKey(it.rarity), item: it })),
    ...Array.from({ length: Math.max(0, EMPTY_SLOTS - bag.length) }, (_, i) => ({ id: `empty-${i}`, name: null as string | null, icon: null as string | null, rarity: null as string | null, item: null as InvRow | null })),
  ];

  const compareForItem = useCallback(
    (it: InvRow) => {
      const slot = gearSlot(it);
      if (!slot) return null;
      const type = (it.item_type || "").toLowerCase();
      if (type === "consumable") return null;
      const eq = equipped[slot] || null;
      if (!eq || eq.id === it.id) return null;

      const a = itemEffectiveStats(it);
      const b = itemEffectiveStats(eq);
      const keys = new Set<StatKey>([...(Object.keys(a) as StatKey[]), ...(Object.keys(b) as StatKey[])]);
      const deltas: Array<{ k: string; v: number }> = [];
      for (const k of keys) {
        const dv = (a[k] || 0) - (b[k] || 0);
        if (dv) deltas.push({ k, v: dv });
      }
      deltas.sort((x, y) => Math.abs(y.v) - Math.abs(x.v));
      if (deltas.length === 0) return null;

      return (
        <div className="mt-1.5">
          <div className="text-[10px] text-muted-foreground">
            Equipped: <span className="text-foreground/90">{eq.name}</span>
          </div>
          <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5">
            {deltas.slice(0, 10).map(({ k, v }) => (
              <div key={k} className="flex items-center justify-between text-[10px] tabular-nums">
                <span className="text-muted-foreground">{statLabel(k)}</span>
                <span className={v > 0 ? "text-emerald-400" : "text-destructive"}>
                  {v > 0 ? `+${v}` : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    },
    [equipped],
  );

  return (
    <div className="space-y-4">
      {/* Two columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Equipment */}
        <div className="game-panel">
          <div className="game-panel-header">Equipment</div>
          <div className="grid grid-cols-5 gap-2">
            {equipmentSlots.map((slot) => {
              const it = slot.item;
              const rc = it ? RARITY_COLORS[rarityKey(it.rarity)] || "" : "";
              const showHoverTip = it && hoveredKey === slot.id && pinnedKey !== slot.id;
              const showPinned = it && pinnedKey === slot.id;
              return (
                <div
                  key={slot.id}
                  data-item-slot={slot.id}
                  className={`relative aspect-square ${it ? `slot-filled ${rc} cursor-pointer` : "slot-empty"}`}
                  onMouseEnter={() => it && setHoveredKey(slot.id)}
                  onMouseLeave={() => setHoveredKey(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!it) return;
                    setPinnedKey((p) => (p === slot.id ? null : slot.id));
                  }}
                >
                  {it ? (
                    <div className="absolute inset-0 flex items-center justify-center p-0.5">
                      <ItemIcon item={it} size={46} />
                      {Number(it.enhancement_level ?? 0) > 0 && (
                        <span
                          className="pointer-events-none absolute bottom-0.5 right-0.5 text-[8px] font-bold leading-none text-primary"
                          style={{ textShadow: "0 0 4px hsl(43 78% 50% / 0.4)" }}
                        >
                          +{it.enhancement_level}
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-[8px] leading-tight text-center opacity-50 font-cinzel">{slot.label}</span>
                  )}
                  {showHoverTip && (
                    <div className="pointer-events-none game-tooltip bottom-full left-1/2 z-30 -translate-x-1/2 mb-2 max-w-[min(92vw,280px)] whitespace-normal text-left">
                      <ItemTooltipPanel item={it} rarityClass={rc} />
                    </div>
                  )}
                  {showPinned && (
                    <div className="game-tooltip bottom-full left-1/2 z-40 -translate-x-1/2 mb-2 max-w-[min(92vw,280px)] whitespace-normal text-left shadow-lg">
                      <ItemTooltipPanel item={it} rarityClass={rc}>
                        <div className="flex flex-wrap gap-1">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setPinnedKey(null);
                              setEnhanceItemId(it.id);
                            }}
                            className="game-btn-primary text-[9px] px-2 py-0.5"
                          >
                            🔨 Enhance
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              void runAction("/api/game/item/unequip", { slot: slot.id }, "Unequipped");
                            }}
                            className="game-btn-secondary text-[9px] px-2 py-0.5"
                          >
                            Unequip
                          </button>
                        </div>
                      </ItemTooltipPanel>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="ornament-divider my-3" />
          <button
            type="button"
            onClick={() => {
              const list = blacksmithCandidates;
              if (list.length === 0) toast("No gear to enhance");
              else if (list.length === 1) setEnhanceItemId(list[0].id);
              else setBlacksmithPickerOpen(true);
            }}
            className="game-btn-primary text-xs w-full"
          >
            🔨 Open Blacksmith
          </button>
        </div>

        {/* Inventory */}
        <div className="game-panel">
          <div className="game-panel-header flex items-center justify-between">
            <span>Inventory</span>
            <span className="text-xs font-semibold font-cinzel text-primary tabular-nums" style={{ textShadow: "0 0 4px hsl(43 78% 50% / 0.2)" }}>
              {Number(char?.gold ?? 0).toLocaleString()} 🪙
            </span>
          </div>
          <div className="grid grid-cols-5 gap-2">
            {invSlots.map((inv) => {
              const rc = inv.rarity ? RARITY_COLORS[inv.rarity] || "" : "";
              const invKey = `inv-${inv.id}`;
              const it = inv.item;
              const showHoverTip = it && hoveredKey === invKey && pinnedKey !== invKey;
              const showPinned = it && pinnedKey === invKey;
              return (
                <div
                  key={inv.id}
                  data-item-slot={invKey}
                  className={`relative aspect-square ${inv.name ? `slot-filled ${rc} ${it ? "cursor-pointer" : ""}` : "slot-empty"}`}
                  onMouseEnter={() => inv.name && setHoveredKey(invKey)}
                  onMouseLeave={() => setHoveredKey(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!it) return;
                    setPinnedKey((p) => (p === invKey ? null : invKey));
                  }}
                >
                  {it ? (
                    <div className="absolute inset-0 flex items-center justify-center p-0.5">
                      <ItemIcon item={it} size={46} />
                      {Number(it.enhancement_level ?? 0) > 0 && (
                        <span
                          className="pointer-events-none absolute bottom-0.5 right-0.5 text-[8px] font-bold leading-none text-primary"
                          style={{ textShadow: "0 0 4px hsl(43 78% 50% / 0.4)" }}
                        >
                          +{it.enhancement_level}
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-[7px] leading-tight text-center opacity-30">Empty</span>
                  )}
                  {it && Number(it.quantity ?? 1) > 1 && (
                    <span className="absolute bottom-0.5 right-1 text-[8px] font-bold text-foreground"
                      style={{ textShadow: '0 1px 2px hsl(0 0% 0% / 0.8)' }}>×{it.quantity}</span>
                  )}
                  {showHoverTip && (
                    <div className="pointer-events-none game-tooltip bottom-full left-1/2 z-30 -translate-x-1/2 mb-2 max-w-[min(92vw,280px)] whitespace-normal text-left">
                      <ItemTooltipPanel item={it} rarityClass={rc} />
                    </div>
                  )}
                  {showPinned && (
                    <div className="game-tooltip bottom-full left-1/2 z-40 -translate-x-1/2 mb-2 max-w-[min(92vw,280px)] whitespace-normal text-left shadow-lg">
                      <ItemTooltipPanel item={it} rarityClass={rc}>
                        <div className="space-y-2">
                          {compareForItem(it)}
                          <div className="flex flex-wrap gap-1.5">
                          {(it.item_type || "").toLowerCase() === "consumable" && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                void runAction("/api/game/item/use", { item_id: it.id }, "Used");
                              }}
                              className="game-btn-secondary px-2 py-0.5 text-[10px]"
                            >
                              Use
                            </button>
                          )}
                          {gearSlot(it) && (
                            <>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setPinnedKey(null);
                                  setEnhanceItemId(it.id);
                                }}
                                className="game-btn-primary px-2 py-0.5 text-[10px]"
                              >
                                🔨 Enhance
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void runAction("/api/game/item/equip", { item_id: it.id }, "Equipped");
                                }}
                                className="game-btn-secondary px-2 py-0.5 text-[10px]"
                              >
                                Equip
                              </button>
                            </>
                          )}
                          {gearSlot(it) && !it.is_equipped && (it.item_type || "").toLowerCase() !== "consumable" && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setPinnedKey(null);
                                setListItemId(it.id);
                              }}
                              className="game-btn-primary px-2 py-0.5 text-[10px]"
                            >
                              📦 List
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              void runAction("/api/game/item/sell", { item_id: it.id }, "Sold");
                            }}
                            className="game-btn-secondary px-2 py-0.5 text-[10px]"
                          >
                            Sell
                          </button>
                          </div>
                        </div>
                      </ItemTooltipPanel>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {blacksmithPickerOpen && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ background: "hsl(0 0% 0% / 0.7)", backdropFilter: "blur(4px)" }}
          onClick={() => setBlacksmithPickerOpen(false)}
        >
          <div className="game-panel w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="game-panel-header">Choose item to enhance</div>
            <ul className="max-h-72 overflow-y-auto space-y-1 mb-4">
              {blacksmithCandidates.map((it) => (
                <li key={it.id}>
                  <button
                    type="button"
                    className="w-full text-left game-btn-secondary text-xs py-2 px-3 flex items-center gap-2"
                    onClick={() => {
                      setEnhanceItemId(it.id);
                      setBlacksmithPickerOpen(false);
                    }}
                  >
                    <span className="shrink-0">
                      <ItemIcon item={it} size={22} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="font-cinzel font-semibold">{it.name}</span>
                      {Number(it.enhancement_level ?? 0) > 0 && (
                        <span className="text-primary"> +{it.enhancement_level}</span>
                      )}
                      {it.is_equipped && <span className="text-muted-foreground"> · Equipped</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex justify-end">
              <button type="button" className="game-btn-secondary text-xs" onClick={() => setBlacksmithPickerOpen(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Blacksmith Modal — uses real enhance API */}
      {enhanceItemId && (() => {
        const it = items.find(i => i.id === enhanceItemId);
        if (!it) return null;
        return (
          <BlacksmithModal
            item={{
              id: it.id,
              name: it.name,
              template_id: it.template_id,
              icon: it.icon || null,
              rarity: rarityKey(it.rarity),
              level: Number(it.enhancement_level ?? 0),
            }}
            enhancePayload={enhancePayload}
            infoLoading={enhanceInfoLoading}
            onClose={() => setEnhanceItemId(null)}
            onBuyProtection={async (protectionKey: string, quantity: number) => {
              try {
                const j = await buyProtection(protectionKey, quantity);
                toast(j.message || (j.ok !== false ? "Purchased" : "Failed"));
                if (j.ok !== false) {
                  const p = await getEnhanceInfo(enhanceItemId);
                  setEnhancePayload(p);
                }
              } catch (e) {
                toast.error(String(e));
              }
            }}
            onEnhance={async (protection: BlacksmithProtection, fragments: number) => {
              const prot =
                protection === "blessing"
                  ? "blessing_scroll"
                  : protection === "charm"
                    ? "safety_charm"
                    : null;
              try {
                const j = await postEnhance(enhanceItemId, prot, fragments);
                const enhanceMsg = j.message || (j.ok !== false ? "Enhanced!" : "Failed");
                if (j.ok !== false) {
                  toast.success(enhanceMsg);
                  const p = await getEnhanceInfo(enhanceItemId);
                  setEnhancePayload(p);
                } else {
                  toast.error(enhanceMsg);
                }
              } catch (e) {
                toast.error(String(e));
              }
            }}
          />
        );
      })()}

      {/* List Item Modal */}
      {listItemId && (() => {
        const it = items.find(i => i.id === listItemId);
        if (!it) return null;
        return (
          <ListItemModal
            item={it}
            onClose={() => setListItemId(null)}
            onSuccess={() => {
              setListItemId(null);
              setPinnedKey(null);
            }}
          />
        );
      })()}

    </div>
  );
}
