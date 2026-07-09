import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/** Small inline error block with a Retry button for failed initial fetches. */
function ErrorState({
  message = "Something went wrong.",
  onRetry,
  className,
}: {
  message?: string;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn("rounded-lg border border-dashed border-destructive/40 bg-black/20 p-8 text-center", className)}
    >
      <p className="text-xs text-muted-foreground mb-3">{message}</p>
      <Button type="button" size="sm" variant="outline" onClick={onRetry}>
        <RefreshCw className="h-3.5 w-3.5" /> Retry
      </Button>
    </div>
  );
}

export { ErrorState };
