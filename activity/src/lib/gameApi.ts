import type {
  ClassOptionRow,
  CombatStatePayload,
  CharacterDerivedStatsPayload,
  DungeonCatalogEntry,
  DungeonParticipant,
  DungeonPartyInvitesResponse,
  DungeonPartyStatus,
  DungeonPartyCreateResponse,
  EnhanceInfoPayload,
  ExploreMapPayload,
  ExploreResultPayload,
  InventoryPayload,
  InvRow,
  LiveEventRow,
  ProgressPayload,
  DeedsPayload,
  IdleRewardsPayload,
  QuestLogPayload,
  SpecGatePayload,
  GuildMePayload,
  GuildInviteCandidate,
  GuildCreateResponse,
  GuildCheckinPayload,
  SocialRosterPayload,
  SocialRequestsPayload,
  SocialPlayersSearchPayload,
  SocialIgnorePayload,
  SocialWhispersPayload,
  SocialSettingsPayload,
  SocialSuggestionsPayload,
  SocialWhisperInboxPayload,
} from "./apiTypes";

function isLocalHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function shouldPreferSameOrigin(base: string, path: string): boolean {
  if (!base || typeof window === "undefined" || !path.startsWith("/api")) return false;
  try {
    const baseUrl = new URL(base);
    const pageUrl = new URL(window.location.origin);
    if (baseUrl.origin === pageUrl.origin) return false;
    if (isLocalHost(pageUrl.hostname)) return false;
    // Discord Activities and Vercel-hosted UI should call same-origin /api and let
    // the host/proxy forward to Railway.
    return pageUrl.hostname.endsWith(".discordsays.com") || pageUrl.hostname.endsWith(".vercel.app");
  } catch {
    return false;
  }
}

export function apiUrl(path: string): string {
  const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  if (shouldPreferSameOrigin(base, p)) return p;
  return `${base}${p}`;
}

/** Clearer errors when fetch fails (e.g. Discord Activity CSP blocks cross-origin API). */
export function describeFetchError(e: unknown, url: string): string {
  const msg = e instanceof Error ? e.message : String(e);
  if (msg === "Failed to fetch" || msg.includes("Load failed") || msg.includes("NetworkError")) {
    return `${msg} (${url}). Inside Discord, requests must go to the same host as the Activity (e.g. Vercel rewrites /api to Railway). See ACTIVITY_SETUP.md — Split UI + API.`;
  }
  return msg;
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

/**
 * Exchange OAuth code from Discord Embedded App SDK.
 * `redirectUri` should be the Activity page origin (e.g. https://123....discordsays.com)
 * so the API can match Developer Portal → OAuth2 → Redirects exactly.
 */
export async function exchangeToken(code: string, redirectUri?: string): Promise<string> {
  const res = await fetch(apiUrl("/api/token"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      ...(redirectUri ? { redirect_uri: redirectUri } : {}),
    }),
  });
  const text = await res.text();
  let j: {
    access_token?: string;
    error?: string;
    detail?: string;
    hint?: string;
    discord_error?: string;
    discord_error_description?: string;
  } = {};
  try {
    j = JSON.parse(text) as typeof j;
  } catch {
    /* not json */
  }
  if (!res.ok) {
    const parts = [`token ${res.status}`];
    if (j.discord_error_description) parts.push(j.discord_error_description);
    else if (j.detail) parts.push(j.detail);
    else if (text) parts.push(text.length > 280 ? `${text.slice(0, 280)}…` : text);
    if (j.hint) parts.push(j.hint);
    throw new Error(parts.join(" — "));
  }
  if (!j.access_token) throw new Error("no access_token");
  return j.access_token;
}

export async function getInventory(token: string, guildId?: string): Promise<InventoryPayload> {
  const res = await fetch(apiUrl("/api/game/inventory"), { headers: authHeaders(token, guildId) });
  if (!res.ok) throw new Error(`inventory ${res.status}`);
  return res.json() as Promise<InventoryPayload>;
}

export async function getCharacterDerivedStats(token: string, guildId?: string): Promise<CharacterDerivedStatsPayload> {
  const res = await fetch(apiUrl("/api/game/character/stats"), { headers: authHeaders(token, guildId) });
  const j = (await res.json()) as CharacterDerivedStatsPayload;
  if (!res.ok) return { ...j, ok: false };
  return { ...j, ok: true };
}

