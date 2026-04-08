"""CaseState — the single source of truth owned by the Orchestrator.

CONTRACT (ARC-013):
- Only the Orchestrator may MUTATE CaseState.
- Agents receive an immutable projection (a frozen dataclass or a TypedDict
  copied via dict(...)) and MUST return an AgentEvent describing what they
  observed/decided. The Orchestrator applies the event to CaseState.
- This guarantees a single writer, replayable history, and a clean audit log.

See ARCHITECTURE.md §"Agent Orchestration Layer" → State Contracts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, TypedDict

from app.domain.entities import Incident, Ticket, TriageResult


class CaseStatus(str, Enum):
    """Lifecycle of a case as it travels through the multi-agent system.

    See `docs/diagrams/state-case-lifecycle.md` for the full state machine.
    """

    NEW = "new"                       # just created, not yet inspected
    INTAKE_OK = "intake_ok"           # IntakeGuard passed
    INTAKE_BLOCKED = "intake_blocked" # IntakeGuard blocked (PII / injection / off-topic)
    TRIAGED = "triaged"               # Triage Agent produced TriageResult
    TICKETED = "ticketed"             # Integration Agent created ticket
    NOTIFIED = "notified"             # Integration Agent notified team
    AWAITING_RESOLUTION = "awaiting_resolution"  # async webhook pending
    RESOLVED = "resolved"             # Resolution Agent completed
    FAILED = "failed"                 # unrecoverable error


# ---------------------------------------------------------------------------
# AgentEvent — the ONLY thing agents are allowed to return.
# ---------------------------------------------------------------------------

EventKind = Literal[
    "intake.passed",
    "intake.blocked",
    "triage.completed",
    "integration.ticket_created",
    "integration.team_notified",
    "resolution.completed",
    "agent.error",
]


@dataclass(frozen=True)
class AgentEvent:
    """Immutable record of what an agent observed/decided.

    Agents return one of these. The Orchestrator applies it to CaseState.
    `payload` is intentionally loose — typed at the event-kind level by the
    router, not at the dataclass level, to keep the contract simple.
    """

    kind: EventKind
    agent: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# CaseState — orchestrator-owned mutable state.
# ---------------------------------------------------------------------------


class CaseState(TypedDict, total=False):
    """Mutable case context. ONLY the orchestrator writes to this."""

    # Identity
    case_id: str

    # Domain artifacts (built up across the pipeline)
    incident: Incident
    triage: Optional[TriageResult]
    ticket: Optional[Ticket]

    # Lifecycle
    status: CaseStatus
    blocked_reason: Optional[str]
    error: Optional[str]

    # Audit log — append-only list of events the orchestrator received
    events: list[AgentEvent]


# ---------------------------------------------------------------------------
# Projections — read-only views handed to agents.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntakeProjection:
    """Minimal slice IntakeGuard needs to make a decision."""

    case_id: str
    incident: Incident


@dataclass(frozen=True)
class TriageProjection:
    """Minimal slice the Triage Agent needs."""

    case_id: str
    incident: Incident


@dataclass(frozen=True)
class IntegrationProjection:
    """Minimal slice the Integration Agent needs."""

    case_id: str
    incident: Incident
    triage: TriageResult


@dataclass(frozen=True)
class ResolutionProjection:
    """Minimal slice the Resolution Agent needs (used by webhook subgraph)."""

    case_id: str
    incident: Incident
    ticket: Ticket
