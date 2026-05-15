import { useMemo, useState } from "react";
import {
  MessageCircle,
  Users,
  Swords,
  UserMinus,
  UserPlus,
  Search,
  Shield,
  EyeOff,
  Ban,
  Send,
  Circle,
  Sparkles,
  Calendar,
  X,
  Check,
  ChevronLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import type {
  BlockedPlayer,
  ChatMessage,
  Friend,
  FriendRequest,
  LiveEventDisplay,
  PlayerSearchHit,
  Presence,
} from "./socialTypes";

const presenceStyle: Record<Presence, { dot: string; label: string }> = {
  online: { dot: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]", label: "Online" },
  "in-combat": { dot: "bg-[var(--blood)] shadow-[0_0_8px_var(--blood)]", label: "In Combat" },
  "in-dungeon": { dot: "bg-[var(--arcane)] shadow-[0_0_8px_var(--arcane)]", label: "In Dungeon" },
  away: { dot: "bg-amber-400", label: "Away" },
  offline: { dot: "bg-muted-foreground/40", label: "Offline" },
};

function OrnateFrame({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("ornate-frame rounded-lg p-4 sm:p-5", className)}>
      <span className="corner-ornament corner-tl" />
      <span className="corner-ornament corner-tr" />
      <span className="corner-ornament corner-bl" />
      <span className="corner-ornament corner-br" />
      {children}
    </div>
  );
}

function SectionTitle({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="mb-4">
      <div className="text-[10px] tracking-[0.3em] text-gold-dim font-display uppercase">{eyebrow}</div>
      <h2 className="font-display text-2xl sm:text-3xl text-shimmer leading-tight">{title}</h2>
    </div>
  );
}

