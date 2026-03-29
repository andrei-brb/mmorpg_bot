import { useState } from "react";
import { toast } from "sonner";

const SPEC_UNLOCK_LEVEL = 10;

interface Spec {
  key: string;
  name: string;
  icon: string;
  role: string;
  description: string;
  passiveName: string;
  passiveDesc: string;
}

const ROGUE_SPECS: Spec[] = [
  {
    key: "assassination",
    name: "Nightfang",
    icon: "🗡️",
    role: "DPS",
    description: "Masters of lethal poisons and precise strikes. Nightfangs exploit every weakness, dealing devastating damage over time while remaining unseen.",
    passiveName: "Venomweave",
    passiveDesc: "Your critical strikes apply a stacking poison that deals 4% of the target's max HP per tick for 6 seconds.",
  },
  {
    key: "subtlety",
    name: "Shadowdancer",
    icon: "🌑",
    role: "DPS / Utility",
    description: "Elusive tricksters who bend shadow and light. Shadowdancers control the battlefield through misdirection, crowd control, and burst windows.",
    passiveName: "Umbral Step",
    passiveDesc: "After using an evasion ability, your next attack within 4 seconds deals 35% bonus damage and restores 15 MP.",
  },
];

interface SpecializationModalProps {
  playerLevel: number;
  currentSpec: string | null;
  onClose: () => void;
  onChoose: (specKey: string) => void;
}

export function SpecializationModal({ playerLevel, currentSpec, onClose, onChoose }: SpecializationModalProps) {
  const [selected, setSelected] = useState<string | null>(null);

  const eligible = playerLevel >= SPEC_UNLOCK_LEVEL && !currentSpec;

  const handleConfirm = () => {
    if (!selected) return;
    const spec = ROGUE_SPECS.find((s) => s.key === selected);
    toast(`🎉 Specialization Chosen: ${spec?.name}`, {
      description: "This choice is permanent. Your path is set.",
    });
    onChoose(selected);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'hsl(0 0% 0% / 0.7)', backdropFilter: 'blur(4px)' }}>
      <div className="game-panel w-full max-w-[560px]" onClick={(e) => e.stopPropagation()}>
        <div className="game-panel-header">⚔️ Choose Your Specialization</div>

        {!eligible && currentSpec && (
          <div className="text-sm text-foreground mb-4">
            You have already chosen: <span className="text-primary font-cinzel font-semibold">{ROGUE_SPECS.find(s => s.key === currentSpec)?.name ?? currentSpec}</span>
          </div>
        )}

        {eligible && (
          <>
            <p className="text-sm text-foreground mb-1">
              You reached <span className="text-primary font-semibold">level {SPEC_UNLOCK_LEVEL}</span> — pick your path.
            </p>
            <p className="text-xs text-destructive mb-4">
              ⚠️ This choice is <strong>permanent</strong> and cannot be undone.
            </p>

            <div className="ornament-divider mb-4" />

            <div className="space-y-3 mb-4">
              {ROGUE_SPECS.map((spec) => (
                <label
                  key={spec.key}
                  onClick={() => setSelected(spec.key)}
                  className={`block p-4 rounded-sm cursor-pointer transition-all ${selected === spec.key ? 'ring-1' : ''}`}
                  style={{
                    background: selected === spec.key
                      ? 'linear-gradient(180deg, hsl(228 18% 16%) 0%, hsl(228 20% 12%) 100%)'
                      : 'linear-gradient(180deg, hsl(228 18% 12%) 0%, hsl(228 20% 9%) 100%)',
                    border: `1px solid ${selected === spec.key ? 'hsl(43 50% 40%)' : 'hsl(228 16% 20%)'}`,
                    boxShadow: selected === spec.key
                      ? 'inset 0 1px 0 hsl(43 50% 40% / 0.2), 0 0 12px hsl(43 78% 50% / 0.1)'
                      : 'inset 0 1px 0 hsl(228 14% 22% / 0.3), 0 2px 4px hsl(0 0% 0% / 0.3)',
                  }}
                >
                  <input type="radio" name="spec" value={spec.key}
                    checked={selected === spec.key}
                    onChange={() => setSelected(spec.key)}
                    className="hidden" />

                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl" style={{ filter: 'drop-shadow(0 1px 3px hsl(0 0% 0% / 0.5))' }}>
                      {spec.icon}
                    </span>
                    <div>
                      <span className="font-cinzel font-semibold text-foreground text-base">{spec.name}</span>
                      <span className="ml-2 text-[10px] px-2 py-0.5 rounded-sm uppercase font-semibold tracking-wider"
                        style={{
                          background: spec.role === 'DPS' ? 'hsl(0 50% 25% / 0.4)' : 'hsl(268 40% 25% / 0.4)',
                          border: `1px solid ${spec.role === 'DPS' ? 'hsl(0 45% 35% / 0.5)' : 'hsl(268 35% 40% / 0.5)'}`,
                          color: spec.role === 'DPS' ? 'hsl(0 60% 65%)' : 'hsl(268 50% 70%)',
                        }}>
                        {spec.role}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-muted-foreground mb-3 leading-relaxed">{spec.description}</p>

                  <div className="p-2 rounded-sm"
                    style={{
                      background: 'hsl(228 20% 8% / 0.6)',
                      border: '1px solid hsl(228 16% 18%)',
                    }}>
                    <div className="text-[10px] font-cinzel uppercase tracking-wider text-primary mb-0.5">
                      Passive: {spec.passiveName}
                    </div>
                    <div className="text-[11px] text-muted-foreground">{spec.passiveDesc}</div>
                  </div>
                </label>
              ))}
            </div>

            <div className="ornament-divider mb-4" />
          </>
        )}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="game-btn-secondary text-xs">Cancel</button>
          {eligible && (
            <button onClick={handleConfirm} disabled={!selected}
              className={`game-btn-primary text-xs ${!selected ? 'opacity-50 cursor-not-allowed' : ''}`}>
              Confirm
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
