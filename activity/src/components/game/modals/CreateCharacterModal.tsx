import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ClassOptionRow } from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";

type Props = {
  onCreated: () => void;
  createCharacter: (name: string, classKey: string) => Promise<{ ok: boolean; message?: string }>;
};

export function CreateCharacterModal({ onCreated, createCharacter }: Props) {
  const [classes, setClasses] = useState<ClassOptionRow[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [classKey, setClassKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitErr, setSubmitErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const j = await api.getCharacterClassOptions();
        if (!cancelled) setClasses(j.classes || []);
      } catch (e) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const nameOk = name.trim().length >= 3 && name.trim().length <= 32;
  const canSubmit = nameOk && classKey && !busy && classes.length > 0;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!classKey || !canSubmit) return;
    setBusy(true);
    setSubmitErr(null);
    const r = await createCharacter(name.trim(), classKey);
    setBusy(false);
    if (r.ok) onCreated();
    else setSubmitErr(r.message || "Could not create character.");
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ background: "hsl(0 0% 0% / 0.75)", backdropFilter: "blur(4px)" }}
      role="dialog"
      aria-modal="true"
      aria-label="Create character"
    >
      <div className="game-panel w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="game-panel-header">Create your hero</div>
        <p className="text-xs text-muted-foreground mb-4">
          New players can choose a name and class here. You can still use `/character create` in Discord if you prefer.
        </p>

        {loadErr && (
          <p className="text-sm text-destructive mb-3" role="alert">
            {loadErr}
          </p>
        )}

        <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Character name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="3–32 characters"
              maxLength={32}
              autoComplete="off"
              className="font-crimson"
            />
          </div>

          <div>
            <div className="text-xs font-medium text-muted-foreground mb-2">Class</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {classes.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => setClassKey(c.key)}
                  className={`text-left rounded-sm border p-3 transition-colors min-h-[44px] ${
                    classKey === c.key
                      ? "border-primary bg-primary/10"
                      : "border-border hover:bg-muted/30"
                  }`}
                >
                  <div className="font-cinzel text-sm">
                    <span className="mr-1">{c.emoji}</span>
                    {c.name}
                    <span className="text-[10px] text-muted-foreground ml-1">({c.role})</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-1 line-clamp-2">{c.description}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Resource: {c.resource}</p>
                </button>
              ))}
            </div>
          </div>

          {submitErr && (
            <p className="text-sm text-destructive" role="alert">
              {submitErr.replace(/\*\*/g, "")}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="submit" disabled={!canSubmit}>
              {busy ? "Creating…" : "Begin adventure"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
