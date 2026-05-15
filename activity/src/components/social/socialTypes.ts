export type Presence = "online" | "away" | "offline" | "in-combat" | "in-dungeon";

export type Friend = {
  id: string;
  username: string;
  display: string;
  level: number;
  className: string;
  presence: Presence;
  zone?: string;
  unread?: number;
  lastSeen?: string;
  lastPreview?: string;
};

export type FriendRequest = {
  id: string;
  username: string;
  display: string;
  level: number;
  className: string;
  sentAt: string;
  direction: "incoming" | "outgoing";
};

export type ChatMessage = {
  id: string;
  from: "me" | "them";
  text: string;
  ts: string;
};

export type BlockedPlayer = {
  id: string;
  username: string;
  display: string;
};

export type LiveEventKind = "world-boss" | "arena" | "raid" | "bonus";

export type LiveEventDisplay = {
  id: string;
  title: string;
  description?: string;
  starts: string;
  type: LiveEventKind;
  joinTab: "Explore" | "Arena" | "Realm";
};

export type PlayerSearchHit = {
  id: string;
  username: string;
  display: string;
  level?: number;
  className?: string;
};
