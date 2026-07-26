import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { GuildTech } from "@mobile/ui/parts/GuildTech";
import * as api from "@/lib/gameApi";
import type { GuildMePayload, GuildQuestRow } from "@/lib/apiTypes";
import { cn } from "@/lib/utils";

/**
 * The guild hall, in Ember.
 *
 * The classic GuildTab is 1,463 lines across nine stacked panels — banner,
 * check-in, quest board, war council, treasury, tech, raid, chat, invites — all
 * one long scroll. This covers what a member touches on a normal day: are we
 * doing well, have I checked in, what's claimable, and can I give gold.
 *
 * War council, raids and chat stay in classic; they're weekly, officer-gated
 * systems and cramming them here would recreate the scroll this is meant to fix.
 *
 * Tech is the exception and now lives here (GuildTech.tsx). It is the game's
 * largest gold sink and the only mechanic where spending gold makes other
 * people stronger — leaving it Discord-only meant phone players could earn gold
 * for the guild but never decide what it bought.
 */

function QuestRow({
  q,
  onClaim,
  busy,
}: {
  q: GuildQuestRow;
  onClaim: (key: string) => void;
  busy: boolean;
}) {
  const pct = q.target > 0 ? Math.min(100, (q.current / q.target) * 100) : 0;
  return (
    <li>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="min-w-0 flex-1 truncate text-[12.5px]" style={{ color: "var(--a-100)" }}>
          {q.name}
        </span>
        {q.my_claimed ? (
          <span className="e-pill e-pill--quiet shrink-0">Claimed</span>
        ) : q.can_claim ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => onClaim(q.key)}
            className="e-pill e-pill--ember shrink-0"
          >
            {busy ? "…" : "Claim"}
          </button>
        ) : (
          <span className="e-num shrink-0 text-[10.5px]" style={{ color: "var(--a-500)" }}>
            {q.current}/{q.target}
          </span>
        )}
      </div>
      <div className="e-bar e-bar--xp" style={{ height: 3 }}>
        <i style={{ width: `${pct}%` }} />
      </div>
    </li>
  );
}

