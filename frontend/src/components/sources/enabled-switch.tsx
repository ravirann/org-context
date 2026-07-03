import { cn } from "@/lib/utils";

interface EnabledSwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  "aria-label": string;
}

/** Minimal accessible switch (role="switch") used for the enabled toggle. */
function EnabledSwitch({
  checked,
  onCheckedChange,
  disabled = false,
  "aria-label": ariaLabel,
}: EnabledSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-4.5 w-8 shrink-0 items-center rounded-full border border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-primary" : "bg-muted-foreground/30",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "pointer-events-none block size-3.5 rounded-full bg-background shadow-sm transition-transform",
          checked ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

export { EnabledSwitch };
