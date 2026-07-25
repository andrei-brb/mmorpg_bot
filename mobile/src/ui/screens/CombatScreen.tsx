import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { CombatTab } from "@/components/game/tabs/CombatTab";
import { enemyPortraitSrc } from "@/lib/enemyPortraitUrl";
import type { CombatEnemy } from "@/lib/apiTypes";
import { cn } from "@/lib/utils";

/**
 * Combat — picking a fight, in Ember.
 *
 * This screen owns the CHOICE: who to fight, how dangerous they are, and
 * whether you're in shape for it. Once a fight starts it hands over to
 * CombatTab, which already renders through DrawerBattle — the phone-native
 * combat layout built earlier in this project. Building a second live-fight
 * view would mean maintaining two.
 *
 * The design change from classic: risk is stated in words, not just a coloured
 * dot, and the comparison that actually matters — their health against yours —
 * is shown as a bar rather than left for you to work out.
 */

const RISK: Record<string, { label: string; color: string; note: string }> = {
  fair: { label: "Fair fight", color: "var(--vital)", note: "You should win this." },
  caution: { label: "Careful", color: "var(--g-400)", note: "Winnable, but it'll cost you." },
  risky: { label: "Risky", color: "var(--e-400)", note: "You may lose this one." },
  deadly: { label: "Deadly", color: "var(--wound)", note: "This will very likely kill you." },
};

