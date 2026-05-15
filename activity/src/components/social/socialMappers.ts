import type {
  LiveEventRow,
  SocialFriendRow,
  SocialIgnoreRow,
  SocialRequestRow,
  SocialWhisperMessage,
} from "@/lib/apiTypes";
import type {
  BlockedPlayer,
  ChatMessage,
  Friend,
  FriendRequest,
  LiveEventDisplay,
  LiveEventKind,
  Presence,
} from "./socialTypes";

export function formatUsername(username: string): string {
  const u = (username || "").trim();
  return u.startsWith("@") ? u : `@${u}`;
}

export function formatLastSeen(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return d.toLocaleDateString();
}

function formatClassLine(cls?: string | null, level?: number | null): string {
  const parts: string[] = [];
  if (cls) {
    parts.push(
      cls
        .split(/[_/]+/g)
        .filter(Boolean)
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" "),
    );
  }
  if (level != null) return parts.length ? `${parts[0]} · Lv ${level}` : `Lv ${level}`;
  return parts.join(" ") || "Adventurer";
}

function mapPresence(row: SocialFriendRow): Presence {
  const status = row.presence_status;
  if (status === "in-combat" || status === "in-dungeon" || status === "offline") return status;
  if (!row.online) return "offline";
  return "online";
}

export function mapFriend(row: SocialFriendRow): Friend {
  const username = formatUsername(row.username);
  const presence = mapPresence(row);
  return {
    id: row.user_id,
    username,
    display: row.character_name?.trim() || row.username,
    level: row.level ?? 0,
    className: formatClassLine(row.class, row.level),
    presence,
    zone: row.zone_hint ?? undefined,
    unread: row.unread_count ?? 0,
    lastSeen: presence === "offline" ? formatLastSeen(row.last_seen) || undefined : undefined,
    lastPreview: row.last_whisper_preview?.trim() || undefined,
  };
}

export function mapRequest(row: SocialRequestRow, direction: "incoming" | "outgoing"): FriendRequest {
  return {
    id: row.request_id,
    username: formatUsername(row.username),
    display: row.character_name?.trim() || row.username,
    level: row.level ?? 0,
    className: formatClassLine(row.class, row.level),
    sentAt: row.created_at ? formatLastSeen(row.created_at) : "",
    direction,
  };
}

export function mapBlocked(row: SocialIgnoreRow): BlockedPlayer {
  return {
    id: row.user_id,
    username: formatUsername(row.username),
    display: row.username,
  };
}

export function mapWhisper(m: SocialWhisperMessage): ChatMessage {
  const ts = m.created_at ? new Date(m.created_at) : null;
  const time =
    ts && !Number.isNaN(ts.getTime())
      ? ts.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "";
  return {
    id: m.id,
    from: m.mine ? "me" : "them",
    text: m.body,
    ts: time,
  };
}

function inferLiveEventKind(ev: LiveEventRow): LiveEventKind {
  const slug = (ev.slug || "").toLowerCase();
  const cfg = ev.config || {};
  if (slug.includes("arena") || slug.includes("pvp")) return "arena";
  if (typeof cfg.explore_boss_chance_add === "number" && cfg.explore_boss_chance_add > 0) return "world-boss";
  if (slug.includes("boss") || slug.includes("hunt")) return "world-boss";
  if (slug.includes("raid") || slug.includes("dungeon")) return "raid";
  if (cfg.xp_multiplier || cfg.gold_multiplier) return "bonus";
  return "bonus";
}

function inferLiveEventJoinTab(ev: LiveEventRow, kind: LiveEventKind): LiveEventDisplay["joinTab"] {
  if (kind === "arena") return "Arena";
  if (kind === "raid") return "Realm";
  return "Explore";
}

export function mapLiveEvent(ev: LiveEventRow, index: number): LiveEventDisplay {
  const ends = ev.ends_at ? new Date(ev.ends_at) : null;
  let starts = "Active";
  if (ends && !Number.isNaN(ends.getTime())) {
    const min = Math.round((ends.getTime() - Date.now()) / 60000);
    starts = min > 0 ? `ends in ${min}m` : "ending soon";
  }
  const type = inferLiveEventKind(ev);
  return {
    id: ev.slug || ev.title || `ev-${index}`,
    title: ev.title || ev.slug || "Event",
    description: ev.description,
    starts,
    type,
    joinTab: inferLiveEventJoinTab(ev, type),
  };
}
