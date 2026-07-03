import { Check, ChevronDown, ChevronRight, X } from "lucide-react";
import { Fragment, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { ScoreBadge } from "@/components/ui/score-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { EvalResult } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

function DetailChips({ details }: { details: EvalResult["details"] }) {
  return (
    <span className="flex flex-wrap gap-1">
      <Badge variant="muted">P {details.precision.toFixed(2)}</Badge>
      <Badge variant="muted">R {details.recall.toFixed(2)}</Badge>
      <Badge variant="muted">kw {details.keyword_hits}</Badge>
      <Badge variant={details.citations_ok ? "success" : "destructive"}>
        citations {details.citations_ok ? "ok" : "bad"}
      </Badge>
    </span>
  );
}

function PassedIcon({ passed }: { passed: boolean }) {
  return passed ? (
    <Check
      role="img"
      aria-label="passed"
      className="size-4 text-emerald-600 dark:text-emerald-400"
    />
  ) : (
    <X role="img" aria-label="failed" className="size-4 text-destructive" />
  );
}

/**
 * Score breakdown grouped per golden task. In comparison mode each task shows
 * a baseline row paired with a context_engine row. Failed rows expand into a
 * destructive-tinted explanation panel.
 */
function EvalResultsTable({ results }: { results: EvalResult[] }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  // Group by task name, preserving API order.
  const groups = new Map<string, EvalResult[]>();
  for (const result of results) {
    const list = groups.get(result.task_name) ?? [];
    list.push(result);
    groups.set(result.task_name, list);
  }

  const toggle = (key: string) =>
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <Table data-testid="eval-results-table">
      <TableHeader>
        <TableRow>
          <TableHead className="w-6" />
          <TableHead>Golden task</TableHead>
          <TableHead>Mode</TableHead>
          <TableHead>Score</TableHead>
          <TableHead>Passed</TableHead>
          <TableHead className="text-right">Tokens</TableHead>
          <TableHead>Details</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {[...groups.entries()].map(([taskName, taskResults]) =>
          taskResults.map((result, index) => {
            const key = `${taskName}:${result.mode}`;
            const isOpen = expanded[key] === true;
            const firstOfGroup = index === 0;
            return (
              <Fragment key={key}>
                <TableRow
                  data-testid={`result-row-${key}`}
                  className={cn(!result.passed && "bg-destructive/4")}
                >
                  <TableCell className="w-6 pr-0">
                    {!result.passed ? (
                      <button
                        type="button"
                        aria-expanded={isOpen}
                        aria-label={`Toggle explanation for ${taskName} (${result.mode})`}
                        className="inline-flex rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => toggle(key)}
                      >
                        {isOpen ? (
                          <ChevronDown className="size-4" aria-hidden="true" />
                        ) : (
                          <ChevronRight className="size-4" aria-hidden="true" />
                        )}
                      </button>
                    ) : null}
                  </TableCell>
                  <TableCell
                    className={cn(
                      "max-w-[220px] truncate text-xs",
                      firstOfGroup
                        ? "font-medium"
                        : "text-muted-foreground",
                    )}
                  >
                    {firstOfGroup ? taskName : "↳"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={result.mode === "baseline" ? "muted" : "secondary"}
                    >
                      {result.mode}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <ScoreBadge score={result.score} />
                  </TableCell>
                  <TableCell>
                    <PassedIcon passed={result.passed} />
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-xs">
                    {formatNumber(result.tokens_used)}
                  </TableCell>
                  <TableCell>
                    <DetailChips details={result.details} />
                  </TableCell>
                </TableRow>
                {isOpen ? (
                  <TableRow
                    data-testid={`result-explanation-${key}`}
                    className="hover:bg-transparent"
                  >
                    <TableCell colSpan={7} className="py-0 pb-2">
                      <div className="rounded-md border border-destructive/30 bg-destructive/8 px-3 py-2 text-xs leading-5 text-foreground">
                        {result.explanation}
                      </div>
                    </TableCell>
                  </TableRow>
                ) : null}
              </Fragment>
            );
          }),
        )}
      </TableBody>
    </Table>
  );
}

export { EvalResultsTable };
