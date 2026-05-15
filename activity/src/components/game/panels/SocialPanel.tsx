import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { SocialView, type SocialTabId } from "@/components/social/SocialView";
import {
  formatUsername,
  mapBlocked,
  mapFriend,
  mapLiveEvent,
  mapRequest,
  mapWhisper,
} from "@/components/social/socialMappers";
import type {
  BlockedPlayer,
  Friend,
  FriendRequest,
  LiveEventDisplay,
  PlayerSearchHit,
} from "@/components/social/socialTypes";
import type { LiveEventRow, SocialPlayerSearchRow, SocialWhisperMessage } from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";

type SocialPanelProps = {
  accessToken: string | null;
  guildId?: string;
  liveEvents?: LiveEventRow[];
};

function mapSearchHit(p: SocialPlayerSearchRow): PlayerSearchHit {
  return {
    id: p.id,
    username: formatUsername(p.username),
    display: p.character_name || p.username,
    level: p.level,
    className: p.class,
  };
}

export function SocialPanel({ accessToken, guildId, liveEvents = [] }: SocialPanelProps) {
  const [activeTab, setActiveTab] = useState<SocialTabId>("friends");
  const [friends, setFriends] = useState<Friend[]>([]);
  const [incoming, setIncoming] = useState<FriendRequest[]>([]);
  const [outgoing, setOutgoing] = useState<FriendRequest[]>([]);
  const [ignored, setIgnored] = useState<BlockedPlayer[]>([]);
  const [totalUnread, setTotalUnread] = useState(0);
  const [appearOffline, setAppearOffline] = useState(false);
  const [allowWhispersFromStrangers, setAllowWhispersFromStrangers] = useState(false);
  const [allowPartyInvitesFromStrangers, setAllowPartyInvitesFromStrangers] = useState(false);
  const [loading, setLoading] = useState(true);
  const [settingsSaving, setSettingsSaving] = useState(false);

  const [addQuery, setAddQuery] = useState("");
  const [addSuggestions, setAddSuggestions] = useState<PlayerSearchHit[]>([]);
  const [showAddSuggestions, setShowAddSuggestions] = useState(false);

  const [ignoreQuery, setIgnoreQuery] = useState("");
  const [ignoreSuggestions, setIgnoreSuggestions] = useState<PlayerSearchHit[]>([]);
  const [showIgnoreSuggestions, setShowIgnoreSuggestions] = useState(false);

  const [whisperFriendId, setWhisperFriendId] = useState<string | null>(null);
  const [whispers, setWhispers] = useState<SocialWhisperMessage[]>([]);

  const requests = useMemo(() => [...incoming, ...outgoing], [incoming, outgoing]);

  const threads = useMemo(() => {
    const map: Record<string, ReturnType<typeof mapWhisper>[]> = {};
    if (whisperFriendId) {
      map[whisperFriendId] = whispers.map(mapWhisper);
    }
    return map;
  }, [whisperFriendId, whispers]);

  const refreshAll = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    let hadCriticalFailure = false;
    try {
      const [rosterR, reqsR, ignR, settingsR] = await Promise.allSettled([
        api.getSocialRoster(accessToken, guildId),
        api.getSocialRequests(accessToken, guildId),
        api.getSocialIgnore(accessToken, guildId),
        api.getSocialSettings(accessToken, guildId),
      ]);

      if (rosterR.status === "fulfilled") {
        setFriends((rosterR.value.friends || []).map(mapFriend));
        setTotalUnread(rosterR.value.total_unread ?? 0);
      } else {
        hadCriticalFailure = true;
        setFriends([]);
        setTotalUnread(0);
      }

      if (reqsR.status === "fulfilled") {
        setIncoming((reqsR.value.incoming || []).map((r) => mapRequest(r, "incoming")));
        setOutgoing((reqsR.value.outgoing || []).map((r) => mapRequest(r, "outgoing")));
      } else {
        hadCriticalFailure = true;
        setIncoming([]);
        setOutgoing([]);
      }

      if (ignR.status === "fulfilled") {
        setIgnored((ignR.value.ignored || []).map(mapBlocked));
      } else {
        setIgnored([]);
      }

      if (settingsR.status === "fulfilled") {
        setAppearOffline(Boolean(settingsR.value.appear_offline));
        setAllowWhispersFromStrangers(Boolean(settingsR.value.allow_whispers_from_strangers));
        setAllowPartyInvitesFromStrangers(Boolean(settingsR.value.allow_party_invites_from_strangers));
      }

      if (hadCriticalFailure) {
        toast.error("Could not load social data. Restart the game server if this persists.");
      }
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

  const fetchPlayerSearch = useCallback(
    async (query: string, purpose: "friend" | "ignore", setter: (rows: PlayerSearchHit[]) => void) => {
      if (!accessToken || query.trim().length < 1) {
        setter([]);
        return;
      }
      try {
        const data = await api.getSocialPlayersSearch(accessToken, query.trim(), guildId, purpose);
        setter((data.players || []).map(mapSearchHit));
      } catch {
        setter([]);
      }
    },
    [accessToken, guildId],
  );

  useEffect(() => {
    const t = setTimeout(() => void fetchPlayerSearch(addQuery, "friend", setAddSuggestions), 250);
    return () => clearTimeout(t);
  }, [addQuery, fetchPlayerSearch]);

  useEffect(() => {
    const t = setTimeout(() => void fetchPlayerSearch(ignoreQuery, "ignore", setIgnoreSuggestions), 250);
    return () => clearTimeout(t);
  }, [ignoreQuery, fetchPlayerSearch]);

  const loadWhispers = useCallback(async () => {
    if (!accessToken || !whisperFriendId) return;
    try {
      const data = await api.getSocialWhispers(accessToken, whisperFriendId, guildId);
      setWhispers(data.messages || []);
    } catch {
      setWhispers([]);
    }
  }, [accessToken, guildId, whisperFriendId]);

  useEffect(() => {
    if (!whisperFriendId) {
      setWhispers([]);
      return;
    }
    void loadWhispers();
    const id = setInterval(() => void loadWhispers(), 8_000);
    return () => clearInterval(id);
  }, [whisperFriendId, loadWhispers]);

  useEffect(() => {
    if (activeTab === "chat" && friends.length > 0 && !whisperFriendId) {
      setWhisperFriendId(friends[0].id);
    }
  }, [activeTab, friends, whisperFriendId]);

  const sendFriendRequest = async (username: string) => {
    if (!accessToken) return;
    const u = username.replace(/^@/, "").trim();
    const res = await api.postSocialFriendRequest(accessToken, { username: u }, guildId);
    if (res.ok) {
      toast.success(res.message || "Request sent.");
      setAddQuery("");
      setShowAddSuggestions(false);
      setActiveTab("requests");
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
    if (!window.confirm(`Remove ${username} from your friends?`)) return;
    const res = await api.deleteSocialFriend(accessToken, userId, guildId);
    if (res.ok) {
      toast.info(res.message || "Unfriended.");
      if (whisperFriendId === userId) setWhisperFriendId(null);
      void refreshAll();
    } else toast.error(res.message || "Failed.");
  };

  const addIgnore = async (username: string) => {
    if (!accessToken) return;
    const u = username.replace(/^@/, "").trim();
    const res = await api.postSocialIgnore(accessToken, { username: u }, guildId);
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

  const sendWhisper = async (body: string) => {
    if (!accessToken || !whisperFriendId) return;
    const res = await api.postSocialWhisper(accessToken, whisperFriendId, body, guildId);
    if (res.ok) {
      void loadWhispers().then(() => refreshAll());
    } else toast.error(res.message || "Could not send whisper.");
  };

  const inviteToParty = async (userId: string) => {
    if (!accessToken) return;
    const res = await api.postDungeonPartyInvite(accessToken, userId, guildId);
    if (res.ok) toast.success(res.message || "Party invite sent.");
    else toast.error(res.message || "Start a dungeon party first, then invite.");
  };

  const challengePvp = async (userId: string) => {
    if (!accessToken) return;
    const res = await api.postPvpChallenge(accessToken, userId, guildId);
    if (res.ok) {
      toast.success(res.message || "Challenge sent.");
      window.dispatchEvent(new CustomEvent("game:setActiveTab", { detail: "Arena" }));
    } else toast.error(res.message || "Could not challenge.");
  };

  const cancelOutgoing = async (requestId: string) => {
    if (!accessToken) return;
    const res = await api.postSocialFriendCancel(accessToken, requestId, guildId);
    if (res.ok) {
      toast.info(res.message || "Cancelled.");
      void refreshAll();
    } else toast.error(res.message || "Failed.");
  };

  const applySettings = async (patch: api.SocialSettingsInput, successMessage?: string) => {
    if (!accessToken || settingsSaving) return;
    setSettingsSaving(true);
    try {
      const res = await api.postSocialSettings(accessToken, patch, guildId);
      if (res.ok !== false) {
        if (res.appear_offline !== undefined) setAppearOffline(Boolean(res.appear_offline));
        if (res.allow_whispers_from_strangers !== undefined) {
          setAllowWhispersFromStrangers(Boolean(res.allow_whispers_from_strangers));
        }
        if (res.allow_party_invites_from_strangers !== undefined) {
          setAllowPartyInvitesFromStrangers(Boolean(res.allow_party_invites_from_strangers));
        }
        if (successMessage) toast.success(successMessage);
        void refreshAll();
      }
    } finally {
      setSettingsSaving(false);
    }
  };

  const toggleAppearOffline = () => {
    const next = !appearOffline;
    void applySettings(
      { appear_offline: next },
      next ? "You appear offline to friends." : "Friends can see your presence.",
    );
  };

  const toggleAllowWhispers = () => {
    const next = !allowWhispersFromStrangers;
    void applySettings(
      { allow_whispers_from_strangers: next },
      next ? "Strangers can whisper you." : "Only friends can whisper you.",
    );
  };

  const toggleAllowPartyInvites = () => {
    const next = !allowPartyInvitesFromStrangers;
    void applySettings(
      { allow_party_invites_from_strangers: next },
      next ? "Non-friends can invite you to parties." : "Only friends can send party invites.",
    );
  };

  const joinLiveEvent = (event: LiveEventDisplay) => {
    window.dispatchEvent(new CustomEvent("game:setActiveTab", { detail: event.joinTab }));
    toast.info(`Head to ${event.joinTab} — ${event.title} is active.`);
  };

  if (!accessToken) {
    return <p className="text-xs text-muted-foreground">Sign in to use social features.</p>;
  }

  const mappedEvents = liveEvents.map(mapLiveEvent);

  return (
    <SocialView
      loading={loading}
      friends={friends}
      requests={requests}
      threads={threads}
      activeThreadId={whisperFriendId}
      appearOffline={appearOffline}
      allowWhispersFromStrangers={allowWhispersFromStrangers}
      allowPartyInvitesFromStrangers={allowPartyInvitesFromStrangers}
      settingsSaving={settingsSaving}
      blocked={ignored}
      liveEvents={mappedEvents}
      totalUnread={totalUnread}
      findQuery={addQuery}
      findSuggestions={addSuggestions}
      showFindSuggestions={showAddSuggestions}
      ignoreQuery={ignoreQuery}
      ignoreSuggestions={ignoreSuggestions}
      showIgnoreSuggestions={showIgnoreSuggestions}
      activeTab={activeTab}
      onActiveTabChange={setActiveTab}
      onFindQueryChange={setAddQuery}
      onShowFindSuggestions={setShowAddSuggestions}
      onIgnoreQueryChange={setIgnoreQuery}
      onShowIgnoreSuggestions={setShowIgnoreSuggestions}
      onMessage={(f) => {
        setWhisperFriendId(f.id);
        setActiveTab("chat");
      }}
      onParty={(f) => void inviteToParty(f.id)}
      onArena={(f) => void challengePvp(f.id)}
      onRemove={(f) => void unfriend(f.id, f.username)}
      onAccept={(r) => void acceptRequest(r.id)}
      onDecline={(r) => void declineRequest(r.id)}
      onCancel={(r) => void cancelOutgoing(r.id)}
      onSendRequest={(u) => void sendFriendRequest(u)}
      onPickFindSuggestion={(u) => void sendFriendRequest(u)}
      onOpenThread={setWhisperFriendId}
      onCloseThread={() => setWhisperFriendId(null)}
      onSendWhisper={(text) => void sendWhisper(text)}
      onToggleAppearOffline={() => void toggleAppearOffline()}
      onToggleAllowWhispers={() => void toggleAllowWhispers()}
      onToggleAllowPartyInvites={() => void toggleAllowPartyInvites()}
      onJoinLiveEvent={joinLiveEvent}
      onBlock={(u) => void addIgnore(u)}
      onUnblock={(id) => void removeIgnore(id)}
      onGoToFind={() => setActiveTab("find")}
    />
  );
}
