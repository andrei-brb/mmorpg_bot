import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { Button } from "@/components/ui/button";
import { WomPanel } from "@/components/wom/WomUi";
import { specIconUrl } from "@/lib/classAndSpecIconUrl";
import { CreateCharacterModal } from "@/components/game/modals/CreateCharacterModal";
import { MailModal } from "@/components/game/modals/MailModal";
import { QuestCompleteModal } from "@/components/game/modals/QuestCompleteModal";
import { QuestOfferModal } from "@/components/game/modals/QuestOfferModal";

/**
 * Session-driven modals for the mobile shell.
 *
 * DUPLICATION NOTICE — this mirrors the modal block of
 * activity/src/components/game/GameShell.tsx (roughly lines 145-282). The modal
 * *components* are shared; only this wiring is restated, because GameShell
 * couples the wiring to the desktop frame it also renders, and the mobile shell
 * needs the wiring without the frame.
 *
 * The cost is real: a change to quest/mail/spec handling in GameShell must be
 * made here too, or mobile silently keeps the old behaviour. The alternative is
 * an optional render-prop seam on GameShell (the same additive pattern used for
 * AuthProvider), which would delete this file. Left as-is for now because the
 * brief was to keep the mobile app out of activity/src entirely.
 */

export type ShellModalsProps = {
  mailOpen: boolean;
  onMailOpenChange: (open: boolean) => void;
};

export function ShellModals({ mailOpen, onMailOpenChange }: ShellModalsProps) {
  const {
    displayName,
    inventory,
    createCharacter,
    specModal,
    closeSpecModal,
    chooseSpecialization,
    questOffer,
    questCompletion,
    acceptQuestOffer,
    declineQuestOffer,
    ackQuestCompletion,
    lostDeliveries,
    clearLostDeliveries,
  } = useGameSession();

  const [specSel, setSpecSel] = useState("");
  const [questBusy, setQuestBusy] = useState(false);

  useEffect(() => {
    if (specModal.options[0]?.key) setSpecSel(specModal.options[0].key);
  }, [specModal.open, specModal.options]);

  const pendingMailFailures = useMemo(() => {
    const raw = questCompletion?.rewards?.item_failures ?? [];
    return raw
      .filter((x) => x?.template_id)
      .map((x) => ({ template_id: String(x.template_id), reason: x.reason }));
  }, [questCompletion]);

  if (inventory && !inventory.character) {
    return (
      <CreateCharacterModal
        createCharacter={createCharacter}
        onCreated={() => toast.success("Welcome to World of Discord!")}
      />
    );
  }

  return (
    <>
      <MailModal
        open={mailOpen}
        onOpenChange={onMailOpenChange}
        lostDeliveries={lostDeliveries}
        pendingFromActiveQuest={pendingMailFailures}
        onDismissNotice={() => {
          clearLostDeliveries();
          onMailOpenChange(false);
        }}
      />

      {questCompletion?.quest_completed && (
        <QuestCompleteModal
          completion={questCompletion}
          busy={questBusy}
          onContinue={() => {
            if (questBusy) return;
            ackQuestCompletion();
          }}
        />
      )}

      {questOffer?.quest_id && (
        <QuestOfferModal
          offer={questOffer}
          busy={questBusy}
          playerAvatarUrl={inventory?.discord?.avatar_url ?? null}
          playerName={inventory?.character?.name ?? displayName ?? null}
          playerClass={inventory?.character?.class ?? null}
          onClose={() => {
            // Closing doesn't auto-decline; the NPC can be revisited.
          }}
          onIgnore={async () => {
            if (!questOffer.quest_id || questBusy) return;
            const line = questOffer.dialogue?.decline?.trim();
            setQuestBusy(true);
            try {
              const r = await declineQuestOffer(questOffer.quest_id);
              if (r.ok) {
                toast.success(r.message || "Quest declined.");
                if (line) toast.message(line, { duration: 6500 });
              } else toast.error(r.message || r.error || "Could not decline quest.");
            } finally {
              setQuestBusy(false);
            }
          }}
          onAccept={async () => {
            if (!questOffer.quest_id || questBusy) return;
            const line = questOffer.dialogue?.accept?.trim();
            setQuestBusy(true);
            try {
              const r = await acceptQuestOffer(questOffer.quest_id);
              if (r.ok) {
                toast.success(r.message || "Quest accepted.");
                if (line) toast.message(line, { duration: 6500 });
              } else toast.error(r.message || r.error || "Could not accept quest.");
            } finally {
              setQuestBusy(false);
            }
          }}
        />
      )}

      {specModal.open && specModal.options.length > 0 && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          style={{ background: "hsl(0 0% 0% / 0.75)", backdropFilter: "blur(4px)" }}
          role="dialog"
          aria-modal="true"
          aria-label="Choose specialization"
        >
          <WomPanel glow className="max-h-[85dvh] w-full max-w-lg overflow-y-auto">
            <div className="game-panel-header">Choose specialization</div>
            <p className="mb-3 text-xs text-muted-foreground">
              Level {specModal.unlockLevel}+ — this choice is permanent.
            </p>
            <div className="mb-4 space-y-2">
              {specModal.options.map((o) => (
                <label
                  key={o.key}
                  className="flex cursor-pointer gap-3 rounded-lg border border-border p-3"
                >
                  <input
                    type="radio"
                    name="spec"
                    value={o.key}
                    checked={specSel === o.key}
                    onChange={() => setSpecSel(o.key)}
                  />
                  <div>
                    <div className="font-cinzel text-sm">
                      <span className="inline-flex items-center gap-2">
                        {specIconUrl(o.key) && (
                          <img
                            src={specIconUrl(o.key)}
                            alt=""
                            width={18}
                            height={18}
                            className="h-[18px] w-[18px] shrink-0 rounded-[2px] object-contain"
                            onError={(ev) => {
                              (ev.currentTarget as HTMLImageElement).style.display = "none";
                            }}
                          />
                        )}
                        <span>
                          {o.emoji} {o.name}
                        </span>
                      </span>{" "}
                      <span className="text-[10px] text-muted-foreground">({o.role})</span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{o.description}</p>
                    <p className="mt-1 text-xs">
                      <strong>{o.passive_name}</strong> — {o.passive_desc}
                    </p>
                  </div>
                </label>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" type="button" onClick={closeSpecModal}>
                Later
              </Button>
              <Button size="sm" type="button" onClick={() => specSel && void chooseSpecialization(specSel)}>
                Confirm
              </Button>
            </div>
          </WomPanel>
        </div>
      )}
    </>
  );
}
