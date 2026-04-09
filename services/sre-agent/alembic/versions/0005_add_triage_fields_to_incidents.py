"""Add triage result fields to incidents table — ARC-023.

Persists the full LangGraph triage output alongside each incident so the
API driver layer (routes_incidents.py) can write the terminal state without
any agent node touching the DB directly.

New columns:
  triage_summary, triage_root_cause, triage_suggested_owners (JSON list),
  triage_confidence, triage_needs_human_review, triage_used_fallback,
  triage_degraded, ticket_id, triaged_at, resolved_at.

New indexes:
  ix_incidents_severity          — filter/sort by severity in list view
  ix_incidents_triage_confidence — analytics queries on confidence scores

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-09
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("triage_summary", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("triage_root_cause", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("triage_suggested_owners", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("triage_confidence", sa.Float(), nullable=True))
    op.add_column("incidents", sa.Column("triage_needs_human_review", sa.Boolean(), nullable=True))
    op.add_column("incidents", sa.Column("triage_used_fallback", sa.Boolean(), nullable=True))
    op.add_column("incidents", sa.Column("triage_degraded", sa.Boolean(), nullable=True))
    op.add_column("incidents", sa.Column("ticket_id", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("triaged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_triage_confidence", "incidents", ["triage_confidence"])


def downgrade() -> None:
    op.drop_index("ix_incidents_triage_confidence", table_name="incidents")
    op.drop_index("ix_incidents_severity", table_name="incidents")

    op.drop_column("incidents", "resolved_at")
    op.drop_column("incidents", "triaged_at")
    op.drop_column("incidents", "ticket_id")
    op.drop_column("incidents", "triage_degraded")
    op.drop_column("incidents", "triage_used_fallback")
    op.drop_column("incidents", "triage_needs_human_review")
    op.drop_column("incidents", "triage_confidence")
    op.drop_column("incidents", "triage_suggested_owners")
    op.drop_column("incidents", "triage_root_cause")
    op.drop_column("incidents", "triage_summary")
