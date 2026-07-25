import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { cn } from "@/lib/utils";
import { useCampData } from "@mobile/ui/useCampData";
import type { QuestLogRow } from "@/lib/apiTypes";

/**
 * Quests, in Ember.
 *
 * The classic tab is a list plus a detail pane plus a story beacon plus a daily
 * panel plus a battle-pass mini-panel — five things competing on one phone
 * screen. Here the compass leads (it's the answer to "what now"), then today's
 * daily, then the log grouped by kind.
 *
 * The compass is server-driven: main_quest_pointer already computes whether
 * you're mid-quest, need to find an NPC, or are gated by level/deeds
 * (apiTypes.ts:450-469). Rendering it rather than re-deriving it means it can
 * never disagree with the backend.
 */

type Bucket = "story" | "daily" | "world" | "done";

function bucketOf(q: QuestLogRow): Bucket {
  if (q.state === "completed" || q.state === "complete") return "done";
  if (q.lore_main) return "story";
  if (q.expires_at) return "daily";
  return "world";
}

const BUCKET_LABEL: Record<Bucket, string> = {
  story: "Story",
  daily: "Timed",
  world: "World",
  done: "Finished",
};

function QuestCard({
  q,
  onTurnIn,
  onTalk,
  onAbandon,
  busy,
}: {
  q: QuestLogRow;
  onTurnIn: (id: string) => void;
  onTalk: (npc?: string) => void;
  onAbandon: (id: string) => void;
  busy: boolean;
}) {
  const [confirmAbandon, setConfirmAbandon] = useState(false);
  const cur = Number(q.progress?.current ?? 0);
  const need = Number(q.progress?.needed ?? 0);
  const pct = need > 0 ? Math.min(100, (cur / need) * 100) : 0;
  const done = need > 0 && cur >= need;
  const canTurnIn = done && Boolean(q.npc_id);

  return (
    <div className={cn("e-card p-4", done && "e-card--ready")}>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="min-w-0 flex-1 text-[13.5px] font-semibold" style={{ color: "var(--a-100)" }}>
          {q.quest_name || "Quest"}
        </span>
        {q.lore_main ? <span className="e-pill e-pill--gold shrink-0">Story</span> : null}
      </div>

      {q.total_steps && Number(q.total_steps) > 1 ? (
        <p className="mb-1 text-[10.5px]" style={{ color: "var(--a-700)" }}>
          Step {q.current_step ?? 1} of {q.total_steps}
        </p>
      ) : null}

      {q.objective ? (
        <p className="mb-2 text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
          {q.objective}
        </p>
      ) : null}

      {need > 0 ? (
        <>
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-[10.5px]" style={{ color: "var(--a-700)" }}>
              {done ? "Ready to turn in" : "Progress"}
            </span>
            <span className="e-num text-[11px]" style={{ color: "var(--a-300)" }}>
              {cur}/{need}
            </span>
          </div>
          <div className="e-bar e-bar--xp" style={{ height: 4 }}>
            <i style={{ width: `${pct}%` }} />
          </div>
        </>
      ) : null}

      <div className="mt-3 flex gap-2">
        {canTurnIn ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => onTurnIn(String(q.quest_id))}
            className="e-btn e-btn--primary flex-1 py-2 text-[13px]"
          >
            {busy ? "…" : `Turn in${q.npc_name ? ` to ${q.npc_name}` : ""}`}
          </button>
        ) : q.npc_id ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => onTalk(q.npc_id ?? undefined)}
            className="e-btn e-btn--ghost flex-1 py-2 text-[13px]"
          >
            Talk to {q.npc_name || "them"}
          </button>
        ) : null}

        {/* Main-story quests can't be abandoned (QuestsTab.tsx:362-363). */}
        {!q.lore_main && q.quest_id ? (
          confirmAbandon ? (
            <>
              <button
                type="button"
                onClick={() => setConfirmAbandon(false)}
                className="e-btn e-btn--quiet px-3 py-2 text-[12px]"
              >
                Keep
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setConfirmAbandon(false);
                  onAbandon(String(q.quest_id));
                }}
                className="e-btn px-3 py-2 text-[12px]"
                style={{ background: "var(--wound)", color: "#fff" }}
              >
                Drop it
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmAbandon(true)}
              className="e-btn e-btn--quiet px-3 py-2 text-[12px]"
            >
              Abandon
            </button>
          )
        ) : null}
      </div>
    </div>
  );
}