export async function getCharacterClassOptions(): Promise<{ classes: ClassOptionRow[] }> {
  const res = await fetch(apiUrl("/api/game/character/class-options"));
  if (!res.ok) throw new Error(`class-options ${res.status}`);
  return res.json() as Promise<{ classes: ClassOptionRow[] }>;
}

export async function postCharacterCreate(
  token: string,
  name: string,
  classKey: string,
  guildId?: string,
): Promise<InventoryPayload & { ok?: boolean; message?: string; error?: string }> {
  const res = await fetch(apiUrl("/api/game/character/create"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ name, class_key: classKey }),
  });
  const j = (await res.json()) as InventoryPayload & { ok?: boolean; message?: string; error?: string };
  if (!res.ok) return { ...j, ok: false };
  return { ...j, ok: true };
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

export async function getIdleRewards(token: string, guildId?: string): Promise<IdleRewardsPayload> {
  const res = await fetch(apiUrl("/api/game/idle/rewards"), { headers: authHeaders(token, guildId) });
  return (await res.json()) as IdleRewardsPayload;
}

export async function postIdleClaim(token: string, guildId?: string): Promise<IdleRewardsPayload> {
  const res = await fetch(apiUrl("/api/game/idle/claim"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ guild_id: guildId }),
  });
  return (await res.json()) as IdleRewardsPayload;
}

export async function getCombatState(token: string, guildId?: string) {
  const res = await fetch(apiUrl("/api/game/combat/state"), { headers: authHeaders(token, guildId) });
  return res;
}

export async function postCombatStateAck(token: string, guildId?: string) {
  return fetch(apiUrl("/api/game/combat/state/ack"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: "{}",
  });
}

export async function getCombatEnemies(token: string, guildId?: string, zoneKey?: string) {
  const qs = zoneKey ? `?zone_key=${encodeURIComponent(zoneKey)}` : "";
  const res = await fetch(apiUrl(`/api/game/combat/enemies${qs}`), { headers: authHeaders(token, guildId) });
  return res;
}

/** Overworld: pick an enemy from the current zone. Dungeon tab: server resolves enemy from `config.settings.DUNGEONS`. */
export type StartCombatParams =
  | { kind: "zone"; enemyKey: string }
  | { kind: "dungeon"; dungeonKey: string; floor: number };

export async function postCombatStart(
  token: string,
  guildId: string | undefined,
  params: StartCombatParams,
): Promise<Response> {
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

// ── Dungeon Party API ──────────────────────────────────────────────────────────

export async function getDungeonPartyStatus(
  token: string,
  guildId?: string,
): Promise<DungeonPartyStatus> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/status"), { headers: authHeaders(token, guildId) });
  if (!res.ok) throw new Error(`party-status ${res.status}`);
  return res.json() as Promise<DungeonPartyStatus>;
}

export async function postDungeonPartyCreate(
  token: string,
  dungeonKey: string,
  guildId?: string,
): Promise<DungeonPartyCreateResponse> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/create"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ dungeon_key: dungeonKey, guild_id: guildId ? String(guildId) : undefined }),
  });
  return res.json() as Promise<DungeonPartyCreateResponse>;
}

export async function postDungeonPartyInvite(
  token: string,
  targetUserId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; participants?: DungeonParticipant[] }> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/invite"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ target_user_id: targetUserId, guild_id: guildId ? String(guildId) : undefined }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; participants?: DungeonParticipant[] }>;
}

export async function postDungeonPartyJoin(
  token: string,
  runId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; run_id?: string; participants?: DungeonParticipant[] }> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/join"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, guild_id: guildId ? String(guildId) : undefined }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; run_id?: string; participants?: DungeonParticipant[] }>;
}

export async function postDungeonPartyLeave(
  token: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/leave"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ guild_id: guildId ? String(guildId) : undefined }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function getDungeonPartyPlayers(
  token: string,
  query: string,
  guildId?: string,
): Promise<{ ok?: boolean; players?: Array<{ id: string; username: string; level: number; class: string }> }> {
  const res = await fetch(
    apiUrl(`/api/game/dungeon/party/players?q=${encodeURIComponent(query)}`),
    { headers: authHeaders(token, guildId) }
  );
  return res.json() as Promise<{ ok?: boolean; players?: Array<{ id: string; username: string; level: number; class: string }> }>;
}

export async function getDungeonPartyInvites(
  token: string,
  guildId?: string,
): Promise<DungeonPartyInvitesResponse> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/invites"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<DungeonPartyInvitesResponse>;
}

