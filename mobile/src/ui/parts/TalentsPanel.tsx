import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import * as api from "@/lib/gameApi";
import type { TalentNodeState, TalentsStatePayload, TalentTreeSection } from "@/lib/apiTypes";
import { cn } from "@/lib/utils";

/**
 * Talents, rebuilt as a list rather than a tree.
 *
 * This is the one place the redesign deliberately abandons the classic SHAPE
 * rather than just its styling. The classic Talent Forge draws a node graph
 * with columns and connecting lines — which is the right form on a desktop and
 * the wrong one on a 390px screen, where it becomes a pan-and-zoom puzzle.
 *
 * A phone reads vertically, so: grouped by tier, prerequisites stated in words,
 * ranks as pips, and the invest button on the row itself. Nothing about the
 * underlying system changes — same nodes, same gates, same API.
 */

function NodeRow({
  n,
  onInvest,
  busy,
  unspent,
}: {
  n: TalentNodeState;
  onInvest: (id: string) => void;
  busy: boolean;
  unspent: number;
}) {
  const ranks = Number(n.ranks ?? 0);
  const max = Number(n.max_ranks ?? 1);
  const maxed = ranks >= max;
  const can = Boolean(n.can_allocate) && !maxed && unspent > 0;
  // descriptions is per-rank; show the one for the rank you'd get next.
  const desc = n.descriptions?.[Math.min(ranks, (n.descriptions?.length ?? 1) - 1)] ?? "";

  return (
    <div
      className="rounded-xl p-3"
      style={{
        border: `1px solid ${ranks > 0 ? "rgba(255,122,47,0.4)" : "var(--n-500)"}`,
        background: ranks > 0 ? "rgba(255,122,47,0.07)" : "rgba(0,0,0,0.26)",
      }}
    >
      <div className="mb-1 flex items-baseline gap-2">
        <span
          className="min-w-0 flex-1 text-[13px] font-semibold"
          style={{ color: ranks > 0 ? "var(--e-300)" : "var(--a-100)" }}
        >
          {n.name || n.id}
        </span>
        {/* Ranks as pips — quicker to read than "2/3" at a glance. */}
        <span className="flex shrink-0 gap-1" aria-label={`${ranks} of ${max} ranks`}>
          {Array.from({ length: max }).map((_, i) => (
            <span
              key={i}
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: i < ranks ? "var(--e-500)" : "var(--n-400)" }}
            />
          ))}
        </span>
      </div>

      {desc ? (
        <p className="mb-2 text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
          {desc}
        </p>
      ) : null}

      {maxed ? (
        <span className="e-pill e-pill--quiet">Maxed</span>
      ) : can ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => onInvest(String(n.id))}
          className="e-pill e-pill--ember"
        >
          {busy ? "…" : `Spend a point`}
        </button>
      ) : (
        <span className="text-[11px]" style={{ color: "var(--a-700)" }}>
          {n.locked_reason ||
            (unspent <= 0
              ? "No points to spend"
              : n.points_required
                ? `Needs ${n.points_required} points in this tree first`
                : "Locked")}
        </span>
      )}
    </div>
  );
}

