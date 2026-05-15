/** Payload shapes for `/api/game/*` — keep aligned with `activity_http.py` + legacy `main.ts`. */

export type InvRow = {
  id: string;
  template_id?: string;
  name: string;
  icon?: string | null;
  quantity?: number | null;
  is_equipped?: boolean | null;
  /** Which slot this row is worn in (NULL when in bag). */
  equip_slot?: string | null;
  /** Template slot (armor/weapon slot type); present on gear. Not overwritten by instance equip_slot. */
  template_equip_slot?: string | null;
  rarity?: string | null;
  level_req?: number | null;
  item_type?: string | null;
  s_str?: number | null;
  s_agi?: number | null;
  s_int?: number | null;
  s_spi?: number | null;
  s_sta?: number | null;
  s_armor?: number | null;
  s_dmg_min?: number | null;
  s_dmg_max?: number | null;
  s_haste?: number | null;
  s_lifesteal?: number | null;
  s_resistance?: number | null;
  s_hit_rating?: number | null;
  r_str?: number | null;
  r_agi?: number | null;
  r_int?: number | null;
  r_spi?: number | null;
  r_sta?: number | null;
  r_haste?: number | null;
  r_lifesteal?: number | null;
  r_resistance?: number | null;
  r_hit_rating?: number | null;
  enhancement_level?: number | null;
  locked?: boolean | null;
  soulbound?: boolean | null;
  vendor_sell?: number | null;
  effect_type?: string | null;
  effect_value?: number | null;
  effect_duration?: number | null;
};

/** Row from GET /api/game/character/class-options */
export type ClassOptionRow = {
  key: string;
  name: string;
  emoji: string;
  role: string;
  resource: string;
  description: string;
};

export type CraftRecipeRow = {
  id: string;
  name: string;
  description?: string | null;
  input_template_id: string;
  output_template_id: string;
  craft_seconds: number;
  required_crafting_level: number;
  gold_cost: number;
  costs: Record<string, number>;
  crafting_xp_reward: number;
  /** 0–1; branch forge roll on claim. */
  success_chance?: number;
  destroy_input_on_fail?: boolean | null;
};

export type ForgeRarityRuleRow = {
  id: string;
  name: string;
  from_rarity: string;
  to_rarity: string;
  applies_to: string;
  required_crafting_level: number;
  max_input_template_level?: number | null;
  gold_cost: number;
  costs: Record<string, number>;
  craft_seconds: number;
  success_chance: number;
  crafting_xp_reward: number;
};

export type CraftJobRow = {
  id: string;
  character_id?: string;
  recipe_id?: string | null;
  recipe_name?: string;
  input_template_id?: string;
  output_template_id?: string;
  craft_seconds?: number;
  gold_cost?: number;
  costs?: Record<string, number>;
  crafting_xp_reward?: number;
  job_kind?: string | null;
  rarity_rule_id?: string | null;
  rarity_rule_name?: string | null;
  rarity_from?: string | null;
  rarity_to?: string | null;
  success_chance?: number;
  destroy_input_on_fail?: boolean | null;
  payload?: Record<string, unknown>;
  started_at?: string;
  completes_at?: string;
  status?: string;
};

export type InventoryPayload = {
  discord?: { id?: string; username?: string; global_name?: string | null; avatar?: string | null; avatar_url?: string | null };
  character: {
    name?: string;
    level?: number;
    class?: string;
    gold?: number;
    specialization?: string | null;
    specialization_name?: string | null;
    current_hp?: number;
    max_hp?: number;
    crafting_level?: number;
    crafting_xp?: number;
  } | null;
  /** Bag capacity counts unequipped inventory rows (equipped gear doesn't count). */
  bag_slots_used?: number;
  bag_slots_max?: number;
  items: InvRow[];
  craft_job?: CraftJobRow | null;
  craft_recipes?: CraftRecipeRow[];
  forge_rarity_rules?: ForgeRarityRuleRow[];
  /** Server ceiling for branch forge outputs (Path B). */
  forge_output_max_level_req?: number;
};

export type CharacterDerivedStatsPayload = {
  ok: boolean;
  attack_power: number;
  spell_power: number;
  dmg_min: number;
  dmg_max: number;
  armor: number;
  crit_chance: number;
  dodge_chance: number;
  haste: number;
  lifesteal: number;
  resistance: number;
  hit_rating: number;
  class_mastery?: { class_key?: string; xp?: number; level?: number; xp_gained?: number; leveled_up?: boolean } | null;
  top_ability_mastery?: { ability_key?: string; xp?: number; level?: number }[];
  error?: string;
  message?: string;
};

