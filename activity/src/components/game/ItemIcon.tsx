import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import type { InvRow } from "@/lib/apiTypes";
import { itemEmojiFallback, itemIconCandidates } from "@/lib/itemIcons";

type Props = {
  item: InvRow;
  size?: number;
  className?: string;
  style?: CSSProperties;
  /**
   * `tile` — fill a sized parent (e.g. inventory cell); PNG uses `object-cover` to match the box.
   * `default` — legacy square icon with `size` as max width/height.
   */
  variant?: "default" | "tile";
};

/** `items/{slot}/{slug}.png` or `items/quest/{id}.png`, then generated sprites, then DB emoji. */
export function ItemIcon({ item, size = 36, className, style, variant = "default" }: Props) {
  const candidates = useMemo(() => itemIconCandidates(item), [item]);
  const emoji = useMemo(() => itemEmojiFallback(item), [item]);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    setIdx(0);
  }, [item.id, item.template_id, item.name]);

  if (idx >= candidates.length) {
    const emojiSize = variant === "tile" ? Math.max(12, Math.round((size ?? 36) * 0.45)) : Math.max(14, (size ?? 36) * 0.55);
    return (
      <span
        className={
          variant === "tile"
            ? `flex h-full w-full items-center justify-center leading-none ${className ?? ""}`
            : className
        }
        style={{ fontSize: emojiSize, lineHeight: 1, ...style }}
        role="img"
        aria-hidden
      >
        {emoji}
      </span>
    );
  }

  const src = candidates[idx];
  const dim = size ?? 36;

  if (variant === "tile") {
    return (
      <img
        key={src}
        src={src}
        alt=""
        className={`block h-full w-full object-cover object-center ${className ?? ""}`}
        style={{
          width: "100%",
          height: "100%",
          ...style,
        }}
        loading="eager"
        decoding="async"
        onError={() => setIdx((i) => i + 1)}
      />
    );
  }

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
