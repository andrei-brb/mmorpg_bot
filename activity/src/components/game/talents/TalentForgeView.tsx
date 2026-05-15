import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronUp, Crown, RotateCcw } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { useGameSession } from "@/context/GameSessionContext";
import {
  buildForgeTreesFromApi,
  pointsInTree,
  ranksFromTalentsState,
} from "@/components/game/talents/talentForgeAdapter";
import { TalentForgePanel } from "@/components/game/talents/TalentForgePanel";
import {
  CLASS_LABELS,
  SPEC_META,
  SPEC_UNLOCK_LEVEL,
} from "@/components/game/talents/talentForgeMeta";
import type { ForgeTalentTree } from "@/components/game/talents/talentForgeTypes";
import type { TalentsStatePayload } from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";
import { cn } from "@/lib/utils";

type Props = {
  characterLevel?: number;
  characterClass?: string;
  characterName?: string;
  onStatsRefresh?: () => void;
};

export function TalentForgeView({ characterLevel, characterClass, characterName, onStatsRefresh }: Props) {
  const { accessToken, guildId, chooseSpecialization, inventory, progress } = useGameSession();
  const [talents, setTalents] = useState<TalentsStatePayload | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const level = talents?.level ?? characterLevel ?? inventory?.character?.level ?? progress?.character?.level ?? 1;
  const classKey = talents?.class_key ?? characterClass ?? inventory?.character?.class ?? "warrior";
  const classLabel = CLASS_LABELS[classKey] || classKey;
  const spec = talents?.specialization ?? inventory?.character?.specialization ?? null;

  const derivedStatsKey = useMemo(() => {
    const lvl = inventory?.character?.level ?? progress?.character?.level ?? 0;
    return `${lvl}|${spec}|${classKey}`;
  }, [inventory?.character?.level, progress?.character?.level, spec, classKey]);

  const loadTalents = useCallback(async () => {
    if (!accessToken) return;
    try {
      const j = await api.getTalents(accessToken, guildId);
      if (j.ok !== false) setTalents(j);
    } catch {
      setTalents(null);
    }
  }, [accessToken, guildId]);

  useEffect(() => {
    void loadTalents();
  }, [loadTalents, derivedStatsKey]);

  const { foundation, specs } = useMemo(
    () => (talents ? buildForgeTreesFromApi(talents) : { foundation: null, specs: [] as ForgeTalentTree[] }),
    [talents],
  );

  const ranks = useMemo(() => (talents ? ranksFromTalentsState(talents) : {}), [talents]);

  const unspent = talents?.points?.unspent ?? 0;
  const earned = talents?.points?.earned ?? 0;
  const spent = talents?.points?.spent ?? 0;
  const canChooseSpec = level >= SPEC_UNLOCK_LEVEL;

  const foundationSpent = foundation ? pointsInTree(foundation, ranks) : 0;

  const onInvest = useCallback(
    async (talentId: string) => {
      if (!accessToken || busy) return;
      setBusy(true);
      setMessage(null);
      try {
        const j = await api.allocateTalent(accessToken, talentId, guildId);
        if (j.ok) {
          setTalents(j);
          setMessage(j.message || "Point spent.");
          onStatsRefresh?.();
        } else {
          setMessage(j.message || "Could not allocate.");
        }
      } catch {
        setMessage("Network error.");
      } finally {
        setBusy(false);
      }
    },
    [accessToken, guildId, busy, onStatsRefresh],
  );

  const onRespec = useCallback(async () => {
    if (!accessToken || busy) return;
    const cost = talents?.respec_gold_cost ?? 0;
    const free = (talents?.respec_count ?? 0) === 0;
    const ok = window.confirm(
      free
        ? "Reset all talent points? First respec is free."
        : `Reset all talent points for ${cost.toLocaleString()} gold?`,
    );
    if (!ok) return;
    setBusy(true);
    setMessage(null);
    try {
      const j = await api.respecTalents(accessToken, guildId);
      if (j.ok) {
        setTalents(j);
        setMessage(j.message || "Talents reset.");
        onStatsRefresh?.();
      } else {
        setMessage(j.message || "Respec failed.");
      }
    } catch {
      setMessage("Network error.");
    } finally {
      setBusy(false);
    }
  }, [accessToken, guildId, busy, talents?.respec_count, talents?.respec_gold_cost, onStatsRefresh]);

  const onChooseSpec = useCallback(
    async (specKey: string) => {
      if (!canChooseSpec || spec) return;
      await chooseSpecialization(specKey);
      await loadTalents();
    },
    [canChooseSpec, spec, chooseSpecialization, loadTalents],
  );

  if (!talents) {
    return <p className="text-xs text-muted-foreground py-4">Loading talent trees…</p>;
  }

  return (
    <TooltipProvider>
      <div className="space-y-4 sm:space-y-6">
        <header className="ornate-frame rounded-md px-4 sm:px-6 py-4 sm:py-5 relative">
          <span className="corner-ornament corner-tl" aria-hidden />
          <span className="corner-ornament corner-tr" aria-hidden />
          <span className="corner-ornament corner-bl" aria-hidden />
          <span className="corner-ornament corner-br" aria-hidden />

          <div className="relative flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4 min-w-0">
              <div
                className="h-12 w-12 sm:h-14 sm:w-14 grid place-items-center rounded border-2 border-gold shadow-gold shrink-0"
                style={{ background: "var(--gradient-node-active)" }}
              >
                <Crown className="h-6 w-6 sm:h-7 sm:w-7 text-background" strokeWidth={2.2} />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-[0.35em] text-gold-dim font-cinzel">
                  {classLabel}
                  {characterName ? ` · ${characterName}` : ""}
                </p>
                <h2 className="font-cinzel text-2xl sm:text-3xl text-shimmer">Talent Trees</h2>
              </div>
            </div>

            <div className="flex items-center gap-4 sm:gap-6 w-full sm:w-auto justify-between sm:justify-end">
              <div className="text-center px-3 sm:px-5 border-x border-border/60">
                <div className="font-cinzel text-2xl sm:text-3xl">
                  <span className={cn(unspent > 0 ? "text-gold-bright" : "text-muted-foreground")}>{unspent}</span>
                  <span className="text-muted-foreground"> / {earned}</span>
                </div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">unspent points</div>
              </div>

              <Button
                type="button"
                onClick={() => void onRespec()}
                variant="outline"
                disabled={busy}
                className="border-gold/50 hover:bg-gold/10 hover:border-gold text-gold font-cinzel tracking-widest text-xs sm:text-sm shrink-0"
              >
                <RotateCcw className="h-4 w-4 mr-1.5 sm:mr-2" />
                RESPEC
                {(talents.respec_count ?? 0) > 0 && talents.respec_gold_cost
                  ? ` (${talents.respec_gold_cost.toLocaleString()}g)`
                  : " (FREE)"}
              </Button>
            </div>
          </div>

          <p className="relative mt-3 sm:mt-4 text-xs text-muted-foreground">
            Preview both specs before level <span className="text-gold">{SPEC_UNLOCK_LEVEL}</span>. At level{" "}
            {SPEC_UNLOCK_LEVEL}, choose your specialization — then earn{" "}
            <span className="text-gold">+1 point every 2 levels</span>. Spent: {spent}.
          </p>
          {message ? <p className="relative mt-2 text-xs text-primary">{message}</p> : null}
        </header>

        {foundation ? (
          <TalentForgePanel
            tree={foundation}
            ranks={ranks}
            pointsInTree={foundationSpent}
            canSpend={unspent > 0}
            onInvest={(id) => void onInvest(id)}
            busy={busy}
            subtitle={<span>{foundationSpent} points in foundation</span>}
          />
        ) : null}

        {specs.length >= 2 ? (
          <SpecChooser
            specs={specs}
            activeSpec={spec}
            canChoose={canChooseSpec}
            level={level}
            onChoose={(sk) => void onChooseSpec(sk)}
          />
        ) : null}

        <div className={cn("grid gap-4 sm:gap-6", specs.length > 1 ? "lg:grid-cols-2" : "grid-cols-1")}>
          {specs.map((tree) => {
            const sk = tree.id;
            const isActive = spec === sk;
            const preview = !spec;
            const treeActive = canChooseSpec && (isActive || preview);
            const treeSpent = pointsInTree(tree, ranks);
            const otherSpec = spec && spec !== sk;
            return (
              <TalentForgePanel
                key={sk}
                tree={tree}
                ranks={ranks}
                pointsInTree={treeSpent}
                canSpend={unspent > 0 && treeActive && !otherSpec}
                active={treeActive}
                busy={busy}
                lockedReason={
                  !canChooseSpec
                    ? `Unlocks at Level ${SPEC_UNLOCK_LEVEL}`
                    : otherSpec
                      ? `${SPEC_META[spec]?.name || spec} chosen`
                      : undefined
                }
                onInvest={(id) => void onInvest(id)}
                subtitle={
                  isActive ? (
                    <span className="text-gold">Active spec</span>
                  ) : preview ? (
                    <span>Preview</span>
                  ) : undefined
                }
              />
            );
          })}
        </div>
      </div>
    </TooltipProvider>
  );
}

