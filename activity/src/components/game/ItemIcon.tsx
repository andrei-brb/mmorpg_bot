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

/** `assets/items/generated/{Display Name}.png` (then .jpg / .jpeg), then DB emoji. */
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

  const src = candidates[idx];
  const dim = size ?? 36;

  return (
    <img
      key={src}
      src={src}
      alt=""
      className={`block shrink-0 object-contain object-center ${className ?? ""}`}
      style={{
        maxWidth: dim,
        maxHeight: dim,
        width: "auto",
        height: "auto",
        ...style,
      }}
      loading="eager"
      decoding="async"
      onError={() => setIdx((i) => i + 1)}
    />
  );
}