function EnemyRow({
  e,
  myHp,
  selected,
  onSelect,
}: {
  e: CombatEnemy;
  myHp: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const risk = RISK[String(e.risk_tier ?? "")] ?? null;
  const hp = Number(e.max_hp ?? 0);
  const isBoss = e.kind === "boss";
  const portrait = e.key ? enemyPortraitSrc(e.key, e.kind ?? "enemy") : "";
  // How their health stacks against yours, capped so a huge boss doesn't
  // flatten the bar into meaninglessness.
  const ratio = myHp > 0 && hp > 0 ? Math.min(2, hp / myHp) : 0;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn("e-card w-full p-3 text-left", selected && "e-card--warm")}
      style={selected ? { borderColor: "var(--e-500)" } : undefined}
    >
      <div className="flex items-center gap-3">
        <span
          className="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-lg"
          style={{
            border: `1px solid ${isBoss ? "var(--wound)" : "var(--n-500)"}`,
            background: "var(--n-700)",
          }}
        >
          {portrait ? (
            <img
              src={portrait}
              alt=""
              className="h-full w-full object-cover"
              onError={(ev) => {
                (ev.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          ) : (
            <span className="text-lg">{e.emoji || "👾"}</span>
          )}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold" style={{ color: "var(--a-100)" }}>
              {e.name}
            </span>
            {isBoss ? <span className="e-pill e-pill--gold shrink-0">Boss</span> : null}
          </div>
          {risk ? (
            <div className="mt-0.5 text-[11px]" style={{ color: risk.color }}>
              {risk.label}
            </div>
          ) : null}
          {hp > 0 ? (
            <div className="mt-1.5">
              <div className="e-bar" style={{ height: 3 }}>
                <i
                  style={{
                    width: `${Math.min(100, ratio * 50)}%`,
                    background: "linear-gradient(90deg, #8E2438, var(--wound))",
                  }}
                />
              </div>
              <div className="e-num mt-1 text-[10px]" style={{ color: "var(--a-700)" }}>
                {hp.toLocaleString()} health
                {myHp > 0 ? ` · you have ${myHp.toLocaleString()}` : ""}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </button>
  );
}

export function CombatScreen() {
  const { inventory, loadCombatSnapshot, startCombat, rest, pendingCombatEnemyKey } =
    useGameSession();

  const [enemies, setEnemies] = useState<CombatEnemy[]>([]);
  const [loading, setLoading] = useState(true);
  const [fighting, setFighting] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const char = inventory?.character ?? null;
  const myHp = Number(char?.current_hp ?? 0);
  const myMaxHp = Number(char?.max_hp ?? 0);
  const hurt = myMaxHp > 0 && myHp / myMaxHp < 0.5;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const snap = await loadCombatSnapshot();
      // Already mid-fight (or Explore queued one) — go straight to the fight.
      if (snap.active || pendingCombatEnemyKey.current) {
        setFighting(true);
      }
      setEnemies(snap.enemies ?? []);
    } catch {
      setEnemies([]);
    } finally {
      setLoading(false);
    }
  }, [loadCombatSnapshot, pendingCombatEnemyKey]);

  useEffect(() => {
    void load();
  }, [load]);

  async function start(enemyKey: string) {
    if (busy) return;
    setBusy(true);
    try {
      const r = await startCombat({ kind: "zone", enemyKey });
      if (r.ok || r.state) setFighting(true);
      else toast.error(r.message || r.error || "Could not start that fight.");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function doRest() {
    setBusy(true);
    try {
      const r = await rest();
      if (r.ok) toast.success(r.message || "You catch your breath.");
      else if (r.cooldown_s) toast.error(`Not yet — ${r.cooldown_s}s to go.`);
      else toast.error(r.message || "Could not rest.");
    } finally {
      setBusy(false);
    }
  }

  if (fighting) {
    return (
      <div className="min-h-full">
        <div
          className="flex items-center px-4 pb-2"
          style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}
        >
          <button
            type="button"
            onClick={() => {
              setFighting(false);
              void load();
            }}
            className="e-pill e-pill--quiet"
          >
            ← Choose another fight
          </button>
        </div>
        <CombatTab />
      </div>
    );
  }

  const bosses = enemies.filter((e) => e.kind === "boss");
  const mobs = enemies.filter((e) => e.kind !== "boss");
  const sel = enemies.find((e) => e.key === picked) ?? null;
  const selRisk = sel ? RISK[String(sel.risk_tier ?? "")] : null;

  return (
    <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
      <div className="mb-3 flex items-baseline justify-between px-4">
        <span className="e-label">Combat</span>
        {myMaxHp > 0 ? (
          <span className="e-num text-[10.5px]" style={{ color: hurt ? "var(--wound)" : "var(--a-700)" }}>
            {myHp.toLocaleString()} / {myMaxHp.toLocaleString()} health
          </span>
        ) : null}
      </div>

      <div className="space-y-3 px-4">
        {/* Being hurt is the single most common reason a fight goes badly, so
            say it before they pick, not after they lose. */}
        {hurt ? (
          <div className="e-card e-card--warm flex items-center gap-3 p-3.5">
            <span className="text-lg" aria-hidden>
              🩸
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold" style={{ color: "var(--a-100)" }}>
                You're hurt
              </p>
              <p className="text-[11px]" style={{ color: "var(--a-500)" }}>
                Resting first will make this go much better.
              </p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => void doRest()}
              className="e-btn e-btn--primary shrink-0 px-4 py-2 text-[13px]"
            >
              Rest
            </button>
          </div>
        ) : null}

        {loading ? (
          <p className="py-10 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
            Looking for trouble…
          </p>
        ) : enemies.length === 0 ? (
          <div className="e-card p-5 text-center">
            <p className="mb-1 text-[13.5px] font-semibold" style={{ color: "var(--a-100)" }}>
              Nothing to fight here
            </p>
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
              Travel to another zone from Explore, or go exploring to flush something out.
            </p>
          </div>
        ) : (
          <>
            {bosses.length > 0 ? (
              <div className="space-y-2">
                <div className="e-label">Bosses</div>
                {bosses.map((e) => (
                  <EnemyRow
                    key={e.key}
                    e={e}
                    myHp={myMaxHp}
                    selected={picked === e.key}
                    onSelect={() => setPicked(e.key)}
                  />
                ))}
              </div>
            ) : null}

            {mobs.length > 0 ? (
              <div className="space-y-2">
                <div className="e-label">{bosses.length > 0 ? "Everything else" : "Enemies"}</div>
                {mobs.map((e) => (
                  <EnemyRow
                    key={e.key}
                    e={e}
                    myHp={myMaxHp}
                    selected={picked === e.key}
                    onSelect={() => setPicked(e.key)}
                  />
                ))}
              </div>
            ) : null}
          </>
        )}
      </div>

      {/* ── The commitment, pinned so it's always in reach ── */}
      {sel ? (
        <div
          className="sticky bottom-0 mt-4 px-4 pt-3"
          style={{
            background: "linear-gradient(180deg, transparent, var(--n-900) 30%)",
            paddingBottom: "calc(0.5rem + env(safe-area-inset-bottom))",
          }}
        >
          {selRisk ? (
            <p className="mb-2 text-center text-[11.5px]" style={{ color: selRisk.color }}>
              {selRisk.note}
            </p>
          ) : null}
          <button
            type="button"
            disabled={busy}
            onClick={() => void start(sel.key)}
            className="e-btn e-btn--primary w-full"
          >
            {busy ? "…" : `Fight ${sel.name}`}
          </button>
        </div>
      ) : null}
    </div>
  );
}
