import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { Button } from "@/components/ui/button";

export function ExploreTab() {
  const { map, refreshMap, travel, explore, lastExplore } = useGameSession();
  const [zonePick, setZonePick] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void refreshMap();
  }, [refreshMap]);

  useEffect(() => {
    if (map?.current_zone && !zonePick) setZonePick(map.current_zone);
  }, [map, zonePick]);

  const zones = map?.zones || [];

  const doTravel = async () => {
    if (!zonePick) return;
    setBusy(true);
    try {
      const r = await travel(zonePick);
      if (r.message) toast(r.message);
      else toast("Traveled.");
    } finally {
      setBusy(false);
    }
  };

  const doExplore = async () => {
    setBusy(true);
    try {
      const json = await explore();
      if (json.error === "cooldown" && json.cooldown_s) {
        toast.error(`Explore cooldown: ${json.cooldown_s}s`);
        return;
      }
      if (!json.ok && json.message) {
        toast.error(json.message);
        return;
      }
      if (json.outcome?.type === "enemy" || json.outcome?.type === "boss") {
        toast("Encounter!", { description: `Fight ${json.outcome.name} in the Combat tab.` });
      } else if (json.outcome?.type === "loot" || json.outcome?.type === "safe") {
        toast("Exploration result", { description: json.message || "You continue your journey." });
      }
      if (json.reward) {
        toast.success(`+${json.reward.xp ?? 0} XP, +${json.reward.gold ?? 0} gold`);
      }
    } finally {
      setBusy(false);
    }
  };

  const cur = zones.find((z) => z.key === map?.current_zone);

  return (
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">World map</div>
        <p className="text-xs text-muted-foreground mb-2">
          Current:{" "}
          <span className="text-foreground">
            {cur?.emoji} {cur?.name ?? "—"}
          </span>
        </p>
        <div className="flex flex-col sm:flex-row gap-2">
          <select
            className="game-select flex-1 bg-background border rounded-sm px-2 py-2 text-sm"
            value={zonePick}
            onChange={(e) => setZonePick(e.target.value)}
          >
            {zones.map((z) => (
              <option key={z.key} value={z.key}>
                {z.emoji} {z.name} ({z.level_min ?? "?"}-{z.level_max ?? "?"}) {z.is_current ? "· here" : ""}
              </option>
            ))}
          </select>
          <Button type="button" className="game-btn-primary" disabled={busy} onClick={() => void doTravel()}>
            Travel
          </Button>
          <Button type="button" variant="secondary" disabled={busy} onClick={() => void doExplore()}>
            Explore
          </Button>
        </div>
      </div>

      {lastExplore && (
        <div className="game-panel">
          <div className="game-panel-header">Last result</div>
          <pre className="text-[10px] text-muted-foreground whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
            {JSON.stringify(lastExplore, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
