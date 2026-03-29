import { useGameSession } from "@/context/GameSessionContext";

export function ActivityGate({ children }: { children: React.ReactNode }) {
  const { phase, errorHtml } = useGameSession();

  if (phase === "boot" || phase === "loading") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground p-6">
        <h1 className="font-cinzel text-xl mb-2">World of Discord</h1>
        <p className="text-muted-foreground text-sm">Connecting…</p>
      </div>
    );
  }

  if (phase === "no_client" || phase === "error") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground p-6 max-w-lg mx-auto">
        <h1 className="font-cinzel text-xl mb-4">World of Discord</h1>
        <div
          className="text-sm text-muted-foreground [&_code]:text-xs [&_code]:bg-muted [&_code]:px-1 [&_code]:rounded"
          dangerouslySetInnerHTML={{ __html: errorHtml || "Unknown error." }}
        />
      </div>
    );
  }

  return <>{children}</>;
}
