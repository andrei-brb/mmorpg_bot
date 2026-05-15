import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

function PresencePill({ friend }: { friend: SocialFriendRow }) {
  if (friend.online) {
    return (
      <span className="text-[10px] text-emerald-400/90 uppercase tracking-wide">
        Online{friend.zone_hint ? ` · ${friend.zone_hint}` : ""}
      </span>
    );
  }
  return (
    <span className="text-[10px] text-muted-foreground">
      {friend.last_seen ? `Last seen ${formatLastSeen(friend.last_seen)}` : "Offline"}
    </span>
  );
}

type SocialPanelProps = {
  accessToken: string | null;
  guildId?: string;
};

export function SocialPanel({ accessToken, guildId }: SocialPanelProps) {
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
    const t = setTimeout(() => {
      void fetchSuggestions(addQuery, setAddSuggestions, "friend");
    }, 250);
    return () => clearTimeout(t);
  }, [addQuery, fetchSuggestions]);

  useEffect(() => {
    const t = setTimeout(() => {
      void fetchSuggestions(ignoreQuery, setIgnoreSuggestions, "ignore");
    }, 250);
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

  const sendFriendRequest = async (username: string) => {
    if (!accessToken) return;
    const res = await api.postSocialFriendRequest(accessToken, { username }, guildId);
    if (res.ok) {
      toast.success(res.message || "Request sent.");
      setAddQuery("");
      setShowAddSuggestions(false);
      void refreshAll();
    } else {
      toast.error(res.message || "Could not send request.");
    }
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

  const unfriend = async (userId: string) => {
    if (!accessToken) return;
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
    else toast.error(res.message || "Could not invite — start a dungeon party first.");
  };

  if (!accessToken) {
    return <p className="text-xs text-muted-foreground">Sign in to use social features.</p>;
  }

  return (
    <div className="space-y-3">
      {loading && friends.length === 0 && incoming.length === 0 ? (
        <p className="text-xs text-muted-foreground">Loading social roster…</p>
      ) : null}

      <WomPanel glow>
        <WomSectionHeader kicker="Friends" title="Roster" />
        {friends.length === 0 ? (
          <p className="text-xs text-muted-foreground">No friends yet — send a request below.</p>
        ) : (
          <ul className="space-y-2">
            {friends.map((f) => (
              <li
                key={f.user_id}
                className="flex flex-wrap items-center gap-2 border-b border-border/30 pb-2 last:border-0 last:pb-0"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-foreground">
                    @{f.username}
                    {f.character_name ? (
                      <span className="text-muted-foreground font-normal"> · {f.character_name}</span>
                    ) : null}
                  </div>
                  <PresencePill friend={f} />
                </div>
                <div className="flex flex-wrap gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant={whisperFriend?.user_id === f.user_id ? "default" : "outline"}
                    className="text-[10px] h-7 font-cinzel"
                    onClick={() => setWhisperFriend(f)}
                  >
                    Whisper
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="text-[10px] h-7 font-cinzel"
                    onClick={() => void inviteToParty(f.user_id)}
                  >
                    Invite
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="text-[10px] h-7 text-muted-foreground"
                    onClick={() => void unfriend(f.user_id)}
                  >
                    Remove
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </WomPanel>

      {whisperFriend ? (
        <WomPanel glow>
          <WomSectionHeader
            kicker="Whisper"
            title={`@${whisperFriend.username}`}
            right={
              <button
                type="button"
                className="text-[10px] text-muted-foreground hover:text-foreground"
                onClick={() => setWhisperFriend(null)}
              >
                Close
              </button>
            }
          />
          <div className="max-h-40 overflow-y-auto space-y-1.5 mb-2 pr-1 text-xs">
            {whispers.length === 0 ? (
              <p className="text-muted-foreground">No messages yet.</p>
            ) : (
              whispers.map((m) => (
                <div
                  key={m.id}
                  className={cn(
                    "rounded px-2 py-1 max-w-[90%]",
                    m.mine ? "ml-auto bg-primary/20 text-foreground" : "bg-muted/50 text-foreground",
                  )}
                >
                  {m.body}
                </div>
              ))
            )}
            <div ref={whisperEndRef} />
          </div>
          <div className="flex gap-2">
            <Input
              value={whisperDraft}
              onChange={(e) => setWhisperDraft(e.target.value)}
              placeholder="Whisper…"
              className="text-xs h-8"
              maxLength={500}
              onKeyDown={(e) => {
                if (e.key === "Enter") void sendWhisper();
              }}
            />
            <Button type="button" size="sm" className="font-cinzel shrink-0" onClick={() => void sendWhisper()}>
              Send
            </Button>
          </div>
        </WomPanel>
      ) : null}

      <WomPanel glow>
        <WomSectionHeader kicker="Requests" title="Pending" />
        {incoming.length === 0 && outgoing.length === 0 ? (
          <p className="text-xs text-muted-foreground">No pending requests.</p>
        ) : (
          <div className="space-y-3 text-xs">
            {incoming.length > 0 ? (
              <div>
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Incoming</p>
                <ul className="space-y-2">
                  {incoming.map((r) => (
                    <li key={r.request_id} className="flex flex-wrap items-center gap-2">
                      <span className="text-foreground font-medium">@{r.username}</span>
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
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Outgoing</p>
                <ul className="space-y-1 text-muted-foreground">
                  {outgoing.map((r) => (
                    <li key={r.request_id}>@{r.username} — pending</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        )}
      </WomPanel>

      <WomPanel glow>
        <WomSectionHeader kicker="Add" title="Friend by username" />
        <div className="relative">
          <Input
            value={addQuery}
            onChange={(e) => {
              setAddQuery(e.target.value);
              setShowAddSuggestions(true);
            }}
            onFocus={() => setShowAddSuggestions(true)}
            placeholder="@username"
            className="text-xs h-8"
          />
          {showAddSuggestions && addSuggestions.length > 0 ? (
            <ul className="absolute z-20 mt-1 w-full rounded border border-border bg-background shadow-lg text-xs max-h-32 overflow-y-auto">
              {addSuggestions.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className="w-full text-left px-2 py-1.5 hover:bg-muted/80"
                    onClick={() => {
                      void sendFriendRequest(p.username);
                      setShowAddSuggestions(false);
                    }}
                  >
                    @{p.username}
                    {p.character_name ? ` · ${p.character_name}` : ""}
                    {p.level != null ? ` · Lv ${p.level}` : ""}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </WomPanel>

      <WomPanel glow>
        <WomSectionHeader kicker="Ignore" title="Blocked players" />
        <div className="relative mb-2">
          <Input
            value={ignoreQuery}
            onChange={(e) => {
              setIgnoreQuery(e.target.value);
              setShowIgnoreSuggestions(true);
            }}
            onFocus={() => setShowIgnoreSuggestions(true)}
            placeholder="@username to ignore"
            className="text-xs h-8"
          />
          {showIgnoreSuggestions && ignoreSuggestions.length > 0 ? (
            <ul className="absolute z-20 mt-1 w-full rounded border border-border bg-background shadow-lg text-xs max-h-32 overflow-y-auto">
              {ignoreSuggestions.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className="w-full text-left px-2 py-1.5 hover:bg-muted/80"
                    onClick={() => {
                      void addIgnore(p.username);
                      setShowIgnoreSuggestions(false);
                    }}
                  >
                    @{p.username}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        {ignored.length === 0 ? (
          <p className="text-xs text-muted-foreground">Nobody ignored.</p>
        ) : (
          <ul className="text-xs space-y-1">
            {ignored.map((row) => (
              <li key={row.user_id} className="flex items-center justify-between gap-2">
                <span>@{row.username}</span>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 text-[10px]"
                  onClick={() => void removeIgnore(row.user_id)}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
      </WomPanel>
    </div>
  );
}
