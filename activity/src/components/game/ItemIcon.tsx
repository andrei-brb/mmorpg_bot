import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import type { InvRow } from "@/lib/apiTypes";
import { itemEmojiFallback, itemIconCandidates } from "@/lib/itemIcons";

type Props = {
  item: InvRow;
  size?: number;
  className?: string;
  style?: CSSProperties;
};

/**
 * Try pack icons (`assets/items/icons/{slug}_{rarity}.png`), generated name paths, `assets/items/{template_id}.png`, then DB emoji.
 */
export function ItemIcon({ item, size = 36, className, style }: Props) {
  const candidates = useMemo(() => itemIconCandidates(item), [item]);
  const emoji = useMemo(() => itemEmojiFallback(item), [item]);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    setIdx(0);
  }, [item.id, item.template_id, item.name]);

  if (idx >= candidates.length) {
    return (
      <span
        className={className}
        style={{ fontSize: Math.max(14, size * 0.55), lineHeight: 1 }}
        role="img"
        aria-hidden
      >
        {emoji}
      </span>
    );
  }

  return (
    <img
      src={candidates[idx]}
      alt=""
      width={size}
      height={size}
      className={`object-contain ${className ?? ""}`}
      style={style}
      loading="lazy"
      decoding="async"
      onError={() => setIdx((i) => i + 1)}
    />
  );
}
