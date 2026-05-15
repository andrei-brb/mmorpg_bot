import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WomPanel, WomSectionHeader } from "@/components/wom/WomUi";
import type {
  SocialFriendRow,
  SocialIgnoreRow,
  SocialPlayerSearchRow,
  SocialRequestRow,
  SocialWhisperMessage,
} from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";
import { cn } from "@/lib/utils";

function formatLastSeen(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return d.toLocaleDateString();
}

function FriendAvatar({ username, online }: { username: string; online?: boolean }) {
  const initial = (username || "?").charAt(0).toUpperCase();
  return (
    <div className="relative shrink-0">
      <div className="flex h-9 w-9 items-center justify-center rounded-full border border-border/60 bg-muted/40 font-cinzel text-sm font-bold text-primary">
        {initial}
      </div>
      <span
        className={cn(
          "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-background",
          online ? "bg-emerald-500" : "bg-muted-foreground/50",
        )}
        aria-hidden
      />
    </div>
  );
}

function PresenceLine({ friend }: { friend: SocialFriendRow }) {
  if (friend.online) {
    return (
      <p className="text-[10px] text-emerald-400/90 truncate">
        Online{friend.zone_hint ? ` · ${friend.zone_hint}` : ""}
      </p>
    );
  }
  return (
    <p className="text-[10px] text-muted-foreground truncate">
      {friend.last_seen ? `Last seen ${formatLastSeen(friend.last_seen)}` : "Offline"}
    </p>
  );
}