export async function postDungeonPartyInviteAccept(
  token: string,
  inviteId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; run_id?: string; participants?: DungeonParticipant[] }> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/invite/accept"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ invite_id: inviteId, guild_id: guildId ? String(guildId) : undefined }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; run_id?: string; participants?: DungeonParticipant[] }>;
}

export async function postDungeonPartyInviteDecline(
  token: string,
  inviteId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/invite/decline"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ invite_id: inviteId, guild_id: guildId ? String(guildId) : undefined }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function deleteDungeonPartyInvite(
  token: string,
  inviteId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/invite"), {
    method: "DELETE",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ invite_id: inviteId, guild_id: guildId ? String(guildId) : undefined }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function postDungeonPartyEnter(
  token: string,
  guildId?: string,
): Promise<{ ok?: boolean; error?: string; message?: string; state?: CombatStatePayload }> {
  const res = await fetch(apiUrl("/api/game/dungeon/party/enter"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ guild_id: guildId ? String(guildId) : undefined }),
  });
  return res.json() as Promise<{ ok?: boolean; error?: string; message?: string; state?: CombatStatePayload }>;
}

export async function postCombatAction(
  token: string,
  body: Record<string, unknown>,
  guildId?: string,
): Promise<Response> {
  return fetch(apiUrl("/api/game/combat/action"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, guild_id: guildId ? String(guildId) : undefined }),
  });
}

export async function postRest(token: string, guildId?: string): Promise<Response> {
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

export async function getDeeds(token: string, guildId?: string): Promise<DeedsPayload> {
  const res = await fetch(apiUrl("/api/game/deeds"), { headers: authHeaders(token, guildId) });
  if (!res.ok) throw new Error(`deeds ${res.status}`);
  return res.json() as Promise<DeedsPayload>;
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

export async function postSpecialization(
  token: string,
  specKey: string,
  guildId?: string,
): Promise<Response> {
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
): Promise<Response> {
  return fetch(apiUrl(endpoint), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getBattlePass(
  token: string,
  guildId?: string,
): Promise<import("./apiTypes").BattlePassStatePayload> {
  const res = await fetch(apiUrl("/api/game/battle-pass"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<import("./apiTypes").BattlePassStatePayload>;
}

export async function claimBattlePassTier(
  token: string,
  tier: number,
  guildId?: string,
  track = "free",
): Promise<{ ok?: boolean; message?: string; delivery?: unknown }> {
  const res = await fetch(apiUrl("/api/game/battle-pass/claim"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ tier, track }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; delivery?: unknown }>;
}

export async function claimDailyLogin(
  token: string,
  guildId?: string,
): Promise<import("./apiTypes").DailyLoginClaimPayload> {
  const res = await fetch(apiUrl("/api/game/daily-login/claim"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  return res.json() as Promise<import("./apiTypes").DailyLoginClaimPayload>;
}

export async function postBattlePassPlaytime(
  token: string,
  minutes: number,
  guildId?: string,
): Promise<{ ok?: boolean; grant?: unknown }> {
  const res = await fetch(apiUrl("/api/game/battle-pass/playtime"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ minutes }),
  });
  return res.json() as Promise<{ ok?: boolean; grant?: unknown }>;
}

export async function getTalents(
  token: string,
  guildId?: string,
): Promise<import("./apiTypes").TalentsStatePayload> {
  const res = await fetch(apiUrl("/api/game/talents"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<import("./apiTypes").TalentsStatePayload>;
}

export async function allocateTalent(
  token: string,
  nodeId: string,
  guildId?: string,
): Promise<import("./apiTypes").TalentsStatePayload & { message?: string }> {
  const res = await fetch(apiUrl("/api/game/talents/allocate"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ node_id: nodeId, delta: 1 }),
  });
  return res.json() as Promise<import("./apiTypes").TalentsStatePayload & { message?: string }>;
}

export async function respecTalents(
  token: string,
  guildId?: string,
): Promise<import("./apiTypes").TalentsStatePayload & { message?: string }> {
  const res = await fetch(apiUrl("/api/game/talents/respec"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  return res.json() as Promise<import("./apiTypes").TalentsStatePayload & { message?: string }>;
}

export async function getForgeOptions(
  token: string,
  itemId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; options?: unknown }> {
  const res = await fetch(
    apiUrl(`/api/game/forge/options?item_id=${encodeURIComponent(itemId)}`),
    { headers: authHeaders(token, guildId) },
  );
  return res.json() as Promise<{ ok?: boolean; message?: string; options?: unknown }>;
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
): Promise<Response> {
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

export async function getShopCatalog(token: string, guildId?: string) {
  const res = await fetch(apiUrl("/api/game/shop/catalog"), { headers: authHeaders(token, guildId) });
  if (!res.ok) throw new Error(`shop-catalog ${res.status}`);
  return res.json() as Promise<{ ok?: boolean; items?: Array<{ id: string; name: string; icon?: string | null; rarity: string; vendor_buy: number; effect_type?: string | null; effect_value?: number | null; effect_duration?: number | null; level_req?: number | null; description?: string | null }> }>;
}

export async function postShopBuy(
  token: string,
  templateId: string,
  qty: number,
  guildId?: string,
): Promise<Response> {
  return fetch(apiUrl("/api/game/shop/buy"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ template_id: templateId, quantity: qty }),
  });
}

export async function getMarketListings(token: string, guildId?: string) {
  const res = await fetch(apiUrl("/api/game/market/listings"), { headers: authHeaders(token, guildId) });
  if (!res.ok) throw new Error(`market-listings ${res.status}`);
  return res.json() as Promise<{ ok?: boolean; listings?: Array<{ id: string; price: number; quantity: number; listed_at: string; name: string; icon?: string | null; description?: string | null; rarity: string; enhancement_level?: number | null; seller_name: string }> }>;
}

export async function postListItemOnMarket(
  token: string,
  itemId: string,
  price: number,
  guildId?: string,
): Promise<Response> {
  return fetch(apiUrl("/api/game/market/list-item"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ item_id: itemId, price }),
  });
}

export async function postMarketBuy(
  token: string,
  listingId: string,
  guildId?: string,
): Promise<{ ok?: boolean; error?: string; message?: string; item_name?: string; price?: number }> {
  const res = await fetch(apiUrl("/api/game/market/buy"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ listing_id: listingId }),
  });
  return res.json() as Promise<{ ok?: boolean; error?: string; message?: string; item_name?: string; price?: number }>;
}

export function calculateMarketPrice(item: InvRow, vendorBuy?: number): number {
  const rarity = (item.rarity || "common").toLowerCase();
  const multipliers: Record<string, number> = {
    common: 3.0,
    uncommon: 4.5,
    rare: 7.0,
    epic: 10.0,
    legendary: 15.0,
  };

  const base = vendorBuy || 50;
  const rarityMult = multipliers[rarity] || 3.0;
  const enhancement = 1.0 + ((item.enhancement_level || 0) * 0.15);

  return Math.round(base * rarityMult * enhancement);
}

export async function postBuyProtection(
  token: string,
  key: string,
  qty: number,
  guildId?: string,
): Promise<Response> {
  return fetch(apiUrl("/api/game/blacksmith/buy-protection"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ protection_key: key, quantity: qty }),
  });
}

export async function postNpcInteract(
  token: string,
  npc: string | undefined,
  guildId?: string,
): Promise<Response> {
  return fetch(apiUrl("/api/game/npc/interact"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ npc }),
  });
}