export type CombatEnemy = {
  key: string;
  name: string;
  emoji: string;
  kind: string;
  /** Scaled max HP for this encounter (matches Activity combat scaling). */
  max_hp?: number;
  /** Server-authored difficulty hint: deadly | risky | caution | fair */
  risk_tier?: "deadly" | "risky" | "caution" | "fair" | string;
};

/** Root `meta` from GET /api/game/combat/enemies */
export type CombatEnemiesMeta = {
  character_level?: number;
  zone_key?: string;
  zone_level_min?: number | null;
  zone_level_max?: number | null;
};

export type CombatAbility = {
  key: string;
  name: string;
  emoji: string;
  cost: number;
  cost_type: string;
  cooldown: number;
  disabled?: string | null;
  /** Server-authored; may be absent on older payloads. */
  description?: string | null;
  /** Pre-mitigation damage range from current combat stats. */
  dmg_min?: number | null;
  dmg_max?: number | null;
  /** Typical heal from spell power (actual may be capped by missing HP). */
  heal_estimate?: number | null;
  crit_pct?: number | null;
  is_aoe?: boolean;
};

export type PartyCombatRow = {
  name: string;
  current_hp: number;
  max_hp: number;
  current_res?: number;
  max_res?: number;
  res_type?: string;
  class?: string | null;
  specialization?: string | null;
  your_turn?: boolean;
};

export type CombatStatePayload = {
  turn: number;
  player: {
    name: string;
    current_hp: number;
    max_hp: number;
    current_res: number;
    max_res: number;
    res_type: string;
    /** Class key (e.g. `warrior`) — from combat state so icons work without waiting on inventory. */
    class?: string | null;
    specialization?: string | null;
  };
  enemy: {
    name: string;
    current_hp: number;
    max_hp: number;
    /** Optional (e.g. Arena PvP) — shows resource bar on duel layout. */
    current_res?: number;
    max_res?: number;
    res_type?: string;
  };
  log: string[];
  abilities: CombatAbility[];
  can_potion: boolean;
  in_dungeon?: boolean;
  /** Activity Dungeon tab — combat started with dungeon_key + floor (see server). */
  dungeon_key?: string | null;
  dungeon_floor?: number | null;
  /** Server dungeon config floor count (do not infer from current floor). */
  dungeon_total_floors?: number | null;
  /** Shared party dungeon — same encounter for all members; abilities only on your turn. */
  party_mode?: boolean;
  your_turn?: boolean;
  active_turn_discord_id?: string | null;
  party_players?: PartyCombatRow[];
  /** Story boss: player cannot deal damage until deed/item requirements are met. */
  lore_blocked?: boolean;
  lore_gate_hint?: string | null;
};

export type DungeonFloorPreview = {
  floor: number;
  enemy_key: string;
  is_boss: boolean;
  name: string;
  emoji: string;
};

export type DungeonCatalogEntry = {
  key: string;
  name: string;
  emoji: string;
  description: string;
  level_req: number;
  floors: number;
  xp_per_floor: number;
  gold_min: number;
  gold_max: number;
  floor_preview: DungeonFloorPreview[];
};

export type DungeonParticipant = {
  id: string;
  name: string;
  level: number;
  class: string;
  /** Discord snowflake — used server-side for shared combat. */
  player_id?: string;
  role: "leader" | "member";
};

export type DungeonPartyStatus = {
  ok?: boolean;
  in_party: boolean;
  run_id?: string;
  is_leader?: boolean;
  dungeon_key?: string;
  participants?: DungeonParticipant[];
};

export type DungeonPartyCreateResponse = {
  ok?: boolean;
  error?: string;
  message?: string;
  run_id?: string;
  dungeon?: { key: string; name: string; emoji: string };
  participants?: DungeonParticipant[];
};

export type DungeonPartyInvite = {
  invite_id: string;
  run_id: string;
  dungeon_key: string;
  inviter: {
    id: string;
    name: string;
    level: number;
    class: string;
  };
  created_at?: string | null;
  expires_at?: string | null;
};

export type DungeonPartyInvitesResponse = {
  ok?: boolean;
  error?: string;
  invites?: DungeonPartyInvite[];
};

export type ExploreZone = {
  key: string;
  name: string;
  emoji: string;
  description?: string;
  level_min?: number;
  level_max?: number;
  faction?: string;
  players?: number;
  boss_alive?: boolean;
  is_current?: boolean;
};

export type ExploreMapPayload = {
  current_zone?: string;
  zones?: ExploreZone[];
  world_boss_windows?: Array<{
    zone_key: string;
    boss_key: string;
    ends_at?: string | null;
    trigger_slug?: string;
    trigger_kind?: string;
    title?: string;
  }>;
};