function Section({
  section,
  title,
  onInvest,
  busy,
  unspent,
}: {
  section: TalentTreeSection;
  title: string;
  onInvest: (id: string) => void;
  busy: boolean;
  unspent: number;
}) {
  const byTier = useMemo(() => {
    const m = new Map<number, TalentNodeState[]>();
    for (const n of section.nodes ?? []) {
      const t = Number(n.tier ?? 0);
      m.set(t, [...(m.get(t) ?? []), n]);
    }
    return [...m.entries()].sort((a, b) => a[0] - b[0]);
  }, [section.nodes]);

  if (byTier.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="e-label pt-1">{title}</div>
      {byTier.map(([tier, nodes]) => (
        <div key={tier} className="space-y-2">
          {byTier.length > 1 ? (
            <div className="text-[10.5px]" style={{ color: "var(--a-700)" }}>
              Tier {tier}
            </div>
          ) : null}
          {nodes.map((n) => (
            <NodeRow key={n.id} n={n} onInvest={onInvest} busy={busy} unspent={unspent} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function TalentsPanel() {
  const { accessToken, guildId, refreshInventory } = useGameSession();
  const [state, setState] = useState<TalentsStatePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirmRespec, setConfirmRespec] = useState(false);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      setState(await api.getTalents(accessToken, guildId));
    } catch {
      setState(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, guildId]);

  useEffect(() => {
    void load();
  }, [load]);

  const pts = state?.points ?? null;
  const unspent = Number(pts?.unspent ?? 0);

  async function invest(nodeId: string) {
    if (!accessToken || busy) return;
    setBusy(true);
    try {
      const j = await api.allocateTalent(accessToken, nodeId, guildId);
      const ok = (j as { ok?: boolean })?.ok !== false;
      if (ok) {
        toast.success("Point spent.");
        await Promise.all([load(), refreshInventory()]);
      } else toast.error((j as { message?: string })?.message || "Could not spend that point.");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function respec() {
    if (!accessToken || busy) return;
    setBusy(true);
    setConfirmRespec(false);
    try {
      const j = await api.respecTalents(accessToken, guildId);
      const ok = (j as { ok?: boolean })?.ok !== false;
      if (ok) {
        toast.success("Talents reset.");
        await Promise.all([load(), refreshInventory()]);
      } else toast.error((j as { message?: string })?.message || "Could not reset.");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <p className="py-10 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
        Reading the tree…
      </p>
    );
  }

  if (!state?.ok && !state?.foundation && !(state?.spec_trees ?? []).length) {
    return (
      <div className="e-card p-5 text-center">
        <p className="text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
          {state?.message || "No talents available yet — they open up as you level."}
        </p>
      </div>
    );
  }

  const respecCost = Number(state?.respec_gold_cost ?? 0);

  return (
    <div className="space-y-3">
      {/* ── Points ── */}
      <div className="e-card e-card--warm p-4">
        <div className="flex items-end gap-5">
          <div>
            <div className="e-num text-3xl font-bold leading-none" style={{ color: "var(--e-400)" }}>
              {unspent}
            </div>
            <div className="mt-1 text-[11px]" style={{ color: "var(--a-500)" }}>
              {unspent === 1 ? "point to spend" : "points to spend"}
            </div>
          </div>
          <div className="mb-0.5">
            <div className="e-num text-[13px]" style={{ color: "var(--a-300)" }}>
              {Number(pts?.spent ?? 0)} spent
            </div>
            <div className="text-[11px]" style={{ color: "var(--a-700)" }}>
              of {Number(pts?.earned ?? 0)} earned
            </div>
          </div>
        </div>
        {unspent > 0 ? (
          <p className="mt-2.5 text-[11.5px]" style={{ color: "var(--e-300)" }}>
            You have points sitting unused — they do nothing until you spend them.
          </p>
        ) : null}
      </div>

      {state.foundation ? (
        <Section
          section={state.foundation}
          title="Class foundation"
          onInvest={(id) => void invest(id)}
          busy={busy}
          unspent={unspent}
        />
      ) : null}

      {(state.spec_trees ?? []).map((t, i) => (
        <Section
          key={t.spec_key ?? i}
          section={t}
          title={
            t.spec_key
              ? String(t.spec_key).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
              : "Specialisation"
          }
          onInvest={(id) => void invest(id)}
          busy={busy}
          unspent={unspent}
        />
      ))}

      {/* ── Respec ── */}
      <div className="e-card p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="e-label">Start over</span>
          <span className="e-num text-[11px]" style={{ color: "var(--a-500)" }}>
            {respecCost > 0 ? `${respecCost.toLocaleString()} gold` : "free"}
          </span>
        </div>
        {confirmRespec ? (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setConfirmRespec(false)}
              className="e-btn e-btn--quiet flex-1 py-2 text-[13px]"
            >
              Keep them
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void respec()}
              className="e-btn flex-1 py-2 text-[13px]"
              style={{ background: "var(--wound)", color: "#fff" }}
            >
              Reset everything
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmRespec(true)}
            className="e-btn e-btn--ghost w-full py-2 text-[13px]"
          >
            Refund all points
          </button>
        )}
      </div>
    </div>
  );
}
