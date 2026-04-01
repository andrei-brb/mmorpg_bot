import { useEffect, useState, useMemo } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { HeroTab } from "./tabs/HeroTab";
import { ExploreTab } from "./tabs/ExploreTab";
import { QuestsTab } from "./tabs/QuestsTab";
import { CombatTab } from "./tabs/CombatTab";
import { ProgressTab } from "./tabs/ProgressTab";
import { MarketTab } from "./tabs/MarketTab";
import { PvpPage } from "@/components/pvp/PvpPage";
import { specIconUrl } from "@/lib/classAndSpecIconUrl";
import { QuestOfferModal } from "./modals/QuestOfferModal";
import { QuestCompleteModal } from "./modals/QuestCompleteModal";
import { CreateCharacterModal } from "./modals/CreateCharacterModal";
import { toast } from "sonner";
import { usePvpApi } from "@/hooks/usePvpApi";

const TABS = ["Hero", "Explore", "Quests", "Combat", "Market", "Arena", "Progress"] as const;
type TabName = (typeof TABS)[number];

const TAB_ICONS: Record<TabName, string> = {
  Hero: "⚔️",
  Explore: "🗺️",
  Quests: "📜",
  Combat: "💀",
  Market: "🏪",
  Arena: "🏟️",
  Progress: "📊",
};

export function GameShell() {
  const [activeTab, setActiveTab] = useState<TabName>("Hero");
  const [profileOpen, setProfileOpen] = useState(false);
  // playerStats will be derived after we get the session values from useGameSession()
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

  const { status: pvpStatus } = usePvpApi();

  // Derive live player stats from the game session / inventory (no random values)
  const playerStats = useMemo(() => {
    const char = inventory?.character || null;
    const items = inventory?.items || [];
    // build equipped map
    const equipped: Record<string, typeof items[number]> = {};
    for (const it of items) {
      if (it.is_equipped && it.equip_slot) equipped[it.equip_slot] = it;
    }

    const hpCur = Number(char?.current_hp ?? 0);
    const hpMax = Number(char?.max_hp ?? 0) || "—";

    // Attack: prefer main hand damage range when available
    const main = equipped["main_hand"];
    const dMin = main ? Number(main.s_dmg_min ?? 0) : 0;
    const dMax = main ? Number(main.s_dmg_max ?? 0) : 0;
    const atk = main ? `${dMin}–${dMax}` : String(
      items.reduce((acc, it) => acc + (Number(it.s_dmg_min ?? 0) + Number(it.s_dmg_max ?? 0)) / 2, 0) | 0,
    );

    // Defense: sum of armor from equipped pieces
    const def = items.reduce((acc, it) => acc + (Number(it.s_armor ?? 0) || 0), 0) | 0;

    // Crit/hit: show hit rating if present
    const hitRating = items.reduce((acc, it) => acc + (Number(it.s_hit_rating ?? 0) || 0), 0) | 0;
    const crit = hitRating ? `${hitRating}%` : "—";

    const xp = "—"; // XP currently not provided by inventory payload
    const guild = "—"; // guild info not available in inventory payload

    const border = pvpStatus?.stats?.rank_tier ?? "—";

    return {
      name: (inventory?.character?.name || displayName || "Adventurer"),
      level: inventory?.character?.level ?? "—",
      class: inventory?.character?.class ?? "—",
      hp: `${hpCur} / ${hpMax}`,
      atk,
      def,
      crit,
      xp,
      guild,
      border,
    };
  }, [inventory, displayName, pvpStatus]);

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
              <div className="flex items-center gap-3">
                <button onClick={() => setProfileOpen(true)} className="relative shrink-0 group cursor-pointer">
                  <div
                    className="absolute -inset-[3px] rounded-full opacity-70 group-hover:opacity-100 transition-opacity"
                    style={{
                      background: 'conic-gradient(from 0deg, hsl(43 78% 50%), hsl(35 80% 38%), hsl(43 78% 50%))',
                    }}
                  />
                  <div className="relative w-10 h-10 sm:w-11 sm:h-11 rounded-full overflow-hidden border-2 border-background">
                    <Avatar className="w-full h-full">
                      {inventory?.discord?.avatar_url ? (
                        <AvatarImage src={String(inventory.discord.avatar_url)} alt={displayName || "Avatar"} />
                      ) : (
                        <AvatarFallback>{(displayName || "Adventurer").slice(0, 2).toUpperCase()}</AvatarFallback>
                      )}
                    </Avatar>
                  </div>
                </button>

                <div>
                  <h1 className="font-cinzel text-xl sm:text-2xl font-bold text-primary tracking-wide"
                    style={{ textShadow: '0 0 12px hsl(43 78% 50% / 0.3), 0 2px 4px hsl(0 0% 0% / 0.5)' }}>
                    World of Discord
                  </h1>
                  <p className="text-sm text-muted-foreground font-crimson mt-0.5">
                    Welcome, <span className="text-foreground font-semibold">{playerStats.name}</span>
                  </p>
                </div>
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
              {activeTab === "Market" && <MarketTab />}
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
      {/* Profile Dialog */}
      <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
        <DialogContent className="sm:max-w-[360px] border-border/60 p-0 overflow-hidden" style={{ background: 'linear-gradient(180deg, hsl(228 18% 12%) 0%, hsl(228 20% 8%) 100%)' }}>
          <DialogTitle className="sr-only">Player Profile</DialogTitle>
          <div className="flex flex-col items-center pt-8 pb-6 px-6">
            <div className="relative mb-4">
              <div className="absolute -inset-[5px] rounded-full" style={{ background: 'conic-gradient(from 0deg, hsl(43 78% 50%), hsl(35 80% 38%), hsl(43 78% 50%), hsl(35 80% 38%), hsl(43 78% 50%))', filter: 'blur(0.5px)' }} />
              <div className="relative w-24 h-24 rounded-full overflow-hidden border-3 border-background">
                <Avatar className="w-full h-full">
                  {inventory?.discord?.avatar_url ? (
                    <AvatarImage src={String(inventory.discord.avatar_url)} alt={displayName || "Avatar"} />
                  ) : (
                    <AvatarFallback>{(displayName || "Adventurer").slice(0, 2).toUpperCase()}</AvatarFallback>
                  )}
                </Avatar>
              </div>
            </div>

            <h2 className="font-cinzel text-lg font-bold text-primary tracking-wide" style={{ textShadow: '0 0 10px hsl(43 78% 50% / 0.3)' }}>{playerStats.name}</h2>
            <p className="text-sm text-muted-foreground font-crimson">Lv. {playerStats.level} {playerStats.class}</p>
            <span className="text-xs text-primary/60 mt-1 font-crimson italic">🏅 {playerStats.border}</span>

            <div className="w-full mt-5 grid grid-cols-2 gap-2">
              {[
                { label: "HP", value: playerStats.hp },
                { label: "ATK", value: playerStats.atk },
                { label: "DEF", value: playerStats.def },
                { label: "CRIT", value: playerStats.crit },
                { label: "XP", value: playerStats.xp },
                { label: "Guild", value: playerStats.guild },
              ].map((s) => (
                <div key={s.label} className="flex justify-between px-3 py-1.5 rounded-sm text-xs" style={{ background: 'hsl(228 16% 14%)', border: '1px solid hsl(228 14% 20%)' }}>
                  <span className="text-muted-foreground">{s.label}</span>
                  <span className="text-foreground font-medium">{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
