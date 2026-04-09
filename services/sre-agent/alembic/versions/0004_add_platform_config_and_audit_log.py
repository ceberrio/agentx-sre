"""Add platform_config and audit_log tables — HU-P032-A.

Creates the platform_config table for multi-section platform settings storage
(with Fernet-encrypted credentials) and the audit_log table for change tracking.
Audit log rows are written in the same transaction as config updates (ARC-026).

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("section", sa.String(64), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("is_credential", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section", "key", name="uq_platform_config_section_key"),
    )
    op.create_index("ix_platform_config_section", "platform_config", ["section"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("section", sa.String(64), nullable=False),
        sa.Column("field_key", sa.String(128), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_section", "audit_log", ["section"])
    op.create_index("ix_audit_log_user_email", "audit_log", ["user_email"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # Seed default platform configuration — INSERT ... ON CONFLICT DO NOTHING
    op.execute(
        sa.text("""
        INSERT INTO platform_config (section, key, value, is_credential)
        VALUES
          ('ticket_system',  'ticket_provider',              'gitlab',   false),
          ('ticket_system',  'gitlab_url',                   '',         false),
          ('ticket_system',  'gitlab_project_id',            '',         false),
          ('ticket_system',  'gitlab_token',                 '',         true),
          ('ticket_system',  'jira_url',                     '',         false),
          ('ticket_system',  'jira_project_key',             '',         false),
          ('ticket_system',  'jira_api_token',               '',         true),
          ('notifications',  'notify_provider',              'slack',    false),
          ('notifications',  'slack_channel',                '',         false),
          ('notifications',  'slack_bot_token',              '',         true),
          ('notifications',  'smtp_host',                    '',         false),
          ('notifications',  'smtp_port',                    '587',      false),
          ('notifications',  'smtp_user',                    '',         false),
          ('notifications',  'smtp_password',                '',         true),
          ('ecommerce_repo', 'context_provider',             'github',   false),
          ('ecommerce_repo', 'eshop_context_dir',            '',         false),
          ('ecommerce_repo', 'faiss_index_path',             '',         false),
          ('observability',  'log_level',                    'INFO',     false),
          ('observability',  'governance_cache_ttl_s',       '300',      false),
          ('observability',  'explainability_provider',      'langfuse', false),
          ('observability',  'langfuse_enabled',             'true',     false),
          ('security',       'guardrails_llm_judge_enabled', 'false',    false),
          ('security',       'max_upload_size_mb',           '10',       false)
        ON CONFLICT (section, key) DO NOTHING
        """)
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_user_email", table_name="audit_log")
    op.drop_index("ix_audit_log_section", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_platform_config_section", table_name="platform_config")
    op.drop_table("platform_config")