export function GuildPanel() {
  const { accessToken, guildId, inventory, refreshInventory } = useGameSession();
  const [me, setMe] = useState<GuildMePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [period, setPeriod] = useState<"daily" | "weekly">("daily");
  const [depositOpen, setDepositOpen] = useState(false);
  const [amount, setAmount] = useState("");

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      setMe(await api.getGuildMe(accessToken, guildId));
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, guildId]);

  useEffect(() => {
    void load();
  }, [load]);

  const g = me?.guild ?? null;
  const checkin = me?.checkin ?? null;
  const quests = me?.quests ?? null;
  const gold = Number(inventory?.character?.gold ?? 0);

  async function doCheckin() {
    if (!accessToken) return;
    setBusy("checkin");
    try {
      const j = await api.postGuildCheckin(accessToken, guildId);
      const ok = (j as { ok?: boolean })?.ok !== false;
      if (ok) {
        toast.success("Checked in.");
        await Promise.all([load(), refreshInventory()]);
      } else toast.error((j as { message?: string })?.message || "Already checked in today.");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function claim(key: string) {
    if (!accessToken) return;
    setBusy(key);
    try {
      const j = await api.postGuildQuestClaim(accessToken, key, guildId);
      const ok = (j as { ok?: boolean })?.ok !== false;
      if (ok) {
        toast.success("Claimed.");
        await Promise.all([load(), refreshInventory()]);
      } else toast.error((j as { message?: string })?.message || "Could not claim.");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function deposit() {
    if (!accessToken) return;
    const n = Math.floor(Number(amount));
    if (!Number.isFinite(n) || n <= 0) return toast.error("Enter an amount.");
    if (n > gold) return toast.error("You don't have that much.");
    setBusy("deposit");
    try {
      const j = await api.postGuildBankDeposit(accessToken, n, guildId);
      const ok = (j as { ok?: boolean })?.ok !== false;
      if (ok) {
        toast.success(`Gave ${n.toLocaleString()} gold to the treasury.`);
        setDepositOpen(false);
        setAmount("");
        await Promise.all([load(), refreshInventory()]);
      } else toast.error((j as { message?: string })?.message || "Could not deposit.");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <p className="py-10 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
        Walking to the hall…
      </p>
    );
  }

  if (!me?.in_guild || !g) {
    return (
      <div className="e-card p-5 text-center">
        <div className="mb-2 text-2xl" aria-hidden>
          🏰
        </div>
        <p className="mb-1 text-[14px] font-semibold" style={{ color: "var(--a-100)" }}>
          You're not in a guild
        </p>
        <p className="text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
          Founding or joining a hall isn’t on mobile yet — you can do it in Discord, then it’ll show up here.
        </p>
      </div>
    );
  }

  const list = period === "daily" ? quests?.daily ?? [] : quests?.weekly ?? [];

  return (
    <div className="space-y-3">
      {/* ── Banner ── */}
      <div className="e-card e-card--warm p-4">
        <div className="mb-3 flex items-baseline gap-2">
          <span className="e-display text-base" style={{ color: "var(--e-300)" }}>
            {g.tag ? `[${g.tag}] ` : ""}
            {g.name}
          </span>
          {g.my_rank ? (
            <span className="e-pill e-pill--quiet capitalize">{g.my_rank}</span>
          ) : null}
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <div className="e-num text-lg font-bold" style={{ color: "var(--a-100)" }}>
              {g.guild_level ?? 1}
            </div>
            <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
              level
            </div>
          </div>
          <div>
            <div className="e-num text-lg font-bold" style={{ color: "var(--a-100)" }}>
              {g.member_count ?? 0}
              {g.max_members ? <span style={{ color: "var(--a-700)" }}>/{g.max_members}</span> : null}
            </div>
            <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
              members
            </div>
          </div>
          <div>
            <div className="e-num text-lg font-bold" style={{ color: "var(--g-400)" }}>
              {Number(g.bank_gold ?? 0).toLocaleString()}
            </div>
            <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
              treasury
            </div>
          </div>
        </div>
        {g.motd ? (
          <p className="mt-3 text-[11.5px] italic leading-relaxed" style={{ color: "var(--a-500)" }}>
            "{g.motd}"
          </p>
        ) : null}
      </div>

      {/* ── Check-in ── */}
      {checkin ? (
        <div className={cn("e-card flex items-center gap-3 p-4", !checkin.checked_today && "e-card--ready")}>
          <div className="min-w-0 flex-1">
            <div className="e-label mb-1">Hall check-in</div>
            <p className="text-[13px]" style={{ color: "var(--a-100)" }}>
              {checkin.checked_today ? "You're in today" : "You haven't checked in"}
            </p>
            <p className="mt-0.5 text-[11px]" style={{ color: "var(--a-500)" }}>
              {checkin.streak} day streak · {checkin.checked_in_guild_today} of the hall in today
            </p>
          </div>
          <button
            type="button"
            disabled={checkin.checked_today || busy === "checkin"}
            onClick={() => void doCheckin()}
            className={cn(
              "e-btn shrink-0 px-4",
              checkin.checked_today ? "e-btn--quiet" : "e-btn--primary",
            )}
          >
            {checkin.checked_today ? "Done" : busy === "checkin" ? "…" : "Check in"}
          </button>
        </div>
      ) : null}

      {/* ── Quest board ── */}
      {quests ? (
        <div className="e-card p-4">
          <div className="mb-3 flex items-center gap-2">
            <span className="e-label flex-1">Quest board</span>
            {(["daily", "weekly"] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriod(p)}
                className={cn("e-pill capitalize", period === p ? "e-pill--ember" : "e-pill--quiet")}
              >
                {p}
              </button>
            ))}
          </div>
          {list.length === 0 ? (
            <p className="text-[12px]" style={{ color: "var(--a-500)" }}>
              No {period} quests right now.
            </p>
          ) : (
            <ul className="space-y-3">
              {list.map((q) => (
                <QuestRow key={q.key} q={q} onClaim={(k) => void claim(k)} busy={busy === q.key} />
              ))}
            </ul>
          )}
        </div>
      ) : null}

      {/* ── Treasury ── */}
      <div className="e-card p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="e-label">Treasury</span>
          <span className="e-num text-[11px]" style={{ color: "var(--a-500)" }}>
            you have {gold.toLocaleString()}
          </span>
        </div>
        {depositOpen ? (
          <div className="space-y-2">
            <input
              inputMode="numeric"
              value={amount}
              onChange={(e) => setAmount(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder="How much gold?"
              className="w-full rounded-xl px-3 py-2.5 text-[15px]"
              style={{ background: "rgba(0,0,0,0.4)", border: "1px solid var(--n-500)", color: "var(--a-100)" }}
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setDepositOpen(false);
                  setAmount("");
                }}
                className="e-btn e-btn--quiet flex-1"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy === "deposit"}
                onClick={() => void deposit()}
                className="e-btn e-btn--primary flex-1"
              >
                {busy === "deposit" ? "…" : "Give"}
              </button>
            </div>
          </div>
        ) : (
          <button type="button" onClick={() => setDepositOpen(true)} className="e-btn e-btn--ghost w-full">
            Donate gold
          </button>
        )}
      </div>

      <GuildTech me={me} onChanged={async () => { await Promise.all([load(), refreshInventory()]); }} />

      <p className="px-1 text-center text-[10.5px] leading-relaxed" style={{ color: "var(--a-700)" }}>
        War council, raids and hall chat aren’t on mobile yet — they’re in Discord.
      </p>
    </div>
  );
}
