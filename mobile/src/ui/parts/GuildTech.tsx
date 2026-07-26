import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import * as api from "@/lib/gameApi";
import type { GuildMePayload, GuildTechDefinition } from "@/lib/apiTypes";

/**
 * Guild tech, on the phone.
 *
 * The whole system already existed and worked: 24 nodes across three branches,
 * member-funded research, unlock/contribute/finalize endpoints, and the
 * resulting multipliers wired into `get_combined_reward_multipliers` so they
 * apply to every member's XP and gold. It just wasn't reachable from the mobile
 * shell — GuildPanel said so in as many words: "War council, guild tech, raids
 * and hall chat aren't on mobile yet — they're in Discord."
 *
 * So this is a client for a working system, not a new one. Nothing about the
 * economics is invented here: costs, prerequisites and effects all come from
 * the server's own definitions.
 *
 * This is also the game's largest gold sink. Contributions leave the economy
 * permanently and buy a bonus every member shares, which is the only mechanic
 * in the game where spending gold makes someone *else* stronger.
 */

const BRANCH_LABEL: Record<string, string> = {
  economy: "Economy",
  war: "War",
  accord: "Accord",
};

const BRANCH_ORDER = ["economy", "war", "accord"];

function fmt(n: number): string {
  return Math.max(0, Math.round(n)).toLocaleString();
}