export type ExploreOutcome =
  | { type: "enemy" | "boss"; key: string; name: string; emoji?: string }
  | { type: "loot" | "safe" };

export type ExploreResultPayload = {
  ok?: boolean;
  error?: string;
  message?: string;
  cooldown_s?: number;
  zone?: { key: string; name: string; emoji: string; level_min?: number; level_max?: number };
  outcome?: ExploreOutcome;
  reward?: { xp?: number; gold?: number };
  npc?: {
    npc_id?: string;
    name?: string;
    title?: string;
    discovery_hint?: string;
    already_met?: boolean;
  } | null;
};

export type ProgressPayload = {
  character?: {
    name?: string;
    level?: number;
    gold?: number;
    last_combat?: string;
    class?: string;
    specialization?: string | null;
    specialization_name?: string | null;
  };
  stats?: { total_combats?: number; wins?: number; losses?: number; fled?: number; win_rate?: number };
  achievements?: {
    id?: string;
    name?: string;
    description?: string;
    icon?: string;
    points?: number;
    category?: string;
    earned_at?: string;
  }[];
  history?: {
    type?: string;
    outcome?: string;
    zone?: string;
    amount?: number;
    reason?: string;
    source?: string;
    at?: string;
  }[];
};

/** GET /api/game/deeds — lore / Obsidian deed flags */
export type DeedsPayload = {
  ok?: boolean;
  flags?: string[];
  error?: string;
};

/** GET /api/game/idle/rewards — POST /api/game/idle/claim */
export type IdleRewardsPayload = {
  ok?: boolean;
  error?: string;
  claimed?: boolean;
  message?: string;
  elapsed_seconds?: number;
  effective_hours?: number;
  pending_xp?: number;
  pending_gold?: number;
  max_hours?: number;
  gold_gained?: number;
  xp_result?: Record<string, unknown>;
  character?: Record<string, unknown>;
};

export type QuestLogRow = {
  quest_id?: string;
  state?: string;
  quest_name?: string;
  quest_desc?: string;
  /** Obsidian / main story — cannot abandon */
  lore_main?: boolean;
  npc_id?: string;
  npc_name?: string;
  npc_title?: string;
  current_step?: number;
  total_steps?: number;
  objective?: string | null;
  completion_check?: { type?: string; value?: string; count?: number } | null;
  progress?: { current?: number; needed?: number } | null;
  expires_at?: string | null;
};

/** Server-driven Obsidian / main-story compass (deeds + completion aware). */
export type MainQuestPointerPayload = {
  kind?: "active" | "seek_npc" | "blocked_level" | "blocked_deeds" | "complete" | "none";
  quest_id?: string | null;
  quest_name?: string | null;
  quest_desc?: string | null;
  objective?: string | null;
  state?: string | null;
  level_required?: number;
  npc_id?: string | null;
  npc_name?: string | null;
  npc_title?: string | null;
  discovery_hint?: string | null;
  region_zones?: string[];
  regions?: { key?: string; name?: string; emoji?: string }[];
  in_current_region?: boolean;
  hint_base?: string;
  hint_region?: string;
  blocked_detail?: string;
  missing_deed_flags?: string[];
};

export type QuestLogPayload = {
  ok?: boolean;
  error?: string;
  quests?: QuestLogRow[];
  main_quest_pointer?: MainQuestPointerPayload | null;
};

export type QuestOfferPayload = {
  npc_id?: string;
  npc_name?: string;
  npc_title?: string;
  intro?: string;
  quest_id?: string;
  quest_name?: string;
  quest_desc?: string;
  lore_main?: boolean;
  level_req?: number;
  time_limit_hours?: number | null;
  rewards?: {
    xp?: number;
    gold?: number;
    items?: string[];
    reputation?: Record<string, number>;
  };
  objectives?: { objective?: string | null; hint?: string | null }[];
  dialogue?: { accept?: string | null; decline?: string | null };
};

export type NpcInteractPayload = {
  ok?: boolean;
  error?: string;
  message?: string;
  npc_id?: string;
  quest_completed?: boolean;
  rewards?: {
    xp?: number;
    gold?: number;
    items?: string[];
    item_failures?: { template_id?: string; reason?: string }[];
    reputation?: Record<string, number>;
  };
  quest_step_updated?: boolean;
  quest_offered?: boolean;
  offer?: QuestOfferPayload;
  lore_main?: boolean;
  next_step_hint?: string;
};

