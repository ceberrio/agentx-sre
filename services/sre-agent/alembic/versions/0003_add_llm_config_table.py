"""Add llm_config table — HU-P029.

Stores encrypted LLM provider configuration with hot-reload support.
API keys are stored as Fernet-encrypted ciphertext (TEXT columns).

Seed row: inserts an "active" config row using GEMINI_API_KEY / OPENROUTER_API_KEY
env vars if present (read at migration time only — ARC-023).
The seed ensures Phase 2 of lifespan() always finds a row in DB on fresh installs.
If no key is provided, the row is seeded with provider=stub so the app starts safely.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-08
"""
from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _encrypt_key(plaintext: str | None, encryption_key: str | None) -> str | None:
    """Fernet-encrypt a plaintext API key, or return None if either arg is absent.

    NOTE: This mirrors PostgresLLMConfigAdapter._encrypt() in
    app/adapters/llm_config/postgres_adapter.py.
    If the encryption scheme changes, update both locations together.
    """
    if not plaintext or not encryption_key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(encryption_key.encode()).encrypt(plaintext.encode()).decode()
    except Exception:  # noqa: BLE001
        return None


def upgrade() -> None:
    op.create_table(
        "llm_config",
        sa.Column("config_key", sa.String(64), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("fallback_provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(256), nullable=False),
        sa.Column("fallback_model", sa.String(256), nullable=False),
        # Fernet-encrypted base64 ciphertext — NULL means no key configured.
        sa.Column("api_key_enc", sa.Text(), nullable=True),
        sa.Column("fallback_api_key_enc", sa.Text(), nullable=True),
        sa.Column(
            "circuit_breaker_threshold",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
        sa.Column(
            "circuit_breaker_cooldown_s",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
        sa.Column(
            "timeout_s",
            sa.Integer(),
            nullable=False,
            server_default="25",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("config_key"),
    )
    op.create_index("ix_llm_config_provider", "llm_config", ["provider"])

    # ----- Seed the active config row (ARC-023) -----
    # Read API keys from env at migration time (seed-time only — not read at runtime).
    encryption_key = os.getenv("CONFIG_ENCRYPTION_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    # Guard: API keys without an encryption key would be silently discarded,
    # producing a NULL api_key_enc row that causes a RuntimeError at runtime.
    # Fail fast here so the operator knows exactly what is missing.
    if (gemini_key or openrouter_key) and not encryption_key:
        raise RuntimeError(
            "CONFIG_ENCRYPTION_KEY must be set when GEMINI_API_KEY or "
            "OPENROUTER_API_KEY is provided. The seed cannot encrypt API keys "
            "without it. Set CONFIG_ENCRYPTION_KEY and re-run the migration."
        )

    if gemini_key:
        provider = "gemini"
        model = "gemini-2.0-flash"
        api_key_enc = _encrypt_key(gemini_key, encryption_key)
        fallback_provider = "openrouter" if openrouter_key else "none"
        fallback_model = "google/gemini-2.0-flash-exp:free"
        fallback_api_key_enc = _encrypt_key(openrouter_key, encryption_key)
    elif openrouter_key:
        provider = "openrouter"
        model = "google/gemini-2.0-flash-exp:free"
        api_key_enc = _encrypt_key(openrouter_key, encryption_key)
        fallback_provider = "none"
        fallback_model = ""
        fallback_api_key_enc = None
    else:
        # No keys available — seed stub so Phase 2 finds a row and starts safely.
        provider = "stub"
        model = ""
        api_key_enc = None
        fallback_provider = "none"
        fallback_model = ""
        fallback_api_key_enc = None

    op.execute(
        sa.text(
            "INSERT INTO llm_config "
            "(config_key, provider, fallback_provider, model, fallback_model, "
            " api_key_enc, fallback_api_key_enc, "
            " circuit_breaker_threshold, circuit_breaker_cooldown_s, timeout_s) "
            "VALUES "
            "(:config_key, :provider, :fallback_provider, :model, :fallback_model, "
            " :api_key_enc, :fallback_api_key_enc, "
            " :threshold, :cooldown_s, :timeout_s) "
            "ON CONFLICT (config_key) DO NOTHING"
        ).bindparams(
            config_key="active",
            provider=provider,
            fallback_provider=fallback_provider,
            model=model,
            fallback_model=fallback_model,
            api_key_enc=api_key_enc,
            fallback_api_key_enc=fallback_api_key_enc,
            threshold=3,
            cooldown_s=60,
            timeout_s=25,
        )
    )


def downgrade() -> None:
    op.drop_index("ix_llm_config_provider", table_name="llm_config")
    op.drop_table("llm_config")
