import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";

export function ExploreTab() {
  const { map, refreshMap, travel, explore, lastExplore } = useGameSession();
  const [zonePick, setZonePick] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { void refreshMap(); }, [refreshMap]);
  useEffect(() => { if (map?.current_zone && !zonePick) setZonePick(map.current_zone); }, [map, zonePick]);

  const zones = map?.zones || [];
  const cur = zones.find((z) => z.key === map?.current_zone);

  const doTravel = async () => {
    if (!zonePick) return;
    setBusy(true);
    try {
      const r = await travel(zonePick);
      if (r.message) toast(r.message); else toast("Traveled.");
    } finally { setBusy(false); }
  };

  const doExplore = async () => {
    setBusy(true);
    try {
      const json = await explore();
      if (json.error === "cooldown" && json.cooldown_s) { toast.error(`Explore cooldown: ${json.cooldown_s}s`); return; }
      if (!json.ok && json.message) { toast.error(json.message); return; }
      if (json.outcome?.type === "enemy" || json.outcome?.type === "boss") {
        toast("Encounter!", { description: `Fight ${json.outcome.name} in the Combat tab.` });
      } else if (json.outcome?.type === "loot" || json.outcome?.type === "safe") {
        toast("Exploration result", { description: json.message || "You continue your journey." });
      }
      if (json.reward) toast.success(`+${json.reward.xp ?? 0} XP, +${json.reward.gold ?? 0} gold`);
    } finally { setBusy(false); }
  };

  const outcomeEl = lastExplore?.outcome;

  return (
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">Explore</div>
        <div className="mb-4">
          <h3 className="font-cinzel text-foreground font-semibold text-base">
            {cur?.emoji} {cur?.name ?? "Unknown"}
          </h3>
          <div className="flex gap-3 text-xs text-muted-foreground mt-1.5">
            <span>Levels {cur?.level_min ?? "?"}-{cur?.level_max ?? "?"}</span>
            <span style={{ color: 'hsl(228 14% 28%)' }}>◆</span>
            <span>{cur?.faction ?? "Neutral"}</span>
            {cur?.players != null && (
              <>
                <span style={{ color: 'hsl(228 14% 28%)' }}>◆</span>
                <span>{cur.players} players nearby</span>
              </>
            )}
          </div>
        </div>

        <div className="ornament-divider mb-4" />

        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <div className="flex-1">
            <label className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider block mb-1.5">Travel to zone</label>
            <select value={zonePick} onChange={(e) => setZonePick(e.target.value)} className="game-select">
              {zones.map((z) => (
                <option key={z.key} value={z.key}>
                  {z.emoji} {z.name} ({z.level_min ?? "?"}-{z.level_max ?? "?"}) {z.is_current ? "· here" : ""}
                </option>
              ))}
            </select>
          </div>
          <button onClick={() => void doTravel()} disabled={busy} className="game-btn-primary self-end">
            Travel
          </button>
        </div>

        <div className="ornament-divider mb-4" />

        <div className="flex items-center gap-3">
          <button onClick={() => void doExplore()} disabled={busy} className="game-btn-secondary">
            Explore
          </button>
          <span className="text-xs text-muted-foreground">Cooldown: ~30s between explorations</span>
        </div>
      </div>

      {/* Last result */}
      {outcomeEl && outcomeEl.type === "enemy" && (
        <div className="game-panel">
          <div className="game-panel-header">⚠️ Encounter!</div>
          <p className="text-sm mb-1">
            <span className="text-destructive font-semibold font-cinzel">{"name" in outcomeEl ? outcomeEl.name : "Enemy"}</span>
          </p>
          <div className="ornament-divider my-2" />
          <p className="text-xs text-muted-foreground">Open the <span className="text-primary">Combat</span> tab to fight.</p>
        </div>
      )}
      {outcomeEl && outcomeEl.type === "boss" && (
        <div className="game-panel">
          <div className="game-panel-header">⚠️ Boss Encounter!</div>
          <p className="text-sm mb-1">
            <span className="text-destructive font-semibold font-cinzel">{"name" in outcomeEl ? outcomeEl.name : "Boss"}</span>
          </p>
          <div className="ornament-divider my-2" />
          <p className="text-xs text-muted-foreground">Open the <span className="text-primary">Combat</span> tab to fight.</p>
        </div>
      )}
      {outcomeEl && (outcomeEl.type === "loot" || outcomeEl.type === "safe") && (
        <div className="game-panel">
          <div className="game-panel-header">{outcomeEl.type === "loot" ? "✨ Discovery!" : "🍃 Quiet Journey"}</div>
          <p className="text-sm text-foreground">{lastExplore?.message || "You continue your journey."}</p>
          {lastExplore?.reward && (
            <>
              <div className="ornament-divider my-2" />
              <div className="flex gap-4 text-xs">
                <span className="text-primary font-semibold" style={{ textShadow: '0 0 4px hsl(43 78% 50% / 0.2)' }}>
                  +{lastExplore.reward.xp ?? 0} XP
                </span>
                <span className="text-gold font-semibold">+{lastExplore.reward.gold ?? 0} 🪙</span>
              </div>
            </>
          )}
        </div>
      )}
      {lastExplore?.npc && (
        <div className="game-panel">
          <div className="game-panel-header">🧙 NPC Encounter</div>
          <p className="text-sm mb-1">
            <span className="text-accent-foreground font-semibold font-cinzel">{lastExplore.npc.name}</span>
            {lastExplore.npc.title && <span className="text-muted-foreground text-xs"> — {lastExplore.npc.title}</span>}
          </p>
          {lastExplore.npc.discovery_hint && (
            <p className="text-xs text-muted-foreground italic">"{lastExplore.npc.discovery_hint}"</p>
          )}
        </div>
      )}
    </div>
  );
}
