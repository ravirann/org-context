import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { ScoreBadge } from "@/components/ui/score-badge";
import type { ContextPacket } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

/**
 * Compact summary of the context packet compiled for an agent run:
 * intent, token estimate, confidence and the top selected sources.
 */
function PacketSummaryCard({ packet }: { packet: ContextPacket }) {
  const topSources = packet.selected_sources.slice(0, 5);

  return (
    <div data-testid="packet-summary" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
        <span className="inline-flex items-center gap-1.5">
          <span className="text-muted-foreground">Intent</span>
          <Badge variant="secondary">{packet.intent}</Badge>
        </span>
        <span className="inline-flex items-center gap-1.5 tabular-nums">
          <span className="text-muted-foreground">Tokens</span>
          <span className="font-medium">{formatNumber(packet.token_estimate)}</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="text-muted-foreground">Confidence</span>
          <ScoreBadge score={packet.confidence_score} />
        </span>
      </div>

      {topSources.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Top selected sources
          </p>
          <ul className="flex flex-col gap-1">
            {topSources.map((source) => (
              <li
                key={source.document_id}
                className="flex items-center gap-2 text-xs"
              >
                <Badge variant="outline" className="shrink-0">
                  {source.doc_type}
                </Badge>
                <span className="truncate">{source.title}</span>
                <ScoreBadge score={source.score} className="ml-auto shrink-0" />
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No sources selected.</p>
      )}

      <div>
        <Link
          to={`/packets/${packet.id}`}
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          Open full packet
          <ArrowUpRight aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}

export { PacketSummaryCard };
