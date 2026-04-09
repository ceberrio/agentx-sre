"""Add users table with seed demo users — HU-P017.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column(
            "role",
            sa.String(50),
            nullable=False,
            server_default="operator",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("google_sub", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("google_sub", name="uq_users_google_sub"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])

    # Seed demo users — one per role so all RBAC scenarios are testable
    op.execute(
        sa.text(
            """
            INSERT INTO users (email, full_name, role, google_sub)
            VALUES
              ('admin@softserve.com',    'SoftServe Admin',    'superadmin',        'mock-sub-001'),
              ('sre-lead@softserve.com', 'SRE Tech Lead',      'admin',             'mock-sub-002'),
              ('config@softserve.com',   'Flow Configurator',  'flow_configurator', 'mock-sub-003'),
              ('operator@softserve.com', 'SRE Operator',       'operator',          'mock-sub-004'),
              ('viewer@softserve.com',   'Dashboard Viewer',   'viewer',            'mock-sub-005')
            ON CONFLICT (email) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
