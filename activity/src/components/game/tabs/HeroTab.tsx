import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { EnhanceInfoPayload, InvRow } from "@/lib/apiTypes";
import { classIconUrl, specIconUrl } from "@/lib/classAndSpecIconUrl";
import { BlacksmithModal, type BlacksmithProtection } from "../modals/BlacksmithModal";
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
  const [status, setStatus] = useState("");

  const char = inventory?.character;
  const items = inventory?.items || [];
  const bag = useMemo(() => items.filter((i) => !i.is_equipped), [items]);
  const equipped = useMemo(() => {
    const m: Record<string, InvRow> = {};
    for (const it of items) if (it.is_equipped && it.equip_slot) m[it.equip_slot] = it;
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
        if (res.ok && j.ok !== false) setPinnedKey(null);
      } catch (e) {
        setStatus(String(e));
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

  return (
    <div className="space-y-4">
      {/* Character Stats */}
      <div className="game-panel">
        <div className="game-panel-header">Character Stats</div>
        {!char ? (
          <p className="text-sm text-muted-foreground">
            No character — use <code className="text-xs">/character create</code> in Discord.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <div className="flex items-center gap-3 text-sm flex-wrap">
                <Avatar className="w-7 h-7 shrink-0">
                  {inventory?.discord?.avatar_url ? (
                    <AvatarImage src={String(inventory.discord.avatar_url)} alt={char.name || "Avatar"} />
                  ) : (
                    <AvatarFallback className="text-[10px]">{(char.name || "?").slice(0, 2).toUpperCase()}</AvatarFallback>
                  )}
                </Avatar>
                <span className="text-foreground font-semibold font-cinzel text-base">{char.name}</span>
                <span className="text-primary font-pixel text-[10px]"
                  style={{ textShadow: '0 0 6px hsl(43 78% 50% / 0.3)' }}>Lv {char.level ?? "?"}</span>
                <span className="ornament-divider w-px h-4 inline-block" style={{ background: 'hsl(228 16% 25%)' }} />
                <span className="flex items-center gap-2">
                  <img
                    src={classIconUrl(char.class || "")}
                    alt=""
                    width={20}
                    height={20}
                    className="w-5 h-5 object-contain shrink-0 rounded-[2px]"
                    style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.35))" }}
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                  <span className="text-secondary-foreground">{char.class}</span>
                </span>
                {(char.specialization_name || char.specialization) && (
                  <>
                    <span className="ornament-divider w-px h-4 inline-block" style={{ background: 'hsl(228 16% 25%)' }} />
                    <span className="flex items-center gap-2">
                      {char.specialization && specIconUrl(char.specialization) && (
                        <img
                          src={specIconUrl(char.specialization)}
                          alt=""
                          width={18}
                          height={18}
                          className="w-[18px] h-[18px] object-contain shrink-0 rounded-[2px]"
                          style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.35))" }}
                          onError={(e) => {
                            (e.currentTarget as HTMLImageElement).style.display = "none";
                          }}
                        />
                      )}
                      <span className="text-accent-foreground text-xs italic">{char.specialization_name || char.specialization}</span>
                    </span>
                  </>
                )}
                {!char.specialization && !char.specialization_name && (
                  <button
                    type="button"
                    onClick={() => void requestSpecChoice()}
                    className="text-primary text-xs hover:underline font-semibold animate-pulse-glow"
                  >
                    Choose Spec!
                  </button>
                )}
              </div>
              <div className="flex items-center gap-1.5 text-sm">
                <span className="text-primary font-semibold font-cinzel"
                  style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.2)' }}>{Number(char.gold ?? 0).toLocaleString()}</span>
                <span>🪙</span>
              </div>
            </div>
            <div className="mb-3">
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-muted-foreground font-cinzel tracking-wider uppercase text-[10px]">Hit Points</span>
                <span className="text-foreground tabular-nums">{hp} / {maxHp || "—"}</span>
              </div>
              <div className="hp-bar-track">
                <div className="hp-bar-fill" style={{ width: `${hpPct}%` }} />
              </div>
            </div>

            <div className="ornament-divider mb-3" />
            <div className="flex gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => {
                  if (char.specialization || char.specialization_name) {
                    toast.info(
                      `Specialization: ${char.specialization_name || char.specialization}`,
                    );
                  } else {
                    void requestSpecChoice();
                  }
                }}
                className="game-btn-secondary text-xs px-3 py-1.5"
              >
                ⚔️ Specialization
              </button>
            </div>
          </>
        )}
        {status && <p className="text-xs text-muted-foreground mt-2">{status}</p>}
      </div>

      <div className="ornament-divider" />

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
          <div className="game-panel-header">Inventory</div>
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

    </div>
  );
}
