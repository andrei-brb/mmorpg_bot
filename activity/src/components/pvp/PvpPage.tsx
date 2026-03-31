import { useState } from "react";
import { usePvpApi } from "@/hooks/usePvpApi";
import { PvpHub } from "@/components/pvp/PvpHub";
import { PvpMatch } from "@/components/pvp/PvpMatch";
import { PvpResult } from "@/components/pvp/PvpResult";
import { PvpHistory } from "@/components/pvp/PvpHistory";
import { Loader2, AlertTriangle, Swords, ScrollText } from "lucide-react";

type ArenaTab = "arena" | "history";

export function PvpPage() {
  const [activeTab, setActiveTab] = useState<ArenaTab>("arena");
  const {
    status,
    match,
    history,
    loading,
    error,
    joinQueue,
    leaveQueue,
    challenge,
    cancelChallenge,
    acceptChallenge,
    searchPlayers,
    sendAction,
    fetchHistory,
    backToHub,
  } = usePvpApi();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="text-center space-y-3">
          <Loader2 className="w-8 h-8 text-gold animate-spin mx-auto" />
          <p className="text-muted-foreground font-crimson text-sm">Loading Arena…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="text-center space-y-3 max-w-sm">
          <AlertTriangle className="w-8 h-8 text-destructive mx-auto" />
          <p className="text-foreground font-cinzel text-sm uppercase tracking-wider">Could not connect to Arena</p>
          <p className="text-xs text-muted-foreground font-crimson">{error}</p>
        </div>
      </div>
    );
  }

  if (match?.status === "finished") {
    return (
      <div className="space-y-4">
        <PvpResult match={match} onRematch={() => joinQueue(match.mode)} onBackToHub={backToHub} />
      </div>
    );
  }

  if (match?.status === "active") {
    return (
      <div className="space-y-4">
        <PvpMatch match={match} onAction={sendAction} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="tab-bar flex overflow-x-auto rounded-sm">
        <button
          type="button"
          className={`tab-btn ${activeTab === "arena" ? "tab-btn-active" : ""}`}
          onClick={() => setActiveTab("arena")}
        >
          <span className="inline-flex items-center gap-1.5">
            <Swords className="w-3.5 h-3.5 shrink-0" />
            <span className="hidden sm:inline">Arena</span>
          </span>
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "history" ? "tab-btn-active" : ""}`}
          onClick={() => setActiveTab("history")}
        >
          <span className="inline-flex items-center gap-1.5">
            <ScrollText className="w-3.5 h-3.5 shrink-0" />
            <span className="hidden sm:inline">History</span>
          </span>
        </button>
      </div>

      {activeTab === "arena" && status && (
        <PvpHub
          status={status}
          onJoinQueue={joinQueue}
          onLeaveQueue={leaveQueue}
          onChallenge={challenge}
          onCancelChallenge={cancelChallenge}
          onAcceptChallenge={acceptChallenge}
          onSearchPlayers={searchPlayers}
        />
      )}

      {activeTab === "history" && history && (
        <PvpHistory history={history} onLoadMore={() => fetchHistory(history.page + 1)} />
      )}
    </div>
  );
}