export type QuestCompletionPayload = {
  npc_id?: string;
  quest_completed?: boolean;
  message?: string;
  lore_main?: boolean;
  rewards?: {
    xp?: number;
    gold?: number;
    items?: string[];
    item_failures?: { template_id?: string; reason?: string }[];
    reputation?: Record<string, number>;
  };
  /** Present when an NPC has another quest after turning in. */
  next_quest_available?: boolean;
  /** When next quest is available but blocked (e.g. level too low). */
  next_quest_blocked?: string;
  /** Human-readable guidance on what to do after completion. */
  next_step_hint?: string;
};

export type SpecOption = {
  key: string;
  name: string;
  emoji: string;
  role: string;
  description: string;
  flavor?: string;
  passive_name: string;
  passive_desc: string;
};

export type SpecGatePayload = {
  ok?: boolean;
  spec_unlock_level?: number;
  needs_choice?: boolean;
  class?: string;
  specialization?: string | null;
  options?: SpecOption[];
};

/** Active guild live events from `GET /api/game/live-events`. */
export type LiveEventRow = {
  slug?: string;
  title?: string;
  description?: string;
  config?: Record<string, unknown>;
  starts_at?: string;
  ends_at?: string;
};

/** Matches `BlacksmithService.get_enhancement_info` + `protections` from Activity HTTP. */
export type EnhanceInfoPayload = {
  ok?: boolean;
  error?: string;
  message?: string;
  info?: {
    current_level?: number;
    next_level?: number | null;
    next_config?: {
      success_rate?: number;
      cost?: number;
      can_break?: boolean;
      stat_boost?: number;
    } | null;
    item?: { name?: string; rarity?: string; enhancement_level?: number };
  } | null;
  /** Counts: blessing_scroll, safety_charm, enhancement_fragment */
  protections?: Record<string, number>;
};

/** Shop catalog item from GET /api/game/shop/catalog. */
export type ShopCatalogItem = {
  id: string;
  name: string;
  icon?: string | null;
  rarity: string;
  vendor_buy: number;
  effect_type?: string | null;
  effect_value?: number | null;
  effect_duration?: number | null;
  level_req?: number | null;
  description?: string | null;
};

/** Player market listing from GET /api/game/market/listings. */
export type MarketListingRow = {
  id: string;
  /** Inventory row template id (item_templates.id), not the listing id. */
  template_id?: string | null;
  template_equip_slot?: string | null;
  price: number;
  quantity: number;
  listed_at: string;
  name: string;
  icon?: string | null;
  description?: string | null;
  rarity: string;
  enhancement_level?: number | null;
  seller_name: string;
};

/** GET /api/game/guild/me + related guild hub payloads */
export type GuildTechDefinition = {
  id: string;
  name: string;
  description: string;
  cost_guild_xp: number;
  cost_bank_gold: number;
  requires: string[];
};

export type GuildFeedMessage = {
  id: string;
  guild_id?: string;
  author_character_id?: string | null;
  body: string;
  message_type?: string;
  meta?: Record<string, unknown>;
  created_at?: string;
  author_name?: string | null;
};

/** GET /api/game/guild/invite/candidates */
export type GuildInviteCandidate = {
  character_id: string;
  name: string;
  level: number;
  class: string;
  username?: string | null;
};

/** POST /api/game/guild/create */
export type GuildCreateResponse = {
  ok: boolean;
  message?: string;
  error?: string;
  guild?: { id: string; name: string; tag: string };
};

export type GuildCheckinPayload = {
  checked_today: boolean;
  streak: number;
  utc_day: string;
  checked_in_guild_today: number;
  rewards: { gold: number; xp: number; guild_xp: number };
};

export type GuildMePayload = {
  ok: boolean;
  in_guild?: boolean;
  message?: string;
  error?: string;
  guild?: {
    id: string;
    name: string;
    tag: string;
    bank_gold?: number;
    guild_level?: number;
    guild_xp?: number;
    max_members?: number;
    member_count?: number;
    my_rank?: string | null;
    my_character_id?: string;
    motd?: string | null;
    announce_channel_id?: number | null;
  };
  boss?: {
    encounter: Record<string, unknown>;
    template: Record<string, unknown>;
    leaderboard: Array<{ character_id: string; total_damage: number; name: string }>;
  } | null;
  tech?: {
    definitions: GuildTechDefinition[];
    unlocked: string[];
  };
  raids?: {
    recent: Array<Record<string, unknown>>;
  };
  checkin?: GuildCheckinPayload;
};

/** GET /api/game/battle-pass */
export type BattlePassTierRow = {
  tier: number;
  track: string;
  reward?: Record<string, unknown>;
  unlocked?: boolean;
  claimed?: boolean;
  claimable?: boolean;
};

