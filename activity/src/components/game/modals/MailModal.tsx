import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

export type MailLostRow = { template_id: string; reason?: string };

function prettyId(s: string) {
  return String(s)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function MailModal({
  open,
  onOpenChange,
  lostDeliveries,
  pendingFromActiveQuest,
  onDismissNotice,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lostDeliveries: MailLostRow[];
  /** Shown while quest complete modal is open — same failures, not yet acked. */
  pendingFromActiveQuest: MailLostRow[];
  onDismissNotice: () => void;
}) {
  const rows = pendingFromActiveQuest.length > 0 ? pendingFromActiveQuest : lostDeliveries;
  const hasRows = rows.length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[400px] border-border/60"
        style={{ background: "linear-gradient(180deg, hsl(228 18% 12%) 0%, hsl(228 20% 8%) 100%)" }}
      >
        <DialogTitle className="font-cinzel text-lg text-primary">Mailbox</DialogTitle>
        <p className="text-xs text-muted-foreground font-crimson">
          Undelivered rewards appear here when your inventory did not have room. Claim-by-mail delivery will arrive in a
          future update; for now, free a slot and complete the step again if the game allows it.
        </p>
        {hasRows ? (
          <ul className="mt-2 max-h-[220px] overflow-y-auto space-y-2 text-sm">
            {rows.map((row, i) => (
              <li
                key={`${row.template_id}-${i}`}
                className="rounded-sm border border-border/50 px-3 py-2 bg-background/40"
              >
                <div className="font-semibold text-foreground font-crimson">📦 {prettyId(row.template_id)}</div>
                {row.reason && <div className="text-xs text-muted-foreground mt-0.5">{row.reason}</div>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground font-crimson py-4">No pending deliveries.</p>
        )}
        {lostDeliveries.length > 0 && (
          <div className="flex justify-end pt-2">
            <Button type="button" variant="outline" size="sm" className="text-xs" onClick={() => onDismissNotice()}>
              Clear notice
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
