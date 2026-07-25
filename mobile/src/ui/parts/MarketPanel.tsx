import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { ItemIcon } from "@/components/game/ItemIcon";
import { normRarity } from "@/hooks/useForge";
import * as api from "@/lib/gameApi";
import type { InvRow, MarketListingRow } from "@/lib/apiTypes";
import { cn } from "@/lib/utils";

/**
 * The market, in Ember.
 *
 * The classic MarketView is 2,410 lines covering auctions, player market,
 * an NPC shop and direct trades, behind two levels of tabs. This is the part
 * players actually use every session — browse, buy, sell — with the rest still
 * reachable in classic.
 *
 * Design position: a buy button spends real gold, so the price and whether you
 * can afford it are the two things that must be unmistakable. Rarity colours the
 * item; affordability colours the price.
 */

const RARITY_VAR: Record<string, string> = {
  common: "var(--r-common)",
  uncommon: "var(--r-uncommon)",
  rare: "var(--r-rare)",
  epic: "var(--r-epic)",
  legendary: "var(--r-legendary)",
  mythic: "var(--r-mythic)",
};

function listedAgo(at?: string): string {
  if (!at) return "";
  const t = Date.parse(at);
  if (!Number.isFinite(t)) return "";
  const m = Math.floor((Date.now() - t) / 60000);
  if (m < 60) return `${Math.max(1, m)}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function MarketPanel() {
  const {
    accessToken,
    guildId,
    inventory,
    marketListings,
    refreshMarketListings,
    listItemOnMarket,
    refreshInventory,
  } = useGameSession();

  const [mode, setMode] = useState<"browse" | "sell">("browse");
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [sellItem, setSellItem] = useState<InvRow | null>(null);
  const [price, setPrice] = useState("");

  const gold = Number(inventory?.character?.gold ?? 0);
  const myCharId = String(inventory?.character?.id ?? "");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    void refreshMarketListings()
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [refreshMarketListings]);

  /** Sellable = in the bag, not soulbound, tradeable. Mirrors MarketView:124. */
  const sellable = useMemo(
    () =>
      (inventory?.items ?? []).filter(
        (it) => !it.is_equipped && !it.soulbound && it.tradeable !== false && !it.locked,
      ),
    [inventory?.items],
  );

  async function buy(l: MarketListingRow) {
    if (busy) return;
    setBusy(l.id);
    try {
      const j = await api.postMarketBuy(accessToken!, l.id, guildId);
      if ((j as { ok?: boolean })?.ok === false) {
        toast.error((j as { message?: string })?.message || "Could not buy that.");
      } else {
        toast.success(`Bought ${l.name}.`);
        await Promise.all([refreshInventory(), refreshMarketListings()]);
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function sell() {
    if (!sellItem || busy) return;
    const p = Math.floor(Number(price));
    if (!Number.isFinite(p) || p <= 0) {
      toast.error("Enter a price.");
      return;
    }
    setBusy("sell");
    const r = await listItemOnMarket(String(sellItem.id), p);
    setBusy(null);
    if (r.ok) {
      toast.success(`${sellItem.name} listed for ${p.toLocaleString()} gold.`);
      setSellItem(null);
      setPrice("");
      setMode("browse");
    } else {
      toast.error(r.message || "Could not list that.");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="flex flex-1 gap-1.5">
          {(
            [
              ["browse", "Browse"],
              ["sell", "Sell"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setMode(k)}
              className={cn("e-pill flex-1 py-2", mode === k ? "e-pill--ember" : "e-pill--quiet")}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="e-pill e-pill--gold e-num shrink-0">🪙 {gold.toLocaleString()}</span>
      </div>

      {mode === "browse" ? (
        loading ? (
          <p className="py-8 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
            Reading the boards…
          </p>
        ) : failed ? (
          <div className="e-card p-4 text-center">
            <p className="mb-3 text-[12px]" style={{ color: "var(--a-500)" }}>
              Couldn't reach the market.
            </p>
            <button
              type="button"
              onClick={() => void refreshMarketListings()}
              className="e-btn e-btn--ghost w-full"
            >
              Try again
            </button>
          </div>
        ) : marketListings.length === 0 ? (
          <p className="py-8 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
            Nothing for sale right now.
          </p>
        ) : (
          <div className="space-y-2">
            {marketListings.map((l) => {
              const r = normRarity(l.rarity);
              const mine = myCharId && String(l.seller_id ?? "") === myCharId;
              const afford = gold >= Number(l.price ?? 0);
              // MarketListingRow isn't an InvRow, but ItemIcon only reads
              // name/template_id/icon — enough to resolve the art.
              const iconItem = {
                id: l.id,
                name: l.name,
                template_id: l.template_id ?? undefined,
                icon: l.icon ?? undefined,
                equip_slot: l.template_equip_slot ?? undefined,
                template_equip_slot: l.template_equip_slot ?? undefined,
                item_type: l.item_type ?? undefined,
                rarity: l.rarity,
              } as unknown as InvRow;

              return (
                <div key={l.id} className="e-card flex items-center gap-3 p-3">
                  <span
                    className="grid h-11 w-11 shrink-0 place-items-center rounded-lg"
                    style={{ border: `1px solid ${RARITY_VAR[r]}`, background: "var(--n-700)" }}
                  >
                    <ItemIcon item={iconItem} size={30} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-semibold" style={{ color: RARITY_VAR[r] }}>
                      {l.name}
                      {Number(l.enhancement_level ?? 0) > 0 ? (
                        <span style={{ color: "var(--e-400)" }}> +{l.enhancement_level}</span>
                      ) : null}
                      {Number(l.quantity ?? 1) > 1 ? (
                        <span style={{ color: "var(--a-500)" }}> ×{l.quantity}</span>
                      ) : null}
                    </div>
                    <div className="truncate text-[10.5px]" style={{ color: "var(--a-700)" }}>
                      {mine ? "your listing" : l.seller_name} · {listedAgo(l.listed_at)}
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div
                      className="e-num text-[13px] font-bold"
                      style={{ color: afford ? "var(--g-400)" : "var(--wound)" }}
                    >
                      {Number(l.price ?? 0).toLocaleString()}
                    </div>
                    {mine ? (
                      <span className="text-[10px]" style={{ color: "var(--a-700)" }}>
                        listed
                      </span>
                    ) : (
                      <button
                        type="button"
                        disabled={!afford || busy === l.id}
                        onClick={() => void buy(l)}
                        className={cn(
                          "e-pill mt-1",
                          afford ? "e-pill--ember" : "e-pill--quiet",
                          !afford && "opacity-60",
                        )}
                      >
                        {busy === l.id ? "…" : afford ? "Buy" : "Too dear"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        /* ── Sell ── */
        <div className="space-y-3">
          {sellItem ? (
            <div className="e-card e-card--warm p-4">
              <div className="mb-3 flex items-center gap-3">
                <span
                  className="grid h-12 w-12 shrink-0 place-items-center rounded-lg"
                  style={{
                    border: `1px solid ${RARITY_VAR[normRarity(sellItem.rarity)]}`,
                    background: "var(--n-700)",
                  }}
                >
                  <ItemIcon item={sellItem} size={32} />
                </span>
                <div className="min-w-0 flex-1">
                  <div
                    className="truncate text-[14px] font-semibold"
                    style={{ color: RARITY_VAR[normRarity(sellItem.rarity)] }}
                  >
                    {sellItem.name}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSellItem(null);
                      setPrice("");
                    }}
                    className="text-[11px] underline"
                    style={{ color: "var(--a-500)" }}
                  >
                    choose a different item
                  </button>
                </div>
              </div>

              <label className="e-label mb-1.5 block">Your price</label>
              <input
                inputMode="numeric"
                value={price}
                onChange={(e) => setPrice(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder="Gold"
                className="w-full rounded-xl px-3 py-2.5 text-[15px]"
                style={{
                  background: "rgba(0,0,0,0.4)",
                  border: "1px solid var(--n-500)",
                  color: "var(--a-100)",
                }}
              />
              {/* Suggested price comes from the game's own pure helper, so it
                  matches what the rest of the app would quote. */}
              <button
                type="button"
                onClick={() => setPrice(String(api.calculateMarketPrice(sellItem)))}
                className="e-pill e-pill--quiet mt-2"
              >
                Suggest {api.calculateMarketPrice(sellItem).toLocaleString()}
              </button>

              <button
                type="button"
                disabled={busy === "sell" || !price}
                onClick={() => void sell()}
                className="e-btn e-btn--primary mt-3 w-full"
              >
                {busy === "sell" ? "Listing…" : "List it"}
              </button>
            </div>
          ) : sellable.length === 0 ? (
            <p className="py-8 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
              Nothing you can sell. Equipped and soulbound items can't be listed.
            </p>
          ) : (
            <div className="grid grid-cols-4 gap-2">
              {sellable.map((it) => {
                const r = normRarity(it.rarity);
                return (
                  <button
                    key={it.id}
                    type="button"
                    onClick={() => {
                      setSellItem(it);
                      setPrice(String(api.calculateMarketPrice(it)));
                    }}
                    className="flex flex-col items-center gap-1 rounded-xl p-2"
                    style={{ border: `1px solid ${RARITY_VAR[r]}66`, background: "rgba(0,0,0,0.3)" }}
                  >
                    <ItemIcon item={it} size={28} />
                    <span
                      className="line-clamp-2 text-center text-[9.5px] leading-tight"
                      style={{ color: "var(--a-300)" }}
                    >
                      {it.name}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      <p className="px-1 text-center text-[10.5px] leading-relaxed" style={{ color: "var(--a-700)" }}>
        Auctions, the NPC shop and direct trades aren’t on mobile yet — they’re in Discord.
      </p>
    </div>
  );
}