export type BattlePassStatePayload = {
  ok?: boolean;
  season?: {
    id: number;
    key?: string;
    name?: string;
    starts_at?: string;
    ends_at?: string;
    max_tier?: number;
    xp_per_tier?: number;
    weekend_multiplier?: number;
    is_live?: boolean;
  } | null;
  progress?: {
    xp: number;
    tier: number;
    xp_in_tier: number;
    xp_needed_for_next: number;
    premium_unlocked?: boolean;
  } | null;
  tiers?: BattlePassTierRow[];
  daily_login?: {
    current_streak: number;
    longest_streak: number;
    claimed_today: boolean;
    weekend_double?: boolean;
  };
};

export type DailyLoginClaimPayload = {
  ok?: boolean;
  message?: string;
  login?: {
    claimed?: boolean;
    current_streak?: number;
    longest_streak?: number;
    gold?: number;
    xp?: number;
    next_claim?: string;
  };
  pass_xp_grants?: unknown[];
  battle_pass?: BattlePassStatePayload;
};

export type TalentNodeState = {
  id?: string;
  name?: string;
  column?: number;
  tier?: number;
  max_ranks?: number;
  node_type?: string;
  layer?: string;
  spec_key?: string | null;
  prereqs?: string[];
  auto_grant?: boolean;
  descriptions?: string[];
  ranks?: number;
  allocated?: boolean;
  can_allocate?: boolean;
  locked_reason?: string | null;
  glow?: boolean;
};

export type TalentTreeSection = {
  class_key?: string;
  spec_key?: string;
  passive_name?: string;
  role?: string;
  nodes?: TalentNodeState[];
};

/** GET /api/game/talents */
export type TalentsStatePayload = {
  ok?: boolean;
  class_key?: string;
  specialization?: string | null;
  level?: number;
  points?: { earned?: number; spent?: number; unspent?: number };
  foundation_locked?: boolean;
  respec_count?: number;
  respec_gold_cost?: number;
  foundation?: TalentTreeSection;
  spec_trees?: TalentTreeSection[];
  allocations?: Record<string, number>;
  class_mastery?: { class_key?: string; xp?: number; level?: number } | null;
  message?: string;
};

/** GET /api/game/social/roster */
export type SocialFriendRow = {
  user_id: string;
  username: string;
  character_id?: string | null;
  character_name?: string | null;
  level?: number | null;
  class?: string | null;
  online?: boolean;
  last_seen?: string | null;
  zone_hint?: string | null;
  unread_count?: number;
  last_whisper_preview?: string | null;
};

export type SocialRosterPayload = {
  ok?: boolean;
  error?: string;
  friends?: SocialFriendRow[];
  total_unread?: number;
};

export type SocialSettingsPayload = {
  ok?: boolean;
  appear_offline?: boolean;
};

export type SocialSuggestionRow = {
  user_id: string;
  username: string;
  character_id?: string | null;
  character_name?: string | null;
  level?: number | null;
  class?: string | null;
  reason?: string;
};

export type SocialSuggestionsPayload = {
  ok?: boolean;
  suggestions?: SocialSuggestionRow[];
};

export type SocialWhisperInboxPayload = {
  ok?: boolean;
  threads?: SocialFriendRow[];
};

/** GET /api/game/social/requests */
export type SocialRequestRow = {
  request_id: string;
  user_id: string;
  username: string;
  character_name?: string | null;
  level?: number | null;
  class?: string | null;
  created_at?: string | null;
};

export type SocialRequestsPayload = {
  ok?: boolean;
  error?: string;
  incoming?: SocialRequestRow[];
  outgoing?: SocialRequestRow[];
};

/** GET /api/game/social/players */
export type SocialPlayerSearchRow = {
  id: string;
  username: string;
  level?: number;
  class?: string;
  character_name?: string;
};

export type SocialPlayersSearchPayload = {
  ok?: boolean;
  players?: SocialPlayerSearchRow[];
};

/** GET /api/game/social/ignore */
export type SocialIgnoreRow = {
  user_id: string;
  username: string;
  created_at?: string | null;
};

export type SocialIgnorePayload = {
  ok?: boolean;
  ignored?: SocialIgnoreRow[];
};

/** GET /api/game/social/whispers */
export type SocialWhisperMessage = {
  id: string;
  from_user_id: string;
  to_user_id: string;
  body: string;
  created_at?: string | null;
  mine?: boolean;
};

export type SocialWhispersPayload = {
  ok?: boolean;
  messages?: SocialWhisperMessage[];
};