export function GuildTech({
  me,
  onChanged,
}: {
  me: GuildMePayload;
  onChanged: () => Promise<void> | void;
}) {
  const { accessToken, guildId, inventory } = useGameSession();
  const [busy, setBusy] = useState<string | null>(null);
  const [openNode, setOpenNode] = useState<string | null>(null);
  const [amount, setAmount] = useState("");

  const tech = me.tech;
  const unlocked = useMemo(() => new Set(tech?.unlocked ?? []), [tech?.unlocked]);
  const funds = tech?.funds ?? {};
  const gold = Number(inventory?.character?.gold ?? 0);

  const byBranch = useMemo(() => {
    const groups: Record<string, GuildTechDefinition[]> = {};
    for (const d of tech?.definitions ?? []) {
      const b = d.branch ?? "economy";
      (groups[b] ||= []).push(d);
    }
    return groups;
  }, [tech?.definitions]);

  if (!tech || !(tech.definitions ?? []).length) return null;

  /** A node is reachable when every prerequisite is already unlocked. Shown
   *  rather than hidden, so the branch reads as a path with a direction. */
  function locked(d: GuildTechDefinition): string | null {
    const missing = (d.requires ?? []).filter((r) => !unlocked.has(r));
    if (!missing.length) return null;
    const names = missing.map(
      (id) => (tech!.definitions ?? []).find((x) => x.id === id)?.name ?? id,
    );
    return `Needs ${names.join(", ")}`;
  }

  async function contribute(nodeId: string) {
    const n = Math.floor(Number(amount));
    if (!Number.isFinite(n) || n <= 0) {
      toast.error("Enter an amount to contribute.");
      return;
    }
    if (n > gold) {
      toast.error(`You only have ${fmt(gold)} gold.`);
      return;
    }
    if (!accessToken) return;
    setBusy(nodeId);
    try {
      const j = await api.postGuildTechContribute(accessToken, nodeId, n, guildId);
      if (j?.ok === false) toast.error(j.message || "Could not contribute.");
      else {
        toast.success(j?.message || `Contributed ${fmt(n)} gold.`);
        setAmount("");
        setOpenNode(null);
        await onChanged();
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function unlock(nodeId: string) {
    if (!accessToken) return;
    setBusy(nodeId);
    try {
      const j = await api.postGuildTechUnlock(accessToken, nodeId, guildId);
      if (j?.ok === false) toast.error(j.message || "Could not unlock.");
      else {
        toast.success(j?.message || "Researched.");
        await onChanged();
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="e-card p-4">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="e-label">Guild research</span>
        <span className="e-num text-[11px]" style={{ color: "var(--a-500)" }}>
          {unlocked.size} / {(tech.definitions ?? []).length}
        </span>
      </div>
      <p className="mb-3 text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
        Gold you contribute is spent permanently and buys a bonus every member keeps.
      </p>

      <div className="space-y-4">
        {BRANCH_ORDER.filter((b) => byBranch[b]?.length).map((branch) => (
          <div key={branch}>
            <div className="e-label mb-2">{BRANCH_LABEL[branch] ?? branch}</div>
            <ul className="space-y-1.5">
              {byBranch[branch].map((d) => {
                const done = unlocked.has(d.id);
                const gate = locked(d);
                const f = funds[d.id];
                const req = Number(f?.required ?? d.fund_gold_required ?? 0);
                const got = Number(f?.contributed ?? 0);
                const pct = req > 0 ? Math.min(100, (got / req) * 100) : 100;
                const funded = req <= 0 || got >= req;
                const isOpen = openNode === d.id;

                return (
                  <li
                    key={d.id}
                    className="rounded-xl p-2.5"
                    style={{
                      border: `1px solid ${done ? "rgba(60,170,100,0.45)" : "var(--n-500)"}`,
                      background: done ? "rgba(25,90,55,0.14)" : "rgba(0,0,0,0.28)",
                      opacity: gate && !done ? 0.6 : 1,
                    }}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span
                        className="min-w-0 flex-1 text-[12.5px] font-semibold"
                        style={{ color: done ? "var(--vital)" : "var(--a-100)" }}
                      >
                        {done ? "✓ " : ""}
                        {d.name}
                      </span>
                      {!done && req > 0 ? (
                        <span className="e-num shrink-0 text-[11px]" style={{ color: "var(--a-500)" }}>
                          {fmt(got)} / {fmt(req)}g
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-0.5 text-[11.5px] leading-relaxed" style={{ color: "var(--a-300)" }}>
                      {d.description}
                    </p>

                    {gate && !done ? (
                      <p className="mt-1 text-[11px]" style={{ color: "var(--a-500)" }}>
                        {gate}
                      </p>
                    ) : null}

                    {!done && !gate ? (
                      <>
                        {req > 0 ? (
                          <div
                            className="mt-2 h-1.5 w-full overflow-hidden rounded-full"
                            style={{ background: "rgba(0,0,0,0.45)" }}
                          >
                            <div
                              className="h-full rounded-full transition-all"
                              style={{ width: `${pct}%`, background: "var(--e-500)" }}
                            />
                          </div>
                        ) : null}

                        <div className="mt-2 flex gap-2">
                          {!funded ? (
                            <button
                              type="button"
                              onClick={() => {
                                setOpenNode(isOpen ? null : d.id);
                                setAmount("");
                              }}
                              className="e-btn e-btn--ghost flex-1 text-[12px]"
                            >
                              {isOpen ? "Cancel" : "Contribute"}
                            </button>
                          ) : (
                            <button
                              type="button"
                              disabled={busy === d.id}
                              onClick={() => void unlock(d.id)}
                              className="e-btn e-btn--primary flex-1 text-[12px]"
                            >
                              {busy === d.id ? "Researching…" : "Research"}
                            </button>
                          )}
                        </div>

                        {isOpen && !funded ? (
                          <div className="mt-2 flex gap-2">
                            <input
                              inputMode="numeric"
                              value={amount}
                              onChange={(e) => setAmount(e.target.value.replace(/[^0-9]/g, ""))}
                              placeholder={`up to ${fmt(Math.min(gold, req - got))}`}
                              className="min-w-0 flex-1 rounded-lg px-2.5 py-1.5 text-[12px]"
                              style={{
                                border: "1px solid var(--n-500)",
                                background: "rgba(0,0,0,0.4)",
                                color: "var(--a-100)",
                              }}
                            />
                            <button
                              type="button"
                              disabled={busy === d.id}
                              onClick={() => void contribute(d.id)}
                              className="e-btn e-btn--primary shrink-0 text-[12px]"
                            >
                              {busy === d.id ? "…" : "Give"}
                            </button>
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
