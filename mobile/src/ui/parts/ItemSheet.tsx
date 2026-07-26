import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { ItemIcon } from "@/components/game/ItemIcon";
import { normRarity } from "@/hooks/useForge";
import type { InvRow } from "@/lib/apiTypes";
import { cn } from "@/lib/utils";

/**
 * Item detail — with a real comparison against what you're already wearing.
 *
 * A NEW system in this shell. The classic UI does have a compare block inside a
 * hover popover (HeroTab.tsx:568-607), but it's hover-first and lives inside a
 * tooltip, which on a phone means long-press and a cramped card. Here it's a
 * proper sheet and the comparison is the headline, not a footnote.
 *
 * The maths is real: InvRow carries static (s_*) and rolled (r_*) stats, and
 * enhancement adds 10% per level, so an honest before/after is computable
 * entirely client-side. Nothing is faked.
 */

const STATS: { key: string; label: string }[] = [
  { key: "str", label: "Strength" },
  { key: "agi", label: "Agility" },
  { key: "int", label: "Intellect" },
  { key: "spi", label: "Spirit" },
  { key: "sta", label: "Stamina" },
  { key: "armor", label: "Armor" },
  { key: "dmg_min", label: "Min damage" },
  { key: "dmg_max", label: "Max damage" },
  { key: "haste", label: "Haste" },
  { key: "hit_rating", label: "Hit" },
  { key: "lifesteal", label: "Lifesteal" },
  { key: "resistance", label: "Resistance" },
];

const RARITY_VAR: Record<string, string> = {
  common: "var(--r-common)",
  uncommon: "var(--r-uncommon)",
  rare: "var(--r-rare)",
  epic: "var(--r-epic)",
  legendary: "var(--r-legendary)",
  mythic: "var(--r-mythic)",
};

/** Static + rolled, then the enhancement multiplier the game applies (+10%/level). */
function statTotal(item: InvRow | null, key: string): number {
  if (!item) return 0;
  const rec = item as unknown as Record<string, unknown>;
  const base = Number(rec[`s_${key}`] ?? 0) + Number(rec[`r_${key}`] ?? 0);
  if (!base) return 0;
  const enh = Number(item.enhancement_level ?? 0);
  return Math.round(base * (1 + enh * 0.1));
}

function slotOf(item: InvRow | null): string {
  return String(item?.equip_slot || item?.template_equip_slot || "");
}

