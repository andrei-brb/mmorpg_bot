import { useEffect, useState, useMemo } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { HeroTab } from "./tabs/HeroTab";
import { CraftingTab } from "./tabs/CraftingTab";
import { ExploreTab } from "./tabs/ExploreTab";
import { QuestsTab } from "./tabs/QuestsTab";
import { CombatTab } from "./tabs/CombatTab";
import { GuildTab } from "./tabs/GuildTab";
import { MarketTab } from "./tabs/MarketTab";
import { RealmTab } from "./tabs/RealmTab";
import { BattlePassTab } from "./tabs/BattlePassTab";
import { PvpPage } from "@/components/pvp/PvpPage";
import { specIconUrl } from "@/lib/classAndSpecIconUrl";
import { QuestOfferModal } from "./modals/QuestOfferModal";
import { QuestCompleteModal } from "./modals/QuestCompleteModal";
import { MailModal } from "./modals/MailModal";
import { CreateCharacterModal } from "./modals/CreateCharacterModal";
import { toast } from "sonner";
import { usePvpApi } from "@/hooks/usePvpApi";
import * as api from "@/lib/gameApi";
import type { CharacterDerivedStatsPayload } from "@/lib/apiTypes";
import { WomPanel } from "@/components/wom/WomUi";

const TABS = ["Hero", "Forge", "Explore", "Quests", "Combat", "Guild", "Market", "Arena", "Pass", "Realm"] as const;
type TabName = (typeof TABS)[number];

const TAB_ICONS: Record<TabName, string> = {
  Hero: "⚔️",
  Forge: "🔨",
  Explore: "🗺️",
  Quests: "📜",
  Combat: "💀",
  Guild: "🏰",
  Market: "🏪",
  Arena: "🏟️",
  Pass: "🎫",
  Realm: "🌐",
};

