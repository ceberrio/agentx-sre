"""MemoryPlatformConfigAdapter — HU-P032-A.

In-memory implementation of IPlatformConfigProvider for test isolation.
No DB or encryption key required. Uses a plain dict as the backing store.
Audit log entries are kept in a list — accessible via self.audit_log for assertions.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from app.domain.ports.platform_config_provider import IPlatformConfigProvider

_CREDENTIAL_KEYS: frozenset[str] = frozenset(
    {"gitlab_token", "jira_api_token", "slack_bot_token", "smtp_password"}
)
_AUDIT_REDACTED = "[REDACTED]"

# Default seed data — mirrors the migration seed so tests work without a DB.
_DEFAULT_SEED: dict[str, dict[str, Any]] = {
    "ticket_system": {
        "ticket_provider": "gitlab",
        "gitlab_url": "",
        "gitlab_project_id": "",
        "gitlab_token": "",
        "jira_url": "",
        "jira_project_key": "",
        "jira_api_token": "",
    },
    "notifications": {
        "notify_provider": "slack",
        "slack_channel": "",
        "slack_bot_token": "",
        "smtp_host": "",
        "smtp_port": "587",
        "smtp_user": "",
        "smtp_password": "",
    },
    "ecommerce_repo": {
        "context_provider": "github",
        "eshop_context_dir": "",
        "faiss_index_path": "",
    },
    "observability": {
        "log_level": "INFO",
        "governance_cache_ttl_s": "300",
        "explainability_provider": "langfuse",
        "langfuse_enabled": "true",
    },
    "security": {
        "guardrails_llm_judge_enabled": "false",
        "max_upload_size_mb": "10",
    },
    # Governance thresholds — mirrors migration 0006 seed (DEC-A05).
    "governance": {
        "confidence_escalation_min": "0.7",
        "quality_score_min_for_autoticket": "0.6",
        "severity_autoticket_threshold": "HIGH",
        "max_rag_docs_to_expose": "5",
        "kill_switch_enabled": "false",
    },
}

# is_credential map matching the seed
_IS_CREDENTIAL: dict[str, bool] = {
    "gitlab_token": True,
    "jira_api_token": True,
    "slack_bot_token": True,
    "smtp_password": True,
}


class MemoryPlatformConfigAdapter(IPlatformConfigProvider):
    """Thread-safe (for tests) in-memory platform config store.

    audit_log is a public list of dicts — assert on it in tests.
    """

    def __init__(self, seed: dict[str, dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = copy.deepcopy(
            seed if seed is not None else _DEFAULT_SEED
        )
        # Track which keys are credentials
        self._is_cred: dict[str, bool] = dict(_IS_CREDENTIAL)
        self.audit_log: list[dict[str, Any]] = []

    # ----- IPlatformConfigProvider -----

    async def get_config(self, section: str) -> dict[str, Any]:
        return dict(self._store.get(section, {}))

    async def get_value(self, section: str, key: str) -> Any | None:
        return self._store.get(section, {}).get(key)

    async def update_config(
        self,
        section: str,
        updates: dict[str, Any],
        updated_by: str = "",
        ip_address: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if section not in self._store:
            self._store[section] = {}

        for key, new_value in updates.items():
            old_value = self._store[section].get(key)
            is_cred = self._is_cred.get(key, key in _CREDENTIAL_KEYS)
            self._is_cred[key] = is_cred

            self._store[section][key] = str(new_value)

            self.audit_log.append(
                {
                    "user_email": updated_by,
                    "action": "config_update",
                    "section": section,
                    "field_key": key,
                    "old_value": _AUDIT_REDACTED if is_cred else str(old_value) if old_value is not None else None,
                    "new_value": _AUDIT_REDACTED if is_cred else str(new_value),
                    "ip_address": ip_address,
                    "created_at": now,
                }
            )

    async def get_credential(self, section: str, key: str) -> str | None:
        value = self._store.get(section, {}).get(key)
        if not value:
            return None
        return value

    async def list_sections(self) -> list[str]:
        return list(self._store.keys())
