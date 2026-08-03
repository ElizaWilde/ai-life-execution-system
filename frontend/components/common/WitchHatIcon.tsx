import type { CSSProperties } from "react";

export default function WitchHatIcon({ className = "", size = 20 }: { className?: string; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className={`witch-hat-icon ${className}`.trim()}
      style={{ "--witch-hat-size": `${size}px` } as CSSProperties}
    />
  );
}
