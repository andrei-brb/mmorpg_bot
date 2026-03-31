import { useEffect, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { Button } from "@/components/ui/button";
import { HeroTab } from "./tabs/HeroTab";
import { ExploreTab } from "./tabs/ExploreTab";
import { QuestsTab } from "./tabs/QuestsTab";
import { CombatTab } from "./tabs/CombatTab";
import { ProgressTab } from "./tabs/ProgressTab";
import { PvpPage } from "@/components/pvp/PvpPage";
import { specIconUrl } from "@/lib/classAndSpecIconUrl";
import { QuestOfferModal } from "./modals/QuestOfferModal";
import { QuestCompleteModal } from "./modals/QuestCompleteModal";
import { CreateCharacterModal } from "./modals/CreateCharacterModal";
import { toast } from "sonner";

const TABS = ["Hero", "Explore", "Quests", "Combat", "Arena", "Progress"] as const;
type TabName = (typeof TABS)[number];

const TAB_ICONS: Record<TabName, string> = {
  Hero: "⚔️",
  Explore: "🗺️",
  Quests: "📜",
  Combat: "💀",
  Arena: "🏟️",
  Progress: "📊",
};

export function GameShell() {
  const [activeTab, setActiveTab] = useState<TabName>("Hero");
  const {
    displayName,
    liveEvents,
    combatFocusActive,
    specModal,
    closeSpecModal,
    chooseSpecialization,
    questOffer,
    questCompletion,
    acceptQuestOffer,
    declineQuestOffer,
    ackQuestCompletion,
    inventory,
    createCharacter,
  } = useGameSession();

  const [specSel, setSpecSel] = useState("");
  const [questBusy, setQuestBusy] = useState(false);
  useEffect(() => {
    if (specModal.options[0]?.key) setSpecSel(specModal.options[0].key);
  }, [specModal.open, specModal.options]);

  if (!inventory) {
    return (
      <div className="min-h-[100dvh] bg-background flex items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (!inventory.character) {
    return (
      <div className="min-h-[100dvh] bg-background flex flex-col">
        <CreateCharacterModal
          createCharacter={createCharacter}
          onCreated={() => toast.success("Welcome to World of Discord!")}
        />
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] bg-background flex flex-col">
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
          onClose={() => {
            if (questBusy) return;
            // Closing doesn't auto-decline; user can come back via NPC again if needed.
          }}
          onIgnore={async () => {
            if (!questOffer.quest_id || questBusy) return;
            setQuestBusy(true);
            try {
              const r = await declineQuestOffer(questOffer.quest_id);
              if (r.ok) toast.success(r.message || "Quest ignored.");
              else toast.error(r.message || r.error || "Could not ignore quest.");
            } finally {
              setQuestBusy(false);
            }
          }}
          onAccept={async () => {
            if (!questOffer.quest_id || questBusy) return;
            setQuestBusy(true);
            try {
              const r = await acceptQuestOffer(questOffer.quest_id);
              if (r.ok) toast.success(r.message || "Quest accepted.");
              else toast.error(r.message || r.error || "Could not accept quest.");
            } finally {
              setQuestBusy(false);
            }
          }}
        />
      )}
      {/* Specialization gate modal (from API) */}
      {specModal.open && specModal.options.length > 0 && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          style={{ background: "hsl(0 0% 0% / 0.75)", backdropFilter: "blur(4px)" }}
          role="dialog"
          aria-modal="true"
          aria-label="Choose specialization"
        >
          <div className="game-panel w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="game-panel-header">Choose specialization</div>
            <p className="text-xs text-muted-foreground mb-3">
              Level {specModal.unlockLevel}+ — this choice is permanent.
            </p>
            <div className="space-y-2 mb-4">
              {specModal.options.map((o) => (
                <label
                  key={o.key}
                  className="flex gap-3 p-3 rounded-sm border border-border cursor-pointer hover:bg-muted/30"
                >
                  <input type="radio" name="spec" value={o.key} checked={specSel === o.key} onChange={() => setSpecSel(o.key)} />
                  <div>
                    <div className="font-cinzel text-sm">
                      <span className="inline-flex items-center gap-2">
                        {specIconUrl(o.key) && (
                          <img
                            src={specIconUrl(o.key)}
                            alt=""
                            width={18}
                            height={18}
                            className="w-[18px] h-[18px] object-contain shrink-0 rounded-[2px]"
                            style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.35))" }}
                          />
                        )}
                        <span>{o.emoji} {o.name}</span>
                      </span>{" "}
                      <span className="text-[10px] text-muted-foreground">({o.role})</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{o.description}</p>
                    <p className="text-xs mt-1">
                      <strong>{o.passive_name}</strong> — {o.passive_desc}
                    </p>
                  </div>
                </label>
              ))}
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" size="sm" type="button" onClick={closeSpecModal}>Later</Button>
              <Button size="sm" type="button" onClick={() => specSel && void chooseSpecialization(specSel)}>Confirm</Button>
            </div>
          </div>
        </div>
      )}

      <div className="mx-auto w-full max-w-[980px] px-5 py-6 flex-1 min-h-0 flex flex-col">
        <div className="game-frame rounded-sm p-4 sm:p-5 flex flex-col flex-1 min-h-0">
          <div className="w-full h-8 -mt-4 sm:-mt-5 mb-4 rounded-t-sm overflow-hidden opacity-40"
            style={{
              backgroundImage: `url('${import.meta.env.BASE_URL}textures/frame-border.jpg')`,
              backgroundSize: '512px 64px',
              backgroundRepeat: 'repeat-x',
              backgroundPosition: 'center',
            }} />

          <div className="game-frame-inner flex flex-col flex-1 min-h-0">
            <div className="crest-motif" />
            <div className="rune-band-left hidden sm:block" />
            <div className="rune-band-right hidden sm:block" />

            <div className="flex items-center justify-between mb-5 pt-1">
              <div>
                <h1 className="font-cinzel text-xl sm:text-2xl font-bold text-primary tracking-wide"
                  style={{ textShadow: '0 0 12px hsl(43 78% 50% / 0.3), 0 2px 4px hsl(0 0% 0% / 0.5)' }}>
                  World of Discord
                </h1>
                <p className="text-sm text-muted-foreground font-crimson mt-0.5">
                  Welcome, <span className="text-foreground font-semibold">{displayName}</span>
                </p>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-medium"
                style={{
                  background: 'linear-gradient(180deg, hsl(228 18% 14%) 0%, hsl(228 20% 10%) 100%)',
                  border: '1px solid hsl(228 16% 20%)',
                  boxShadow: 'inset 0 1px 0 hsl(228 14% 22% / 0.4), 0 2px 4px hsl(0 0% 0% / 0.3)',
                }}>
                <span className="w-2 h-2 rounded-full bg-connected animate-pulse-glow"
                  style={{ boxShadow: '0 0 6px hsl(140 55% 42% / 0.5)' }} />
                <span className="text-foreground">Connected</span>
              </div>
            </div>

            <div className="ornament-divider mb-4" />

            {!combatFocusActive && liveEvents.length > 0 && (
              <div
                className="mb-4 p-3 rounded-sm text-xs"
                style={{
                  background: "linear-gradient(180deg, hsl(43 40% 12% / 0.35) 0%, hsl(228 20% 10% / 0.5) 100%)",
                  border: "1px solid hsl(43 50% 35% / 0.35)",
                }}
              >
                <div className="font-cinzel font-semibold text-primary mb-2">Guild live events</div>
                <ul className="space-y-2">
                  {liveEvents.map((ev) => (
                    <li key={ev.slug || ev.title || String(ev.ends_at)}>
                      <span className="font-semibold text-foreground">{ev.title || ev.slug || "Event"}</span>
                      {ev.description && (
                        <span className="text-muted-foreground"> — {ev.description}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {!combatFocusActive && (
              <div className="tab-bar rounded-sm mb-5 flex overflow-x-auto">
                {TABS.map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`tab-btn ${activeTab === tab ? "tab-btn-active" : ""}`}
                  >
                    <span className="mr-1.5">{TAB_ICONS[tab]}</span>
                    <span className="hidden sm:inline">{tab}</span>
                  </button>
                ))}
              </div>
            )}

            <div className={combatFocusActive ? "sm:px-1 flex flex-col flex-1 min-h-0" : "sm:px-1"}>
              {activeTab === "Hero" && <HeroTab />}
              {activeTab === "Explore" && <ExploreTab />}
              {activeTab === "Quests" && <QuestsTab />}
              {activeTab === "Combat" && <CombatTab focusMode={combatFocusActive} />}
              {activeTab === "Arena" && <PvpPage />}
              {activeTab === "Progress" && <ProgressTab />}
            </div>
          </div>

          <div className="w-full h-8 -mb-4 sm:-mb-5 mt-4 rounded-b-sm overflow-hidden opacity-40"
            style={{
              backgroundImage: `url('${import.meta.env.BASE_URL}textures/frame-border.jpg')`,
              backgroundSize: '512px 64px',
              backgroundRepeat: 'repeat-x',
              backgroundPosition: 'center',
              transform: 'scaleY(-1)',
            }} />
        </div>
      </div>
    </div>
  );
}
