"""Pydantic v2 request/response models for the /v1 API (see docs/API_CONTRACT.md).

Field names are snake_case, mirrored 1:1 in ``frontend/src/lib/types.ts``. Where a
model maps directly onto an ORM row it enables ``from_attributes`` so routers can build
it with ``Model.model_validate(orm_obj)``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

# --------------------------------------------------------------------------- #
# Shared                                                                       #
# --------------------------------------------------------------------------- #


class Page[T](BaseModel):
    """Generic pagination envelope: ``{items, total, page, page_size}``."""

    items: list[T]
    total: int
    page: int
    page_size: int


class Items[T](BaseModel):
    """Non-paginated ``{items: [...]}`` envelope."""

    items: list[T]


# --------------------------------------------------------------------------- #
# Me                                                                           #
# --------------------------------------------------------------------------- #


class MeOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    team_name: str | None = None


# --------------------------------------------------------------------------- #
# Dashboard                                                                    #
# --------------------------------------------------------------------------- #


class DashboardSummary(BaseModel):
    total_documents: int
    connected_sources: int
    active_repos: int
    active_services: int
    active_users: int
    context_packets: int
    agent_runs: int
    failed_agent_runs: int
    stale_documents: int
    conflicting_documents: int
    acl_violations_blocked: int
    latest_eval_score: float | None = None


class TrendPoint(BaseModel):
    date: str
    value: float


class Trends(BaseModel):
    eval_scores: list[TrendPoint]
    source_freshness: list[TrendPoint]
    review_rework: list[TrendPoint]
    packets_per_day: list[TrendPoint]


# --------------------------------------------------------------------------- #
# Context packets                                                             #
# --------------------------------------------------------------------------- #


class CompileRequest(BaseModel):
    task: str
    repo: str | None = None
    service: str | None = None
    max_tokens: int | None = None


class SelectedSource(BaseModel):
    document_id: str
    title: str
    doc_type: str
    score: float
    reasons: list[str]


class RejectedSource(BaseModel):
    document_id: str
    title: str
    doc_type: str
    score: float
    reason: str


class Citation(BaseModel):
    marker: str
    document_id: str
    title: str
    url: str | None = None
    quote: str


class ConflictNote(BaseModel):
    conflict_id: str
    topic_key: str
    chosen_document_id: str | None = None
    note: str


class AclNotes(BaseModel):
    blocked_count: int = 0
    note: str = ""


class ContextPacketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task: str
    intent: str
    repo: str | None = None
    service: str | None = None
    compiled_context: str
    selected_sources: list[SelectedSource]
    rejected_sources: list[RejectedSource]
    citations: list[Citation]
    conflict_notes: list[ConflictNote]
    acl_notes: AclNotes
    token_estimate: int
    confidence_score: float
    freshness_score: float
    authority_score: float
    risks: list[str]
    recommended_tests: list[str]
    agent_outcome: str
    feedback_score: float | None = None
    requested_by_name: str
    created_at: datetime


class ContextPacketSummary(BaseModel):
    id: str
    task: str
    intent: str
    repo: str | None = None
    service: str | None = None
    token_estimate: int
    confidence_score: float
    agent_outcome: str
    requested_by_name: str
    created_at: datetime
    source_count: int


class ContextPacketDetail(ContextPacketOut):
    feedback: list[FeedbackOut]
    agent_run: AgentRunSummary | None = None


# --------------------------------------------------------------------------- #
# Search                                                                       #
# --------------------------------------------------------------------------- #


class SearchRequest(BaseModel):
    query: str
    doc_types: list[str] | None = None
    source_ids: list[str] | None = None
    repo: str | None = None
    service: str | None = None
    status: str | None = None
    page: int = 1
    page_size: int = 20


class SearchResult(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    doc_type: str
    source_name: str
    snippet: str
    score: float
    url: str | None = None
    repo: str | None = None
    service: str | None = None
    status: str
    freshness_score: float
    authority_score: float
    last_activity_at: datetime


class SearchResponse(Page[SearchResult]):
    acl_blocked_count: int = 0


# --------------------------------------------------------------------------- #
# Documents                                                                    #
# --------------------------------------------------------------------------- #


class DocumentSourceRef(BaseModel):
    id: str
    name: str
    type: str


class DocumentAcl(BaseModel):
    public: bool
    team_names: list[str]
    user_count: int


class DocumentChunk(BaseModel):
    id: str
    ord: int
    content: str
    token_count: int


class RelatedDocument(BaseModel):
    id: str
    title: str
    doc_type: str
    relation: str


class DocumentConflictRef(BaseModel):
    id: str
    topic_key: str
    title: str
    status: str


class PacketUsage(BaseModel):
    packet_id: str
    task: str
    created_at: datetime
    was_selected: bool


class DocumentDetail(BaseModel):
    id: str
    title: str
    content: str
    doc_type: str
    url: str | None = None
    status: str
    repo: str | None = None
    service: str | None = None
    source: DocumentSourceRef
    author_name: str | None = None
    team_name: str | None = None
    topic_key: str | None = None
    authority_score: float
    freshness_score: float
    last_activity_at: datetime
    acl: DocumentAcl
    chunks: list[DocumentChunk]
    citations_of: int
    related: list[RelatedDocument]
    conflicts: list[DocumentConflictRef]
    packet_usage: list[PacketUsage]


# --------------------------------------------------------------------------- #
# Relationships                                                                #
# --------------------------------------------------------------------------- #


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    ref: str | None = None
    stale: bool
    conflicted: bool
    degree: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    weight: float


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class PathStep(BaseModel):
    node: GraphNode
    edge: GraphEdge | None = None


class PathResponse(BaseModel):
    path: list[PathStep]
    found: bool


# --------------------------------------------------------------------------- #
# Heatmaps                                                                     #
# --------------------------------------------------------------------------- #


class HeatmapCell(BaseModel):
    day: str
    value: int


class HeatmapRow(BaseModel):
    user_id: str
    user_name: str
    team_name: str | None = None
    cells: list[HeatmapCell]
    total: int


class HeatmapUsersResponse(BaseModel):
    rows: list[HeatmapRow]
    days: list[str]


class OwnershipRow(BaseModel):
    key: str
    owner_team: str | None = None
    doc_count: int
    owner_user_names: list[str]
    coverage_score: float
    last_activity_at: datetime | None = None


class OwnershipResponse(BaseModel):
    rows: list[OwnershipRow]


class ContextDebtRow(BaseModel):
    key: str
    repo: str | None = None
    service: str | None = None
    team_name: str | None = None
    stale_count: int
    missing_owner: bool
    conflict_count: int
    rejected_count: int
    failed_runs: int
    debt_score: float


class ContextDebtHeatmapResponse(BaseModel):
    rows: list[ContextDebtRow]


# --------------------------------------------------------------------------- #
# Agent runs                                                                   #
# --------------------------------------------------------------------------- #


class AgentRunSummary(BaseModel):
    id: str
    agent_name: str
    task: str
    repo: str | None = None
    service: str | None = None
    user_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    context_packet_id: str | None = None


class ReviewerComment(BaseModel):
    author: str
    comment: str


class AgentRunDetail(AgentRunSummary):
    plan: str | None = None
    changed_files: list[str]
    test_output: str | None = None
    pr_url: str | None = None
    reviewer_comments: list[ReviewerComment]
    langfuse_trace_url: str | None = None
    context_packet: ContextPacketOut | None = None


# --------------------------------------------------------------------------- #
# Evals                                                                        #
# --------------------------------------------------------------------------- #


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mode: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    summary: dict[str, Any] | None = None


class EvalResultOut(BaseModel):
    task_name: str
    mode: str
    score: float
    passed: bool
    explanation: str
    tokens_used: int
    details: dict[str, Any]


class EvalRunDetail(EvalRunOut):
    results: list[EvalResultOut]
    golden_tasks_total: int


class EvalRunRequest(BaseModel):
    mode: str = "comparison"


class EvalRunEnqueued(BaseModel):
    eval_run_id: str
    status: str


class GoldenTask(BaseModel):
    id: str
    name: str
    task: str
    repo: str | None = None
    service: str | None = None
    is_active: bool
    expected_keywords: list[str]


# --------------------------------------------------------------------------- #
# Sources                                                                      #
# --------------------------------------------------------------------------- #


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    name: str
    enabled: bool
    sync_status: str
    last_synced_at: datetime | None = None
    last_error: str | None = None
    document_count: int
    acl_sync_status: str
    authority_rank: int
    freshness_window_days: int


class SourceCreate(BaseModel):
    type: str
    name: str
    config: dict[str, Any] | None = None


class SourceUpdate(BaseModel):
    enabled: bool | None = None
    name: str | None = None
    authority_rank: int | None = None
    freshness_window_days: int | None = None
    config: dict[str, Any] | None = None


class SyncEnqueued(BaseModel):
    status: str


# --------------------------------------------------------------------------- #
# Conflicts                                                                    #
# --------------------------------------------------------------------------- #


class ConflictAffected(BaseModel):
    repos: list[str] = []
    services: list[str] = []


class ConflictOut(BaseModel):
    id: str
    topic_key: str
    title: str
    status: str
    document_count: int
    affected: ConflictAffected
    created_at: datetime


class ConflictDocument(BaseModel):
    id: str
    title: str
    doc_type: str
    source_name: str
    freshness_score: float
    authority_score: float
    last_activity_at: datetime
    excerpt: str


class ConflictDetail(BaseModel):
    id: str
    topic_key: str
    title: str
    status: str
    affected: ConflictAffected
    resolution_note: str | None = None
    resolved_by_name: str | None = None
    resolved_at: datetime | None = None
    linked_adr_url: str | None = None
    recommended_document_id: str | None = None
    documents: list[ConflictDocument]


class ConflictResolveRequest(BaseModel):
    recommended_document_id: str | None = None
    note: str
    linked_adr_url: str | None = None


# --------------------------------------------------------------------------- #
# Context debt                                                                 #
# --------------------------------------------------------------------------- #


class StaleDocsRow(BaseModel):
    repo: str | None = None
    service: str | None = None
    team_name: str | None = None
    count: int


class MissingOwnerRow(BaseModel):
    key: str
    doc_count: int


class UndocumentedApiRow(BaseModel):
    name: str
    service: str


class RepeatedMissRow(BaseModel):
    query: str
    count: int


class FailedAgentAreaRow(BaseModel):
    repo: str | None = None
    service: str | None = None
    failed: int
    total: int


class NeverUsedDocRow(BaseModel):
    id: str
    title: str
    doc_type: str
    created_at: datetime


class FrequentlyRejectedDocRow(BaseModel):
    id: str
    title: str
    rejection_count: int


class ConflictsBySourceTypeRow(BaseModel):
    source_type: str
    count: int


class ContextDebtReport(BaseModel):
    stale_docs: list[StaleDocsRow]
    missing_owners: list[MissingOwnerRow]
    undocumented_apis: list[UndocumentedApiRow]
    repeated_misses: list[RepeatedMissRow]
    failed_agent_areas: list[FailedAgentAreaRow]
    never_used_docs: list[NeverUsedDocRow]
    frequently_rejected_docs: list[FrequentlyRejectedDocRow]
    conflicts_by_source_type: list[ConflictsBySourceTypeRow]


# --------------------------------------------------------------------------- #
# Feedback                                                                     #
# --------------------------------------------------------------------------- #


class FeedbackCreate(BaseModel):
    type: str
    context_packet_id: str | None = None
    document_id: str | None = None
    comment: str | None = None


class FeedbackOut(BaseModel):
    id: str
    type: str
    context_packet_id: str | None = None
    document_id: str | None = None
    comment: str | None = None
    user_name: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Admin & settings                                                            #
# --------------------------------------------------------------------------- #


class AdminUser(BaseModel):
    id: str
    email: str
    name: str
    role: str
    team_name: str | None = None
    is_active: bool


class AdminTeam(BaseModel):
    id: str
    name: str
    member_count: int


class ApiKeyOut(BaseModel):
    id: str
    label: str
    kind: str
    user_name: str
    is_active: bool
    last_used_at: datetime | None = None


class AuditLogOut(BaseModel):
    id: str
    actor_name: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    detail: dict[str, Any]
    created_at: datetime


class SettingsOut(BaseModel):
    retrieval_weights: dict[str, Any]
    freshness_window_days: Any
    authority_rules: dict[str, Any]
    eval_thresholds: dict[str, Any]
    retention: dict[str, Any]
    pii_redaction: dict[str, Any]
    feature_flags: dict[str, Any]
    token_budget: dict[str, Any]


# Resolve forward references (ContextPacketDetail -> FeedbackOut / AgentRunSummary).
ContextPacketDetail.model_rebuild()
