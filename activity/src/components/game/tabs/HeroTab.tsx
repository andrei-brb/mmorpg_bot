import { useCallback, useEffect, useMemo, useState } from "react";
import { Sword, Hammer, Recycle, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CharacterDerivedStatsPayload, EnhanceInfoPayload, IdleRewardsPayload, InvRow } from "@/lib/apiTypes";
import { classIconUrl } from "@/lib/classAndSpecIconUrl";
import { getCharacterDerivedStats, getIdleRewards, postIdleClaim, publicBaseUrl } from "@/lib/gameApi";
import { hasSpecPortrait, specPortraitKey } from "@/lib/specPortraitCatalog";
import { BlacksmithModal, type BlacksmithProtection } from "../modals/BlacksmithModal";
import { ListItemModal } from "../modals/ListItemModal";
import { ItemIcon } from "../ItemIcon";
import { ItemPopover } from "@/components/hero/ItemPopover";
import { WomPanel } from "@/components/wom/WomUi";

/** Flanking portrait (hero-blacksmith visual); weapons sit in hex row below */
const FORGE_LEFT_SLOTS = ["head", "neck", "chest", "legs"] as const;
const FORGE_RIGHT_SLOTS = ["hands", "ring", "trinket", "feet"] as const;

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

/**
 * Unified icon size for both paper-doll and bag tiles (ItemIcon `size` prop = CSS px).
 * Slot frames are capped in `index.css` (`.hero-ref-equip-slot`, `.hero-ref-bag-grid`):
 *   <420px viewport: max 3.75rem → 60px at 16px root
 *   ≥420px: max 4rem → 64px at 16px root
 */
const HERO_ITEM_ICON = 48;
const HERO_BAG_ITEM_ICON = HERO_ITEM_ICON;

const RARITY_COLORS: Record<string, string> = {
  common: "text-rarity-common border-rarity-common/40",
  uncommon: "text-rarity-uncommon border-rarity-uncommon/40",
  rare: "text-rarity-rare border-rarity-rare/40",
  epic: "text-rarity-epic border-rarity-epic/40",
  legendary: "text-rarity-legendary border-rarity-legendary/40",
};

function forgeFrameAccent(rawRarity?: string | null): { ring: string; glow: string; chipText: string } {
  switch (rarityKey(rawRarity)) {
    case "legendary":
      return {
        ring: "ring-gold/90",
        glow: "shadow-[inset_0_0_26px_oklch(0.88_0.16_88/0.32)] animate-pulse-gold",
        chipText: "text-gold-200",
      };
    case "epic":
      return {
        ring: "ring-arcane/70",
        glow: "shadow-[inset_0_0_22px_oklch(0.65_0.22_295/0.28)]",
        chipText: "text-purple-300",
      };
    case "rare":
      return {
        ring: "ring-frost/60",
        glow: "shadow-[inset_0_0_22px_oklch(0.78_0.14_220/0.25)]",
        chipText: "text-frost",
      };
    case "uncommon":
      return {
        ring: "ring-verdant/55",
        glow: "shadow-[inset_0_0_18px_oklch(0.55_0.14_150/0.22)]",
        chipText: "text-verdant",
      };
    default:
      return {
        ring: "ring-gold/30",
        glow: "shadow-[inset_0_0_18px_oklch(0_0_0/0.55)]",
        chipText: "text-gold-600",
      };
  }
}

function rarityKey(rarity?: string | null) {
  return (rarity || "common").toLowerCase();
}

function normalizeClassKeyForHero(classKeyOrName: string): string {
  return classKeyOrName.trim().toLowerCase().replace(/\s+/g, "_");
}

/** Template slot for icons / actions; `equip_slot` alone was overwritten by SQL before `template_equip_slot` existed. */
function gearSlot(it: InvRow): string | null {
  const s = (it.template_equip_slot || it.equip_slot || "").trim();
  return s || null;
}

function isProtectionTemplate(it: InvRow): boolean {
  return (it.template_id || "").toLowerCase().startsWith("protection_");
}

