import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";
import { DiscordSDK } from "@discord/embedded-app-sdk";
import type {
  CombatEnemy,
  CombatStatePayload,
  ExploreMapPayload,
  ExploreResultPayload,
  InventoryPayload,
  LiveEventRow,
  MarketListingRow,
  NpcInteractPayload,
  ProgressPayload,
  QuestCompletionPayload,
  QuestOfferPayload,
  QuestLogPayload,
  SpecGatePayload,
  SpecOption,
} from "@/lib/apiTypes";
import type { StartCombatParams } from "@/lib/gameApi";
import * as api from "@/lib/gameApi";

type Phase = "boot" | "loading" | "ready" | "error" | "no_client";

type GameSessionValue = {
  phase: Phase;
  errorHtml?: string;
  accessToken: string | null;
  guildId?: string;
  channelId?: string;
  inventory: InventoryPayload | null;
  map: ExploreMapPayload | null;
  lastExplore: ExploreResultPayload | null;
  progress: ProgressPayload | null;
  quests: QuestLogPayload | null;
  liveEvents: LiveEventRow[];
  refreshLiveEvents: () => Promise<void>;
  /** UI-only: when true, shell switches to combat focus layout (hide tabs, fit in viewport). */
  combatFocusActive: boolean;
  setCombatFocusActive: (active: boolean) => void;
  specModal: { open: boolean; options: SpecOption[]; unlockLevel: number };
  closeSpecModal: () => void;
  chooseSpecialization: (specKey: string) => Promise<void>;
  refreshInventory: () => Promise<void>;
  refreshMap: () => Promise<void>;
  refreshProgress: () => Promise<void>;
  refreshQuests: () => Promise<void>;
  /** Create first character (Activity); same rules as `/character create` in Discord. */
  createCharacter: (name: string, classKey: string) => Promise<{ ok: boolean; message?: string }>;
  travel: (zoneKey: string) => Promise<{ ok: boolean; message?: string }>;
  explore: () => Promise<ExploreResultPayload>;
  /** After explore encounter — Combat tab consumes to auto-start. */
  pendingCombatEnemyKey: React.MutableRefObject<string | null>;
  loadCombatSnapshot: () => Promise<{
    active: boolean;
    state?: CombatStatePayload;
    enemies: CombatEnemy[];
  }>;
  startCombat: (
    params: StartCombatParams,
  ) => Promise<{ ok: boolean; state?: CombatStatePayload; message?: string }>;
  combatAction: (body: Record<string, unknown>) => Promise<api.CombatActionJson>;
  rest: () => Promise<{ ok: boolean; message?: string; cooldown_s?: number }>;
  itemPost: (endpoint: string, body: Record<string, unknown>) => Promise<Response>;
  getEnhanceInfo: (itemId: string) => Promise<import("@/lib/apiTypes").EnhanceInfoPayload>;
  postEnhance: (
    itemId: string,
    protection: string | null,
    fragments: number,
  ) => Promise<{ ok?: boolean; message?: string }>;
  buyProtection: (key: string, qty: number) => Promise<{ ok?: boolean; message?: string }>;
  buyShopItem: (templateId: string, qty: number) => Promise<{ ok?: boolean; message?: string }>;
  marketListings: MarketListingRow[];
  refreshMarketListings: () => Promise<void>;
  npcInteract: (npc?: string) => Promise<{ ok: boolean; message?: string; error?: string }>;
  abandonQuest: (questId: string) => Promise<{ ok: boolean; message?: string; error?: string }>;
  questOffer: QuestOfferPayload | null;
  questCompletion: QuestCompletionPayload | null;
  acceptQuestOffer: (questId: string) => Promise<{ ok: boolean; message?: string; error?: string }>;
  declineQuestOffer: (questId: string) => Promise<{ ok: boolean; message?: string; error?: string }>;
  ackQuestCompletion: () => void;
  /** Opens API-driven spec modal when eligible, otherwise explains why (toast). */
  requestSpecChoice: () => Promise<void>;
  displayName: string;
};

