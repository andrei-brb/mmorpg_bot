export type PvpMode = "casual" | "ranked";
export type MatchStatus = "idle" | "queued" | "challenged" | "active" | "finished";
export type MatchResult = "victory" | "defeat" | "draw";
export type ActionType = "attack" | "skill" | "defend" | "pass";

export interface PvpStats {
  rating: number;
  rank_tier: string;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  streak: number;
}

export interface PvpPlayer {
  user_id: string;
  username: string;
  character_name: string;
  level: number;
  class: string;
  spec?: string;
  hp: number;
  max_hp: number;
  resource: number;
  max_resource: number;
  portrait_url?: string;
}

export interface PvpRules {
  bracket: string;
  level_range: string;
  gear_normalized: boolean;
}

export interface CombatLogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: "damage" | "heal" | "buff" | "debuff" | "system";
}

export interface SkillSlot {
  key: string;
  name: string;
  icon?: string;
  cooldown: number;
  max_cooldown: number;
  description: string;
}

export interface IncomingChallenge {
  from_discord_id: string;
  from_name: string;
  mode: PvpMode;
}

export interface PvpStatus {
  match_status: MatchStatus;
  mode?: PvpMode;
  stats?: PvpStats;
  player?: PvpPlayer;
  rules?: PvpRules;
  queue_time?: number;
  challenge_target?: string;
  challenge_timer?: number;
  /** Present when another player challenged you (poll GET /pvp/status). */
  incoming_challenge?: IncomingChallenge;
  /** Embedded active match from server (GET /pvp/status). */
  match?: PvpMatchState;
  error?: string;
}

export interface PvpMatchState {
  match_id: string;
  status: "active" | "finished";
  result?: MatchResult;
  mode: PvpMode;
  is_your_turn: boolean;
  turn_timer: number;
  player: PvpPlayer;
  opponent: PvpPlayer;
  combat_log: CombatLogEntry[];
  skills: SkillSlot[];
  result_stats?: {
    damage_dealt: number;
    damage_taken: number;
    crits: number;
    duration_seconds: number;
    rating_delta?: number;
  };
}

export interface PvpHistoryEntry {
  match_id: string;
  date: string;
  opponent_name: string;
  result: MatchResult;
  mode: PvpMode;
  rating_delta?: number;
}

export interface PvpHistoryResponse {
  matches: PvpHistoryEntry[];
  has_more: boolean;
  page: number;
}
