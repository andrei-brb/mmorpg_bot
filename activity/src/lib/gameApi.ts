import type {
  CombatStatePayload,
  DungeonCatalogEntry,
  EnhanceInfoPayload,
  ExploreMapPayload,
  ExploreResultPayload,
  InventoryPayload,
  LiveEventRow,
  ProgressPayload,
  QuestLogPayload,
  SpecGatePayload,
} from "./apiTypes";

export function apiUrl(path: string): string {
  const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}

export function publicBaseUrl(): string {
  const b = import.meta.env.BASE_URL || "/";
  return b.endsWith("/") ? b : `${b}/`;
}

export function authHeaders(accessToken: string, guildId?: string): HeadersInit {
  const h: Record<string, string> = { Authorization: `Bearer ${accessToken}` };
  if (guildId) h["X-Guild-Id"] = String(guildId);
  return h;
}

export async function exchangeToken(code: string): Promise<string> {
  const res = await fetch(apiUrl("/api/token"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) throw new Error(`token ${res.status}`);
  const j = (await res.json()) as { access_token?: string };
  if (!j.access_token) throw new Error("no access_token");
  return j.access_token;
}

export async function getInventory(token: string, guildId?: string): Promise<InventoryPayload> {
  const res = await fetch(apiUrl("/api/game/inventory"), { headers: authHeaders(token, guildId) });
  if (!res.ok) throw new Error(`inventory ${res.status}`);
  return res.json() as Promise<InventoryPayload>;
}

export async function getMap(token: string, guildId?: string): Promise<ExploreMapPayload> {
  const res = await fetch(apiUrl("/api/game/map"), { headers: authHeaders(token, guildId) });
  if (res.status === 401) throw new Error("401");
  if (!res.ok) throw new Error(`map ${res.status}`);
  return res.json() as Promise<ExploreMapPayload>;
}

export async function postTravel(
  token: string,
  zoneKey: string,
  guildId?: string,
): Promise<{ ok?: boolean; error?: string; message?: string }> {
  const res = await fetch(apiUrl("/api/game/travel"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ zone_key: zoneKey }),
  });
  return res.json() as Promise<{ ok?: boolean; error?: string; message?: string }>;
}

export async function postExplore(token: string, guildId?: string): Promise<ExploreResultPayload> {
  const res = await fetch(apiUrl("/api/game/explore"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  return res.json() as Promise<ExploreResultPayload>;
}

export async function getCombatState(token: string, guildId?: string) {
  const res = await fetch(apiUrl("/api/game/combat/state"), { headers: authHeaders(token, guildId) });
  return res;
}

export async function getCombatEnemies(token: string, guildId?: string) {
  const res = await fetch(apiUrl("/api/game/combat/enemies"), { headers: authHeaders(token, guildId) });
  return res;
}

/** Overworld: pick an enemy from the current zone. Dungeon tab: server resolves enemy from `config.settings.DUNGEONS`. */
export type StartCombatParams =
  | { kind: "zone"; enemyKey: string }
  | { kind: "dungeon"; dungeonKey: string; floor: number };

export async function postCombatStart(token: string, guildId: string | undefined, params: StartCombatParams) {
  const body =
    params.kind === "zone"
      ? { enemy_key: params.enemyKey }
      : { dungeon_key: params.dungeonKey, floor: params.floor };
  return fetch(apiUrl("/api/game/combat/start"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, guild_id: guildId ? String(guildId) : undefined }),
  });
}

export async function getDungeons(
  token: string,
  guildId?: string,
): Promise<{ ok?: boolean; dungeons?: DungeonCatalogEntry[] }> {
  const res = await fetch(apiUrl("/api/game/dungeons"), { headers: authHeaders(token, guildId) });
  if (!res.ok) throw new Error(`dungeons ${res.status}`);
  return res.json() as Promise<{ ok?: boolean; dungeons?: DungeonCatalogEntry[] }>;
}

