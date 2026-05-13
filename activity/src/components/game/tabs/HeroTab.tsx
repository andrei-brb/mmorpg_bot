import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CharacterDerivedStatsPayload, EnhanceInfoPayload, IdleRewardsPayload, InvRow } from "@/lib/apiTypes";
import { classIconUrl } from "@/lib/classAndSpecIconUrl";
import { getCharacterDerivedStats, getIdleRewards, postIdleClaim } from "@/lib/gameApi";
import { BlacksmithModal, type BlacksmithProtection } from "../modals/BlacksmithModal";
import { ListItemModal } from "../modals/ListItemModal";
import { ItemIcon } from "../ItemIcon";
import { ItemTooltipPanel } from "../ItemTooltipPanel";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";

const EQUIP_ORDER = [
  "head", "chest", "hands", "legs", "feet",
  "main_hand", "off_hand", "neck", "ring", "trinket",
] as const;

/** Left column (top → bottom): armor block. Right: weapons & accessories. */
const PAPER_LEFT_SLOTS = ["head", "chest", "hands", "legs", "feet"] as const;
const PAPER_RIGHT_SLOTS = ["main_hand", "off_hand", "neck", "ring", "trinket"] as const;

const SLOT_LABELS: Record<string, string> = {
  head: "Head", chest: "Chest", hands: "Hands", legs: "Legs", feet: "Feet",
  main_hand: "Main Hand", off_hand: "Off Hand", neck: "Neck", ring: "Ring", trinket: "Trinket",
};

const SLOT_ICONS: Record<string, string> = {
  head: "🪖", chest: "🛡️", hands: "🧤", legs: "🦿", feet: "👢",
  main_hand: "⚔️", off_hand: "🛡️", neck: "📿", ring: "💍", trinket: "💎",
};