export function ItemSheet({
  item,
  onClose,
}: {
  item: InvRow;
  onClose: () => void;
}) {
  const { inventory, itemPost, refreshInventory, refreshProgress } = useGameSession();
  const [busy, setBusy] = useState(false);

  const equipped = Boolean(item.is_equipped);
  const rarity = normRarity(item.rarity);
  const color = RARITY_VAR[rarity] ?? RARITY_VAR.common;

  /** If this piece belongs to a set, how that set is going.
   *
   *  Deliberately shown HERE rather than in a separate codex screen: the moment
   *  you care which set a piece belongs to is the moment you're looking at it
   *  deciding whether to equip, sell or salvage. A codex would also be thin —
   *  only two sets exist today. */
  const setState = useMemo(() => {
    if (!item.set_id) return null;
    return (inventory?.item_sets ?? []).find((s) => s.set_id === item.set_id) ?? null;
  }, [item.set_id, inventory?.item_sets]);

  /** What's currently worn in this item's slot — the thing to compare against. */
  const worn = useMemo(() => {
    if (equipped) return null;
    const slot = slotOf(item);
    if (!slot) return null;
    return (inventory?.items ?? []).find((it) => it.is_equipped && it.equip_slot === slot) ?? null;
  }, [equipped, item, inventory?.items]);

  const rows = useMemo(() => {
    return STATS.map((s) => {
      const mine = statTotal(item, s.key);
      const theirs = statTotal(worn, s.key);
      return { ...s, mine, theirs, delta: mine - theirs };
    }).filter((r) => r.mine !== 0 || r.theirs !== 0);
  }, [item, worn]);

  const netBetter = rows.reduce((a, r) => a + r.delta, 0);

  async function act(endpoint: string, label: string) {
    if (busy) return;
    setBusy(true);
    try {
      const res = await itemPost(endpoint, { item_id: item.id });
      const j = (await res.json()) as { ok?: boolean; message?: string };
      if (res.ok && j.ok !== false) {
        toast.success(j.message || `${label} done.`);
        await Promise.all([refreshInventory(), refreshProgress()]);
        onClose();
      } else {
        toast.error(j.message || `Could not ${label.toLowerCase()}.`);
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
      />
      <div
        className="e-sheet e-scroll fixed inset-x-0 bottom-0 z-50 max-h-[84dvh] px-4"
        role="dialog"
        aria-modal="true"
        aria-label={item.name}
      >
        <div className="e-grabber" />

        <div className="mb-4 flex items-start gap-3">
          <div
            className="grid h-14 w-14 shrink-0 place-items-center rounded-xl"
            style={{ border: `1px solid ${color}`, background: "var(--n-700)" }}
          >
            <ItemIcon item={item} size={40} />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="e-display text-base leading-tight" style={{ color }}>
              {item.name}
              {Number(item.enhancement_level ?? 0) > 0 ? (
                <span style={{ color: "var(--e-400)" }}> +{item.enhancement_level}</span>
              ) : null}
            </h2>
            <p className="mt-0.5 text-[11px] capitalize" style={{ color: "var(--a-500)" }}>
              {rarity}
              {slotOf(item) ? ` · ${slotOf(item).replace(/_/g, " ")}` : ""}
              {item.level_req ? ` · requires level ${item.level_req}` : ""}
            </p>
            {equipped ? <span className="e-pill e-pill--ember mt-2 inline-block">Equipped</span> : null}
          </div>
        </div>

        {/* ── Set membership ── */}
        {item.set_id ? (
          <div
            className="mb-3 rounded-xl p-3"
            style={{
              border: "1px solid rgba(255,122,47,0.3)",
              background: "rgba(255,122,47,0.07)",
            }}
          >
            <div className="mb-1 flex items-baseline justify-between gap-2">
              <span className="text-[12.5px] font-semibold" style={{ color: "var(--e-300)" }}>
                {setState?.name ?? String(item.set_id).replace(/_/g, " ")}
              </span>
              {setState ? (
                <span className="e-num shrink-0 text-[11.5px]" style={{ color: "var(--a-300)" }}>
                  {setState.equipped}
                  {setState.max_pieces ? ` / ${setState.max_pieces}` : ""} worn
                </span>
              ) : null}
            </div>
            {setState?.active_bonus ? (
              <p className="text-[11.5px] leading-relaxed" style={{ color: "var(--vital)" }}>
                ✓ {setState.active_bonus}
              </p>
            ) : null}
            {setState?.next_bonus && setState.pieces_to_next ? (
              <p className="mt-0.5 text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
                {setState.pieces_to_next} more → {setState.next_bonus}
              </p>
            ) : !setState ? (
              /* Not wearing any of it yet — so item_sets has no entry, and the
                 only honest thing to say is that this is part of a set. */
              <p className="text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
                Part of a set — wearing more pieces together grants bonuses.
              </p>
            ) : null}
          </div>
        ) : null}

        {/* ── The comparison ── */}
        {worn ? (
          <div className="mb-3">
            <div className="mb-2 flex items-baseline justify-between">
              <span className="e-label">Compared to {worn.name}</span>
              <span
                className="e-num text-[12px] font-bold"
                style={{ color: netBetter > 0 ? "var(--vital)" : netBetter < 0 ? "var(--wound)" : "var(--a-500)" }}
              >
                {netBetter > 0 ? "▲ upgrade" : netBetter < 0 ? "▼ downgrade" : "— sidegrade"}
              </span>
            </div>
          </div>
        ) : null}

        {rows.length > 0 ? (
          <ul className="space-y-1.5 pb-1">
            {rows.map((r) => (
              <li
                key={r.key}
                className="flex items-baseline justify-between gap-2 rounded-lg px-2.5 py-1.5"
                style={{ background: "rgba(0,0,0,0.28)" }}
              >
                <span className="text-[12px]" style={{ color: "var(--a-300)" }}>
                  {r.label}
                </span>
                <span className="e-num shrink-0 text-[12px]">
                  <span style={{ color: "var(--a-100)" }}>{r.mine}</span>
                  {worn ? (
                    <span
                      className="ml-2 font-semibold"
                      style={{
                        color:
                          r.delta > 0 ? "var(--vital)" : r.delta < 0 ? "var(--wound)" : "var(--a-700)",
                      }}
                    >
                      {r.delta > 0 ? `+${r.delta}` : r.delta < 0 ? `${r.delta}` : "="}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-3 text-[12px]" style={{ color: "var(--a-500)" }}>
            This item has no combat stats.
          </p>
        )}

        <div className="mt-4 flex gap-2">
          {equipped ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void act("/api/game/item/unequip", "Unequipped")}
              className={cn("e-btn e-btn--ghost flex-1", busy && "opacity-60")}
            >
              Unequip
            </button>
          ) : slotOf(item) ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void act("/api/game/item/equip", "Equipped")}
              className={cn("e-btn e-btn--primary flex-1", busy && "opacity-60")}
            >
              {busy ? "…" : "Equip"}
            </button>
          ) : item.effect_type ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void act("/api/game/item/use", "Used")}
              className={cn("e-btn e-btn--primary flex-1", busy && "opacity-60")}
            >
              {busy ? "…" : "Use"}
            </button>
          ) : null}
          <button type="button" onClick={onClose} className="e-btn e-btn--quiet flex-1">
            Close
          </button>
        </div>
      </div>
    </>
  );
}
