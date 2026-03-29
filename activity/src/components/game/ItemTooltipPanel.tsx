import type { ReactNode } from "react";
import type { InvRow } from "@/lib/apiTypes";
import { itemTooltipLines, itemTooltipSubtitle } from "@/lib/itemStatLines";

type Props = {
  item: InvRow;
  rarityClass: string;
  children?: ReactNode;
};

export function ItemTooltipPanel({ item, rarityClass, children }: Props) {
  const lines = itemTooltipLines(item);
  const sub = itemTooltipSubtitle(item);

  return (
    <>
      <div className={`font-semibold font-cinzel ${rarityClass}`}>
        {item.name}{" "}
        {Number(item.enhancement_level ?? 0) > 0 && (
          <span className="text-primary">+{item.enhancement_level}</span>
        )}
      </div>
      {sub ? (
        <div className="text-[10px] text-muted-foreground mt-0.5 leading-snug">{sub}</div>
      ) : null}
      {lines.length > 0 ? (
        <>
          <div className="ornament-divider my-1.5" />
          <ul className="list-none text-[10px] text-foreground/90 space-y-0.5 tabular-nums leading-snug">
            {lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </>
      ) : null}
      {children ? (
        <>
          <div className="ornament-divider my-1.5" />
          {children}
        </>
      ) : null}
    </>
  );
}