function Avatar({ name, presence, size = 44 }: { name: string; presence?: Presence; size?: number }) {
  const initials = name
    .split(" ")
    .map((s) => s[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <div
        className="w-full h-full rounded-full grid place-items-center font-display text-gold-bright"
        style={{
          background: "var(--gradient-node-available)",
          border: "1px solid var(--gold-dim)",
          boxShadow: "inset 0 0 12px rgba(0,0,0,0.6)",
        }}
      >
        {initials}
      </div>
      {presence ? (
        <span
          className={cn(
            "absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-background",
            presenceStyle[presence].dot,
          )}
        />
      ) : null}
    </div>
  );
}

function FriendCard({
  friend,
  onMessage,
  onParty,
  onArena,
  onRemove,
}: {
  friend: Friend;
  onMessage: (f: Friend) => void;
  onParty: (f: Friend) => void;
  onArena: (f: Friend) => void;
  onRemove: (f: Friend) => void;
}) {
  const p = presenceStyle[friend.presence];
  return (
    <div className="group relative rounded-md border border-border/60 bg-card/60 backdrop-blur-sm p-3 sm:p-4 transition hover:border-[var(--gold-dim)] hover:shadow-[0_0_24px_rgba(212,175,55,0.15)]">
      <div className="flex items-start gap-3">
        <Avatar name={friend.display} presence={friend.presence} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-display text-base sm:text-lg text-foreground truncate">{friend.display}</span>
            {friend.level > 0 ? (
              <span className="text-[10px] font-display tracking-widest text-gold px-1.5 py-0.5 rounded border border-[var(--gold-dim)]/50 bg-black/40">
                LVL {friend.level}
              </span>
            ) : null}
            {(friend.unread ?? 0) > 0 ? (
              <Badge className="ml-auto bg-[var(--blood)] text-white border-0 h-5 px-1.5 text-[10px]">
                {friend.unread}
              </Badge>
            ) : null}
          </div>
          <div className="text-xs text-muted-foreground truncate">{friend.username}</div>
          <div className="mt-1 text-xs text-foreground/80 truncate">{friend.className}</div>
          <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
            <Circle className="w-2 h-2 fill-emerald-400 text-emerald-400" />
            <span>{p.label}</span>
            {friend.zone ? <span className="opacity-60">· {friend.zone}</span> : null}
            {friend.presence === "offline" && friend.lastSeen ? (
              <span className="opacity-60">· last {friend.lastSeen}</span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-4 gap-1.5">
        <ActionBtn icon={<MessageCircle className="w-4 h-4" />} label="Whisper" onClick={() => onMessage(friend)} />
        <ActionBtn icon={<Users className="w-4 h-4" />} label="Party" onClick={() => onParty(friend)} />
        <ActionBtn icon={<Swords className="w-4 h-4" />} label="Arena" onClick={() => onArena(friend)} />
        <ActionBtn icon={<UserMinus className="w-4 h-4" />} label="Remove" onClick={() => onRemove(friend)} danger />
      </div>
    </div>
  );
}

function ActionBtn({
  icon,
  label,
  onClick,
  danger,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-col items-center gap-0.5 py-2 rounded-sm border text-[10px] font-display tracking-wider uppercase transition",
        "border-border/60 bg-black/30 text-foreground/80 hover:text-gold-bright hover:border-[var(--gold-dim)] hover:bg-black/50",
        danger && "hover:text-[var(--blood)] hover:border-[var(--blood)]/60",
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

const TABS = [
  { id: "friends", label: "Friends", icon: Users },
  { id: "requests", label: "Requests", icon: UserPlus },
  { id: "find", label: "Find", icon: Search },
  { id: "chat", label: "Chat", icon: MessageCircle },
  { id: "privacy", label: "Privacy", icon: Shield },
] as const;

export type SocialTabId = (typeof TABS)[number]["id"];

export type SocialViewProps = {
  loading?: boolean;
  friends: Friend[];
  requests: FriendRequest[];
  threads: Record<string, ChatMessage[]>;
  activeThreadId: string | null;
  appearOffline: boolean;
  allowWhispersFromStrangers: boolean;
  allowPartyInvitesFromStrangers: boolean;
  settingsSaving?: boolean;
  blocked: BlockedPlayer[];
  liveEvents: LiveEventDisplay[];
  totalUnread: number;
  findQuery: string;
  findSuggestions: PlayerSearchHit[];
  showFindSuggestions: boolean;
  ignoreQuery: string;
  ignoreSuggestions: PlayerSearchHit[];
  showIgnoreSuggestions: boolean;
  onFindQueryChange: (v: string) => void;
  onShowFindSuggestions: (v: boolean) => void;
  onIgnoreQueryChange: (v: string) => void;
  onShowIgnoreSuggestions: (v: boolean) => void;
  onTabChange?: (tab: SocialTabId) => void;
  onMessage: (f: Friend) => void;
  onParty: (f: Friend) => void;
  onArena: (f: Friend) => void;
  onRemove: (f: Friend) => void;
  onAccept: (r: FriendRequest) => void;
  onDecline: (r: FriendRequest) => void;
  onCancel: (r: FriendRequest) => void;
  onSendRequest: (username: string) => void;
  onPickFindSuggestion: (username: string) => void;
  onOpenThread: (friendId: string) => void;
  onCloseThread: () => void;
  onSendWhisper: (text: string) => void;
  onToggleAppearOffline: () => void;
  onToggleAllowWhispers: () => void;
  onToggleAllowPartyInvites: () => void;
  onJoinLiveEvent: (event: LiveEventDisplay) => void;
  onBlock: (username: string) => void;
  onUnblock: (id: string) => void;
  onGoToFind?: () => void;
  activeTab?: SocialTabId;
  onActiveTabChange?: (tab: SocialTabId) => void;
};

export function SocialView({
  loading,
  friends,
  requests,
  threads,
  activeThreadId,
  appearOffline,
  allowWhispersFromStrangers,
  allowPartyInvitesFromStrangers,
  settingsSaving,
  blocked,
  liveEvents,
  totalUnread,
  findQuery,
  findSuggestions,
  showFindSuggestions,
  ignoreQuery,
  ignoreSuggestions,
  showIgnoreSuggestions,
  onFindQueryChange,
  onShowFindSuggestions,
  onIgnoreQueryChange,
  onShowIgnoreSuggestions,
  onTabChange,
  onMessage,
  onParty,
  onArena,
  onRemove,
  onAccept,
  onDecline,
  onCancel,
  onSendRequest,
  onPickFindSuggestion,
  onOpenThread,
  onCloseThread,
  onSendWhisper,
  onToggleAppearOffline,
  onToggleAllowWhispers,
  onToggleAllowPartyInvites,
  onJoinLiveEvent,
  onBlock,
  onUnblock,
  onGoToFind,
  activeTab: controlledTab,
  onActiveTabChange,
}: SocialViewProps) {
  const [internalTab, setInternalTab] = useState<SocialTabId>("friends");
  const tab = controlledTab ?? internalTab;

  const setTabBoth = (id: SocialTabId) => {
    if (controlledTab === undefined) setInternalTab(id);
    onActiveTabChange?.(id);
    onTabChange?.(id);
  };

  const incomingCount = requests.filter((r) => r.direction === "incoming").length;
  const onlineCount = friends.filter((f) => f.presence !== "offline").length;

  return (
    <div className="realm-social space-y-4 sm:space-y-6 min-h-0 flex flex-col">
      <OrnateFrame>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <SectionTitle eyebrow="✦ Realm · Social ✦" title="Friends & Chat" />
            <p className="text-xs sm:text-sm text-muted-foreground max-w-md">
              Forge bonds across the realm. Whisper allies, rally a party, and challenge rivals to the arena.
            </p>
          </div>
          <div className="flex items-center gap-3 text-[11px] font-display tracking-widest uppercase text-gold-dim">
            <span>
              {onlineCount} / {friends.length} online
            </span>
          </div>
        </div>
      </OrnateFrame>

      <div className="ornate-frame rounded-lg p-1.5 shrink-0">
        <div className="grid grid-cols-5 gap-1">
          {TABS.map(({ id, label, icon: Icon }) => {
            const active = tab === id;
            const badge = id === "chat" ? totalUnread : id === "requests" ? incomingCount : 0;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setTabBoth(id)}
                className={cn(
                  "relative flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 py-2 px-1 sm:px-3 rounded-sm font-display text-[10px] sm:text-xs tracking-widest uppercase transition min-h-[44px]",
                  active
                    ? "bg-gradient-to-b from-[var(--gold)]/20 to-transparent text-gold-bright shadow-[inset_0_-2px_0_var(--gold)]"
                    : "text-muted-foreground hover:text-foreground hover:bg-white/5",
                )}
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
                {badge > 0 ? (
                  <span className="absolute top-1 right-1 sm:relative sm:top-auto sm:right-auto bg-[var(--blood)] text-white text-[9px] rounded-full min-w-[16px] h-4 px-1 grid place-items-center">
                    {badge > 9 ? "9+" : badge}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      </div>

      {loading ? <p className="text-xs text-muted-foreground px-1">Loading…</p> : null}

      <div className="flex-1 min-h-0">
        {tab === "friends" ? (
          <FriendsTab
            friends={friends}
            onMessage={onMessage}
            onParty={onParty}
            onArena={onArena}
            onRemove={onRemove}
            onGoToFind={onGoToFind ?? (() => setTabBoth("find"))}
          />
        ) : null}
        {tab === "requests" ? (
          <RequestsTab requests={requests} onAccept={onAccept} onDecline={onDecline} onCancel={onCancel} />
        ) : null}
        {tab === "find" ? (
          <FindTab
            query={findQuery}
            suggestions={findSuggestions}
            showSuggestions={showFindSuggestions}
            onQueryChange={onFindQueryChange}
            onShowSuggestions={onShowFindSuggestions}
            onSendRequest={onSendRequest}
            onPick={onPickFindSuggestion}
          />
        ) : null}
        {tab === "chat" ? (
          <ChatTab
            friends={friends}
            threads={threads}
            activeThreadId={activeThreadId}
            totalUnread={totalUnread}
            onOpenThread={onOpenThread}
            onCloseThread={onCloseThread}
            onSend={onSendWhisper}
          />
        ) : null}
        {tab === "privacy" ? (
          <PrivacyTab
            appearOffline={appearOffline}
            allowWhispersFromStrangers={allowWhispersFromStrangers}
            allowPartyInvitesFromStrangers={allowPartyInvitesFromStrangers}
            settingsSaving={settingsSaving}
            onToggleAppearOffline={onToggleAppearOffline}
            onToggleAllowWhispers={onToggleAllowWhispers}
            onToggleAllowPartyInvites={onToggleAllowPartyInvites}
            ignoreQuery={ignoreQuery}
            ignoreSuggestions={ignoreSuggestions}
            showIgnoreSuggestions={showIgnoreSuggestions}
            onIgnoreQueryChange={onIgnoreQueryChange}
            onShowIgnoreSuggestions={onShowIgnoreSuggestions}
            onBlock={onBlock}
            blocked={blocked}
            onUnblock={onUnblock}
          />
        ) : null}
      </div>

      <LiveEventsCard events={liveEvents} onJoin={onJoinLiveEvent} />
    </div>
  );
}

function FriendsTab({
  friends,
  onMessage,
  onParty,
  onArena,
  onRemove,
  onGoToFind,
}: {
  friends: Friend[];
  onMessage: (f: Friend) => void;
  onParty: (f: Friend) => void;
  onArena: (f: Friend) => void;
  onRemove: (f: Friend) => void;
  onGoToFind: () => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = friends.filter(
    (f) =>
      f.display.toLowerCase().includes(query.toLowerCase()) ||
      f.username.toLowerCase().includes(query.toLowerCase()),
  );
  const online = filtered.filter((f) => f.presence !== "offline");
  const offline = filtered.filter((f) => f.presence === "offline");

  if (friends.length === 0) {
    return (
      <EmptyState
        icon={<Users className="w-6 h-6" />}
        title="No friends yet"
        hint="Add allies from the Find tab to begin your party."
        actionLabel="Find players"
        onAction={onGoToFind}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter friends…"
          className="pl-9 bg-card/60 border-border/60 focus-visible:ring-[var(--gold)]"
        />
      </div>

      {online.length > 0 ? (
        <div>
          <GroupHeader label={`Online — ${online.length}`} />
          <div className="grid gap-3 sm:grid-cols-2">
            {online.map((f) => (
              <FriendCard
                key={f.id}
                friend={f}
                onMessage={onMessage}
                onParty={onParty}
                onArena={onArena}
                onRemove={onRemove}
              />
            ))}
          </div>
        </div>
      ) : null}

      {offline.length > 0 ? (
        <div>
          <GroupHeader label={`Offline — ${offline.length}`} />
          <div className="grid gap-3 sm:grid-cols-2 opacity-70">
            {offline.map((f) => (
              <FriendCard
                key={f.id}
                friend={f}
                onMessage={onMessage}
                onParty={onParty}
                onArena={onArena}
                onRemove={onRemove}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function GroupHeader({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 mb-2">
      <span className="font-display text-[10px] tracking-[0.3em] uppercase text-gold-dim">{label}</span>
      <div className="flex-1 h-px bg-gradient-to-r from-[var(--gold)]/40 to-transparent" />
    </div>
  );
}

function RequestsTab({
  requests,
  onAccept,
  onDecline,
  onCancel,
}: {
  requests: FriendRequest[];
  onAccept: (r: FriendRequest) => void;
  onDecline: (r: FriendRequest) => void;
  onCancel: (r: FriendRequest) => void;
}) {
  const incoming = requests.filter((r) => r.direction === "incoming");
  const outgoing = requests.filter((r) => r.direction === "outgoing");

  if (requests.length === 0) {
    return (
      <EmptyState
        icon={<UserPlus className="w-6 h-6" />}
        title="No pending requests"
        hint="When someone seeks your fellowship, they'll appear here."
      />
    );
  }

  return (
    <div className="space-y-5">
      {incoming.length > 0 ? (
        <section>
          <GroupHeader label={`Incoming — ${incoming.length}`} />
          <div className="grid gap-2">
            {incoming.map((r) => (
              <RequestRow
                key={r.id}
                req={r}
                primary={{ label: "Accept", icon: <Check className="w-4 h-4" />, onClick: () => onAccept(r) }}
                secondary={{ label: "Decline", icon: <X className="w-4 h-4" />, onClick: () => onDecline(r) }}
              />
            ))}
          </div>
        </section>
      ) : null}
      {outgoing.length > 0 ? (
        <section>
          <GroupHeader label={`Sent — ${outgoing.length}`} />
          <div className="grid gap-2">
            {outgoing.map((r) => (
              <RequestRow
                key={r.id}
                req={r}
                secondary={{ label: "Cancel", icon: <X className="w-4 h-4" />, onClick: () => onCancel(r) }}
              />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function RequestRow({
  req,
  primary,
  secondary,
}: {
  req: FriendRequest;
  primary?: { label: string; icon: React.ReactNode; onClick: () => void };
  secondary?: { label: string; icon: React.ReactNode; onClick: () => void };
}) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-border/60 bg-card/60 p-3">
      <Avatar name={req.display} size={40} />
      <div className="min-w-0 flex-1">
        <div className="font-display text-foreground truncate">
          {req.display}
          {req.level > 0 ? (
            <span className="ml-2 text-[10px] text-gold border border-[var(--gold-dim)]/50 px-1 py-0.5 rounded">
              LVL {req.level}
            </span>
          ) : null}
        </div>
        <div className="text-xs text-muted-foreground truncate">
          {req.username} · {req.className}
        </div>
        {req.sentAt ? <div className="text-[10px] text-muted-foreground/70">{req.sentAt}</div> : null}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {primary ? (
          <Button
            onClick={primary.onClick}
            size="sm"
            className="bg-gradient-to-b from-[var(--gold-bright)] to-[var(--gold-dim)] text-background hover:brightness-110 border-0"
          >
            {primary.icon}
            <span className="ml-1 hidden sm:inline">{primary.label}</span>
          </Button>
        ) : null}
        {secondary ? (
          <Button
            onClick={secondary.onClick}
            size="sm"
            variant="outline"
            className="border-border/60 hover:border-[var(--blood)]/60 hover:text-[var(--blood)]"
          >
            {secondary.icon}
            <span className="ml-1 hidden sm:inline">{secondary.label}</span>
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function FindTab({
  query,
  suggestions,
  showSuggestions,
  onQueryChange,
  onShowSuggestions,
  onSendRequest,
  onPick,
}: {
  query: string;
  suggestions: PlayerSearchHit[];
  showSuggestions: boolean;
  onQueryChange: (v: string) => void;
  onShowSuggestions: (v: boolean) => void;
  onSendRequest: (username: string) => void;
  onPick: (username: string) => void;
}) {
  const trimmed = query.trim().replace(/^@/, "");
  const canSend = trimmed.length >= 2;

  return (
    <div className="space-y-4">
      <OrnateFrame>
        <SectionTitle eyebrow="Seek a hero" title="Add by @username" />
        <div className="relative flex-1">
          <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gold-dim z-10" />
          <Input
            value={query}
            onChange={(e) => {
              onQueryChange(e.target.value);
              onShowSuggestions(true);
            }}
            onFocus={() => onShowSuggestions(true)}
            onBlur={() => setTimeout(() => onShowSuggestions(false), 150)}
            placeholder="@username"
            className="pl-9 bg-black/40 border-border/60 focus-visible:ring-[var(--gold)] font-mono"
          />
          {showSuggestions && suggestions.length > 0 ? (
            <ul className="absolute z-20 mt-1 w-full rounded-md border border-border/80 bg-background/95 shadow-lg text-xs max-h-36 overflow-y-auto backdrop-blur-sm">
              {suggestions.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className="w-full text-left px-3 py-2 hover:bg-muted/80 transition-colors"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => onPick(p.username.replace(/^@/, ""))}
                  >
                    <span className="font-medium text-foreground">{p.username}</span>
                    {p.display ? <span className="text-muted-foreground"> · {p.display}</span> : null}
                    {p.level != null ? <span className="text-muted-foreground"> · Lv {p.level}</span> : null}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <div className="mt-3">
          <Button
            disabled={!canSend}
            onClick={() => onSendRequest(trimmed)}
            className="w-full sm:w-auto bg-gradient-to-b from-[var(--gold-bright)] to-[var(--gold-dim)] text-background hover:brightness-110 border-0 font-display tracking-widest uppercase"
          >
            <UserPlus className="w-4 h-4" /> Send Request
          </Button>
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Search by Discord <span className="text-gold">@username</span>. They must accept before you can whisper.
        </p>
      </OrnateFrame>
    </div>
  );
}

function ChatTab({
  friends,
  threads,
  activeThreadId,
  totalUnread,
  onOpenThread,
  onCloseThread,
  onSend,
}: {
  friends: Friend[];
  threads: Record<string, ChatMessage[]>;
  activeThreadId: string | null;
  totalUnread: number;
  onOpenThread: (friendId: string) => void;
  onCloseThread: () => void;
  onSend: (text: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const activeFriend = friends.find((f) => f.id === activeThreadId);
  const messages = activeThreadId ? threads[activeThreadId] ?? [] : [];
  const showList = !activeThreadId;

  const threadList = useMemo(() => {
    const withActivity = friends.filter((f) => (threads[f.id]?.length ?? 0) > 0 || (f.unread ?? 0) > 0);
    const rest = friends.filter((f) => !withActivity.includes(f));
    return [...withActivity, ...rest];
  }, [friends, threads]);

  if (friends.length === 0) {
    return (
      <EmptyState
        icon={<MessageCircle className="w-6 h-6" />}
        title="No friends to message"
        hint="Add friends first, then return here to whisper."
      />
    );
  }

  return (
    <div className="grid sm:grid-cols-[280px_1fr] gap-3 min-h-[360px] sm:min-h-[480px]">
      <div className={cn("ornate-frame rounded-lg p-2", !showList && "hidden sm:block")}>
        <div className="px-2 py-1 text-[10px] tracking-[0.3em] uppercase text-gold-dim font-display">Whispers</div>
        <ScrollArea className="h-[320px] sm:h-[440px]">
          <div className="space-y-1 pr-2">
            {threadList.map((f) => {
              const last = threads[f.id]?.slice(-1)[0];
              const preview = last?.text ?? f.lastPreview;
              const active = activeThreadId === f.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => onOpenThread(f.id)}
                  className={cn(
                    "w-full flex items-center gap-2 p-2 rounded-md text-left transition border",
                    active ? "bg-[var(--gold)]/10 border-[var(--gold-dim)]/50" : "border-transparent hover:bg-white/5",
                  )}
                >
                  <Avatar name={f.display} presence={f.presence} size={36} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-display text-sm truncate">{f.display}</span>
                      {(f.unread ?? 0) > 0 ? (
                        <Badge className="ml-auto bg-[var(--blood)] text-white border-0 h-4 px-1.5 text-[10px]">
                          {f.unread}
                        </Badge>
                      ) : null}
                    </div>
                    <div className="text-[11px] text-muted-foreground truncate">{preview ?? "Start a whisper…"}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </ScrollArea>
      </div>

      <div className={cn("ornate-frame rounded-lg flex flex-col min-h-[360px]", showList && "hidden sm:flex")}>
        {!activeFriend ? (
          <div className="flex-1 grid place-items-center text-center p-6">
            <div>
              <MessageCircle className="w-8 h-8 text-gold-dim mx-auto mb-2" />
              <div className="font-display text-gold-bright">Select a whisper</div>
              <p className="text-xs text-muted-foreground mt-1">Choose an ally from the left to begin.</p>
              {totalUnread > 0 ? (
                <p className="text-[10px] text-primary mt-3">{totalUnread} unread while you were away.</p>
              ) : null}
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-3 p-3 border-b border-[var(--gold-dim)]/30">
              <button type="button" className="sm:hidden text-muted-foreground" onClick={onCloseThread}>
                <ChevronLeft className="w-5 h-5" />
              </button>
              <Avatar name={activeFriend.display} presence={activeFriend.presence} size={36} />
              <div className="min-w-0 flex-1">
                <div className="font-display truncate">{activeFriend.display}</div>
                <div className="text-[11px] text-muted-foreground truncate">
                  {presenceStyle[activeFriend.presence].label}
                  {activeFriend.zone ? ` · ${activeFriend.zone}` : ""}
                </div>
              </div>
            </div>

            <ScrollArea className="flex-1 p-3">
              <div className="space-y-2">
                {messages.map((m) => {
                  const mine = m.from === "me";
                  return (
                    <div key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
                      <div
                        className={cn(
                          "max-w-[78%] rounded-lg px-3 py-2 text-sm border",
                          mine
                            ? "bg-gradient-to-br from-[var(--gold)]/25 to-[var(--gold)]/10 border-[var(--gold-dim)]/40 text-foreground"
                            : "bg-black/40 border-border/60 text-foreground/90",
                        )}
                      >
                        <div>{m.text}</div>
                        {m.ts ? <div className="text-[10px] text-muted-foreground mt-1 text-right">{m.ts}</div> : null}
                      </div>
                    </div>
                  );
                })}
                {messages.length === 0 ? (
                  <div className="text-center text-xs text-muted-foreground py-10">No messages yet — say hello.</div>
                ) : null}
              </div>
            </ScrollArea>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                const t = draft.trim();
                if (!t) return;
                onSend(t);
                setDraft("");
              }}
              className="p-2 border-t border-[var(--gold-dim)]/30 flex gap-2"
            >
              <Input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Whisper a message…"
                maxLength={500}
                className="bg-black/40 border-border/60 focus-visible:ring-[var(--gold)]"
              />
              <Button
                type="submit"
                className="bg-gradient-to-b from-[var(--gold-bright)] to-[var(--gold-dim)] text-background hover:brightness-110 border-0 shrink-0"
              >
                <Send className="w-4 h-4" />
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

function PrivacyTab({
  appearOffline,
  allowWhispersFromStrangers,
  allowPartyInvitesFromStrangers,
  settingsSaving,
  onToggleAppearOffline,
  onToggleAllowWhispers,
  onToggleAllowPartyInvites,
  ignoreQuery,
  ignoreSuggestions,
  showIgnoreSuggestions,
  onIgnoreQueryChange,
  onShowIgnoreSuggestions,
  onBlock,
  blocked,
  onUnblock,
}: {
  appearOffline: boolean;
  allowWhispersFromStrangers: boolean;
  allowPartyInvitesFromStrangers: boolean;
  settingsSaving?: boolean;
  onToggleAppearOffline: () => void;
  onToggleAllowWhispers: () => void;
  onToggleAllowPartyInvites: () => void;
  ignoreQuery: string;
  ignoreSuggestions: PlayerSearchHit[];
  showIgnoreSuggestions: boolean;
  onIgnoreQueryChange: (v: string) => void;
  onShowIgnoreSuggestions: (v: boolean) => void;
  onBlock: (username: string) => void;
  blocked: BlockedPlayer[];
  onUnblock: (id: string) => void;
}) {
  return (
    <div className="space-y-4">
      <OrnateFrame>
        <SectionTitle eyebrow="Veil & Wards" title="Privacy" />
        <div className="space-y-1">
          <ToggleRow
            icon={<EyeOff className="w-4 h-4" />}
            title="Appear Offline"
            desc="Friends see you as offline. Party and Arena invites from blocked players are still rejected."
            checked={appearOffline}
            disabled={settingsSaving}
            onChange={onToggleAppearOffline}
          />
          <ToggleRow
            icon={<MessageCircle className="w-4 h-4" />}
            title="Allow Whispers"
            desc="Let strangers send you private messages."
            checked={allowWhispersFromStrangers}
            disabled={settingsSaving}
            onChange={onToggleAllowWhispers}
          />
          <ToggleRow
            icon={<Users className="w-4 h-4" />}
            title="Allow Party Invites"
            desc="Receive invitations from non-friends."
            checked={allowPartyInvitesFromStrangers}
            disabled={settingsSaving}
            onChange={onToggleAllowPartyInvites}
          />
        </div>
      </OrnateFrame>

      <OrnateFrame>
        <SectionTitle eyebrow="Banished" title="Block List" />
        <p className="text-[11px] text-muted-foreground mb-3 -mt-2">
          Blocked players cannot friend you, invite you to parties, or challenge you in Arena.
        </p>
        <div className="relative mb-3">
          <Ban className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground z-10" />
          <Input
            value={ignoreQuery}
            onChange={(e) => {
              onIgnoreQueryChange(e.target.value);
              onShowIgnoreSuggestions(true);
            }}
            onFocus={() => onShowIgnoreSuggestions(true)}
            onBlur={() => setTimeout(() => onShowIgnoreSuggestions(false), 150)}
            placeholder="@username to block"
            className="pl-9 bg-black/40 border-border/60 focus-visible:ring-[var(--gold)]"
          />
          {showIgnoreSuggestions && ignoreSuggestions.length > 0 ? (
            <ul className="absolute z-20 mt-1 w-full rounded-md border border-border/80 bg-background/95 shadow-lg text-xs max-h-36 overflow-y-auto backdrop-blur-sm">
              {ignoreSuggestions.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className="w-full text-left px-3 py-2 hover:bg-muted/80"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => onBlock(p.username.replace(/^@/, ""))}
                  >
                    <span className="font-medium">{p.username}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        {blocked.length === 0 ? (
          <div className="text-xs text-muted-foreground">No one is blocked.</div>
        ) : (
          <div className="space-y-2">
            {blocked.map((b) => (
              <div key={b.id} className="flex items-center gap-3 p-2 rounded-md border border-border/60 bg-black/30">
                <Ban className="w-4 h-4 text-[var(--blood)] shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="font-display truncate">{b.display}</div>
                  <div className="text-[11px] text-muted-foreground truncate">{b.username}</div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  onClick={() => onUnblock(b.id)}
                  className="border-border/60 hover:border-[var(--gold-dim)] hover:text-gold-bright"
                >
                  Unblock
                </Button>
              </div>
            ))}
          </div>
        )}
      </OrnateFrame>
    </div>
  );
}

function ToggleRow({
  icon,
  title,
  desc,
  checked,
  disabled,
  onChange,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  checked: boolean;
  disabled?: boolean;
  onChange: () => void;
}) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-border/40 last:border-0">
      <div className="mt-0.5 text-gold-dim">{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="font-display text-sm">{title}</div>
        <div className="text-[11px] text-muted-foreground">{desc}</div>
      </div>
      <Switch checked={checked} disabled={disabled} onCheckedChange={() => onChange()} />
    </div>
  );
}

function EmptyState({
  icon,
  title,
  hint,
  actionLabel,
  onAction,
}: {
  icon: React.ReactNode;
  title: string;
  hint: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <OrnateFrame className="text-center py-10">
      <div className="mx-auto w-12 h-12 rounded-full grid place-items-center border border-[var(--gold-dim)]/40 text-gold-dim mb-3">
        {icon}
      </div>
      <div className="font-display text-gold-bright">{title}</div>
      <p className="text-xs text-muted-foreground mt-1 max-w-xs mx-auto">{hint}</p>
      {actionLabel && onAction ? (
        <Button type="button" size="sm" variant="secondary" className="mt-4 font-display" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </OrnateFrame>
  );
}

function LiveEventsCard({
  events,
  onJoin,
}: {
  events: LiveEventDisplay[];
  onJoin: (event: LiveEventDisplay) => void;
}) {
  if (!events.length) return null;
  return (
    <OrnateFrame>
      <div className="flex items-center justify-between mb-3">
        <SectionTitle eyebrow="Realm Pulse" title="Live Events" />
        <Calendar className="w-4 h-4 text-gold-dim" />
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {events.map((e) => (
          <div
            key={e.id}
            className="flex items-center gap-3 p-3 rounded-md border border-[var(--gold-dim)]/40 bg-gradient-to-br from-black/40 to-[var(--gold)]/5"
          >
            <div className="w-10 h-10 rounded-md grid place-items-center border border-[var(--gold-dim)]/40 bg-black/40 shrink-0">
              {e.type === "world-boss" && <Swords className="w-5 h-5 text-[var(--blood)]" />}
              {e.type === "arena" && <Shield className="w-5 h-5 text-[var(--arcane)]" />}
              {(e.type === "raid" || e.type === "bonus") && <Sparkles className="w-5 h-5 text-gold-bright" />}
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-display text-sm truncate">{e.title}</div>
              {e.description ? (
                <p className="text-[11px] text-muted-foreground line-clamp-2">{e.description}</p>
              ) : null}
              <div className="text-[10px] text-gold-dim mt-1 uppercase tracking-wider">{e.starts}</div>
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="shrink-0 border-[var(--gold-dim)]/50 hover:text-gold-bright hover:border-[var(--gold)]"
              onClick={() => onJoin(e)}
            >
              Join
            </Button>
          </div>
        ))}
      </div>
    </OrnateFrame>
  );
}