export function GameShell() {
  const [activeTab, setActiveTab] = useState<TabName>("Hero");
  const [profileOpen, setProfileOpen] = useState(false);
  const [derivedStats, setDerivedStats] = useState<CharacterDerivedStatsPayload | null>(null);
  // playerStats will be derived after we get the session values from useGameSession()
  const {
    accessToken,
    guildId,
    displayName,
    liveEvents,
    combatFocusActive,
    arenaFocusActive,
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
    lostDeliveries,
    clearLostDeliveries,
  } = useGameSession();

  const { status: pvpStatus } = usePvpApi();

  /** Hide main shell chrome (header + tab bar) during overworld combat focus or active Arena match. */
  const shellChromeHidden = combatFocusActive || arenaFocusActive;

  // Allow child tabs (quests, etc.) to request a tab switch without threading `setActiveTab` through context.
  useEffect(() => {
    const onSetTab = (ev: Event) => {
      const tab = (ev as CustomEvent).detail;
      if (typeof tab !== "string") return;
      const norm =
        tab === "Progress" || tab === "progress" || tab === "realm" ? "Realm" : tab;
      if ((TABS as readonly string[]).includes(norm)) setActiveTab(norm as TabName);
    };
    window.addEventListener("game:setActiveTab", onSetTab);
    return () => window.removeEventListener("game:setActiveTab", onSetTab);
  }, []);

  // Refetch derived stats when equipped gear changes (so profile updates immediately after equip/unequip).
  const derivedStatsKey = useMemo(() => {
    const items = inventory?.items || [];
    const eq = items
      .filter((it) => Boolean(it.is_equipped && it.equip_slot))
      .map((it) => `${it.equip_slot}:${it.template_id || it.id}:${Number(it.enhancement_level ?? 0)}`)
      .sort()
      .join("|");
    const lvl = inventory?.character?.level ?? 0;
    return `${lvl}|${eq}`;
  }, [inventory?.character?.level, inventory?.items]);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void api
      .getCharacterDerivedStats(accessToken, guildId)
      .then((j) => {
        if (cancelled) return;
        setDerivedStats(j.ok ? j : null);
      })
      .catch(() => {
        if (cancelled) return;
        setDerivedStats(null);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId, derivedStatsKey]);

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

    const atk = derivedStats ? `${derivedStats.dmg_min}–${derivedStats.dmg_max}` : "—";
    const def = derivedStats ? String(derivedStats.armor) : "—";
    const crit = derivedStats ? `${derivedStats.crit_chance.toFixed(1)}%` : "—";
    const mastery = derivedStats?.class_mastery?.level ? `Lv ${derivedStats.class_mastery.level}` : "—";

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
      mastery,
      xp,
      guild,
      border,
    };
  }, [inventory, displayName, pvpStatus, derivedStats]);

  const [specSel, setSpecSel] = useState("");
  const [questBusy, setQuestBusy] = useState(false);
  const [mailOpen, setMailOpen] = useState(false);

  const pendingMailFailures = useMemo(() => {
    const raw = questCompletion?.rewards?.item_failures ?? [];
    return raw
      .filter((x) => x?.template_id)
      .map((x) => ({ template_id: String(x.template_id), reason: x.reason }));
  }, [questCompletion]);

  const mailBadgeActive = lostDeliveries.length > 0 || pendingMailFailures.length > 0;
  useEffect(() => {
    if (specModal.options[0]?.key) setSpecSel(specModal.options[0].key);
  }, [specModal.open, specModal.options]);

  if (!inventory) {
    return (
      <div className="app-bg min-h-[100dvh] flex items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)] font-body">Loading…</p>
      </div>
    );
  }

  if (!inventory.character) {
    return (
      <div className="app-bg min-h-[100dvh] flex flex-col">
        <CreateCharacterModal
          createCharacter={createCharacter}
          onCreated={() => toast.success("Welcome to World of Discord!")}
        />
      </div>
    );
  }

  return (
    <div className="app-bg min-h-[100dvh] flex flex-col text-foreground">
      <MailModal
        open={mailOpen}
        onOpenChange={setMailOpen}
        lostDeliveries={lostDeliveries}
        pendingFromActiveQuest={pendingMailFailures}
        onDismissNotice={() => {
          clearLostDeliveries();
          setMailOpen(false);
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
          playerAvatarUrl={inventory.discord?.avatar_url ?? null}
          playerName={inventory.character?.name ?? displayName ?? null}
          playerClass={inventory.character?.class ?? null}
          onClose={() => {
            if (questBusy) return;
            // Closing doesn't auto-decline; user can come back via NPC again if needed.
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
      {/* Specialization gate modal (from API) */}
      {specModal.open && specModal.options.length > 0 && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          style={{ background: "hsl(0 0% 0% / 0.75)", backdropFilter: "blur(4px)" }}
          role="dialog"
          aria-modal="true"
          aria-label="Choose specialization"
        >
          <WomPanel glow className="w-full max-w-lg max-h-[90vh] overflow-y-auto">
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
          </WomPanel>
        </div>
      )}

      <div
        className={`mx-auto w-full max-w-[min(100%,1400px)] px-3 sm:px-4 flex-1 min-h-0 flex flex-col ${
          shellChromeHidden ? "py-2 sm:py-3" : "py-3 sm:py-4"
        }`}
      >
        <div
          className={`game-frame rounded-sm flex flex-col flex-1 min-h-0 ${
            shellChromeHidden ? "p-2 sm:p-3" : "p-3 sm:p-4"
          }`}
        >
          <div
            className={`w-full h-8 -mt-4 sm:-mt-5 rounded-t-sm overflow-hidden opacity-40 ${
              shellChromeHidden ? "mb-2" : "mb-4"
            }`}
            style={{
              backgroundImage: `url('${import.meta.env.BASE_URL}textures/frame-border.jpg')`,
              backgroundSize: '512px 64px',
              backgroundRepeat: 'repeat-x',
              backgroundPosition: "center",
            }}
          />

          <div className="game-frame-inner flex flex-col flex-1 min-h-0">
            <div className="crest-motif" />
            <div className="rune-band-left hidden sm:block" />
            <div className="rune-band-right hidden sm:block" />

            {!shellChromeHidden && liveEvents.length > 0 && (
              <div
                className="mb-3 p-3 rounded-sm text-xs"
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

            {!shellChromeHidden && (
              <div className="flex items-stretch gap-2 mb-3 min-h-0">
                <div className="tab-bar rounded-sm flex-1 min-w-0 flex overflow-x-auto">
                  {TABS.map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`tab-btn ${activeTab === tab ? "tab-btn-active tab-active-glow" : ""}`}
                    >
                      <span className="mr-1.5">{TAB_ICONS[tab]}</span>
                      <span className="hidden sm:inline">{tab}</span>
                    </button>
                  ))}
                </div>
                <div className="flex shrink-0 items-center gap-1.5 pl-1 border-l border-border/60 self-center py-1">
                  <div
                    className="flex items-center gap-1.5 px-2 py-1 rounded-sm text-[10px] font-medium text-muted-foreground"
                    title="Connected to game server"
                    style={{
                      background: "linear-gradient(180deg, hsl(228 18% 14%) 0%, hsl(228 20% 10%) 100%)",
                      border: "1px solid hsl(228 16% 20%)",
                    }}
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-full bg-connected animate-pulse-glow shrink-0"
                      style={{ boxShadow: "0 0 4px hsl(140 55% 42% / 0.5)" }}
                    />
                    <span className="hidden sm:inline">Live</span>
                  </div>
                  <button
                    type="button"
                    className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-sm transition-transform hover:scale-[1.03] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                    style={{
                      background: "linear-gradient(180deg, hsl(228 18% 18%) 0%, hsl(228 22% 10%) 100%)",
                      border: "1px solid hsl(228 16% 28%)",
                      boxShadow: "0 2px 8px hsl(0 0% 0% / 0.35), inset 0 1px 0 hsl(228 14% 30% / 0.35)",
                    }}
                    aria-label={mailBadgeActive ? "Mailbox, undelivered rewards" : "Mailbox"}
                    onClick={() => setMailOpen(true)}
                  >
                    <span className="text-[1.15rem] leading-none select-none" aria-hidden>
                      ✉️
                    </span>
                    {mailBadgeActive ? (
                      <span
                        className="absolute right-0 top-0 h-2 w-2 rounded-full bg-red-500 ring-2 ring-[hsl(228_22%_10%)]"
                        aria-hidden
                      />
                    ) : null}
                  </button>
                  <button
                    type="button"
                    onClick={() => setProfileOpen(true)}
                    className="relative group cursor-pointer shrink-0 rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                    aria-label="Open profile"
                  >
                    <div
                      className="absolute -inset-[2px] rounded-full opacity-60 group-hover:opacity-100 transition-opacity pointer-events-none"
                      style={{
                        background: "conic-gradient(from 0deg, hsl(43 78% 50%), hsl(35 80% 38%), hsl(43 78% 50%))",
                      }}
                    />
                    <div className="relative w-9 h-9 rounded-full overflow-hidden border-2 border-background">
                      <Avatar className="w-full h-full">
                        {inventory?.discord?.avatar_url ? (
                          <AvatarImage src={String(inventory.discord.avatar_url)} alt={displayName || "Avatar"} />
                        ) : (
                          <AvatarFallback className="text-[10px]">{(displayName || "Adventurer").slice(0, 2).toUpperCase()}</AvatarFallback>
                        )}
                      </Avatar>
                    </div>
                  </button>
                </div>
              </div>
            )}

            <div
              className={
                shellChromeHidden
                  ? "sm:px-1 flex flex-col flex-1 min-h-0 -mt-1"
                  : "sm:px-1 flex flex-col flex-1 min-h-0"
              }
            >
              <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
                {activeTab === "Hero" && <HeroTab />}
                {activeTab === "Forge" && <CraftingTab />}
                {activeTab === "Explore" && <ExploreTab />}
                {activeTab === "Quests" && <QuestsTab />}
                {activeTab === "Combat" && <CombatTab focusMode={combatFocusActive} />}
                {activeTab === "Guild" && <GuildTab />}
                {activeTab === "Market" && <MarketTab />}
                {activeTab === "Arena" && <PvpPage />}
                {activeTab === "Pass" && <BattlePassTab />}
                {activeTab === "Realm" && <RealmTab />}
              </div>
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
                { label: "Mastery", value: playerStats.mastery },
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