export function QuestsScreen() {
  const { quests, refreshQuests, abandonQuest, npcInteract, refreshInventory } = useGameSession();
  const camp = useCampData();
  const [busy, setBusy] = useState(false);
  const [bucket, setBucket] = useState<Bucket | "all">("all");

  const rows = useMemo(() => quests?.quests ?? [], [quests?.quests]);
  const pointer = quests?.main_quest_pointer ?? null;

  const grouped = useMemo(() => {
    const g: Record<Bucket, QuestLogRow[]> = { story: [], daily: [], world: [], done: [] };
    for (const q of rows) g[bucketOf(q)].push(q);
    return g;
  }, [rows]);

  const visible: [Bucket, QuestLogRow[]][] =
    bucket === "all"
      ? (["story", "daily", "world", "done"] as Bucket[])
          .map((b) => [b, grouped[b]] as [Bucket, QuestLogRow[]])
          .filter(([, list]) => list.length > 0)
      : [[bucket, grouped[bucket]]];

  async function talk(npc?: string) {
    setBusy(true);
    try {
      const r = await npcInteract(npc);
      if (!r.ok) toast.error(r.message || r.error || "They had nothing to say.");
      else if (!r.openedQuestOffer && !r.openedCompletion && r.message) toast.message(r.message);
    } finally {
      setBusy(false);
    }
  }

  async function turnIn(questId: string) {
    // Turn-in runs through the NPC, same as classic (QuestsTab.tsx:422-441).
    const q = rows.find((x) => String(x.quest_id) === questId);
    await talk(q?.npc_id ?? undefined);
    await Promise.all([refreshQuests(), refreshInventory()]);
  }

  async function drop(questId: string) {
    setBusy(true);
    try {
      const r = await abandonQuest(questId);
      if (r.ok) toast.success(r.message || "Abandoned.");
      else toast.error(r.message || r.error || "Could not abandon.");
    } finally {
      setBusy(false);
    }
  }

  const daily = camp.daily;

  return (
    <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
      <div className="mb-3 flex items-baseline justify-between px-4">
        <span className="e-label">Quests</span>
        <span className="e-num text-[10.5px]" style={{ color: "var(--a-700)" }}>
          {rows.filter((q) => bucketOf(q) !== "done").length} open
        </span>
      </div>

      <div className="space-y-3 px-4">
        {/* ── The compass ── */}
        {pointer && pointer.kind && pointer.kind !== "none" ? (
          <div className="e-card e-card--warm p-4">
            <div className="mb-1.5 flex items-center gap-2">
              <span className="text-base" aria-hidden>
                🧭
              </span>
              <span className="e-label">Your story</span>
            </div>
            <p className="text-[14px] font-semibold leading-snug" style={{ color: "var(--a-100)" }}>
              {String((pointer as Record<string, unknown>).quest_name || "") ||
                (pointer.kind === "complete"
                  ? "You've seen it through — for now"
                  : pointer.kind === "seek_npc"
                    ? "Someone is waiting for you"
                    : "The path goes on")}
            </p>
            {String((pointer as Record<string, unknown>).hint || "") ? (
              <p className="mt-1.5 text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
                {String((pointer as Record<string, unknown>).hint)}
              </p>
            ) : null}
            {/* Gates are stated plainly instead of leaving you stuck. */}
            {pointer.kind === "blocked_level" ? (
              <p className="mt-2 text-[11.5px]" style={{ color: "var(--e-300)" }}>
                You need more levels before this opens.
              </p>
            ) : null}
            {pointer.kind === "blocked_deeds" ? (
              <p className="mt-2 text-[11.5px]" style={{ color: "var(--e-300)" }}>
                There are deeds still undone before this opens.
              </p>
            ) : null}
          </div>
        ) : null}

        {/* ── Today ── */}
        {daily ? (
          <div className={cn("e-card p-4", daily.is_complete && "e-card--ready")}>
            <div className="mb-2 flex items-baseline justify-between gap-2">
              <span className="e-label">Today's quest</span>
              {daily.is_complete ? (
                <span className="e-pill e-pill--ember">Complete</span>
              ) : (
                <span className="text-[10px]" style={{ color: "var(--a-700)" }}>
                  resets at midnight
                </span>
              )}
            </div>
            <p className="text-[13.5px] font-semibold" style={{ color: "var(--a-100)" }}>
              {daily.name || "Daily quest"}
            </p>
            <div className="mt-2.5 space-y-2">
              {(daily.objectives || []).map((o) => {
                const have = Number((daily.progress || {})[o.id] ?? 0);
                const need = Number(o.count ?? 0);
                return (
                  <div key={o.id}>
                    <div className="mb-1 flex items-baseline justify-between gap-2">
                      <span className="min-w-0 flex-1 truncate text-[11.5px]" style={{ color: "var(--a-300)" }}>
                        {o.description || o.kind}
                      </span>
                      <span className="e-num shrink-0 text-[11px]" style={{ color: "var(--a-500)" }}>
                        {have}/{need}
                      </span>
                    </div>
                    <div className="e-bar e-bar--xp" style={{ height: 3 }}>
                      <i style={{ width: `${need > 0 ? Math.min(100, (have / need) * 100) : 0}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

        {/* ── Filters ── */}
        {rows.length > 0 ? (
          <div className="e-scroll-x flex gap-1.5 pb-0.5">
            <button
              type="button"
              onClick={() => setBucket("all")}
              className={cn("e-pill shrink-0", bucket === "all" ? "e-pill--ember" : "e-pill--quiet")}
            >
              All
            </button>
            {(["story", "daily", "world", "done"] as Bucket[])
              .filter((b) => grouped[b].length > 0)
              .map((b) => (
                <button
                  key={b}
                  type="button"
                  onClick={() => setBucket(b)}
                  className={cn("e-pill shrink-0", bucket === b ? "e-pill--ember" : "e-pill--quiet")}
                >
                  {BUCKET_LABEL[b]} {grouped[b].length}
                </button>
              ))}
          </div>
        ) : null}

        {/* ── The log ── */}
        {rows.length === 0 ? (
          <div className="e-card p-5 text-center">
            <p className="mb-1 text-[13.5px] font-semibold" style={{ color: "var(--a-100)" }}>
              No quests yet
            </p>
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
              Explore and talk to whoever you find — quests come from people, not menus.
            </p>
          </div>
        ) : (
          visible.map(([b, list]) => (
            <div key={b} className="space-y-2">
              {bucket === "all" ? <div className="e-label pt-1">{BUCKET_LABEL[b]}</div> : null}
              {list.map((q) => (
                <QuestCard
                  key={q.quest_id ?? q.quest_name}
                  q={q}
                  busy={busy}
                  onTurnIn={(id) => void turnIn(id)}
                  onTalk={(npc) => void talk(npc)}
                  onAbandon={(id) => void drop(id)}
                />
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
