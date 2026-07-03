import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

interface TooltipProps extends Omit<HTMLAttributes<HTMLSpanElement>, "content"> {
  content: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  children: ReactNode;
}

const SIDE_CLASSES: Record<NonNullable<TooltipProps["side"]>, string> = {
  top: "bottom-full left-1/2 mb-1.5 -translate-x-1/2",
  bottom: "top-full left-1/2 mt-1.5 -translate-x-1/2",
  left: "right-full top-1/2 mr-1.5 -translate-y-1/2",
  right: "left-full top-1/2 ml-1.5 -translate-y-1/2",
};

/**
 * CSS-only tooltip: shows on hover and on keyboard focus of the wrapped
 * element. Content must be short text (it does not manage overflow).
 */
function Tooltip({ content, side = "top", className, children, ...props }: TooltipProps) {
  return (
    <span className={cn("group/tooltip relative inline-flex", className)} {...props}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-50 whitespace-nowrap rounded-md border bg-card px-2 py-1 text-[11px] text-card-foreground opacity-0 shadow-md transition-opacity duration-100 group-focus-within/tooltip:opacity-100 group-hover/tooltip:opacity-100",
          SIDE_CLASSES[side],
        )}
      >
        {content}
      </span>
    </span>
  );
}

export { Tooltip };
