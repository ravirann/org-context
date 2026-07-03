"""SQLAlchemy 2.0 typed ORM models for the context engine (see docs/DATA_MODEL.md)."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from context_engine.config.constants import EMBEDDING_DIM

# ---------------------------------------------------------------------------
# Enums (stored as strings, native_enum=False)
# ---------------------------------------------------------------------------


class UserRole(enum.StrEnum):
    admin = "admin"
    lead = "lead"
    engineer = "engineer"
    viewer = "viewer"


class ApiKeyKind(enum.StrEnum):
    api = "api"
    mcp = "mcp"


class SourceType(enum.StrEnum):
    github = "github"
    jira = "jira"
    slack = "slack"
    confluence = "confluence"
    adr = "adr"
    incident = "incident"
    ci = "ci"
    feedback = "feedback"


class SyncStatus(enum.StrEnum):
    idle = "idle"
    syncing = "syncing"
    ok = "ok"
    error = "error"


class AclSyncStatus(enum.StrEnum):
    ok = "ok"
    pending = "pending"
    error = "error"


class DocType(enum.StrEnum):
    code = "code"
    pr = "pr"
    ticket = "ticket"
    doc = "doc"
    message = "message"
    adr = "adr"
    incident = "incident"
    ci_run = "ci_run"
    feedback = "feedback"


class DocStatus(enum.StrEnum):
    active = "active"
    stale = "stale"
    deprecated = "deprecated"


class EntityType(enum.StrEnum):
    repo = "repo"
    service = "service"
    user = "user"
    team = "team"
    pr = "pr"
    ticket = "ticket"
    doc = "doc"
    adr = "adr"
    incident = "incident"
    api = "api"
    db_table = "db_table"
    context_packet = "context_packet"
    agent_run = "agent_run"


class EdgeType(enum.StrEnum):
    owns = "owns"
    member_of = "member_of"
    authored = "authored"
    references = "references"
    modifies = "modifies"
    resolves = "resolves"
    caused_by = "caused_by"
    depends_on = "depends_on"
    documents = "documents"
    cites = "cites"
    deployed_in = "deployed_in"
    used_by = "used_by"


class Intent(enum.StrEnum):
    bugfix = "bugfix"
    feature = "feature"
    refactor = "refactor"
    incident_response = "incident_response"
    question = "question"
    unknown = "unknown"


class AgentOutcome(enum.StrEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    abandoned = "abandoned"


class AgentRunStatus(enum.StrEnum):
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class ConflictStatus(enum.StrEnum):
    open = "open"
    resolved = "resolved"


class FeedbackType(enum.StrEnum):
    useful = "useful"
    irrelevant = "irrelevant"
    missing_context = "missing_context"
    stale_context = "stale_context"
    permission_issue = "permission_issue"
    suggest_source = "suggest_source"
    promote_authoritative = "promote_authoritative"
    mark_deprecated = "mark_deprecated"


class EvalMode(enum.StrEnum):
    baseline = "baseline"
    context_engine = "context_engine"
    comparison = "comparison"


class EvalRunStatus(enum.StrEnum):
    running = "running"
    completed = "completed"
    failed = "failed"


class EvalResultMode(enum.StrEnum):
    baseline = "baseline"
    context_engine = "context_engine"


class ActivityEventType(enum.StrEnum):
    commit = "commit"
    pr = "pr"
    review = "review"
    doc_edit = "doc_edit"
    ticket = "ticket"
    incident = "incident"
    packet_use = "packet_use"


def _enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """String-stored enum column type (no native PG enum)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


# ---------------------------------------------------------------------------
# Base + mixins
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Single declarative base for all models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[str]: JSONB,
    }


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    members: Mapped[list[User]] = relationship(back_populates="team")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), nullable=False)
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    avatar_color: Mapped[str] = mapped_column(String(16), default="#64748b", nullable=False)

    team: Mapped[Team | None] = relationship(back_populates="members")
    api_keys: Mapped[list[ApiKey]] = relationship(back_populates="user")


class ApiKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = _uuid_pk()
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[ApiKeyKind] = mapped_column(
        _enum(ApiKeyKind, "api_key_kind"), default=ApiKeyKind.api, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="api_keys")


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = _uuid_pk()
    type: Mapped[SourceType] = mapped_column(_enum(SourceType, "source_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    sync_status: Mapped[SyncStatus] = mapped_column(
        _enum(SyncStatus, "sync_status"), default=SyncStatus.idle, nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    acl_sync_status: Mapped[AclSyncStatus] = mapped_column(
        _enum(AclSyncStatus, "acl_sync_status"), default=AclSyncStatus.ok, nullable=False
    )
    authority_rank: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    freshness_window_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)

    documents: Mapped[list[Document]] = relationship(back_populates="source")


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_documents_source_external"),
        Index("ix_documents_topic_key", "topic_key"),
        Index("ix_documents_repo", "repo"),
        Index("ix_documents_service", "service"),
        Index("ix_documents_doc_type", "doc_type"),
        Index("ix_documents_status", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(300), nullable=False)
    doc_type: Mapped[DocType] = mapped_column(_enum(DocType, "doc_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    repo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    status: Mapped[DocStatus] = mapped_column(
        _enum(DocStatus, "doc_status"), default=DocStatus.active, nullable=False
    )
    topic_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    authority_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    freshness_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    acl_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    acl_team_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    acl_user_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejection_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    source: Mapped[Source] = relationship(back_populates="documents")
    author: Mapped[User | None] = relationship(foreign_keys=[author_id])
    team: Mapped[Team | None] = relationship()
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Chunk.ord"
    )


class Chunk(TimestampMixin, Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    ord: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=True,
    )

    document: Mapped[Document] = relationship(back_populates="chunks")


class Entity(TimestampMixin, Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("type", "name", name="uq_entities_type_name"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    type: Mapped[EntityType] = mapped_column(_enum(EntityType, "entity_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    entity_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Edge(TimestampMixin, Base):
    __tablename__ = "edges"
    __table_args__ = (
        UniqueConstraint(
            "source_entity_id", "target_entity_id", "type", name="uq_edges_source_target_type"
        ),
        Index("ix_edges_source_entity_id", "source_entity_id"),
        Index("ix_edges_target_entity_id", "target_entity_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[EdgeType] = mapped_column(_enum(EdgeType, "edge_type"), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    edge_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    source_entity: Mapped[Entity] = relationship(foreign_keys=[source_entity_id])
    target_entity: Mapped[Entity] = relationship(foreign_keys=[target_entity_id])


class ContextPacket(TimestampMixin, Base):
    __tablename__ = "context_packets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    task: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Intent] = mapped_column(
        _enum(Intent, "intent"), default=Intent.unknown, nullable=False
    )
    repo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    compiled_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    selected_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    rejected_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    conflict_notes: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    acl_notes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    authority_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    risks: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    recommended_tests: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    agent_outcome: Mapped[AgentOutcome] = mapped_column(
        _enum(AgentOutcome, "agent_outcome"), default=AgentOutcome.pending, nullable=False
    )
    feedback_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    requester: Mapped[User] = relationship()


class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_name: Mapped[str] = mapped_column(String(200), nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    repo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        _enum(AgentRunStatus, "agent_run_status"), default=AgentRunStatus.running, nullable=False
    )
    context_packet_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("context_packets.id"), nullable=True
    )
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_files: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    test_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewer_comments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()
    context_packet: Mapped[ContextPacket | None] = relationship()


class Conflict(TimestampMixin, Base):
    __tablename__ = "conflicts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    topic_key: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[ConflictStatus] = mapped_column(
        _enum(ConflictStatus, "conflict_status"), default=ConflictStatus.open, nullable=False
    )
    recommended_document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    affected: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    linked_adr_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    resolver: Mapped[User | None] = relationship()


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    context_packet_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("context_packets.id"), nullable=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    type: Mapped[FeedbackType] = mapped_column(_enum(FeedbackType, "feedback_type"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    context_packet: Mapped[ContextPacket | None] = relationship()
    document: Mapped[Document | None] = relationship()


class EvalTask(TimestampMixin, Base):
    __tablename__ = "eval_tasks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    repo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expected_document_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    expected_keywords: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EvalRun(TimestampMixin, Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    mode: Mapped[EvalMode] = mapped_column(
        _enum(EvalMode, "eval_mode"), default=EvalMode.comparison, nullable=False
    )
    status: Mapped[EvalRunStatus] = mapped_column(
        _enum(EvalRunStatus, "eval_run_status"), default=EvalRunStatus.running, nullable=False
    )
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    triggerer: Mapped[User | None] = relationship()
    results: Mapped[list[EvalResult]] = relationship(
        back_populates="eval_run", cascade="all, delete-orphan"
    )


class EvalResult(TimestampMixin, Base):
    __tablename__ = "eval_results"

    id: Mapped[uuid.UUID] = _uuid_pk()
    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    eval_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("eval_tasks.id"), nullable=False)
    mode: Mapped[EvalResultMode] = mapped_column(
        _enum(EvalResultMode, "eval_result_mode"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    eval_run: Mapped[EvalRun] = relationship(back_populates="results")
    eval_task: Mapped[EvalTask] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    actor: Mapped[User | None] = relationship()


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any] | list[Any] | int | float | str | bool | None] = mapped_column(
        JSONB, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "repo", "service", "event_type", "day", name="uq_activity_events_cell"
        ),
        Index("ix_activity_events_day", "day"),
        Index("ix_activity_events_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    repo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    event_type: Mapped[ActivityEventType] = mapped_column(
        _enum(ActivityEventType, "activity_event_type"), nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship()
    team: Mapped[Team | None] = relationship()