function canSalvage(it: InvRow): boolean {
  if (it.locked || it.is_equipped) return false;
  const t = (it.item_type || "").toLowerCase();
  if (!["weapon", "armor", "accessory"].includes(t)) return false;
  return Boolean(it.template_equip_slot || it.equip_slot);
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
  const [enhanceItemId, setEnhanceItemId] = useState<string | null>(null);
  const [enhancePayload, setEnhancePayload] = useState<EnhanceInfoPayload | null>(null);
  const [enhanceInfoLoading, setEnhanceInfoLoading] = useState(false);
  const [blacksmithPickerOpen, setBlacksmithPickerOpen] = useState(false);
  const [listItemId, setListItemId] = useState<string | null>(null);
  const [inventoryView, setInventoryView] = useState<"gear" | "consumables" | "materials">("gear");
  const [derivedStats, setDerivedStats] = useState<CharacterDerivedStatsPayload | null>(null);
  const [salvageMode, setSalvageMode] = useState(false);
  const [salvageIds, setSalvageIds] = useState<Set<string>>(() => new Set());
  const [salvaging, setSalvaging] = useState(false);
  const [inventoryPage, setInventoryPage] = useState(0);

  const char = inventory?.character;
  const items = inventory?.items || [];
  const heroPaperClassKey = normalizeClassKeyForHero(char?.class || "warrior");
  const trySpecPortraitFirst = hasSpecPortrait(char?.class || "warrior", char?.specialization);
  const specPortraitFileKey = specPortraitKey(char?.class || "warrior", char?.specialization);

  type PaperPortraitStep = "spec" | "class" | "bundled";
  const [paperPortraitStep, setPaperPortraitStep] = useState<PaperPortraitStep>(() =>
    trySpecPortraitFirst ? "spec" : "class",
  );

  useEffect(() => {
    setPaperPortraitStep(trySpecPortraitFirst ? "spec" : "class");
  }, [trySpecPortraitFirst, heroPaperClassKey, char?.specialization]);

  const PORTRAIT_CACHE_BUSTER = "3";
  const paperPortraitSrc = useMemo(() => {
    const base = publicBaseUrl();
    const v = PORTRAIT_CACHE_BUSTER;
    if (paperPortraitStep === "bundled") return classIconUrl(char?.class || "warrior");
    if (paperPortraitStep === "spec" && trySpecPortraitFirst && specPortraitFileKey) {
      return `${base}portraits/characters/${encodeURIComponent(specPortraitFileKey)}.png?v=${v}`;
    }
    return `${base}classes/class_${encodeURIComponent(heroPaperClassKey)}.png?v=${v}`;
  }, [
    paperPortraitStep,
    trySpecPortraitFirst,
    specPortraitFileKey,
    heroPaperClassKey,
    char?.class,
  ]);

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
        const j = (await res.json()) as {
          ok?: boolean;
          message?: string;
          results?: { message?: string; ok?: boolean }[];
        };
        const line =
          j.message ||
          (Array.isArray(j.results) && j.results[0]?.message) ||
          msg;
        toast(line);
        await refreshInventory();
      } catch (e) {
        toast.error(String(e));
      }
    },
    [itemPost, refreshInventory],
  );

  // Keep salvage selection in sync with inventory refreshes.
  useEffect(() => {
    if (!salvageMode || salvageIds.size === 0) return;
    const bagIdSet = new Set(bag.map((x) => x.id));
    setSalvageIds((prev) => {
      const next = new Set<string>();
      for (const id of prev) if (bagIdSet.has(id)) next.add(id);
      return next;
    });
  }, [salvageMode, salvageIds.size, bag]);

  const toggleSalvageId = useCallback((id: string) => {
    setSalvageIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectShownBy = useCallback(
    (pred: (it: InvRow) => boolean) => {
      setSalvageIds((prev) => {
        const next = new Set(prev);
        for (const it of bagShown) if (pred(it) && canSalvage(it)) next.add(it.id);
        return next;
      });
    },
    [bagShown],
  );

  const clearSalvageSelection = useCallback(() => setSalvageIds(new Set()), []);

  const salvageBatchSelected = useCallback(async () => {
    if (salvaging) return;
    const ids = Array.from(salvageIds).filter((id) => {
      const it = bag.find((x) => x.id === id);
      return it && canSalvage(it);
    });
    if (ids.length === 0) return;

    setSalvaging(true);
    try {
      const res = await itemPost("/api/game/item/salvage", { item_ids: ids });
      const j = (await res.json()) as {
        ok?: boolean;
        results?: { item_id?: string; ok?: boolean; message?: string }[];
      };
      await refreshInventory();
      setSalvageIds(new Set());

      const results = j.results || [];
      const okCount = results.filter((r) => r.ok).length;
      const failCount = results.length - okCount;
      const failMsgs = results.filter((r) => !r.ok && r.message).map((r) => r.message as string);

      if (res.ok && j.ok !== false && okCount > 0 && failCount === 0) {
        toast.success(`Salvaged ${okCount} item${okCount === 1 ? "" : "s"}. Check materials tab for scrap.`);
      } else if (okCount > 0) {
        toast.warning(`Salvaged ${okCount} item(s). ${failCount} failed.`, {
          description: failMsgs.length ? failMsgs.slice(0, 3).join(" · ") : undefined,
        });
      } else {
        toast.error("Could not salvage selected items.", {
          description: failMsgs.length ? failMsgs.slice(0, 3).join(" · ") : undefined,
        });
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSalvaging(false);
    }
  }, [salvageIds, salvaging, itemPost, refreshInventory, bag]);

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
        <div>
          <div className="text-[10px] text-muted-foreground">
            Equipped: <span className="text-foreground/90">{eq.name}</span>
          </div>
          <div className="mt-1.5 flex flex-col gap-1">
            {deltas.slice(0, 10).map(({ k, v }) => (
              <div key={k} className="flex items-center justify-between gap-3 text-[10px] tabular-nums">
                <span className="min-w-0 shrink text-muted-foreground">{statLabel(k)}</span>
                <span className={`shrink-0 font-medium ${v > 0 ? "text-emerald-400" : "text-destructive"}`}>
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

  function forgeChipShell(
    slotId: string,
    it: InvRow | null,
    tone: ReturnType<typeof forgeFrameAccent>,
    rc: string,
    compactIcon: boolean,
  ) {
    const px = compactIcon ? 36 : HERO_ITEM_ICON;
    const frame = (
      <div
        className={`hero-forge-clip-blade-sm relative flex aspect-square h-14 w-14 items-center justify-center ring-1 sm:h-16 sm:w-16 ${
          it ? `${tone.ring} ${tone.glow} cursor-pointer hover:scale-105 ${rc}` : "tex-forge ring-gold/10 opacity-95"
        } transition-transform`}
      >
        {it ? (
          <>
            <div className="absolute inset-0 z-[1] flex items-center justify-center p-0.5">
              <ItemIcon item={it} size={compactIcon ? px : HERO_ITEM_ICON} />
            </div>
            {Number(it.enhancement_level ?? 0) > 0 ? (
              <span className="pointer-events-none absolute -right-1.5 -top-1.5 z-[8] rounded-sm border border-gold/60 bg-background px-1 py-px font-display text-[9px] font-semibold tracking-wider text-gold-200">
                +{it.enhancement_level}
              </span>
            ) : null}
          </>
        ) : (
          <span className="relative z-[1] flex flex-col items-center justify-center opacity-65">
            <span className="text-lg leading-none" aria-hidden>
              {SLOT_ICONS[slotId] ?? "◇"}
            </span>
          </span>
        )}
      </div>
    );
    return (
      <div className="relative z-[6] shrink-0" data-item-slot={slotId}>
        {it ? (
          <ItemPopover
            item={it}
            equipped
            onUnequip={() => void runAction("/api/game/item/unequip", { slot: slotId }, "Unequipped")}
            onEnhance={isEnhanceableGear(it) ? () => setEnhanceItemId(it.id) : undefined}
          >
            {frame}
          </ItemPopover>
        ) : (
          frame
        )}
      </div>
    );
  }

  function renderForgeEquipChip(slotId: string, side: "left" | "right") {
    const it = equipped[slotId] || null;
    const rk = rarityKey(it?.rarity);
    const tone = forgeFrameAccent(rk);
    const rc = RARITY_COLORS[rk] || "";
    const chip = forgeChipShell(slotId, it, tone, rc, true);
    return (
      <div
        key={slotId}
        className={`group relative flex items-center gap-2 ${side === "left" ? "flex-row-reverse" : "flex-row"}`}
      >
        {chip}
        <span className="pointer-events-none whitespace-nowrap font-display text-[10px] uppercase tracking-[0.25em] text-gold-dim opacity-0 transition-opacity group-hover:opacity-100">
          {SLOT_LABELS[slotId] ?? slotId}
        </span>
      </div>
    );
  }

  function renderForgeWeaponHex(slotId: string, subtitle: string) {
    const it = equipped[slotId] || null;
    const rk = rarityKey(it?.rarity);
    const tone = forgeFrameAccent(rk);
    const rc = RARITY_COLORS[rk] || "";
    const frame = (
      <div
        className={`relative flex h-16 w-16 items-center justify-center hero-forge-clip-rhombus tex-forge hero-forge-edge-gold ring-1 sm:h-[4.75rem] sm:w-[4.75rem] ${
          it ? `${tone.ring} ${tone.glow} cursor-pointer hover:brightness-105 ${rc}` : "ring-gold/25"
        }`}
      >
        {it ? (
          <div className="absolute inset-[3px] z-[2] flex items-center justify-center">
            <ItemIcon item={it} size={40} />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-gold-dim">
            <Sword className="h-8 w-8 -rotate-45 text-gold-200 opacity-55" aria-hidden />
          </div>
        )}
        {it && Number(it.enhancement_level ?? 0) > 0 ? (
          <span className="pointer-events-none absolute -right-1 -top-0.5 z-[8] rounded-sm border border-gold/60 bg-background px-1 py-px font-display text-[9px] text-gold-200">
            +{it.enhancement_level}
          </span>
        ) : null}
      </div>
    );
    return (
      <div className="flex flex-col items-center">
        <div className="relative z-[6]" data-item-slot={slotId}>
          {it ? (
            <ItemPopover
              item={it}
              equipped
              onUnequip={() => void runAction("/api/game/item/unequip", { slot: slotId }, "Unequipped")}
              onEnhance={isEnhanceableGear(it) ? () => setEnhanceItemId(it.id) : undefined}
            >
              {frame}
            </ItemPopover>
          ) : (
            frame
          )}
        </div>
        <span className="mt-1 text-center font-display text-[10px] tracking-[0.3em] text-gold-dim">{subtitle}</span>
      </div>
    );
  }

  const combatStats = derivedStats?.ok !== false && derivedStats ? derivedStats : null;
  const combatPowerDisplay =
    combatStats != null
      ? Math.round(
          combatStats.attack_power +
            combatStats.spell_power +
            combatStats.armor * 2 +
            combatStats.hit_rating * 12 +
            combatStats.haste * 15 +
            combatStats.crit_chance * 180,
        ).toLocaleString()
      : "—";

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="relative flex min-h-0 flex-1 flex-col px-1 pb-2 hero-tab-ref">
        <div className="relative flex min-h-0 flex-1 flex-col tex-forge hero-forge-edge-gold-strong p-[2px]">
          <span className="corner-ornament corner-tl" aria-hidden />
          <span className="corner-ornament corner-tr" aria-hidden />
          <span className="corner-ornament corner-bl" aria-hidden />
          <span className="corner-ornament corner-br" aria-hidden />

          {/* Always row: Activity iframe is often under 640px wide, so Tailwind sm/md never split columns. */}
          <div className="relative flex min-h-0 flex-1 flex-row gap-px border border-gold/30 bg-black/60">
            <section className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-x-hidden overflow-y-auto tex-leather">
              <div className="flex items-center justify-between px-5 pt-4">
                <div className="hero-forge-clip-tag border border-gold/40 bg-gold/15 px-3 py-1">
                  <span className="font-display text-[10px] tracking-[0.3em] text-gold-200">
                    HERO · LV.{char?.level ?? "—"}
                  </span>
                </div>
                <div className="hero-forge-clip-tag border border-gold/25 bg-black/50 px-3 py-1">
                  <span className="font-display text-[10px] tracking-[0.3em] text-gold-600">
                    SET BONUS · {setBonusDisplay}
                  </span>
                </div>
              </div>

              <div className="px-5 pt-4">
                <h2 className="font-display text-3xl leading-none tracking-[0.18em] text-gold-200 sm:text-4xl lg:text-5xl">
                  {(char?.name || "Hero").toUpperCase()}
                </h2>
                <p className="mt-1 text-[11px] uppercase tracking-[0.4em] text-gold-dim">
                  {(char?.class || "—").toString().replace(/_/g, " ").toUpperCase()}
                  {char?.specialization_name || char?.specialization ? (
                    <>
                      {" "}
                      <span className="opacity-50">·</span>{" "}
                      {(char.specialization_name || String(char.specialization || "").replace(/_/g, " ")).toUpperCase()}
                    </>
                  ) : null}
                </p>
                <div className="divider-ornate mb-2 mt-4" />
              </div>

              <div className="relative mx-auto mt-2 w-full max-w-[min(460px,100%)] aspect-[4/5] max-h-[min(420px,calc(100dvh-14rem))] shrink-0 sm:max-h-[min(480px,calc(100dvh-16rem))]">
                <div className="absolute inset-x-10 inset-y-6 bg-[radial-gradient(circle_at_50%_40%,oklch(0.78_0.14_78/0.35),transparent_65%)] blur-2xl" />
                <div className="absolute inset-x-14 top-2 bottom-16 sm:inset-x-20">
                  <div className="relative h-full w-full overflow-hidden border border-gold/40 tex-parchment hero-forge-clip-blade hero-forge-edge-gold">
                    <img
                      src={paperPortraitSrc}
                      alt=""
                      className="absolute inset-0 h-full w-full object-cover"
                      decoding="async"
                      onError={() => {
                        setPaperPortraitStep((prev) => {
                          if (prev === "spec") return "class";
                          if (prev === "class") return "bundled";
                          return prev;
                        });
                      }}
                    />
                    <div className="pointer-events-none absolute inset-1 border border-gold/15" />
                  </div>
                </div>

                <div className="absolute left-1 top-1/2 flex -translate-y-1/2 flex-col gap-2.5 sm:left-2 sm:gap-3">
                  {FORGE_LEFT_SLOTS.map((s) => renderForgeEquipChip(s, "left"))}
                </div>
                <div className="absolute right-1 top-1/2 flex -translate-y-1/2 flex-col gap-2.5 sm:right-2 sm:gap-3">
                  {FORGE_RIGHT_SLOTS.map((s) => renderForgeEquipChip(s, "right"))}
                </div>

                <div className="absolute bottom-6 left-1/2 flex w-[88%] max-w-[360px] -translate-x-1/2 justify-center gap-4 sm:-bottom-1 sm:w-full">
                  {renderForgeWeaponHex("main_hand", "MAIN")}
                  {renderForgeWeaponHex("off_hand", "OFF")}
                </div>
              </div>

              <div className="relative mx-4 mb-4 mt-4 border border-gold/25 tex-forge px-4 py-3 hero-forge-edge-gold hero-forge-clip-blade">
                <div className="grid grid-cols-2 gap-4">
                  <div className="border-r border-gold/15 pr-4 text-center">
                    <p className="text-[10px] uppercase tracking-[0.3em] text-gold-dim">Combat power</p>
                    <p className="font-display text-3xl leading-tight text-gold-200">{combatPowerDisplay}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[10px] uppercase tracking-[0.3em] text-gold-dim">Treasury</p>
                    <p className="font-display text-3xl leading-tight text-gold">
                      {Number(char?.gold ?? 0).toLocaleString()} 🪙
                    </p>
                  </div>
                </div>
              </div>
            </section>

            <section className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-x-hidden bg-background">
              {accessToken && char ? (
                <div className="relative">
                  <div className="hero-forge-clip-banner flex items-center justify-between bg-gradient-to-r from-gold-dim via-gold-200 to-gold-dim px-6 py-2.5 text-background sm:px-8">
                    <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
                      <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-background" />
                      <span className="truncate font-display text-[10px] tracking-[0.22em] sm:text-xs sm:tracking-[0.25em]">
                        OFFLINE EARNINGS ·{" "}
                        {idleLoading ? (
                          <span className="font-bold">…</span>
                        ) : idleRewards?.ok === false ? (
                          <span className="font-bold">UNAVAILABLE</span>
                        ) : (
                          <span className="font-bold">
                            +{idleRewards?.pending_xp ?? 0} XP · {idleRewards?.pending_gold ?? 0} GOLD
                          </span>
                        )}
                      </span>
                      {typeof idleRewards?.effective_hours === "number" && idleRewards.effective_hours > 0 ? (
                        <span className="hidden text-[10px] tracking-[0.3em] opacity-70 sm:inline">
                          ~{idleRewards.effective_hours.toFixed(1)}H ACCRUED
                        </span>
                      ) : null}
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
                      className="hero-forge-clip-tag shrink-0 bg-background/90 px-3 py-1 font-display text-[10px] tracking-[0.3em] text-gold-200 transition-colors hover:bg-background disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {idleClaiming ? "…" : "COLLECT"}
                    </button>
                  </div>
                  <p className="mx-6 mt-2 text-[10px] uppercase tracking-[0.25em] text-muted-foreground sm:mx-8">
                    Accrues while you&apos;re away (cap {idleRewards?.max_hours ?? 24}h per claim).
                  </p>
                </div>
              ) : (
                <div className="border-b border-gold/20 px-6 py-3 text-[11px] text-muted-foreground">
                  Sign in through Discord to view inventory and progression.
                </div>
              )}

              <div className="flex items-stretch border-b border-gold/20 tex-forge">
                {(["gear", "consumables", "materials"] as const).map((v) => {
                  const labels = { gear: "Gear", consumables: "Consumables", materials: "Materials" } as const;
                  const active = inventoryView === v;
                  return (
                    <button
                      key={v}
                      type="button"
                      onClick={() => {
                        if (v !== "gear") setSalvageMode(false);
                        setSalvageIds(new Set());
                        setInventoryView(v === "consumables" ? "consumables" : v === "materials" ? "materials" : "gear");
                      }}
                      className={`relative flex-1 py-3 font-display text-xs tracking-[0.28em] transition-colors sm:py-4 sm:text-sm ${active ? "text-gold-200" : "text-gold-600 hover:text-gold"} `}
                    >
                      {labels[v].toUpperCase()}
                      {active ? (
                        <>
                          <span className="absolute inset-x-4 -bottom-px h-[2px] bg-gradient-to-r from-transparent via-gold-200 to-transparent sm:inset-x-6" />
                          <span className="absolute inset-x-0 top-0 h-px bg-gold/30" />
                        </>
                      ) : null}
                    </button>
                  );
                })}
                <button
                  type="button"
                  title="Salvage mode — select gear to dismantle"
                  onClick={() => {
                    setSalvageMode((m) => !m);
                    setSalvageIds(new Set());
                  }}
                  className={`flex items-center gap-2 border-l border-gold/20 px-3 font-display text-[10px] tracking-[0.25em] transition-colors sm:px-5 sm:text-xs ${salvageMode ? "text-gold-200" : "text-gold-600 hover:text-gold-200"}`}
                >
                  <Recycle className="h-4 w-4 shrink-0" />
                  <span className="hidden sm:inline">SALVAGE</span>
                </button>
              </div>

              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 sm:p-6">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[10px] uppercase tracking-[0.3em] text-gold-dim">
                    BAG · {bagSlotsUsed}/{bagSlotsMax || "—"}{" "}
                    {bagSlotsMax > 0 ? <span className="opacity-50">·</span> : null}{" "}
                    {bagSlotsMax > 0 ? <span className="uppercase">FREE {bagSlotsFree}</span> : null}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setSalvageMode(true);
                      setSalvageIds(new Set());
                    }}
                    className="text-[10px] uppercase tracking-[0.3em] text-gold hover:text-gold-200"
                  >
                    Mass salvage →
                  </button>
                </div>
                {bagSlotsMax > 0 && bagSlotsFree === 0 ? (
                  <p className="mb-2 text-[9px] leading-snug text-amber-200/85">
                    Bag is full — capacity is shared across Gear, Consumables, and Materials.
                  </p>
                ) : null}

                <div className="grid grid-cols-5 gap-2 sm:grid-cols-6">
                  {invSlots.map((inv) => {
                    const rc = inv.rarity ? RARITY_COLORS[inv.rarity] || "" : "";
                    const invKey = `inv-${inv.id}`;
                    const it = inv.item;
                    const isSelected = it ? salvageIds.has(it.id) : false;
                    const tone = forgeFrameAccent(rarityKey(it?.rarity));
                    const slot = it ? gearSlot(it) : null;
                    const isConsumable = it ? (it.item_type || "").toLowerCase() === "consumable" : false;

                    const tile = (
                      <div
                        className={`hero-forge-clip-blade-sm relative flex aspect-square items-center justify-center ring-1 ${
                          it
                            ? `tex-leather cursor-pointer transition-transform hover:scale-[1.03] ${tone.ring} ${tone.glow} ${rc}`
                            : "bg-black/40 [background-image:repeating-linear-gradient(45deg,oklch(0_0_0/0.4)_0_2px,transparent_2px_6px)] ring-gold/10"
                        }`}
                      >
                        {salvageMode && it && canSalvage(it) ? (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleSalvageId(it.id);
                            }}
                            className={`absolute left-0.5 top-0.5 z-20 h-3.5 w-3.5 rounded-sm border text-[9px] leading-none ${
                              isSelected
                                ? "border-primary bg-primary/90 text-primary-foreground"
                                : "border-border bg-background/80 text-foreground"
                            }`}
                            title={isSelected ? "Unselect" : "Select for salvage"}
                          >
                            {isSelected ? "✓" : ""}
                          </button>
                        ) : null}
                        {it ? (
                          <>
                            <div className="absolute inset-0 z-[1] flex items-center justify-center overflow-hidden p-0.5">
                              <ItemIcon item={it} variant="tile" size={HERO_BAG_ITEM_ICON} />
                            </div>
                            {Number(it.enhancement_level ?? 0) > 0 ? (
                              <span className="pointer-events-none absolute left-0.5 top-0.5 z-[3] font-display text-[9px] font-semibold tracking-wider text-gold-200">
                                +{it.enhancement_level}
                              </span>
                            ) : null}
                          </>
                        ) : (
                          <span className="relative z-[1] text-[9px] tabular-nums text-gold-600/50">—</span>
                        )}
                        {it && Number(it.quantity ?? 1) > 1 ? (
                          <span
                            className="pointer-events-none absolute bottom-0.5 right-0.5 z-[4] font-display text-[10px] text-parchment"
                            style={{ textShadow: "0 1px 2px hsl(0 0% 0% / 0.85)" }}
                          >
                            ×{it.quantity}
                          </span>
                        ) : null}
                      </div>
                    );

                    return (
                      <div key={inv.id} className="relative z-[2]" data-item-slot={invKey}>
                        {it && !salvageMode ? (
                          <ItemPopover
                            item={it}
                            equipped={Boolean(it.is_equipped)}
                            compare={compareForItem(it) ?? undefined}
                            onUse={
                              isConsumable
                                ? () => void runAction("/api/game/item/use", { item_id: it.id }, "Used")
                                : undefined
                            }
                            onUnequip={
                              it.is_equipped && slot
                                ? () => void runAction("/api/game/item/unequip", { slot }, "Unequipped")
                                : undefined
                            }
                            onEquip={
                              !it.is_equipped && slot && !isConsumable
                                ? () => void runAction("/api/game/item/equip", { item_id: it.id }, "Equipped")
                                : undefined
                            }
                            onEnhance={isEnhanceableGear(it) ? () => setEnhanceItemId(it.id) : undefined}
                            onList={
                              slot && !it.is_equipped && !isConsumable ? () => setListItemId(it.id) : undefined
                            }
                            onSalvage={
                              canSalvage(it)
                                ? () => void runAction("/api/game/item/salvage", { item_id: it.id }, "Salvaged")
                                : undefined
                            }
                          >
                            {tile}
                          </ItemPopover>
                        ) : (
                          <div
                            onClick={(e) => {
                              e.stopPropagation();
                              if (!it) return;
                              if (salvageMode && canSalvage(it)) toggleSalvageId(it.id);
                            }}
                          >
                            {tile}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {maxInvPage > 0 ? (
                  <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                    <span className="text-[10px] tabular-nums text-muted-foreground">
                      Page {invPage + 1} / {maxInvPage + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => setInventoryPage((p) => Math.max(0, p - 1))}
                      className="game-btn-secondary px-2 py-1 text-[10px]"
                      disabled={invPage <= 0}
                    >
                      ← Prev
                    </button>
                    <button
                      type="button"
                      onClick={() => setInventoryPage((p) => Math.min(maxInvPage, p + 1))}
                      className="game-btn-primary px-2 py-1 text-[10px]"
                      disabled={invPage >= maxInvPage}
                    >
                      Next →
                    </button>
                  </div>
                ) : null}

                {salvageMode ? (
                  <div className="mt-4 border border-gold/25 bg-black/30 p-3 tex-forge">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-xs text-foreground">
                        Selected: <span className="font-semibold tabular-nums">{salvageIds.size}</span>
                      </div>
                      <div className="flex flex-wrap justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => selectShownBy(() => true)}
                          className="game-btn-secondary px-2 py-1 text-[10px]"
                          disabled={salvaging}
                        >
                          Select salvageable
                        </button>
                        <button
                          type="button"
                          onClick={() => selectShownBy((row) => rarityKey(row.rarity) === "common")}
                          className="game-btn-secondary px-2 py-1 text-[10px]"
                          disabled={salvaging}
                        >
                          Common
                        </button>
                        <button
                          type="button"
                          onClick={() => selectShownBy((row) => rarityKey(row.rarity) === "uncommon")}
                          className="game-btn-secondary px-2 py-1 text-[10px]"
                          disabled={salvaging}
                        >
                          Uncommon
                        </button>
                        <button
                          type="button"
                          onClick={clearSalvageSelection}
                          className="game-btn-secondary px-2 py-1 text-[10px]"
                          disabled={salvaging || salvageIds.size === 0}
                        >
                          Clear
                        </button>
                        <button
                          type="button"
                          onClick={() => void salvageBatchSelected()}
                          className="game-btn-primary px-2 py-1 text-[10px]"
                          disabled={salvaging || salvageIds.size === 0}
                        >
                          {salvaging ? "Salvaging…" : "Salvage selected"}
                        </button>
                      </div>
                    </div>
                    <p className="mt-2 text-[10px] text-muted-foreground">
                      Weapons, armor, and accessories only. Equipped and locked items cannot be salvaged.
                    </p>
                  </div>
                ) : null}
                </div>

              <div className="shrink-0 px-4 pb-4 sm:px-6 sm:pb-6">
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {(
                    [
                      ["Attack", combatStats ? Math.round(combatStats.attack_power) : "—"],
                      ["Defense", combatStats ? Math.round(combatStats.armor) : "—"],
                      ["Critical", combatStats ? Math.round(combatStats.crit_chance) : "—"],
                      ["Speed", combatStats ? Math.round(combatStats.haste) : "—"],
                    ] as const
                  ).map(([label, val]) => (
                    <div
                      key={label}
                      className="relative border border-gold/25 tex-forge px-3 py-2.5 text-center hero-forge-edge-gold hero-forge-clip-blade-sm"
                    >
                      <p className="text-[9px] uppercase tracking-[0.3em] text-gold-dim">{label}</p>
                      <p className="mt-0.5 font-display text-2xl leading-tight text-gold-200">{val}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="shrink-0 p-4 pt-0 sm:p-6 sm:pt-0">
                <button
                  type="button"
                  onClick={() => {
                    const list = blacksmithCandidates;
                    if (list.length === 0) toast("No gear to enhance");
                    else if (list.length === 1) setEnhanceItemId(list[0].id);
                    else setBlacksmithPickerOpen(true);
                  }}
                  className="group relative mb-6 w-full cursor-pointer overflow-hidden hero-forge-clip-blade"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-gold-dim via-gold-200 to-gold-dim" />
                  <div className="absolute inset-0 opacity-30 mix-blend-overlay [background-image:repeating-linear-gradient(135deg,oklch(0_0_0/0.4)_0_2px,transparent_2px_5px)]" />
                  <div className="relative flex items-center justify-center gap-3 py-3.5 text-background sm:py-4">
                    <Hammer className="h-5 w-5 shrink-0" />
                    <span className="font-display text-lg tracking-[0.35em] sm:text-xl">OPEN BLACKSMITH</span>
                    <ChevronRight className="h-5 w-5 shrink-0 transition-transform group-hover:translate-x-1" />
                  </div>
                  <div className="absolute top-0 -left-full h-full w-1/2 bg-gradient-to-r from-transparent via-white/40 to-transparent transition-transform duration-700 group-hover:translate-x-[300%]" />
                </button>
              </div>
              </div>
            </section>
          </div>
        </div>
      </div>

      {blacksmithPickerOpen && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ background: "hsl(0 0% 0% / 0.7)", backdropFilter: "blur(4px)" }}
          onClick={() => setBlacksmithPickerOpen(false)}
        >
          <WomPanel glow className="w-full max-w-md" onClick={(e) => e.stopPropagation()}>
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
          </WomPanel>
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
            }}
          />
        );
      })()}

    </div>
  );
}
