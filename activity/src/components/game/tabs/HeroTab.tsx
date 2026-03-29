import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { InvRow } from "@/lib/apiTypes";
import { BlacksmithModal } from "../modals/BlacksmithModal";
import { ItemIcon } from "../ItemIcon";
import { ItemTooltipPanel } from "../ItemTooltipPanel";
import { SpecializationModal } from "../modals/SpecializationModal";

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

export function HeroTab() {
  const {
    inventory, refreshInventory, itemPost,
    getEnhanceInfo, postEnhance, buyProtection,
  } = useGameSession();

  /** Hover: stats only. Click: `pinnedKey` keeps actions open until outside click or same slot toggled. */
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const [pinnedKey, setPinnedKey] = useState<string | null>(null);
  const [enhanceItemId, setEnhanceItemId] = useState<string | null>(null);
  const [showSpec, setShowSpec] = useState(false);
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

  const equipmentSlots = EQUIP_ORDER.map((slot) => ({
    id: slot,
    label: SLOT_LABELS[slot],
    item: equipped[slot] || null,
  }));

  const EMPTY_SLOTS = 20;
  const invSlots = [
    ...bag.map((it) => ({ id: it.id, name: it.name, icon: it.icon || SLOT_ICONS[it.equip_slot || ""] || "📦", rarity: rarityKey(it.rarity), item: it })),
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
                <span className="text-foreground font-semibold font-cinzel text-base">{char.name}</span>
                <span className="text-primary font-pixel text-[10px]"
                  style={{ textShadow: '0 0 6px hsl(43 78% 50% / 0.3)' }}>Lv {char.level ?? "?"}</span>
                <span className="ornament-divider w-px h-4 inline-block" style={{ background: 'hsl(228 16% 25%)' }} />
                <span className="text-secondary-foreground">{char.class}</span>
                {(char.specialization_name || char.specialization) && (
                  <>
                    <span className="ornament-divider w-px h-4 inline-block" style={{ background: 'hsl(228 16% 25%)' }} />
                    <span className="text-accent-foreground text-xs italic">{char.specialization_name || char.specialization}</span>
                  </>
                )}
                {!char.specialization && !char.specialization_name && (
                  <button onClick={() => setShowSpec(true)}
                    className="text-primary text-xs hover:underline font-semibold animate-pulse-glow">
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
              <button onClick={() => setShowSpec(true)} className="game-btn-secondary text-xs px-3 py-1.5">
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
          <button onClick={() => {
            const first = items.find(i => i.is_equipped);
            if (first) setEnhanceItemId(first.id);
            else toast("No items to enhance");
          }} className="game-btn-primary text-xs w-full">
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
                          {it.equip_slot && (
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

      {/* Blacksmith Modal — uses real enhance API */}
      {enhanceItemId && (() => {
        const it = items.find(i => i.id === enhanceItemId);
        if (!it) return null;
        return (
          <BlacksmithModal
            item={{
              name: it.name,
              icon: SLOT_ICONS[it.equip_slot || ""] || "⚔️",
              rarity: rarityKey(it.rarity),
              level: Number(it.enhancement_level ?? 0),
            }}
            onClose={() => setEnhanceItemId(null)}
            onEnhance={async () => {
              try {
                const j = await postEnhance(enhanceItemId, null, 0);
                toast(j.message || (j.ok ? "Enhanced!" : "Failed"));
              } catch (e) { toast.error(String(e)); }
              setEnhanceItemId(null);
              await refreshInventory();
            }}
          />
        );
      })()}

      {/* Specialization Modal */}
      {showSpec && (
        <SpecializationModal
          playerLevel={char?.level ?? 0}
          currentSpec={char?.specialization || null}
          onClose={() => setShowSpec(false)}
          onChoose={(key) => { setShowSpec(false); toast(`Chose: ${key}`); }}
        />
      )}
    </div>
  );
}
