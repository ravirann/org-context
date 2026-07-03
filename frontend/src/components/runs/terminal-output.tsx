import { cn } from "@/lib/utils";

const ERROR_PATTERN = /FAIL|Error/;

/**
 * Terminal-styled block for agent test output: dark background, mono font,
 * scrollable, with lines containing FAIL/Error highlighted in red.
 */
function TerminalOutput({ output }: { output: string }) {
  return (
    <pre
      data-testid="terminal-output"
      className="scroll-area max-h-80 overflow-auto rounded-md border border-zinc-800 bg-zinc-950 p-3 font-mono text-xs leading-5 text-zinc-200"
    >
      {output.split("\n").map((line, index) => {
        const isError = ERROR_PATTERN.test(line);
        return (
          <span
            // Line order is stable — index keys are fine for static output.
            key={index}
            data-line-error={isError || undefined}
            className={cn(
              "block whitespace-pre-wrap",
              isError && "bg-red-950/60 font-semibold text-red-400",
            )}
          >
            {line.length > 0 ? line : " "}
          </span>
        );
      })}
    </pre>
  );
}

export { TerminalOutput };
