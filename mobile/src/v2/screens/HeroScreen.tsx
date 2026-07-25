import { useEffect, useMemo, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { ItemIcon } from "@/components/game/ItemIcon";
import { normRarity } from "@/hooks/useForge";
import * as api from "@/lib/gameApi";
import type { CharacterDerivedStatsPayload, InvRow } from "@/lib/apiTypes";
import { cn } from "@/lib/utils";
import { CharacterHero } from "@mobile/v2/parts/CharacterHero";
import { ItemSheet } from "@mobile/v2/parts/ItemSheet";
import { PowerSheet, computePower } from "@mobile/v2/parts/PowerSheet";

/**
 * Hero — "I want to get stronger."
 *
 * Merges what the classic UI splits across Hero (gear + bag) and Forge
 * (crafting), because from the player's side those are one intent, not two.
 *
 * Two deliberate changes beyond the merge:
 *  - Combat Power is tappable and explains itself (PowerSheet). It was an
 *    opaque number.
 *  - Tapping any item shows a real upgrade/downgrade comparison (ItemSheet)
 *    rather than a hover tooltip, which does not exist on a phone.
 */

const SLOTS: { key: string; label: string }[] = [
  { key: "head", label: "Head" },
  { key: "neck", label: "Neck" },
  { key: "chest", label: "Chest" },
  { key: "hands", label: "Hands" },
  { key: "legs", label: "Legs" },
  { key: "feet", label: "Feet" },
  { key: "main_hand", label: "Main" },
  { key: "off_hand", label: "Off" },
  { key: "ring", label: "Ring" },
  { key: "trinket", label: "Trinket" },
];

const RARITY_VAR: Record<string, string> = {
  common: "var(--r-common)",
  uncommon: "var(--r-uncommon)",
  rare: "var(--r-rare)",
  epic: "var(--r-epic)",
  legendary: "var(--r-legendary)",
  mythic: "var(--r-mythic)",
};

type BagFilter = "gear" | "consumable" | "material";

function bagCategory(it: InvRow): BagFilter {
  const t = String(it.item_type || "").toLowerCase();
  if (t === "weapon" || t === "armor" || t === "accessory") return "gear";
  if (it.effect_type || t === "consumable" || t === "potion") return "consumable";
  return "material";
}

export function HeroScreen() {
  const { inventory, accessToken, guildId } = useGameSession();
  const [derived, setDerived] = useState<CharacterDerivedStatsPayload | null>(null);
  const [openItem, setOpenItem] = useState<InvRow | null>(null);
  const [powerOpen, setPowerOpen] = useState(false);
  const [filter, setFilter] = useState<BagFilter>("gear");

  const char = inventory?.character ?? null;
  const items = useMemo(() => inventory?.items ?? [], [inventory?.items]);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void api
      .getCharacterDerivedStats(accessToken, guildId)
      .then((d) => !cancelled && setDerived(d))
      .catch(() => !cancelled && setDerived(null));
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId, items]);

  const equippedBySlot = useMemo(() => {
    const m: Record<string, InvRow> = {};
    for (const it of items) if (it.is_equipped && it.equip_slot) m[it.equip_slot] = it;
    return m;
  }, [items]);

  const bag = useMemo(
    () => items.filter((it) => !it.is_equipped && bagCategory(it) === filter),
    [items, filter],
  );

  const power = computePower(derived);
  const emptySlots = SLOTS.filter((s) => !equippedBySlot[s.key]).length;

  return (
    <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
      <div className="mb-1 px-4">
        <span className="e-label">Hero</span>
      </div>

      <CharacterHero compact />

      <div className="space-y-3 px-4">
        {/* ── Power, and where it comes from ── */}
        <button
          type="button"
          onClick={() => setPowerOpen(true)}
          className="e-card e-card--warm flex w-full items-center gap-3 p-4 text-left"
        >
          <div className="min-w-0 flex-1">
            <div className="e-label mb-1">Combat power</div>
            <div className="e-num text-3xl font-bold leading-none" style={{ color: "var(--e-400)" }}>
              {power.toLocaleString()}
            </div>
            <p className="mt-1.5 text-[11.5px]" style={{ color: "var(--a-500)" }}>
              Tap to see what's carrying it
            </p>
          </div>
          <div className="shrink-0 text-right">
            {derived ? (
              <>
                <div className="e-num text-[12px]" style={{ color: "var(--a-300)" }}>
                  {Number(derived.dmg_min ?? 0)}–{Number(derived.dmg_max ?? 0)} dmg
                </div>
                <div className="e-num mt-1 text-[12px]" style={{ color: "var(--a-300)" }}>
                  {Number(derived.armor ?? 0).toLocaleString()} armor
                </div>
                <div className="e-num mt-1 text-[12px]" style={{ color: "var(--a-300)" }}>
                  {Number(derived.crit_chance ?? 0).toFixed(1)}% crit
                </div>
              </>
            ) : null}
          </div>
        </button>

        {/* ── Equipment ── */}
        <div className="e-card p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <span className="e-label">Equipment</span>
            {emptySlots > 0 ? (
              <span className="text-[10.5px]" style={{ color: "var(--e-400)" }}>
                {emptySlots} empty {emptySlots === 1 ? "slot" : "slots"}
              </span>
            ) : (
              <span className="text-[10.5px]" style={{ color: "var(--a-700)" }}>
                fully geared
              </span>
            )}
          </div>
          <div className="grid grid-cols-5 gap-2">
            {SLOTS.map((s) => {
              const it = equippedBySlot[s.key];
              const color = it ? RARITY_VAR[normRarity(it.rarity)] : "var(--n-500)";
              return (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => it && setOpenItem(it)}
                  disabled={!it}
                  className="flex flex-col items-center gap-1"
                >
                  <span
                    className="grid aspect-square w-full place-items-center rounded-lg"
                    style={{
                      border: `1px solid ${color}`,
                      background: it ? "var(--n-700)" : "rgba(0,0,0,0.25)",
                      opacity: it ? 1 : 0.5,
                    }}
                  >
                    {it ? (
                      <ItemIcon item={it} size={26} />
                    ) : (
                      <span className="text-[9px]" style={{ color: "var(--a-700)" }}>
                        —
                      </span>
                    )}
                  </span>
                  <span className="text-[8.5px] leading-none" style={{ color: "var(--a-700)" }}>
                    {s.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Bag ── */}
        <div className="e-card p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <span className="e-label">Bag</span>
            <span className="e-num text-[10.5px]" style={{ color: "var(--a-500)" }}>
              {inventory?.bag_slots_used ?? 0} / {inventory?.bag_slots_max ?? 0}
            </span>
          </div>

          <div className="mb-3 flex gap-1.5">
            {(
              [
                ["gear", "Gear"],
                ["consumable", "Usable"],
                ["material", "Materials"],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setFilter(k)}
                className={cn("e-pill flex-1", filter === k ? "e-pill--ember" : "e-pill--quiet")}
              >
                {label}
              </button>
            ))}
          </div>

          {bag.length === 0 ? (
            <p className="py-6 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
              Nothing here.
            </p>
          ) : (
            <div className="grid grid-cols-5 gap-2">
              {bag.map((it) => {
                const color = RARITY_VAR[normRarity(it.rarity)];
                return (
                  <button
                    key={it.id}
                    type="button"
                    onClick={() => setOpenItem(it)}
                    className="relative flex flex-col items-center"
                  >
                    <span
                      className="grid aspect-square w-full place-items-center rounded-lg"
                      style={{ border: `1px solid ${color}`, background: "var(--n-700)" }}
                    >
                      <ItemIcon item={it} size={26} />
                    </span>
                    {Number(it.quantity ?? 1) > 1 ? (
                      <span
                        className="e-num absolute -right-1 -top-1 rounded-full px-1 text-[8px] font-bold"
                        style={{ background: "var(--n-900)", color: "var(--a-300)", border: "1px solid var(--n-500)" }}
                      >
                        {it.quantity}
                      </span>
                    ) : null}
                    {Number(it.enhancement_level ?? 0) > 0 ? (
                      <span className="mt-0.5 text-[8px] font-bold" style={{ color: "var(--e-400)" }}>
                        +{it.enhancement_level}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <p className="px-1 text-center text-[11px] leading-relaxed" style={{ color: "var(--a-700)" }}>
          Forge, enhancement and repair live in the classic Forge tab for now —
          switch back in Settings to reach them.
        </p>
      </div>

      {openItem ? <ItemSheet item={openItem} onClose={() => setOpenItem(null)} /> : null}
      {powerOpen ? <PowerSheet derived={derived} onClose={() => setPowerOpen(false)} /> : null}
    </div>
  );
}
