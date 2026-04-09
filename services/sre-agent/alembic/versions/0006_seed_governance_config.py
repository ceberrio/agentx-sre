"""Seed governance section in platform_config — DEC-A05.

Inserts the default governance thresholds row into the platform_config table
using INSERT ON CONFLICT DO NOTHING so re-running the migration (e.g. after
rollback + re-apply) is idempotent and never overwrites operator changes.

Governance keys seeded:
  confidence_escalation_min         — float stored as text, default 0.7
  quality_score_min_for_autoticket  — float stored as text, default 0.6
  severity_autoticket_threshold     — one of LOW/MEDIUM/HIGH/CRITICAL, default HIGH
  max_rag_docs_to_expose            — int stored as text, default 5
  kill_switch_enabled               — bool stored as text, default false

These values match the GovernanceThresholds TS interface in types.ts and the
GovernancePage defaults. They feed the GET /config/governance endpoint.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-09
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("""
        INSERT INTO platform_config (section, key, value, is_credential)
        VALUES
          ('governance', 'confidence_escalation_min',        '0.7',    false),
          ('governance', 'quality_score_min_for_autoticket', '0.6',    false),
          ('governance', 'severity_autoticket_threshold',    'HIGH',   false),
          ('governance', 'max_rag_docs_to_expose',           '5',      false),
          ('governance', 'kill_switch_enabled',              'false',  false)
        ON CONFLICT (section, key) DO NOTHING
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
        DELETE FROM platform_config WHERE section = 'governance'
        """)
    )
