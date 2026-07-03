import { Fragment } from "react";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

interface HighlightedTextProps {
  text: string;
  /** The raw search query — each whitespace-separated term is highlighted. */
  query: string;
}

/**
 * Wraps case-insensitive occurrences of the query terms in <mark>. The API
 * returns plain-text snippets, so highlighting happens client-side.
 */
function HighlightedText({ text, query }: HighlightedTextProps) {
  const terms = Array.from(
    new Set(
      query
        .split(/\s+/)
        .map((t) => t.trim())
        .filter((t) => t.length >= 2),
    ),
  ).map(escapeRegExp);

  if (terms.length === 0) return <>{text}</>;

  const pattern = new RegExp(`(${terms.join("|")})`, "gi");
  const parts = text.split(pattern);

  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <mark
            key={index}
            className="rounded-xs bg-amber-200/70 px-0.5 text-inherit dark:bg-amber-500/30"
          >
            {part}
          </mark>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  );
}

export { HighlightedText };
