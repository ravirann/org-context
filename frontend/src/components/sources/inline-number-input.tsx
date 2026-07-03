import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";

interface InlineNumberInputProps {
  value: number;
  min: number;
  max: number;
  disabled?: boolean;
  "aria-label": string;
  /** Called with the clamped value on blur / Enter, only when it changed. */
  onCommit: (value: number) => void;
}

/** Inline-editable number cell: commits on blur or Enter, reverts on Escape. */
function InlineNumberInput({
  value,
  min,
  max,
  disabled = false,
  "aria-label": ariaLabel,
  onCommit,
}: InlineNumberInputProps) {
  const [draft, setDraft] = useState(String(value));
  // Guards against double-commits (Enter immediately followed by blur).
  const lastSent = useRef<number | null>(null);

  // Follow server-driven changes (e.g. after a PATCH refetch).
  useEffect(() => {
    setDraft(String(value));
    lastSent.current = null;
  }, [value]);

  const commit = () => {
    const parsed = Number(draft);
    if (draft.trim() === "" || Number.isNaN(parsed)) {
      setDraft(String(value));
      return;
    }
    const clamped = Math.min(max, Math.max(min, Math.round(parsed)));
    setDraft(String(clamped));
    if (clamped !== value && lastSent.current !== clamped) {
      lastSent.current = clamped;
      onCommit(clamped);
    }
  };

  return (
    <Input
      type="number"
      inputMode="numeric"
      min={min}
      max={max}
      aria-label={ariaLabel}
      className="h-7 w-16 px-1.5 text-right text-xs tabular-nums"
      value={draft}
      disabled={disabled}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          commit();
          e.currentTarget.blur();
        } else if (e.key === "Escape") {
          setDraft(String(value));
        }
      }}
    />
  );
}

export { InlineNumberInput };
