import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/** CSS scroll container with thin, theme-aware scrollbars. */
const ScrollArea = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("scroll-area", className)} {...props} />
  ),
);
ScrollArea.displayName = "ScrollArea";

export { ScrollArea };
