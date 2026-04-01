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
  } | null;
  items: InvRow[];
};

export type CombatEnemy = { key: string; name: string; emoji: string; kind: string };

export type CombatAbility = {
  key: string;
  name: string;
  emoji: string;
  cost: number;
  cost_type: string;
  cooldown: number;
  disabled?: string | null;
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
  enemy: { name: string; current_hp: number; max_hp: number };
  log: string[];
  abilities: CombatAbility[];
  can_potion: boolean;
  in_dungeon?: boolean;
  /** Activity Dungeon tab — combat started with dungeon_key + floor (see server). */
  dungeon_key?: string | null;
  dungeon_floor?: number | null;
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

export type QuestLogRow = {
  quest_id?: string;
  state?: string;
  quest_name?: string;
  quest_desc?: string;
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

export type QuestLogPayload = { ok?: boolean; error?: string; quests?: QuestLogRow[] };

export type QuestOfferPayload = {
  npc_id?: string;
  npc_name?: string;
  npc_title?: string;
  intro?: string;
  quest_id?: string;
  quest_name?: string;
  quest_desc?: string;
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
  rewards?: { xp?: number; gold?: number; items?: string[]; reputation?: Record<string, number> };
  quest_step_updated?: boolean;
  quest_offered?: boolean;
  offer?: QuestOfferPayload;
};

export type QuestCompletionPayload = {
  npc_id?: string;
  quest_completed?: boolean;
  message?: string;
  rewards?: { xp?: number; gold?: number; items?: string[]; reputation?: Record<string, number> };
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