const GameSessionContext = createContext<GameSessionValue | null>(null);

function runWithTimeout<T>(p: Promise<T>, ms: number): Promise<T | "timeout"> {
  return new Promise((resolve) => {
    const t = setTimeout(() => resolve("timeout"), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (err) => {
        clearTimeout(t);
        console.error(err);
        resolve("timeout");
      },
    );
  });
}

export function GameSessionProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>("boot");
  const [errorHtml, setErrorHtml] = useState<string | undefined>();
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [guildId, setGuildId] = useState<string | undefined>();
  const [channelId, setChannelId] = useState<string | undefined>();
  const [inventory, setInventory] = useState<InventoryPayload | null>(null);
  const [map, setMap] = useState<ExploreMapPayload | null>(null);
  const [lastExplore, setLastExplore] = useState<ExploreResultPayload | null>(null);
  const [progress, setProgress] = useState<ProgressPayload | null>(null);
  const [quests, setQuests] = useState<QuestLogPayload | null>(null);
  const [questOffer, setQuestOffer] = useState<QuestOfferPayload | null>(null);
  const [questCompletion, setQuestCompletion] = useState<QuestCompletionPayload | null>(null);
  const [queuedOfferAfterCompletion, setQueuedOfferAfterCompletion] = useState<QuestOfferPayload | null>(null);
  const [liveEvents, setLiveEvents] = useState<LiveEventRow[]>([]);
  const [marketListings, setMarketListings] = useState<MarketListingRow[]>([]);
  const [combatFocusActive, setCombatFocusActive] = useState(false);
  const [specModal, setSpecModal] = useState<{
    open: boolean;
    options: SpecOption[];
    unlockLevel: number;
  }>({ open: false, options: [], unlockLevel: 10 });

  const pendingCombatEnemyKey = useRef<string | null>(null);
  const sdkRef = useRef<DiscordSDK | null>(null);

  const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;

  const refreshInventory = useCallback(async () => {
    if (!accessToken) return;
    try {
      const inv = await api.getInventory(accessToken, guildId);
      setInventory(inv);
    } catch (e) {
      console.warn("refreshInventory", e);
    }
  }, [accessToken, guildId]);

  const refreshMap = useCallback(async () => {
    if (!accessToken) return;
    try {
      const m = await api.getMap(accessToken, guildId);
      setMap(m);
    } catch (e) {
      if (String(e).includes("401")) window.location.reload();
      console.warn("refreshMap", e);
    }
  }, [accessToken, guildId]);

  const refreshProgress = useCallback(async () => {
    if (!accessToken) return;
    try {
      const p = await api.getProgress(accessToken, guildId);
      setProgress(p);
      // Keep Hero tab (inventory.character) in sync with level/gold updates that can occur
      // via server-side actions (e.g., XP grants) without forcing a full app refresh.
      const pc = p?.character;
      if (pc && (pc.level != null || pc.gold != null || pc.class != null || pc.specialization != null)) {
        setInventory((inv) => {
          if (!inv || !inv.character) return inv;
          const next = { ...inv, character: { ...inv.character } } as any;
          if (pc.level != null) next.character.level = pc.level;
          if (pc.gold != null) next.character.gold = pc.gold;
          if (pc.class != null) next.character.class = pc.class;
          if (pc.specialization !== undefined) next.character.specialization = pc.specialization;
          if (pc.specialization_name !== undefined) next.character.specialization_name = pc.specialization_name;
          return next;
        });
      }
    } catch (e) {
      console.warn("refreshProgress", e);
    }
  }, [accessToken, guildId]);

  const refreshQuests = useCallback(async () => {
    if (!accessToken) return;
    try {
      const q = await api.getQuests(accessToken, guildId);
      setQuests(q);
    } catch (e) {
      console.warn("refreshQuests", e);
    }
  }, [accessToken, guildId]);

  const refreshLiveEvents = useCallback(async () => {
    if (!accessToken) return;
    try {
      const j = await api.getLiveEvents(accessToken, guildId);
      setLiveEvents(j.events || []);
    } catch (e) {
      console.warn("refreshLiveEvents", e);
    }
  }, [accessToken, guildId]);

  const checkSpecModal = useCallback(async () => {
    if (!accessToken) return;
    try {
      const json = await api.getSpecializations(accessToken, guildId);
      if (json.ok && json.needs_choice && json.options?.length) {
        setSpecModal({
          open: true,
          options: json.options,
          unlockLevel: json.spec_unlock_level ?? 10,
        });
      } else {
        setSpecModal((s) => ({ ...s, open: false }));
      }
    } catch {
      /* ignore */
    }
  }, [accessToken, guildId]);

  const closeSpecModal = useCallback(() => {
    setSpecModal((s) => ({ ...s, open: false }));
  }, []);

  const requestSpecChoice = useCallback(async () => {
    if (!accessToken) return;
    try {
      const json = (await api.getSpecializations(accessToken, guildId)) as SpecGatePayload;
      if (!json.ok) {
        toast.error("Could not load specialization options.");
        return;
      }
      if (json.needs_choice && json.options?.length) {
        setSpecModal({
          open: true,
          options: json.options,
          unlockLevel: json.spec_unlock_level ?? 10,
        });
      } else if (json.specialization) {
        toast.info("You already have a specialization for this character.");
      } else {
        toast.info(`Reach level ${json.spec_unlock_level ?? 10} to choose a specialization.`);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
  }, [accessToken, guildId]);

  const chooseSpecialization = useCallback(
    async (specKey: string) => {
      if (!accessToken) return;
      const res = await api.postSpecialization(accessToken, specKey, guildId);
      const j = (await res.json()) as { ok?: boolean; message?: string; error?: string };
      if (res.ok && j.ok) {
        closeSpecModal();
        toast.success(j.message || "Specialization saved.");
        await refreshInventory();
        await refreshProgress();
      } else {
        toast.error(j.message || j.error || "Could not choose specialization.");
      }
    },
    [accessToken, guildId, closeSpecModal, refreshInventory, refreshProgress],
  );

  const travel = useCallback(
    async (zoneKey: string) => {
      if (!accessToken) return { ok: false, message: "no token" };
      const res = await api.postTravel(accessToken, zoneKey, guildId);
      await refreshInventory();
      await refreshMap();
      return { ok: !res.error, message: res.message };
    },
    [accessToken, guildId, refreshInventory, refreshMap],
  );

  const explore = useCallback(async () => {
    if (!accessToken) return { ok: false, error: "no token" } as ExploreResultPayload;
    const json = await api.postExplore(accessToken, guildId);
    setLastExplore(json);
    pendingCombatEnemyKey.current = null;
    if (json.outcome && "key" in json.outcome && typeof json.outcome.key === "string") {
      pendingCombatEnemyKey.current = json.outcome.key;
    }
    await refreshInventory();
    await refreshMap();
    return json;
  }, [accessToken, guildId, refreshInventory, refreshMap]);

  const loadCombatSnapshot = useCallback(async () => {
    if (!accessToken) return { active: false, enemies: [] as CombatEnemy[] };
    const [stRes, enRes] = await Promise.all([
      api.getCombatState(accessToken, guildId),
      api.getCombatEnemies(accessToken, guildId),
    ]);
    const stJson = await api.parseCombatState(stRes);
    const enJson = (await enRes.json()) as { enemies?: CombatEnemy[] };
    return {
      active: Boolean(stJson.active && stJson.state),
      state: stJson.state,
      enemies: enJson.enemies || [],
    };
  }, [accessToken, guildId]);

  const startCombat = useCallback(
    async (params: StartCombatParams) => {
      if (!accessToken) return { ok: false, message: "no token" };
      const startRes = await api.postCombatStart(accessToken, guildId, params);
      const startJson = (await startRes.json()) as {
        ok?: boolean;
        error?: string;
        message?: string;
        state?: CombatStatePayload;
      };
      if ((startRes.status === 200 || startRes.status === 409) && startJson.state) {
        return { ok: true, state: startJson.state };
      }
      return { ok: false, message: startJson.message || startJson.error };
    },
    [accessToken, guildId],
  );

  const combatAction = useCallback(
    async (body: Record<string, unknown>) => {
      if (!accessToken) return {};
      const res = await api.postCombatAction(accessToken, body, guildId);
      return (await res.json()) as api.CombatActionJson;
    },
    [accessToken, guildId],
  );

  const rest = useCallback(async () => {
    if (!accessToken) return { ok: false, message: "no token" };
    const res = await api.postRest(accessToken, guildId);
    const json = (await res.json()) as { ok?: boolean; error?: string; message?: string; cooldown_s?: number };
    if (res.status === 429 && json.error === "cooldown") {
      return { ok: false, message: json.message, cooldown_s: json.cooldown_s };
    }
    await refreshInventory();
    await refreshProgress();
    return { ok: Boolean(json.ok), message: json.message };
  }, [accessToken, guildId, refreshInventory, refreshProgress]);

  const itemPost = useCallback(
    async (endpoint: string, body: Record<string, unknown>) => {
      if (!accessToken) throw new Error("no token");
      return api.postItem(accessToken, endpoint, body, guildId);
    },
    [accessToken, guildId],
  );

  const getEnhanceInfo = useCallback(
    async (itemId: string) => {
      if (!accessToken) throw new Error("no token");
      return api.getEnhanceInfo(accessToken, itemId, guildId);
    },
    [accessToken, guildId],
  );

  const postEnhance = useCallback(
    async (itemId: string, protection: string | null, fragments: number) => {
      if (!accessToken) return { ok: false };
      const res = await api.postEnhance(accessToken, itemId, protection, fragments, guildId);
      const j = (await res.json()) as { ok?: boolean; message?: string };
      await refreshInventory();
      await refreshProgress();
      return j;
    },
    [accessToken, guildId, refreshInventory, refreshProgress],
  );

  const buyProtection = useCallback(
    async (key: string, qty: number) => {
      if (!accessToken) return { ok: false };
      const res = await api.postBuyProtection(accessToken, key, qty, guildId);
      const j = (await res.json()) as { ok?: boolean; message?: string };
      await refreshInventory();
      await refreshProgress();
      return j;
    },
    [accessToken, guildId, refreshInventory, refreshProgress],
  );

  const buyShopItem = useCallback(
    async (templateId: string, qty: number) => {
      if (!accessToken) return { ok: false };
      const res = await api.postShopBuy(accessToken, templateId, qty, guildId);
      const j = (await res.json()) as { ok?: boolean; message?: string };
      await refreshInventory();
      await refreshProgress();
      return j;
    },
    [accessToken, guildId, refreshInventory, refreshProgress],
  );

  const refreshMarketListings = useCallback(async () => {
    if (!accessToken) return;
    try {
      const r = await api.getMarketListings(accessToken, guildId);
      setMarketListings(r.listings || []);
    } catch (e) {
      console.warn("refreshMarketListings", e);
    }
  }, [accessToken, guildId]);

  const npcInteract = useCallback(
    async (npc?: string) => {
      if (!accessToken) return { ok: false, error: "no_token" };
      const res = await api.postNpcInteract(accessToken, npc, guildId);
      let j: NpcInteractPayload = {};
      try {
        j = (await res.json()) as NpcInteractPayload;
      } catch {
        /* ignore */
      }
      if (res.ok && j.ok !== false) {
        if (j.quest_completed) {
          setQuestCompletion({
            npc_id: j.npc_id,
            quest_completed: true,
            message: j.message,
            rewards: j.rewards,
          });
          if (j.offer) setQueuedOfferAfterCompletion(j.offer);
        } else if (j.offer) {
          setQuestOffer(j.offer);
        }
      }
      await refreshInventory();
      await refreshProgress();
      await refreshQuests();
      const ok = res.ok && j.ok !== false;
      return { ok, message: j.message, error: j.error };
    },
    [accessToken, guildId, refreshInventory, refreshProgress, refreshQuests],
  );

  const ackQuestCompletion = useCallback(() => {
    setQuestCompletion(null);
    if (queuedOfferAfterCompletion) {
      setQuestOffer(queuedOfferAfterCompletion);
      setQueuedOfferAfterCompletion(null);
    }
  }, [queuedOfferAfterCompletion]);

  const acceptQuestOffer = useCallback(
    async (questId: string) => {
      if (!accessToken) return { ok: false, error: "no_token" };
      const res = await api.postQuestAccept(accessToken, questId, guildId);
      let j: { ok?: boolean; message?: string; error?: string } = {};
      try {
        j = (await res.json()) as typeof j;
      } catch {
        /* ignore */
      }
      await refreshQuests();
      setQuestOffer(null);
      const ok = res.ok && j.ok !== false;
      return { ok, message: j.message, error: j.error };
    },
    [accessToken, guildId, refreshQuests],
  );

  const declineQuestOffer = useCallback(
    async (questId: string) => {
      if (!accessToken) return { ok: false, error: "no_token" };
      const res = await api.postQuestDecline(accessToken, questId, guildId);
      let j: { ok?: boolean; message?: string; error?: string } = {};
      try {
        j = (await res.json()) as typeof j;
      } catch {
        /* ignore */
      }
      await refreshQuests();
      setQuestOffer(null);
      const ok = res.ok && j.ok !== false;
      return { ok, message: j.message, error: j.error };
    },
    [accessToken, guildId, refreshQuests],
  );

  const abandonQuest = useCallback(
    async (questId: string) => {
      if (!accessToken) return { ok: false, error: "no_token" };
      const res = await api.postQuestAbandon(accessToken, questId, guildId);
      let j: { ok?: boolean; message?: string; error?: string } = {};
      try {
        j = (await res.json()) as typeof j;
      } catch {
        /* ignore */
      }
      await refreshQuests();
      const ok = res.ok && j.ok !== false;
      return { ok, message: j.message, error: j.error };
    },
    [accessToken, guildId, refreshQuests],
  );

  const createCharacter = useCallback(
    async (name: string, classKey: string) => {
      if (!accessToken) return { ok: false, message: "Not signed in" };
      const j = await api.postCharacterCreate(accessToken, name, classKey, guildId);
      if (!j.ok || !j.character) {
        return { ok: false, message: j.message || j.error || "Could not create character." };
      }
      setInventory(j);
      await Promise.all([refreshMap(), refreshProgress(), refreshQuests(), refreshLiveEvents()]);
      return { ok: true };
    },
    [accessToken, guildId, refreshMap, refreshProgress, refreshQuests, refreshLiveEvents],
  );

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      if (!clientId) {
        setPhase("no_client");
        setErrorHtml(
          "Missing <code>VITE_DISCORD_CLIENT_ID</code>. Copy <code>activity/.env.example</code> to <code>activity/.env</code>.",
        );
        return;
      }
      setPhase("loading");
      const sdk = new DiscordSDK(clientId);
      sdkRef.current = sdk;

      const raced = await runWithTimeout(sdk.ready(), 12000);
      if (cancelled) return;
      if (raced === "timeout") {
        setPhase("error");
        setErrorHtml(
          "Could not connect to Discord. Open this app <strong>inside Discord</strong> as an Activity, or use dev proxy + ngrok.",
        );
        return;
      }

      let code: string;
      try {
        const auth = await sdk.commands.authorize({
          client_id: clientId,
          response_type: "code",
          state: "",
          prompt: "none",
          scope: ["identify", "applications.commands"],
        });
        code = auth.code;
      } catch (e) {
        console.error(e);
        setPhase("error");
        setErrorHtml("Authorization was cancelled or failed.");
        return;
      }

      try {
        const token = await api.exchangeToken(code);
        if (cancelled) return;
        try {
          await sdk.commands.authenticate({ access_token: token });
        } catch (e) {
          console.warn("authenticate", e);
        }
        setAccessToken(token);
        setGuildId(sdk.guildId ?? undefined);
        setChannelId(sdk.channelId ?? undefined);

        const inv = await api.getInventory(token, sdk.guildId ?? undefined);
        if (cancelled) return;
        setInventory(inv);
        setPhase("ready");
      } catch (e) {
        setPhase("error");
        const detail =
          e instanceof Error ? api.describeFetchError(e, api.apiUrl("/api/token")) : String(e);
        setErrorHtml(
          `Sign-in failed: ${detail} If you see HTTP status errors, confirm DISCORD_CLIENT_SECRET on Railway and OAuth redirect URLs in the Developer Portal.`,
        );
      }
    }
    void boot();
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  useEffect(() => {
    if (phase !== "ready" || !accessToken) return;
    const t = window.setTimeout(() => void checkSpecModal(), 400);
    return () => window.clearTimeout(t);
  }, [phase, accessToken, inventory?.character?.level, checkSpecModal]);

  useEffect(() => {
    if (phase !== "ready" || !accessToken) return;
    void refreshLiveEvents();
  }, [phase, accessToken, refreshLiveEvents]);

  useEffect(() => {
    if (phase !== "ready" || !accessToken) return;
    void refreshProgress();
  }, [phase, accessToken, refreshProgress]);

  const displayName = useMemo(() => {
    const d = inventory?.discord;
    const gn = d?.global_name || d?.username;
    return gn || inventory?.character?.name || "Adventurer";
  }, [inventory]);

  const value = useMemo<GameSessionValue>(
    () => ({
      phase,
      errorHtml,
      accessToken,
      guildId,
      channelId,
      inventory,
      map,
      lastExplore,
      progress,
      quests,
      liveEvents,
      refreshLiveEvents,
      combatFocusActive,
      setCombatFocusActive,
      specModal,
      closeSpecModal,
      chooseSpecialization,
      refreshInventory,
      refreshMap,
      refreshProgress,
      refreshQuests,
      createCharacter,
      travel,
      explore,
      pendingCombatEnemyKey,
      loadCombatSnapshot,
      startCombat,
      combatAction,
      rest,
      itemPost,
      getEnhanceInfo,
      postEnhance,
      buyProtection,
      buyShopItem,
      marketListings,
      refreshMarketListings,
      npcInteract,
      abandonQuest,
      questOffer,
      questCompletion,
      acceptQuestOffer,
      declineQuestOffer,
      ackQuestCompletion,
      requestSpecChoice,
      displayName,
    }),
    [
      phase,
      errorHtml,
      accessToken,
      guildId,
      channelId,
      inventory,
      map,
      lastExplore,
      progress,
      quests,
      liveEvents,
      refreshLiveEvents,
      combatFocusActive,
      setCombatFocusActive,
      specModal,
      closeSpecModal,
      chooseSpecialization,
      refreshInventory,
      refreshMap,
      refreshProgress,
      refreshQuests,
      createCharacter,
      travel,
      explore,
      loadCombatSnapshot,
      startCombat,
      combatAction,
      rest,
      itemPost,
      getEnhanceInfo,
      postEnhance,
      buyProtection,
      buyShopItem,
      marketListings,
      refreshMarketListings,
      npcInteract,
      abandonQuest,
      questOffer,
      questCompletion,
      acceptQuestOffer,
      declineQuestOffer,
      ackQuestCompletion,
      requestSpecChoice,
      displayName,
    ],
  );

  return <GameSessionContext.Provider value={value}>{children}</GameSessionContext.Provider>;
}

export function useGameSession(): GameSessionValue {
  const v = useContext(GameSessionContext);
  if (!v) throw new Error("useGameSession outside GameSessionProvider");
  return v;
}
