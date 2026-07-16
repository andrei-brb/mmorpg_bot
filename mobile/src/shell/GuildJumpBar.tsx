import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Sticky section nav for the Guild hall. Mobile only.
 *
 * The hall is seven stacked panels — Check-in, Quest board, War Council,
 * Treasury, Guild Tech, Raid sortie, Recruitment. Nothing about it is broken on
 * a phone (it has no fixed widths and no collapsed grids), it is simply long:
 * reaching the Treasury means scrolling past everything else. This adds a way
 * to jump instead of scroll.
 *
 * It reads the anchors GuildTab's shared SectionHeader stamps
 * (data-guild-section) rather than hard-coding a list, so a new section shows up
 * here on its own.
 */
export function GuildJumpBar() {
  const [sections, setSections] = useState<string[]>([]);
  const [active, setActive] = useState<string>("");
  const barRef = useRef<HTMLDivElement>(null);

  // Sections mount with the tab and change when the guild state does (no guild →
  // "Found a hall"), so re-scan rather than reading once.
  useEffect(() => {
    const scan = () => {
      const found = Array.from(document.querySelectorAll<HTMLElement>("[data-guild-section]"))
        .map((el) => el.dataset.guildSection || "")
        .filter(Boolean);
      setSections((prev) => (prev.join("|") === found.join("|") ? prev : found));
    };
    scan();
    const mo = new MutationObserver(scan);
    mo.observe(document.body, { childList: true, subtree: true });
    return () => mo.disconnect();
  }, []);

  // Highlight whichever section is nearest the top of the scroller.
  useEffect(() => {
    if (sections.length === 0) return;
    const els = Array.from(document.querySelectorAll<HTMLElement>("[data-guild-section]"));
    if (els.length === 0) return;
    const io = new IntersectionObserver(
      (entries) => {
        const top = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (top) setActive((top.target as HTMLElement).dataset.guildSection || "");
      },
      { rootMargin: "-72px 0px -70% 0px", threshold: 0 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [sections]);

  const jump = useCallback((name: string) => {
    const el = document.querySelector<HTMLElement>(`[data-guild-section="${CSS.escape(name)}"]`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    setActive(name);
  }, []);

  if (sections.length < 3) return null;

  return (
    <div ref={barRef} className="guild-jumpbar -mx-3 mb-2 px-3 py-2">
      <div className="flex gap-1.5 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
        {sections.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => jump(s)}
            aria-current={active === s ? "true" : undefined}
            className={cn(
              "shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-[11px] transition-colors",
              active === s
                ? "border-gold/60 bg-gold/12 text-gold-bright"
                : "border-border text-muted-foreground",
            )}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