/** Unified icon size for both paper-doll and bag tiles so all slots match. */
const HERO_ITEM_ICON = 38;
const HERO_BAG_ITEM_ICON = HERO_ITEM_ICON;

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
  if (t === "consumable" || t === "quest" || t === "material" || t === "cosmetic") return false;
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
    getEnhanceInfo, postEnhance, buyProtection,
    accessToken, guildId, refreshProgress,
  } = useGameSession();

  const [idleRewards, setIdleRewards] = useState<IdleRewardsPayload | null>(null);
  const [idleLoading, setIdleLoading] = useState(false);
  const [idleClaiming, setIdleClaiming] = useState(false);
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const [pinnedKey, setPinnedKey] = useState<string | null>(null);
  const [enhanceItemId, setEnhanceItemId] = useState<string | null>(null);
  const [enhancePayload, setEnhancePayload] = useState<EnhanceInfoPayload | null>(null);
  const [enhanceInfoLoading, setEnhanceInfoLoading] = useState(false);
  const [blacksmithPickerOpen, setBlacksmithPickerOpen] = useState(false);
  const [listItemId, setListItemId] = useState<string | null>(null);
  const [inventoryView, setInventoryView] = useState<"gear" | "consumables" | "materials">("gear");
  const [derivedStats, setDerivedStats] = useState<CharacterDerivedStatsPayload | null>(null);
  const [batchSellMode, setBatchSellMode] = useState(false);
  const [batchSellIds, setBatchSellIds] = useState<Set<string>>(() => new Set());
  const [batchSelling, setBatchSelling] = useState(false);
  const [inventoryPage, setInventoryPage] = useState(0);

  const char = inventory?.character;
  const items = inventory?.items || [];

  useEffect(() => {
    if (!accessToken || !char) {
      setIdleRewards(null);
      return;
    }
    let cancelled = false;
    setIdleLoading(true);
    void getIdleRewards(accessToken, guildId)
      .then((j) => {
        if (!cancelled) setIdleRewards(j);
      })
      .catch(() => {
        if (!cancelled) setIdleRewards({ ok: false, error: "fetch_failed" });
      })
      .finally(() => {
        if (!cancelled) setIdleLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId, char?.name, char?.level]);

  useEffect(() => {
    if (!accessToken || !char) {
      setDerivedStats(null);
      return;
    }
    let cancelled = false;
    void getCharacterDerivedStats(accessToken, guildId)
      .then((s) => {
        if (!cancelled) setDerivedStats(s);
      })
      .catch(() => {
        if (!cancelled) setDerivedStats(null);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId, char?.name, char?.level, items]);

  const claimIdleRewards = useCallback(async () => {
    if (!accessToken || idleClaiming) return;
    setIdleClaiming(true);
    try {
      const j = await postIdleClaim(accessToken, guildId);
      setIdleRewards(j);
      if (!j.ok) {
        toast.error(j.error === "no_character" ? "No character found." : "Could not claim offline earnings.");
        return;
      }
      if (j.claimed) {
        const gx = typeof j.xp_result?.xp_gained === "number" ? j.xp_result.xp_gained : j.pending_xp;
        const gg = j.gold_gained ?? j.pending_gold ?? 0;
        toast.success(`Collected ${gx ?? 0} XP and ${gg}🪙.`);
        await refreshInventory();
        await refreshProgress();
      } else if (j.message) {
        toast.message(j.message);
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setIdleClaiming(false);
    }
  }, [accessToken, guildId, idleClaiming, refreshInventory, refreshProgress]);

  /** Hover: stats only. Click: `pinnedKey` keeps actions open until outside click or same slot toggled. */
  const bag = useMemo(() => items.filter((i) => !i.is_equipped), [items]);
  const bagSlotsMax = Number(inventory?.bag_slots_max ?? 0) || 0;
  const bagSlotsUsed = Number(inventory?.bag_slots_used ?? bag.length) || 0;
  const bagSlotsFree = Math.max(0, (bagSlotsMax || 0) - (bagSlotsUsed || 0));
  const bagConsumablesOnly = useMemo(() => {
    return bag.filter((it) => (it.item_type || "").toLowerCase() === "consumable");
  }, [bag]);
  const bagMaterials = useMemo(() => {
    return bag.filter((it) => {
      const t = (it.item_type || "").toLowerCase();
      return t === "material" || t === "quest" || isProtectionTemplate(it);
    });
  }, [bag]);
  const bagGear = useMemo(() => {
    return bag.filter((it) => {
      const t = (it.item_type || "").toLowerCase();
      if (t === "consumable" || t === "material" || t === "quest" || isProtectionTemplate(it)) return false;
      return true;
    });
  }, [bag]);
  const bagShown =
    inventoryView === "consumables"
      ? bagConsumablesOnly
      : inventoryView === "materials"
        ? bagMaterials
        : bagGear;

  const SLOTS_PER_PAGE = 20; // 4 rows x 5 columns
  const maxInvPage = Math.max(0, Math.ceil(bagShown.length / SLOTS_PER_PAGE) - 1);
  const invPage = Math.max(0, Math.min(inventoryPage, maxInvPage));
  const invPageStart = invPage * SLOTS_PER_PAGE;
  const bagShownPage = useMemo(
    () => bagShown.slice(invPageStart, invPageStart + SLOTS_PER_PAGE),
    [bagShown, invPageStart],
  );
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

  // Keep batch selection in sync with inventory refreshes.
  useEffect(() => {
    if (!batchSellMode || batchSellIds.size === 0) return;
    const bagIdSet = new Set(bag.map((x) => x.id));
    setBatchSellIds((prev) => {
      const next = new Set<string>();
      for (const id of prev) if (bagIdSet.has(id)) next.add(id);
      return next;
    });
  }, [batchSellMode, batchSellIds.size, bag]);

  const toggleBatchSellId = useCallback((id: string) => {
    setBatchSellIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectShownBy = useCallback(
    (pred: (it: InvRow) => boolean) => {
      setBatchSellIds((prev) => {
        const next = new Set(prev);
        for (const it of bagShown) if (pred(it)) next.add(it.id);
        return next;
      });
    },
    [bagShown],
  );

  const clearBatchSell = useCallback(() => setBatchSellIds(new Set()), []);

  const sellBatchSelected = useCallback(async () => {
    if (batchSelling) return;
    const ids = Array.from(batchSellIds);
    if (ids.length === 0) return;

    setBatchSelling(true);
    try {
      let okCount = 0;
      let failCount = 0;
      let goldTotal = 0;
      const failMsgs: string[] = [];

      for (const id of ids) {
        const res = await itemPost("/api/game/item/sell", { item_id: id });
        const j = (await res.json()) as { ok?: boolean; message?: string; gold?: number };
        const ok = res.ok && j.ok !== false;
        if (ok) {
          okCount += 1;
          goldTotal += Number(j.gold ?? 0) || 0;
        } else {
          failCount += 1;
          if (j.message && failMsgs.length < 3) failMsgs.push(j.message);
        }
      }

      await refreshInventory();
      setBatchSellIds(new Set());

      if (okCount > 0 && failCount === 0) {
        toast.success(`Sold ${okCount} item${okCount === 1 ? "" : "s"} for ${goldTotal}🪙.`);
      } else if (okCount > 0) {
        toast.warning(
          `Sold ${okCount} item${okCount === 1 ? "" : "s"} for ${goldTotal}🪙. ${failCount} failed.`,
          { description: failMsgs.length ? failMsgs.join(" · ") : undefined },
        );
      } else {
        toast.error("Could not sell selected items.", {
          description: failMsgs.length ? failMsgs.join(" · ") : undefined,
        });
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBatchSelling(false);
    }
  }, [batchSellIds, batchSelling, itemPost, refreshInventory]);

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

  const setBonusDisplay = useMemo(() => {
    const n = items.filter(
      (i) => i.is_equipped && ["epic", "legendary"].includes(rarityKey(i.rarity)),
    ).length;
    return `${Math.min(n, 5)}/5`;
  }, [items]);

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

  // Fixed 4×5 slot grid per page (same “box” UI whether slots are full or empty).
  const invSlots = useMemo(() => {
    const slots: Array<{
      id: string;
      name: string | null;
      rarity: string;
      item: InvRow | null;
    }> = [];
    for (let i = 0; i < SLOTS_PER_PAGE; i++) {
      const it = bagShownPage[i];
      if (it) {
        slots.push({
          id: it.id,
          name: it.name,
          rarity: rarityKey(it.rarity),
          item: it,
        });
      } else {
        slots.push({
          id: `bag-slot-${inventoryView}-${invPage}-${i}`,
          name: null,
          rarity: "",
          item: null,
        });
      }
    }
    return slots;
  }, [bagShownPage, inventoryView, invPage]);

  // When switching filters or the list shrinks, keep the page in range.
  useEffect(() => {
    setInventoryPage((p) => Math.max(0, Math.min(p, maxInvPage)));
  }, [maxInvPage, inventoryView]);

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

  function renderEquipSlotCell(slotId: string) {
    const it = equipped[slotId] || null;
    const rc = it ? RARITY_COLORS[rarityKey(it.rarity)] || "" : "";
    const showHoverTip = it && hoveredKey === slotId && pinnedKey !== slotId;
    const showPinned = it && pinnedKey === slotId;
    return (
      <div
        key={slotId}
        data-item-slot={slotId}
        className={`hero-ref-equip-slot relative aspect-square w-full ${
          it ? `slot-filled slot-hero-filled ${rc} cursor-pointer` : "slot-empty slot-hero-empty"
        }`}
        onMouseEnter={() => it && setHoveredKey(slotId)}
        onMouseLeave={() => setHoveredKey(null)}
        onClick={(e) => {
          e.stopPropagation();
          if (!it) return;
          setPinnedKey((p) => (p === slotId ? null : slotId));
        }}
      >
        {it ? (
          <div className="absolute inset-0 z-[1] flex items-center justify-center p-1">
            <ItemIcon item={it} size={HERO_ITEM_ICON} />
            {Number(it.enhancement_level ?? 0) > 0 && (
              <span
                className="pointer-events-none absolute bottom-0.5 right-0.5 text-[7px] font-bold leading-none text-primary"
                style={{ textShadow: "0 0 4px hsl(43 78% 50% / 0.4)" }}
              >
                +{it.enhancement_level}
              </span>
            )}
          </div>
        ) : (
          <span className="relative z-[1] flex flex-col items-center justify-center gap-0.5 text-[7px] leading-tight text-center opacity-60 font-cinzel select-none">
            <span className="text-[11px] leading-none opacity-80" aria-hidden>
              {SLOT_ICONS[slotId] ?? "◇"}
            </span>
            <span className="hidden sm:inline text-[5px] uppercase tracking-tighter">{SLOT_LABELS[slotId]}</span>
          </span>
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
                    void runAction("/api/game/item/unequip", { slot: slotId }, "Unequipped");
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
  }

  const combatStats = derivedStats?.ok !== false && derivedStats ? derivedStats : null;

  return (
    <div className="space-y-2.5 hero-tab-ref">
      {accessToken && char ? (
        <div className="game-panel game-panel-hero">
          <div className="game-panel-header game-panel-header-hero">Offline earnings</div>
          <p className="hero-panel-subtitle">
            Accrues while you&apos;re away (up to {idleRewards?.max_hours ?? 24}h per claim).
          </p>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-muted-foreground">
              {idleLoading ? (
                <span>Checking…</span>
              ) : idleRewards?.ok === false ? (
                <span className="text-destructive">Could not load offline earnings.</span>
              ) : (
                <>
                  Pending{" "}
                  <span className="font-medium tabular-nums text-foreground">{idleRewards?.pending_xp ?? 0}</span> XP ·{" "}
                  <span className="font-medium tabular-nums text-foreground">{idleRewards?.pending_gold ?? 0}</span>{" "}
                  🪙
                  {typeof idleRewards?.effective_hours === "number" && idleRewards.effective_hours > 0 && (
                    <span className="ml-1.5 text-[11px] opacity-80">
                      (~{idleRewards.effective_hours.toFixed(1)} h accrued)
                    </span>
                  )}
                </>
              )}
            </div>
            <button
              type="button"
              disabled={
                idleClaiming ||
                idleLoading ||
                idleRewards?.ok === false ||
                ((idleRewards?.pending_xp ?? 0) === 0 && (idleRewards?.pending_gold ?? 0) === 0)
              }
              onClick={() => void claimIdleRewards()}
              className="game-btn-primary text-xs px-3 py-1.5 shrink-0"
            >
              {idleClaiming ? "Collecting…" : "Collect"}
            </button>
          </div>
        </div>
      ) : null}
      {/* Two columns */}
      <div className="hero-ref-hero-columns grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3 md:gap-3">
        {/* Equipment — paper doll + combat stats */}
        <div className="game-panel game-panel-hero hero-ref-equip-panel min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-2 mb-1">
            <div className="min-w-0">
              <div className="game-panel-header game-panel-header-hero !mb-0 hero-ref-equip-title">Equipment</div>
              <p className="hero-panel-subtitle !mb-0 !mt-1">Worn gear and weapons</p>
            </div>
            <div className="hero-ref-set-bonus shrink-0 text-right leading-tight">
              <div className="hero-ref-set-bonus-label">Set bonus</div>
              <div className="hero-ref-set-bonus-value tabular-nums">{setBonusDisplay}</div>
            </div>
          </div>

          <div className="hero-ref-paper-doll mt-2">
            <div className="hero-ref-paper-col">{PAPER_LEFT_SLOTS.map((s) => renderEquipSlotCell(s))}</div>
            <div className="hero-ref-paper-portrait">
              <div
                className="hero-ref-paper-portrait-classbg"
                style={{ backgroundImage: `url(${classIconUrl(char?.class || "warrior")})` }}
                aria-hidden
              />
              {inventory?.discord?.avatar_url ? (
                <Avatar className="hero-ref-paper-portrait-avatar">
                  <AvatarImage src={String(inventory.discord.avatar_url)} alt="" className="object-cover" />
                  <AvatarFallback className="bg-transparent text-[8px]">
                    {(char?.name || "?").slice(0, 1).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
              ) : null}
              <div className="hero-ref-paper-portrait-level">Lv.{char?.level ?? "—"}</div>
              <div className="hero-ref-paper-portrait-nameplate">
                <div className="hero-ref-paper-name">{(char?.name || "Hero").toUpperCase()}</div>
                <div className="hero-ref-paper-classline">
                  {(char?.class || "—").toString().replace(/_/g, " ").toUpperCase()}
                  {(char?.specialization_name || char?.specialization) && (
                    <>
                      {" "}
                      <span className="opacity-60">—</span>{" "}
                      {(char.specialization_name || String(char.specialization || "").replace(/_/g, " ")).toUpperCase()}
                    </>
                  )}
                </div>
              </div>
            </div>
            <div className="hero-ref-paper-col">{PAPER_RIGHT_SLOTS.map((s) => renderEquipSlotCell(s))}</div>
          </div>

          <div className="ornament-divider my-2" />

          <div className="hero-ref-combat-stats">
            {(
              [
                ["Attack", combatStats ? Math.round(combatStats.attack_power) : "—"],
                ["Defense", combatStats ? Math.round(combatStats.armor) : "—"],
                ["Accuracy", combatStats ? Math.round(combatStats.hit_rating) : "—"],
                ["Critical", combatStats ? Math.round(combatStats.crit_chance) : "—"],
                ["Speed", combatStats ? Math.round(combatStats.haste) : "—"],
              ] as const
            ).map(([label, val]) => (
              <div key={label} className="hero-ref-combat-stat-cell">
                <div className="hero-ref-combat-stat-label">{label}</div>
                <div className="hero-ref-combat-stat-value tabular-nums">{val}</div>
              </div>
            ))}
          </div>

          <div className="ornament-divider my-2" />
          <button
            type="button"
            onClick={() => {
              const list = blacksmithCandidates;
              if (list.length === 0) toast("No gear to enhance");
              else if (list.length === 1) setEnhanceItemId(list[0].id);
              else setBlacksmithPickerOpen(true);
            }}
            className="game-btn-primary hero-btn-jewel hero-ref-blacksmith-btn w-full uppercase tracking-widest font-cinzel font-semibold"
          >
            🔨 Open Blacksmith
          </button>
        </div>

        {/* Inventory */}
        <div className="game-panel game-panel-hero min-w-0 hero-ref-inventory-panel">
          <div className="game-panel-header game-panel-header-hero flex flex-col gap-1 min-w-0">
            {/* Row 1: title + gold/bag — keeps currency inside the panel */}
            <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 min-w-0">
              <span className="hero-inventory-title shrink-0 hero-ref-inventory-title">Inventory</span>
              <div className="text-right shrink-0 min-w-0">
                <div className="hero-stat-gold tabular-nums whitespace-nowrap">
                  {Number(char?.gold ?? 0).toLocaleString()} 🪙
                </div>
                {bagSlotsMax > 0 && (
                  <div className="hero-stat-muted tabular-nums whitespace-nowrap uppercase tracking-wide text-[8px]">
                    Bag: {bagSlotsUsed}/{bagSlotsMax} · Free: {bagSlotsFree}
                  </div>
                )}
              </div>
            </div>
            <p className="hero-panel-subtitle w-full max-w-full">Stashed gear, consumables &amp; crafting goods</p>
            {/* Row 2: filters + batch sell — ornate chrome */}
            <div className="hero-inventory-chrome min-w-0">
              <div className="flex flex-wrap items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => setInventoryView("gear")}
                  className={`hero-inventory-segment ${inventoryView === "gear" ? "hero-inventory-segment-active" : ""}`}
                >
                  Gear
                </button>
                <button
                  type="button"
                  onClick={() => setInventoryView("consumables")}
                  className={`hero-inventory-segment ${
                    inventoryView === "consumables" ? "hero-inventory-segment-active" : ""
                  }`}
                >
                  Consumables
                </button>
                <button
                  type="button"
                  onClick={() => setInventoryView("materials")}
                  className={`hero-inventory-segment ${
                    inventoryView === "materials" ? "hero-inventory-segment-active" : ""
                  }`}
                >
                  Materials
                </button>
              </div>
              <button
                type="button"
                onClick={() => {
                  setPinnedKey(null);
                  setBatchSellMode((v) => !v);
                  setBatchSellIds(new Set());
                }}
                className={`hero-batch-toggle hero-ref-batch-sell shrink-0 ${batchSellMode ? "hero-batch-toggle-active" : ""}`}
                title="Select multiple items and sell them together"
              >
                Batch sell
              </button>
            </div>
          </div>
          <div className="hero-equip-grid hero-ref-bag-grid">
            {invSlots.map((inv) => {
              const rc = inv.rarity ? RARITY_COLORS[inv.rarity] || "" : "";
              const invKey = `inv-${inv.id}`;
              const it = inv.item;
              const showHoverTip = it && hoveredKey === invKey && pinnedKey !== invKey;
              const showPinned = it && pinnedKey === invKey;
              const isSelected = it ? batchSellIds.has(it.id) : false;
              return (
                <div
                  key={inv.id}
                  data-item-slot={invKey}
                  className={`hero-ref-bag-slot relative aspect-square ${
                    inv.name
                      ? `slot-filled slot-hero-filled ${rc} ${it ? "cursor-pointer" : ""}`
                      : "slot-empty slot-hero-empty"
                  }`}
                  onMouseEnter={() => inv.name && setHoveredKey(invKey)}
                  onMouseLeave={() => setHoveredKey(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!it) return;
                    if (batchSellMode) {
                      toggleBatchSellId(it.id);
                      return;
                    }
                    setPinnedKey((p) => (p === invKey ? null : invKey));
                  }}
                >
                  {batchSellMode && it && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleBatchSellId(it.id);
                      }}
                      className={`absolute top-0.5 left-0.5 z-20 h-3 w-3 rounded-sm border text-[8px] leading-none ${
                        isSelected ? "bg-primary/90 border-primary text-primary-foreground" : "bg-background/70 border-border text-foreground"
                      }`}
                      title={isSelected ? "Unselect" : "Select for batch sell"}
                    >
                      {isSelected ? "✓" : ""}
                    </button>
                  )}
                  {it ? (
                    <>
                      <div className="hero-ref-bag-icon absolute inset-0 z-[1] overflow-hidden rounded-[1px]">
                        <ItemIcon item={it} variant="tile" size={HERO_BAG_ITEM_ICON} />
                      </div>
                      {Number(it.enhancement_level ?? 0) > 0 && (
                        <span
                          className="pointer-events-none absolute bottom-px right-px z-[3] text-[6px] font-bold leading-none text-primary"
                          style={{ textShadow: "0 0 3px hsl(43 78% 50% / 0.5)" }}
                        >
                          +{it.enhancement_level}
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="relative z-[1] text-[6px] leading-tight text-center opacity-35">Empty</span>
                  )}
                  {it && Number(it.quantity ?? 1) > 1 && (
                    <span className="absolute bottom-px right-px z-[4] text-[6px] font-bold text-foreground"
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

          {maxInvPage > 0 && (
            <div className="hero-pager-bar mt-2 flex justify-end items-center gap-2">
              <span className="text-[10px] tabular-nums text-muted-foreground">
                Page {invPage + 1} / {maxInvPage + 1}
              </span>
              <button
                type="button"
                onClick={() => setInventoryPage((p) => Math.max(0, p - 1))}
                className="game-btn-secondary text-[10px] px-2 py-1"
                disabled={invPage <= 0}
                title="Previous page"
              >
                ← Prev
              </button>
              <button
                type="button"
                onClick={() => setInventoryPage((p) => Math.min(maxInvPage, p + 1))}
                className="game-btn-primary text-[10px] px-2 py-1"
                disabled={invPage >= maxInvPage}
                title="Next page"
              >
                Next →
              </button>
            </div>
          )}

          {batchSellMode && (
            <div className="hero-batch-panel mt-3 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs text-foreground">
                  Selected: <span className="font-semibold tabular-nums">{batchSellIds.size}</span>
                </div>
                <div className="flex flex-wrap gap-1.5 justify-end">
                  <button
                    type="button"
                    onClick={() => selectShownBy(() => true)}
                    className="game-btn-secondary px-2 py-1 text-[10px]"
                    disabled={batchSelling}
                  >
                    Select shown
                  </button>
                  <button
                    type="button"
                    onClick={() => selectShownBy((it) => rarityKey(it.rarity) === "common")}
                    className="game-btn-secondary px-2 py-1 text-[10px]"
                    disabled={batchSelling}
                  >
                    Common
                  </button>
                  <button
                    type="button"
                    onClick={() => selectShownBy((it) => rarityKey(it.rarity) === "uncommon")}
                    className="game-btn-secondary px-2 py-1 text-[10px]"
                    disabled={batchSelling}
                  >
                    Uncommon
                  </button>
                  <button
                    type="button"
                    onClick={clearBatchSell}
                    className="game-btn-secondary px-2 py-1 text-[10px]"
                    disabled={batchSelling || batchSellIds.size === 0}
                  >
                    Clear
                  </button>
                  <button
                    type="button"
                    onClick={() => void sellBatchSelected()}
                    className="game-btn-primary px-2 py-1 text-[10px]"
                    disabled={batchSelling || batchSellIds.size === 0}
                  >
                    {batchSelling ? "Selling…" : "Sell selected"}
                  </button>
                </div>
              </div>
              <div className="mt-2 text-[10px] text-muted-foreground">
                Tip: locked / equipped / soulbound items will fail and remain in your bag.
              </div>
            </div>
          )}
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
                      <ItemIcon item={it} size={20} />
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
              template_equip_slot: it.template_equip_slot,
              equip_slot: it.equip_slot,
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