export async function postQuestAbandon(
  token: string,
  questId: string,
  guildId?: string,
): Promise<Response> {
  return fetch(apiUrl("/api/game/quest/abandon"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ quest_id: questId }),
  });
}

export async function postQuestAccept(
  token: string,
  questId: string,
  guildId?: string,
): Promise<Response> {
  return fetch(apiUrl("/api/game/quest/accept"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ quest_id: questId }),
  });
}

export async function postQuestDecline(
  token: string,
  questId: string,
  guildId?: string,
): Promise<Response> {
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
  outcome?: {
    type?: string;
    title?: string;
    lines?: string[];
    /** Structured rewards (may be absent depending on outcome type / older server payloads). */
    xp?: number;
    gold?: number;
    leveled_up?: boolean;
    loot?: string[];
  };
  error?: string;
  message?: string;
};

export async function parseCombatState(res: Response): Promise<{
  active?: boolean;
  state?: CombatStatePayload;
  ended_outcome?: CombatActionJson;
}> {
  return res.json() as Promise<{
    active?: boolean;
    state?: CombatStatePayload;
    ended_outcome?: CombatActionJson;
  }>;
}

export async function getGuildMe(token: string, guildId?: string): Promise<GuildMePayload> {
  const res = await fetch(apiUrl("/api/game/guild/me"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<GuildMePayload>;
}

export async function postGuildCreate(
  token: string,
  payload: { name: string; tag: string },
  discordGuildId?: string,
): Promise<GuildCreateResponse> {
  const res = await fetch(apiUrl("/api/game/guild/create"), {
    method: "POST",
    headers: { ...authHeaders(token, discordGuildId), "Content-Type": "application/json" },
    body: JSON.stringify({ name: payload.name.trim(), tag: payload.tag.trim() }),
  });
  return res.json() as Promise<GuildCreateResponse>;
}

export async function postGuildCheckin(
  token: string,
  guildId?: string,
): Promise<{ ok: boolean; message?: string; checkin?: GuildCheckinPayload }> {
  const res = await fetch(apiUrl("/api/game/guild/checkin"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: "{}",
  });
  return res.json() as Promise<{ ok: boolean; message?: string; checkin?: GuildCheckinPayload }>;
}

export async function getGuildInviteCandidates(
  token: string,
  query: string,
  guildId?: string,
  signal?: AbortSignal,
): Promise<{ ok?: boolean; error?: string; players?: GuildInviteCandidate[] }> {
  const res = await fetch(
    apiUrl(`/api/game/guild/invite/candidates?q=${encodeURIComponent(query)}`),
    { headers: authHeaders(token, guildId), signal },
  );
  return res.json() as Promise<{ ok?: boolean; error?: string; players?: GuildInviteCandidate[] }>;
}

export async function postGuildInviteSend(
  token: string,
  targetCharacterId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/guild/invite/send"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ target_character_id: targetCharacterId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function postGuildBankDeposit(
  token: string,
  amount: number,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; bank_gold?: number }> {
  const res = await fetch(apiUrl("/api/game/guild/bank/deposit"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ amount }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; bank_gold?: number }>;
}

export async function postGuildBankWithdraw(
  token: string,
  amount: number,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; bank_gold?: number; character_gold?: number }> {
  const res = await fetch(apiUrl("/api/game/guild/bank/withdraw"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ amount }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; bank_gold?: number; character_gold?: number }>;
}

export async function getGuildFeed(
  token: string,
  guildId?: string,
  cursor?: string,
): Promise<{ ok?: boolean; messages?: unknown[]; next_cursor?: string | null }> {
  const q = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  const res = await fetch(apiUrl(`/api/game/guild/feed${q}`), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<{ ok?: boolean; messages?: unknown[]; next_cursor?: string | null }>;
}

export async function postGuildFeed(
  token: string,
  body: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/guild/feed"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function postGuildBossStart(
  token: string,
  bossKey: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; encounter?: Record<string, unknown> | null }> {
  const res = await fetch(apiUrl("/api/game/guild/boss/start"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ boss_key: bossKey }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; encounter?: Record<string, unknown> | null }>;
}

export async function postGuildBossHit(
  token: string,
  encounterId: string | undefined,
  guildId?: string,
): Promise<{
  ok?: boolean;
  message?: string;
  encounter?: Record<string, unknown> | null;
  leaderboard?: unknown[];
}> {
  const res = await fetch(apiUrl("/api/game/guild/boss/hit"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify(encounterId ? { encounter_id: encounterId } : {}),
  });
  return res.json() as Promise<{
    ok?: boolean;
    message?: string;
    encounter?: Record<string, unknown> | null;
    leaderboard?: unknown[];
  }>;
}

export async function postGuildTechUnlock(
  token: string,
  nodeId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; guild_xp?: number; bank_gold?: number; unlocked?: string[] }> {
  const res = await fetch(apiUrl("/api/game/guild/tech/unlock"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ node_id: nodeId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; guild_xp?: number; bank_gold?: number; unlocked?: string[] }>;
}

export async function postGuildRaidCreate(
  token: string,
  templateKey: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; run?: Record<string, unknown>; participants?: unknown[] }> {
  const res = await fetch(apiUrl("/api/game/guild/raid/create"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ template_key: templateKey }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; run?: Record<string, unknown>; participants?: unknown[] }>;
}

export async function postGuildRaidSignup(
  token: string,
  runId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; participants?: unknown[] }> {
  const res = await fetch(apiUrl("/api/game/guild/raid/signup"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; participants?: unknown[] }>;
}

export async function postGuildRaidStart(
  token: string,
  runId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; run?: Record<string, unknown> | null }> {
  const res = await fetch(apiUrl("/api/game/guild/raid/start"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; run?: Record<string, unknown> | null }>;
}

export async function postGuildRaidComplete(
  token: string,
  runId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; run?: Record<string, unknown> | null }> {
  const res = await fetch(apiUrl("/api/game/guild/raid/complete"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; run?: Record<string, unknown> | null }>;
}

export async function getSocialRoster(token: string, guildId?: string): Promise<SocialRosterPayload> {
  const res = await fetch(apiUrl("/api/game/social/roster"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<SocialRosterPayload>;
}

export async function getSocialRequests(token: string, guildId?: string): Promise<SocialRequestsPayload> {
  const res = await fetch(apiUrl("/api/game/social/requests"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<SocialRequestsPayload>;
}

export async function getSocialPlayersSearch(
  token: string,
  query: string,
  guildId?: string,
  purpose: "friend" | "ignore" = "friend",
): Promise<SocialPlayersSearchPayload> {
  const res = await fetch(
    apiUrl(`/api/game/social/players?q=${encodeURIComponent(query)}&purpose=${purpose}`),
    { headers: authHeaders(token, guildId) },
  );
  return res.json() as Promise<SocialPlayersSearchPayload>;
}

export async function postSocialFriendRequest(
  token: string,
  opts: { username?: string; target_user_id?: string },
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; request_id?: string }> {
  const res = await fetch(apiUrl("/api/game/social/friend/request"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; request_id?: string }>;
}

export async function postSocialFriendAccept(
  token: string,
  requestId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/social/friend/accept"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function postSocialFriendDecline(
  token: string,
  requestId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/social/friend/decline"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function deleteSocialFriend(
  token: string,
  friendUserId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/social/friend"), {
    method: "DELETE",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ friend_user_id: friendUserId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function getSocialIgnore(token: string, guildId?: string): Promise<SocialIgnorePayload> {
  const res = await fetch(apiUrl("/api/game/social/ignore"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<SocialIgnorePayload>;
}

export async function postSocialIgnore(
  token: string,
  opts: { username?: string; blocked_user_id?: string },
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/social/ignore"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function deleteSocialIgnore(
  token: string,
  blockedUserId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/social/ignore"), {
    method: "DELETE",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ blocked_user_id: blockedUserId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function getSocialWhispers(
  token: string,
  withUserId: string,
  guildId?: string,
): Promise<SocialWhispersPayload> {
  const res = await fetch(
    apiUrl(`/api/game/social/whispers?with=${encodeURIComponent(withUserId)}`),
    { headers: authHeaders(token, guildId) },
  );
  return res.json() as Promise<SocialWhispersPayload>;
}

export async function postSocialWhisper(
  token: string,
  toUserId: string,
  body: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/social/whisper"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ to_user_id: toUserId, body }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function getSocialSettings(token: string, guildId?: string): Promise<SocialSettingsPayload> {
  const res = await fetch(apiUrl("/api/game/social/settings"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<SocialSettingsPayload>;
}

export type SocialSettingsInput = {
  appear_offline?: boolean;
  allow_whispers_from_strangers?: boolean;
  allow_party_invites_from_strangers?: boolean;
};

export async function postSocialSettings(
  token: string,
  settings: SocialSettingsInput,
  guildId?: string,
): Promise<SocialSettingsPayload> {
  const res = await fetch(apiUrl("/api/game/social/settings"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  return res.json() as Promise<SocialSettingsPayload>;
}

export async function postSocialFriendCancel(
  token: string,
  requestId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string }> {
  const res = await fetch(apiUrl("/api/game/social/friend/cancel"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string }>;
}

export async function getSocialSuggestions(token: string, guildId?: string): Promise<SocialSuggestionsPayload> {
  const res = await fetch(apiUrl("/api/game/social/suggestions"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<SocialSuggestionsPayload>;
}

export async function getSocialWhisperInbox(token: string, guildId?: string): Promise<SocialWhisperInboxPayload> {
  const res = await fetch(apiUrl("/api/game/social/whispers/inbox"), { headers: authHeaders(token, guildId) });
  return res.json() as Promise<SocialWhisperInboxPayload>;
}

export async function postPvpChallenge(
  token: string,
  targetUserId: string,
  guildId?: string,
): Promise<{ ok?: boolean; message?: string; error?: string }> {
  const res = await fetch(apiUrl("/api/game/pvp/challenge"), {
    method: "POST",
    headers: { ...authHeaders(token, guildId), "Content-Type": "application/json" },
    body: JSON.stringify({ target_user_id: targetUserId }),
  });
  return res.json() as Promise<{ ok?: boolean; message?: string; error?: string }>;
}
