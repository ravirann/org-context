import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";

interface InlineTextInputProps {
  value: string;
  disabled?: boolean;
  "aria-label": string;
  /** Called with the trimmed value on blur / Enter, only when it changed. */
  onCommit: (value: string) => void;
}

/** Inline-editable text cell: commits on blur or Enter, reverts on Escape. */
function InlineTextInput({
  value,
  disabled = false,
  "aria-label": ariaLabel,
  onCommit,
}: InlineTextInputProps) {
  const [draft, setDraft] = useState(value);
  const lastSent = useRef<string | null>(null);

  useEffect(() => {
    setDraft(value);
    lastSent.current = null;
  }, [value]);

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed === "") {
      setDraft(value);
      return;
    }
    setDraft(trimmed);
    if (trimmed !== value && lastSent.current !== trimmed) {
      lastSent.current = trimmed;
      onCommit(trimmed);
    }
  };

  return (
    <Input
      aria-label={ariaLabel}
      className="h-7 w-40 px-1.5 text-xs"
      value={draft}
      disabled={disabled}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          commit();
          e.currentTarget.blur();
        } else if (e.key === "Escape") {
          setDraft(value);
        }
      }}
    />
  );
}

export { InlineTextInput };