export async function postCombatAction(token: string, body: Record<string, unknown>, guildId?: string) {
  return fetch(apiUrl("/api/game/combat/action"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, guild_id: guildId ? String(guildId) : undefined }),
  });
}

export async function postRest(token: string, guildId?: string) {
  return fetch(apiUrl("/api/game/rest"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ guild_id: guildId ? String(guildId) : undefined }),
  });
}

export async function getProgress(token: string, guildId?: string): Promise<ProgressPayload> {
  const res = await fetch(apiUrl("/api/game/progress"), { headers: authHeaders(token, guildId) });
  if (!res.ok) throw new Error(`progress ${res.status}`);
  return res.json() as Promise<ProgressPayload>;
}

export async function getQuests(token: string, guildId?: string): Promise<QuestLogPayload> {
  const res = await fetch(apiUrl("/api/game/quests"), { headers: authHeaders(token, guildId) });
  if (!res.ok) throw new Error(`quests ${res.status}`);
  return res.json() as Promise<QuestLogPayload>;
}

export async function getLiveEvents(
  token: string,
  guildId?: string,
): Promise<{ ok?: boolean; events?: LiveEventRow[] }> {
  const res = await fetch(apiUrl("/api/game/live-events"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<{ ok?: boolean; events?: LiveEventRow[] }>;
}

export async function getSpecializations(token: string, guildId?: string): Promise<SpecGatePayload> {
  const res = await fetch(apiUrl("/api/game/specializations"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<SpecGatePayload>;
}

export async function postSpecialization(token: string, specKey: string, guildId?: string) {
  return fetch(apiUrl("/api/game/character/specialization"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ spec_key: specKey }),
  });
}

export async function postItem(
  token: string,
  endpoint: string,
  body: Record<string, unknown>,
  guildId?: string,
) {
  return fetch(apiUrl(endpoint), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getEnhanceInfo(token: string, itemId: string, guildId?: string): Promise<EnhanceInfoPayload> {
  const res = await fetch(
    apiUrl(`/api/game/item/enhance/info?item_id=${encodeURIComponent(itemId)}`),
    { headers: authHeaders(token, guildId) },
  );
  return res.json() as Promise<EnhanceInfoPayload>;
}

export async function postEnhance(
  token: string,
  itemId: string,
  protectionType: string | null,
  fragmentCount: number,
  guildId?: string,
) {
  return fetch(apiUrl("/api/game/item/enhance"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({
      item_id: itemId,
      protection_type: protectionType || null,
      fragment_count: fragmentCount,
    }),
  });
}

export async function postBuyProtection(token: string, key: string, qty: number, guildId?: string) {
  return fetch(apiUrl("/api/game/blacksmith/buy-protection"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ protection_key: key, quantity: qty }),
  });
}

export async function postNpcInteract(token: string, npc: string | undefined, guildId?: string) {
  return fetch(apiUrl("/api/game/npc/interact"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ npc }),
  });
}

export async function postQuestAbandon(token: string, questId: string, guildId?: string) {
  return fetch(apiUrl("/api/game/quest/abandon"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ quest_id: questId }),
  });
}

export async function postQuestAccept(token: string, questId: string, guildId?: string) {
  return fetch(apiUrl("/api/game/quest/accept"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ quest_id: questId }),
  });
}

export async function postQuestDecline(token: string, questId: string, guildId?: string) {
  return fetch(apiUrl("/api/game/quest/decline"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ quest_id: questId }),
  });
}

export type CombatActionJson = {
  ok?: boolean;
  ended?: boolean;
  state?: CombatStatePayload;
  outcome?: { type?: string; title?: string; lines?: string[] };
  error?: string;
  message?: string;
};

export async function parseCombatState(res: Response): Promise<{
  active?: boolean;
  state?: CombatStatePayload;
}> {
  return res.json() as Promise<{ active?: boolean; state?: CombatStatePayload }>;
}
