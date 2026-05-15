import { useEffect, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { usePvpApi } from "@/hooks/usePvpApi";
import { PvpHub } from "@/components/pvp/PvpHub";
import { PvpMatch } from "@/components/pvp/PvpMatch";
import { PvpResult } from "@/components/pvp/PvpResult";
import { PvpHistory } from "@/components/pvp/PvpHistory";
import { Loader2, AlertTriangle } from "lucide-react";
import { ArenaLayout, type ArenaHubSubTab } from "@/components/arena/ArenaLayout";

export function PvpPage() {
  const [arenaSub, setArenaSub] = useState<ArenaHubSubTab>("stats");
  const { setArenaFocusActive } = useGameSession();
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

  useEffect(() => {
    const active = match?.status === "active";
    setArenaFocusActive(active);
    return () => setArenaFocusActive(false);
  }, [match?.status, setArenaFocusActive]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="space-y-3 text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-gold" />
          <p className="font-crimson text-sm text-muted-foreground">Loading Arena…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="max-w-sm space-y-3 text-center">
          <AlertTriangle className="mx-auto h-8 w-8 text-destructive" />
          <p className="font-cinzel text-sm uppercase tracking-wider text-foreground">Could not connect to Arena</p>
          <p className="font-crimson text-xs text-muted-foreground">{error}</p>
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
    <ArenaLayout activeSub={arenaSub} onSubChange={setArenaSub}>
      {arenaSub === "stats" && status && (
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
      {arenaSub === "history" &&
        (history ? (
          <PvpHistory history={history} onLoadMore={() => fetchHistory(history.page + 1)} />
        ) : (
          <div className="flex justify-center py-12 font-crimson text-sm text-muted-foreground">Loading history…</div>
        ))}
    </ArenaLayout>
  );
}