function UsernameSearch({
  value,
  onChange,
  suggestions,
  showSuggestions,
  onShowSuggestions,
  placeholder,
  onPick,
}: {
  value: string;
  onChange: (v: string) => void;
  suggestions: SocialPlayerSearchRow[];
  showSuggestions: boolean;
  onShowSuggestions: (v: boolean) => void;
  placeholder: string;
  onPick: (username: string) => void;
}) {
  return (
    <div className="relative">
      <Input
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          onShowSuggestions(true);
        }}
        onFocus={() => onShowSuggestions(true)}
        onBlur={() => setTimeout(() => onShowSuggestions(false), 150)}
        placeholder={placeholder}
        className="text-xs h-9"
      />
      {showSuggestions && suggestions.length > 0 ? (
        <ul className="absolute z-20 mt-1 w-full rounded-md border border-border/80 bg-background/95 shadow-lg text-xs max-h-36 overflow-y-auto backdrop-blur-sm">
          {suggestions.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className="w-full text-left px-3 py-2 hover:bg-muted/80 transition-colors"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => onPick(p.username)}
              >
                <span className="font-medium text-foreground">@{p.username}</span>
                {p.character_name ? (
                  <span className="text-muted-foreground"> · {p.character_name}</span>
                ) : null}
                {p.level != null ? <span className="text-muted-foreground"> · Lv {p.level}</span> : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

type SocialPanelProps = {
  accessToken: string | null;
  guildId?: string;
};

type SocialSubTab = "friends" | "requests" | "find" | "messages" | "blocked";

export function SocialPanel({ accessToken, guildId }: SocialPanelProps) {
  const [subTab, setSubTab] = useState<SocialSubTab>("friends");
  const [friends, setFriends] = useState<SocialFriendRow[]>([]);
  const [incoming, setIncoming] = useState<SocialRequestRow[]>([]);
  const [outgoing, setOutgoing] = useState<SocialRequestRow[]>([]);
  const [ignored, setIgnored] = useState<SocialIgnoreRow[]>([]);
  const [loading, setLoading] = useState(true);

  const [addQuery, setAddQuery] = useState("");
  const [addSuggestions, setAddSuggestions] = useState<SocialPlayerSearchRow[]>([]);
  const [showAddSuggestions, setShowAddSuggestions] = useState(false);

  const [ignoreQuery, setIgnoreQuery] = useState("");
  const [ignoreSuggestions, setIgnoreSuggestions] = useState<SocialPlayerSearchRow[]>([]);
  const [showIgnoreSuggestions, setShowIgnoreSuggestions] = useState(false);

  const [whisperFriend, setWhisperFriend] = useState<SocialFriendRow | null>(null);
  const [whispers, setWhispers] = useState<SocialWhisperMessage[]>([]);
  const [whisperDraft, setWhisperDraft] = useState("");
  const whisperEndRef = useRef<HTMLDivElement>(null);

  const requestCount = incoming.length + outgoing.length;

  const refreshAll = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const [roster, reqs, ign] = await Promise.all([
        api.getSocialRoster(accessToken, guildId),
        api.getSocialRequests(accessToken, guildId),
        api.getSocialIgnore(accessToken, guildId),
      ]);
      setFriends(roster.friends || []);
      setIncoming(reqs.incoming || []);
      setOutgoing(reqs.outgoing || []);
      setIgnored(ign.ignored || []);
    } catch {
      toast.error("Could not load social data.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, guildId]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (!accessToken) return;
    const id = setInterval(() => void refreshAll(), 12_000);
    return () => clearInterval(id);
  }, [accessToken, refreshAll]);

  const fetchSuggestions = useCallback(
    async (
      query: string,
      setter: (rows: SocialPlayerSearchRow[]) => void,
      purpose: "friend" | "ignore",
    ) => {
      if (!accessToken || query.trim().length < 1) {
        setter([]);
        return;
      }
      try {
        const data = await api.getSocialPlayersSearch(accessToken, query.trim(), guildId, purpose);
        setter(data.players || []);
      } catch {
        setter([]);
      }
    },
    [accessToken, guildId],
  );

  useEffect(() => {
    const t = setTimeout(() => void fetchSuggestions(addQuery, setAddSuggestions, "friend"), 250);
    return () => clearTimeout(t);
  }, [addQuery, fetchSuggestions]);

  useEffect(() => {
    const t = setTimeout(() => void fetchSuggestions(ignoreQuery, setIgnoreSuggestions, "ignore"), 250);
    return () => clearTimeout(t);
  }, [ignoreQuery, fetchSuggestions]);

  const loadWhispers = useCallback(async () => {
    if (!accessToken || !whisperFriend) return;
    try {
      const data = await api.getSocialWhispers(accessToken, whisperFriend.user_id, guildId);
      setWhispers(data.messages || []);
    } catch {
      setWhispers([]);
    }
  }, [accessToken, guildId, whisperFriend]);

  useEffect(() => {
    if (!whisperFriend) {
      setWhispers([]);
      return;
    }
    void loadWhispers();
    const id = setInterval(() => void loadWhispers(), 8_000);
    return () => clearInterval(id);
  }, [whisperFriend, loadWhispers]);

  useEffect(() => {
    whisperEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [whispers]);

  useEffect(() => {
    if (subTab === "messages" && friends.length > 0 && !whisperFriend) {
      setWhisperFriend(friends[0]);
    }
  }, [subTab, friends, whisperFriend]);

  const openWhisper = (friend: SocialFriendRow) => {
    setWhisperFriend(friend);
    setSubTab("messages");
  };

  const sendFriendRequest = async (username: string) => {
    if (!accessToken) return;
    const res = await api.postSocialFriendRequest(accessToken, { username }, guildId);
    if (res.ok) {
      toast.success(res.message || "Request sent.");
      setAddQuery("");
      setShowAddSuggestions(false);
      setSubTab("requests");
      void refreshAll();
    } else toast.error(res.message || "Could not send request.");
  };

  const acceptRequest = async (requestId: string) => {
    if (!accessToken) return;
    const res = await api.postSocialFriendAccept(accessToken, requestId, guildId);
    if (res.ok) {
      toast.success(res.message || "Friend added.");
      void refreshAll();
    } else toast.error(res.message || "Failed.");
  };

  const declineRequest = async (requestId: string) => {
    if (!accessToken) return;
    const res = await api.postSocialFriendDecline(accessToken, requestId, guildId);
    if (res.ok) {
      toast.info(res.message || "Declined.");
      void refreshAll();
    } else toast.error(res.message || "Failed.");
  };

  const unfriend = async (userId: string, username: string) => {
    if (!accessToken) return;
    if (!window.confirm(`Remove @${username} from your friends?`)) return;
    const res = await api.deleteSocialFriend(accessToken, userId, guildId);
    if (res.ok) {
      toast.info(res.message || "Unfriended.");
      if (whisperFriend?.user_id === userId) setWhisperFriend(null);
      void refreshAll();
    } else toast.error(res.message || "Failed.");
  };

  const addIgnore = async (username: string) => {
    if (!accessToken) return;
    const res = await api.postSocialIgnore(accessToken, { username }, guildId);
    if (res.ok) {
      toast.success(res.message || "Ignored.");
      setIgnoreQuery("");
      setShowIgnoreSuggestions(false);
      void refreshAll();
    } else toast.error(res.message || "Failed.");
  };

  const removeIgnore = async (userId: string) => {
    if (!accessToken) return;
    const res = await api.deleteSocialIgnore(accessToken, userId, guildId);
    if (res.ok) {
      toast.info(res.message || "Removed from ignore.");
      void refreshAll();
    } else toast.error(res.message || "Failed.");
  };

  const sendWhisper = async () => {
    if (!accessToken || !whisperFriend) return;
    const body = whisperDraft.trim();
    if (!body) return;
    const res = await api.postSocialWhisper(accessToken, whisperFriend.user_id, body, guildId);
    if (res.ok) {
      setWhisperDraft("");
      void loadWhispers();
    } else toast.error(res.message || "Could not send whisper.");
  };

  const inviteToParty = async (userId: string) => {
    if (!accessToken) return;
    const res = await api.postDungeonPartyInvite(accessToken, userId, guildId);
    if (res.ok) toast.success(res.message || "Party invite sent.");
    else toast.error(res.message || "Start a dungeon party first, then invite.");
  };

  if (!accessToken) {
    return <p className="text-xs text-muted-foreground">Sign in to use social features.</p>;
  }

  return (
    <WomPanel glow className="flex flex-col min-h-0 flex-1">
      <WomSectionHeader kicker="Realm" title="Social" />
      <Tabs
        value={subTab}
        onValueChange={(v) => setSubTab(v as SocialSubTab)}
        className="flex flex-col flex-1 min-h-0"
      >
        <TabsList
          className={cn(
            "h-auto w-full shrink-0 grid grid-cols-5 gap-0.5 p-1",
            "bg-muted/40 border border-border/40 rounded-sm",
          )}
        >
          <TabsTrigger
            value="friends"
            className="text-[9px] sm:text-[10px] px-1 py-2 data-[state=active]:bg-background/90 font-cinzel uppercase tracking-wide"
          >
            Friends{friends.length > 0 ? ` (${friends.length})` : ""}
          </TabsTrigger>
          <TabsTrigger
            value="requests"
            className="text-[9px] sm:text-[10px] px-1 py-2 data-[state=active]:bg-background/90 font-cinzel uppercase tracking-wide relative"
          >
            Requests
            {incoming.length > 0 ? (
              <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-3.5 px-0.5 rounded-full bg-primary text-[8px] text-primary-foreground flex items-center justify-center">
                {incoming.length}
              </span>
            ) : null}
          </TabsTrigger>
          <TabsTrigger
            value="find"
            className="text-[9px] sm:text-[10px] px-1 py-2 data-[state=active]:bg-background/90 font-cinzel uppercase tracking-wide"
          >
            Find
          </TabsTrigger>
          <TabsTrigger
            value="messages"
            className="text-[9px] sm:text-[10px] px-1 py-2 data-[state=active]:bg-background/90 font-cinzel uppercase tracking-wide"
          >
            Chat
          </TabsTrigger>
          <TabsTrigger
            value="blocked"
            className="text-[9px] sm:text-[10px] px-1 py-2 data-[state=active]:bg-background/90 font-cinzel uppercase tracking-wide"
          >
            Blocked
          </TabsTrigger>
        </TabsList>

        {loading ? (
          <p className="text-xs text-muted-foreground mt-3 px-1">Loading…</p>
        ) : null}

        <TabsContent value="friends" className="flex-1 min-h-0 overflow-y-auto mt-2 space-y-2 pr-0.5 pb-1 data-[state=inactive]:hidden">
          {friends.length === 0 ? (
            <div className="rounded-sm border border-dashed border-border/50 p-4 text-center">
              <p className="text-xs text-muted-foreground mb-2">No friends yet.</p>
              <Button type="button" size="sm" variant="secondary" className="font-cinzel text-xs" onClick={() => setSubTab("find")}>
                Find players
              </Button>
            </div>
          ) : (
            <ul className="space-y-2">
              {friends.map((f) => (
                <li
                  key={f.user_id}
                  className="flex gap-3 rounded-sm border border-border/40 bg-muted/20 p-2.5 hover:border-border/70 transition-colors"
                >
                  <FriendAvatar username={f.username} online={f.online} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground truncate">
                      @{f.username}
                    </p>
                    {f.character_name || f.level != null ? (
                      <p className="text-[10px] text-muted-foreground truncate">
                        {f.character_name}
                        {f.level != null ? ` · Lv ${f.level}` : ""}
                        {f.class ? ` ${f.class}` : ""}
                      </p>
                    ) : null}
                    <PresenceLine friend={f} />
                    <div className="flex flex-wrap gap-1 mt-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="h-7 text-[10px] font-cinzel px-2"
                        onClick={() => openWhisper(f)}
                      >
                        Message
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="h-7 text-[10px] font-cinzel px-2"
                        onClick={() => void inviteToParty(f.user_id)}
                      >
                        Party
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 text-[10px] text-muted-foreground px-2"
                        onClick={() => void unfriend(f.user_id, f.username)}
                      >
                        Remove
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </TabsContent>

        <TabsContent value="requests" className="flex-1 min-h-0 overflow-y-auto mt-2 space-y-3 pr-0.5 pb-1 data-[state=inactive]:hidden">
          {requestCount === 0 ? (
            <p className="text-xs text-muted-foreground px-1">No pending friend requests.</p>
          ) : (
            <>
              {incoming.length > 0 ? (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2 px-1">
                    Incoming ({incoming.length})
                  </p>
                  <ul className="space-y-2">
                    {incoming.map((r) => (
                      <li
                        key={r.request_id}
                        className="flex flex-wrap items-center gap-2 rounded-sm border border-border/40 bg-muted/20 p-2.5"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">@{r.username}</p>
                          {r.character_name ? (
                            <p className="text-[10px] text-muted-foreground">{r.character_name}</p>
                          ) : null}
                        </div>
                        <Button size="sm" className="h-7 text-[10px] font-cinzel" onClick={() => void acceptRequest(r.request_id)}>
                          Accept
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-[10px] font-cinzel"
                          onClick={() => void declineRequest(r.request_id)}
                        >
                          Decline
                        </Button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {outgoing.length > 0 ? (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2 px-1">
                    Sent ({outgoing.length})
                  </p>
                  <ul className="space-y-1.5">
                    {outgoing.map((r) => (
                      <li
                        key={r.request_id}
                        className="flex items-center justify-between rounded-sm border border-border/30 px-2.5 py-2 text-xs"
                      >
                        <span className="text-foreground">@{r.username}</span>
                        <span className="text-muted-foreground text-[10px] uppercase">Pending</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          )}
        </TabsContent>

        <TabsContent value="find" className="flex-1 min-h-0 overflow-y-auto mt-2 pr-0.5 pb-1 data-[state=inactive]:hidden">
          <p className="text-xs text-muted-foreground mb-3 px-1 leading-relaxed">
            Search any player globally by Discord username. They must accept your request before you can chat.
          </p>
          <UsernameSearch
            value={addQuery}
            onChange={setAddQuery}
            suggestions={addSuggestions}
            showSuggestions={showAddSuggestions}
            onShowSuggestions={setShowAddSuggestions}
            placeholder="@username"
            onPick={(u) => void sendFriendRequest(u)}
          />
        </TabsContent>

        <TabsContent
          value="messages"
          className="flex-1 min-h-0 mt-2 flex flex-col gap-2 pb-1 data-[state=inactive]:hidden"
        >
          {friends.length === 0 ? (
            <p className="text-xs text-muted-foreground px-1">Add friends to send whispers.</p>
          ) : (
            <>
              <div className="flex gap-1 overflow-x-auto pb-1 shrink-0">
                {friends.map((f) => (
                  <button
                    key={f.user_id}
                    type="button"
                    onClick={() => setWhisperFriend(f)}
                    className={cn(
                      "shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-cinzel transition-colors",
                      whisperFriend?.user_id === f.user_id
                        ? "border-primary bg-primary/15 text-primary"
                        : "border-border/50 text-muted-foreground hover:text-foreground",
                    )}
                  >
                    @{f.username}
                  </button>
                ))}
              </div>
              {whisperFriend ? (
                <div className="flex flex-col flex-1 min-h-0 rounded-sm border border-border/50 bg-muted/10">
                  <div className="border-b border-border/40 px-3 py-2 shrink-0">
                    <p className="text-xs font-cinzel text-primary">@{whisperFriend.username}</p>
                    <PresenceLine friend={whisperFriend} />
                  </div>
                  <div className="flex-1 min-h-[120px] max-h-44 overflow-y-auto p-2 space-y-1.5 text-xs">
                    {whispers.length === 0 ? (
                      <p className="text-muted-foreground text-center py-4">Say hello.</p>
                    ) : (
                      whispers.map((m) => (
                        <div
                          key={m.id}
                          className={cn(
                            "rounded-md px-2.5 py-1.5 max-w-[85%] break-words",
                            m.mine
                              ? "ml-auto bg-primary/25 text-foreground border border-primary/20"
                              : "bg-muted/60 text-foreground border border-border/30",
                          )}
                        >
                          {m.body}
                        </div>
                      ))
                    )}
                    <div ref={whisperEndRef} />
                  </div>
                  <div className="flex gap-2 p-2 border-t border-border/40 shrink-0">
                    <Input
                      value={whisperDraft}
                      onChange={(e) => setWhisperDraft(e.target.value)}
                      placeholder="Type a whisper…"
                      className="text-xs h-8 flex-1"
                      maxLength={500}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          void sendWhisper();
                        }
                      }}
                    />
                    <Button type="button" size="sm" className="font-cinzel shrink-0 h-8" onClick={() => void sendWhisper()}>
                      Send
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground text-center py-6">Select a friend above to chat.</p>
              )}
            </>
          )}
        </TabsContent>

        <TabsContent value="blocked" className="flex-1 min-h-0 overflow-y-auto mt-2 space-y-3 pr-0.5 pb-1 data-[state=inactive]:hidden">
          <p className="text-xs text-muted-foreground px-1 leading-relaxed">
            Ignored players cannot send you friend requests. Removing someone does not re-add them as a friend.
          </p>
          <UsernameSearch
            value={ignoreQuery}
            onChange={setIgnoreQuery}
            suggestions={ignoreSuggestions}
            showSuggestions={showIgnoreSuggestions}
            onShowSuggestions={setShowIgnoreSuggestions}
            placeholder="@username to block"
            onPick={(u) => void addIgnore(u)}
          />
          {ignored.length === 0 ? (
            <p className="text-xs text-muted-foreground px-1">Nobody blocked.</p>
          ) : (
            <ul className="space-y-1.5">
              {ignored.map((row) => (
                <li
                  key={row.user_id}
                  className="flex items-center justify-between rounded-sm border border-border/40 px-2.5 py-2 text-xs"
                >
                  <span className="font-medium">@{row.username}</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 text-[10px]"
                    onClick={() => void removeIgnore(row.user_id)}
                  >
                    Unblock
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </TabsContent>
      </Tabs>
    </WomPanel>
  );
}