function SpecChooser({
  specs,
  activeSpec,
  canChoose,
  level,
  onChoose,
}: {
  specs: ForgeTalentTree[];
  activeSpec: string | null;
  canChoose: boolean;
  level: number;
  onChoose: (specKey: string) => void;
}) {
  return (
    <div className="ornate-frame rounded-md p-4 sm:p-5 relative">
      <span className="corner-ornament corner-tl" aria-hidden />
      <span className="corner-ornament corner-tr" aria-hidden />
      <span className="corner-ornament corner-bl" aria-hidden />
      <span className="corner-ornament corner-br" aria-hidden />
      <div className="relative flex items-center justify-between gap-4 mb-4">
        <div>
          <p className="text-[10px] uppercase tracking-[0.4em] text-gold-dim font-cinzel">Step Two</p>
          <h3 className="font-cinzel text-lg sm:text-xl text-gold-bright tracking-widest uppercase">
            Choose Specialization
          </h3>
        </div>
        {!canChoose ? (
          <p className="text-xs text-muted-foreground italic text-right">
            Reach <span className="text-gold">level {SPEC_UNLOCK_LEVEL}</span> to commit. Currently Lv {level}.
          </p>
        ) : activeSpec ? (
          <p className="text-xs text-gold font-cinzel uppercase tracking-wider">Committed</p>
        ) : null}
      </div>
      <div className="relative grid sm:grid-cols-2 gap-3 sm:gap-4">
        {specs.map((tree) => {
          const sk = tree.id;
          const meta = SPEC_META[sk];
          const Icon = meta?.icon || tree.icon;
          const isActive = activeSpec === sk;
          const isDimmed = Boolean(activeSpec && !isActive);
          return (
            <button
              key={sk}
              type="button"
              disabled={!canChoose || (Boolean(activeSpec) && !isActive)}
              onClick={() => onChoose(sk)}
              className={cn(
                "group relative flex items-center gap-3 sm:gap-4 p-3 sm:p-4 border-2 rounded transition-all text-left",
                "disabled:cursor-not-allowed",
                isActive
                  ? "border-gold shadow-gold bg-gold/5"
                  : isDimmed
                    ? "border-border/40 opacity-50"
                    : canChoose
                      ? "border-border hover:border-gold/70 hover:bg-gold/5"
                      : "border-border/40 opacity-60",
              )}
            >
              <div
                className={cn(
                  "h-12 w-12 sm:h-14 sm:w-14 grid place-items-center rounded border-2 shrink-0",
                  isActive ? "border-gold-bright" : "border-border",
                )}
                style={{ background: isActive ? "var(--gradient-node-active)" : "var(--gradient-node-locked)" }}
              >
                <Icon className={cn("h-6 w-6 sm:h-7 sm:w-7", isActive ? "text-background" : "text-gold")} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-cinzel text-base sm:text-lg uppercase tracking-widest text-gold-bright">
                    {meta?.name || tree.name}
                  </span>
                  {isActive ? (
                    <span className="text-[10px] font-cinzel uppercase tracking-widest px-2 py-0.5 rounded bg-gold text-background">
                      Active
                    </span>
                  ) : null}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{meta?.tagline || tree.flavor}</p>
              </div>
              <ChevronUp
                className={cn(
                  "h-5 w-5 shrink-0 transition-transform",
                  isActive ? "rotate-0 text-gold" : "rotate-180 text-muted-foreground/40",
                )}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
