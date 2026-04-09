"""Tests for HU-P029 — LLM Provider Configuration with Hot Reload.

AC-01: GET /config/llm returns current config with masked API keys (ADMIN+).
AC-02: PUT /config/llm persists config, encrypts keys, hot-reloads adapter (SUPERADMIN).
AC-03: Hot reload completes < 5s (network excluded) — elapsed_ms in response.
AC-04: API keys are NEVER returned in plaintext in HTTP responses.
AC-05: PUT /config/llm requires SUPERADMIN role — ADMIN and below get 403.
AC-06: GET /config/llm requires ADMIN or SUPERADMIN — OPERATOR gets 403.
AC-07: LLMConfig.masked() replaces keys with mask token.
AC-08: MemoryLLMConfigAdapter persists and retrieves config correctly.
AC-09: PostgresLLMConfigAdapter encrypts and decrypts API keys with Fernet.
AC-10: ILLMConfigProvider.test_connection() returns True for memory adapter.
AC-11: LLMCircuitBreaker.reconfigure() updates threshold and cooldown_s.
AC-12: container.reload_llm_adapter() swaps self.llm atomically under lock.
AC-13: Partial PUT only updates provided fields — other fields keep current values.
AC-14: Invalid circuit_breaker_threshold (<1) returns HTTP 422.
BR-01: LLMConfig.masked() always masks api_key when present.
BR-02: Merge helper keeps existing API key when request sends None.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.adapters.llm_config.memory_adapter import MemoryLLMConfigAdapter
from app.adapters.llm.circuit_breaker import LLMCircuitBreaker
from app.domain.entities.llm_config import LLMConfig, _API_KEY_MASK
from app.domain.entities.user import User, UserRole
from tests.conftest import build_jwt_container, make_jwt_for_role, make_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_CONFIG = LLMConfig(
    provider="gemini",
    fallback_provider="openrouter",
    model="gemini-2.0-flash",
    fallback_model="google/gemini-2.0-flash-exp:free",
    api_key="plaintext-api-key-001",
    fallback_api_key="plaintext-fallback-key-002",
    circuit_breaker_threshold=3,
    circuit_breaker_cooldown_s=60,
    timeout_s=25,
)


def _build_container(
    role: UserRole = UserRole.SUPERADMIN,
    config: LLMConfig | None = None,
) -> SimpleNamespace:
    """Build a test container with JWT auth (real) + mocked llm_config_provider."""
    _cfg = config or _BASE_CONFIG
    _adapter = MemoryLLMConfigAdapter(default_config=_cfg)
    container = build_jwt_container(role=role)
    container.llm_config_provider = _adapter
    container.llm = MagicMock()
    container.llm.name = "stub"
    # Attach reload helpers
    container._reload_lock = asyncio.Lock()

    async def _reload(cfg: LLMConfig) -> float:
        container.llm = MagicMock()
        container.llm.name = cfg.provider
        return 12.5

    container.reload_llm_adapter = _reload
    return container


# ---------------------------------------------------------------------------
# AC-07, BR-01: LLMConfig.masked() — pure domain tests
# ---------------------------------------------------------------------------


class TestLLMConfigMasked:
    """AC-07, BR-01: LLMConfig.masked() always replaces API keys with mask token."""

    def test_masked_replaces_api_key(self):
        """AC-07: masked() replaces api_key with mask token."""
        config = LLMConfig(
            provider="gemini",
            fallback_provider="openrouter",
            model="gemini-2.0-flash",
            fallback_model="google/gemini-2.0-flash-exp:free",
            api_key="real-secret-key",
        )
        masked = config.masked()
        assert masked.api_key == _API_KEY_MASK

    def test_masked_replaces_fallback_api_key(self):
        """AC-07: masked() replaces fallback_api_key with mask token."""
        config = LLMConfig(
            provider="gemini",
            fallback_provider="openrouter",
            model="gemini-2.0-flash",
            fallback_model="google/gemini-2.0-flash-exp:free",
            fallback_api_key="real-fallback-key",
        )
        masked = config.masked()
        assert masked.fallback_api_key == _API_KEY_MASK

    def test_masked_leaves_none_key_as_none(self):
        """BR-01: masked() does not replace None keys — they stay None."""
        config = LLMConfig(
            provider="gemini",
            fallback_provider="none",
            model="gemini-2.0-flash",
            fallback_model="gemini-2.0-flash",
            api_key=None,
            fallback_api_key=None,
        )
        masked = config.masked()
        assert masked.api_key is None
        assert masked.fallback_api_key is None

    def test_masked_does_not_mutate_original(self):
        """AC-07: masked() returns a copy — original config is unchanged."""
        config = LLMConfig(
            provider="gemini",
            fallback_provider="openrouter",
            model="gemini-2.0-flash",
            fallback_model="google/gemini-2.0-flash-exp:free",
            api_key="plaintext-key",
        )
        config.masked()
        assert config.api_key == "plaintext-key"

    def test_masked_preserves_non_key_fields(self):
        """AC-07: masked() does not alter any non-key field."""
        config = _BASE_CONFIG.model_copy()
        masked = config.masked()
        assert masked.provider == config.provider
        assert masked.model == config.model
        assert masked.circuit_breaker_threshold == config.circuit_breaker_threshold


# ---------------------------------------------------------------------------
# AC-07: LLMConfig validation
# ---------------------------------------------------------------------------


class TestLLMConfigValidation:
    """AC-14: Validation rejects invalid threshold/cooldown/timeout values."""

    def test_threshold_below_one_raises(self):
        with pytest.raises(Exception):
            LLMConfig(
                provider="gemini",
                fallback_provider="openrouter",
                model="m",
                fallback_model="m",
                circuit_breaker_threshold=0,
            )

    def test_cooldown_below_one_raises(self):
        with pytest.raises(Exception):
            LLMConfig(
                provider="gemini",
                fallback_provider="openrouter",
                model="m",
                fallback_model="m",
                circuit_breaker_cooldown_s=0,
            )

    def test_timeout_below_one_raises(self):
        with pytest.raises(Exception):
            LLMConfig(
                provider="gemini",
                fallback_provider="openrouter",
                model="m",
                fallback_model="m",
                timeout_s=0,
            )


# ---------------------------------------------------------------------------
# AC-08: MemoryLLMConfigAdapter
# ---------------------------------------------------------------------------


class TestMemoryLLMConfigAdapter:
    """AC-08, AC-10: MemoryLLMConfigAdapter persists and retrieves config."""

    def test_get_returns_default_config(self):
        """AC-08: get_llm_config() returns the default config on init."""
        adapter = MemoryLLMConfigAdapter(default_config=_BASE_CONFIG)
        result = asyncio.run(adapter.get_llm_config())
        assert result.provider == "gemini"
        assert result.api_key == "plaintext-api-key-001"

    def test_update_persists_new_config(self):
        """AC-08: update_llm_config() replaces the stored config."""
        adapter = MemoryLLMConfigAdapter(default_config=_BASE_CONFIG)
        new_config = _BASE_CONFIG.model_copy(update={"provider": "anthropic", "model": "claude-3-5-sonnet-latest"})
        saved = asyncio.run(adapter.update_llm_config(new_config))
        retrieved = asyncio.run(adapter.get_llm_config())
        assert saved.provider == "anthropic"
        assert retrieved.provider == "anthropic"

    def test_get_api_key_for_primary_provider(self):
        """AC-08: get_api_key() returns primary key for primary provider."""
        adapter = MemoryLLMConfigAdapter(default_config=_BASE_CONFIG)
        key = asyncio.run(adapter.get_api_key("gemini"))
        assert key == "plaintext-api-key-001"

    def test_get_api_key_for_fallback_provider(self):
        """AC-08: get_api_key() returns fallback key for fallback provider."""
        adapter = MemoryLLMConfigAdapter(default_config=_BASE_CONFIG)
        key = asyncio.run(adapter.get_api_key("openrouter"))
        assert key == "plaintext-fallback-key-002"

    def test_get_api_key_returns_none_for_unknown_provider(self):
        """AC-08: get_api_key() returns None for unknown provider names."""
        adapter = MemoryLLMConfigAdapter(default_config=_BASE_CONFIG)
        key = asyncio.run(adapter.get_api_key("anthropic"))
        assert key is None

    def test_test_connection_returns_true(self):
        """AC-10: Memory adapter test_connection() always returns True."""
        adapter = MemoryLLMConfigAdapter(default_config=_BASE_CONFIG)
        result = asyncio.run(adapter.test_connection())
        assert result is True


# ---------------------------------------------------------------------------
# AC-09: PostgresLLMConfigAdapter — encryption/decryption (unit, no DB)
# ---------------------------------------------------------------------------


class TestPostgresAdapterEncryption:
    """AC-09: Fernet encryption/decryption round-trip for API keys."""

    def _make_adapter(self):
        from cryptography.fernet import Fernet
        from app.adapters.llm_config.postgres_adapter import PostgresLLMConfigAdapter

        key = Fernet.generate_key()
        fernet = Fernet(key)
        # Session factory is mocked — we only test encrypt/decrypt here.
        session_factory = MagicMock()
        return PostgresLLMConfigAdapter(
            session_factory=session_factory,
            fernet=fernet,
            bootstrap_config=_BASE_CONFIG,
        )

    def test_encrypt_produces_different_bytes(self):
        """AC-09: Encrypted ciphertext is not equal to the plaintext."""
        adapter = self._make_adapter()
        ciphertext = adapter._encrypt("plaintext-key")
        assert ciphertext is not None
        assert ciphertext != "plaintext-key"

    def test_decrypt_reverses_encrypt(self):
        """AC-09: decrypt(encrypt(x)) == x."""
        adapter = self._make_adapter()
        original = "my-secret-api-key-12345"
        ciphertext = adapter._encrypt(original)
        recovered = adapter._decrypt(ciphertext)
        assert recovered == original

    def test_encrypt_none_returns_none(self):
        """AC-09: encrypt(None) -> None (no key configured case)."""
        adapter = self._make_adapter()
        assert adapter._encrypt(None) is None

    def test_decrypt_none_returns_none(self):
        """AC-09: decrypt(None) -> None."""
        adapter = self._make_adapter()
        assert adapter._decrypt(None) is None

    def test_decrypt_invalid_token_returns_none(self):
        """AC-09: Invalid ciphertext returns None (not an exception)."""
        adapter = self._make_adapter()
        result = adapter._decrypt("this-is-not-valid-fernet-ciphertext")
        assert result is None


# ---------------------------------------------------------------------------
# AC-11: LLMCircuitBreaker.reconfigure()
# ---------------------------------------------------------------------------


class TestCircuitBreakerReconfigure:
    """AC-11: reconfigure() updates threshold and cooldown_s cleanly."""

    def _make_breaker(self) -> LLMCircuitBreaker:
        from app.domain.entities import TriagePrompt, TriageResult, Severity, InjectionVerdict
        from app.domain.ports import ILLMProvider

        class _StubProvider(ILLMProvider):
            name = "stub"
            async def triage(self, prompt): ...
            async def classify_injection(self, text): ...
            async def embed(self, texts): ...
            async def generate(self, prompt): ...

        return LLMCircuitBreaker(primary=_StubProvider(), threshold=3, cooldown_s=60)

    def test_reconfigure_updates_threshold(self):
        """AC-11: reconfigure() changes _threshold to new value."""
        breaker = self._make_breaker()
        breaker.reconfigure(threshold=5, cooldown_s=60)
        assert breaker._threshold == 5

    def test_reconfigure_updates_cooldown(self):
        """AC-11: reconfigure() changes _cooldown_s to new value."""
        breaker = self._make_breaker()
        breaker.reconfigure(threshold=3, cooldown_s=120)
        assert breaker._cooldown_s == 120

    def test_reconfigure_resets_failure_state(self):
        """AC-11: reconfigure() resets consecutive_failures and opened_at."""
        breaker = self._make_breaker()
        breaker._consecutive_failures = 2
        breaker._opened_at = 999999.0
        breaker.reconfigure(threshold=3, cooldown_s=60)
        assert breaker._consecutive_failures == 0
        assert breaker._opened_at is None


# ---------------------------------------------------------------------------
# AC-12: container.reload_llm_adapter() — atomic swap
# ---------------------------------------------------------------------------


class TestContainerReloadLLMAdapter:
    """AC-12, AC-03: reload_llm_adapter() swaps adapter atomically, returns elapsed_ms < 5000."""

    def test_reload_swaps_llm_and_returns_elapsed(self):
        """AC-12: After reload, container.llm is a new adapter; elapsed_ms is returned."""
        from app.infrastructure.container import Container

        # Build a minimal container with a MemoryLLMConfigAdapter and stub LLM.
        from app.adapters.llm.stub_adapter import StubLLMAdapter
        from app.adapters.llm_config.memory_adapter import MemoryLLMConfigAdapter

        stub = StubLLMAdapter()
        jwt_adapter = MagicMock()
        auth_service = MagicMock()
        llm_config_provider = MemoryLLMConfigAdapter(default_config=_BASE_CONFIG)

        from app.adapters.platform_config.memory_adapter import MemoryPlatformConfigAdapter

        container = Container(
            llm=stub,
            ticket=MagicMock(),
            notify=MagicMock(),
            storage=MagicMock(),
            context=MagicMock(),
            jwt_adapter=jwt_adapter,
            auth_service=auth_service,
            llm_config_provider=llm_config_provider,
            platform_config_provider=MemoryPlatformConfigAdapter(),
        )

        # Use a stub config for reload (avoids real API key validation).
        stub_config = LLMConfig(
            provider="stub",
            fallback_provider="none",
            model="stub",
            fallback_model="stub",
        )

        elapsed_ms = asyncio.run(container.reload_llm_adapter(stub_config))

        assert elapsed_ms < 5000, f"Hot reload took {elapsed_ms}ms — DEC-A06 violation"
        assert container.llm.name == "circuit_breaker"

    def test_reload_respects_asyncio_lock(self):
        """AC-12: Concurrent reloads are serialized by asyncio.Lock."""
        from app.infrastructure.container import Container
        from app.adapters.llm.stub_adapter import StubLLMAdapter
        from app.adapters.llm_config.memory_adapter import MemoryLLMConfigAdapter

        from app.adapters.platform_config.memory_adapter import MemoryPlatformConfigAdapter

        container = Container(
            llm=StubLLMAdapter(),
            ticket=MagicMock(),
            notify=MagicMock(),
            storage=MagicMock(),
            context=MagicMock(),
            jwt_adapter=MagicMock(),
            auth_service=MagicMock(),
            llm_config_provider=MemoryLLMConfigAdapter(default_config=_BASE_CONFIG),
            platform_config_provider=MemoryPlatformConfigAdapter(),
        )

        stub_config = LLMConfig(
            provider="stub",
            fallback_provider="none",
            model="stub",
            fallback_model="stub",
        )

        async def _run_concurrent():
            results = await asyncio.gather(
                container.reload_llm_adapter(stub_config),
                container.reload_llm_adapter(stub_config),
            )
            return results

        elapsed_list = asyncio.run(_run_concurrent())
        # Both should complete without error (lock serializes them).
        assert len(elapsed_list) == 2
        assert all(ms >= 0 for ms in elapsed_list)


# ---------------------------------------------------------------------------
# AC-01, AC-04, AC-06: GET /config/llm
# ---------------------------------------------------------------------------


class TestGetLLMConfigRoute:
    """AC-01, AC-04, AC-06: GET /config/llm returns masked config, enforces ADMIN+ role."""

    def _get_client(self, role: UserRole) -> tuple[TestClient, dict]:
        from app.main import app

        container = _build_container(role=role)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(role)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            return client, headers

    def test_admin_can_read_config(self):
        """AC-01: ADMIN role can GET /config/llm and receives 200."""
        from app.main import app

        container = _build_container(role=UserRole.ADMIN)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(UserRole.ADMIN)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/config/llm", headers=headers)

        assert resp.status_code == 200

    def test_superadmin_can_read_config(self):
        """AC-01: SUPERADMIN role can GET /config/llm."""
        from app.main import app

        container = _build_container(role=UserRole.SUPERADMIN)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(UserRole.SUPERADMIN)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/config/llm", headers=headers)

        assert resp.status_code == 200

    def test_api_key_is_masked_in_response(self):
        """AC-04: API keys are never returned in plaintext."""
        from app.main import app

        container = _build_container(role=UserRole.SUPERADMIN)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(UserRole.SUPERADMIN)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/config/llm", headers=headers)

        body = resp.json()
        assert body["config"]["api_key"] == _API_KEY_MASK
        assert body["config"]["fallback_api_key"] == _API_KEY_MASK
        # Must not contain the plaintext key anywhere in the response.
        assert "plaintext-api-key-001" not in resp.text
        assert "plaintext-fallback-key-002" not in resp.text

    def test_operator_gets_403(self):
        """AC-06: OPERATOR role receives 403 on GET /config/llm."""
        from app.main import app

        container = _build_container(role=UserRole.OPERATOR)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(UserRole.OPERATOR)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/config/llm", headers=headers)

        assert resp.status_code == 403

    def test_viewer_gets_403(self):
        """AC-06: VIEWER role receives 403 on GET /config/llm."""
        from app.main import app

        container = _build_container(role=UserRole.VIEWER)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(UserRole.VIEWER)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/config/llm", headers=headers)

        assert resp.status_code == 403

    def test_unauthenticated_gets_401(self):
        """AC-06: No credentials → 401."""
        from app.main import app

        container = _build_container(role=UserRole.SUPERADMIN)
        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/config/llm")

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC-02, AC-03, AC-04, AC-05, AC-13, AC-14, BR-02: PUT /config/llm
# ---------------------------------------------------------------------------


class TestUpdateLLMConfigRoute:
    """AC-02, AC-03, AC-04, AC-05, AC-13, AC-14, BR-02: PUT /config/llm."""

    def _put_config(self, body: dict, role: UserRole = UserRole.SUPERADMIN):
        from app.main import app

        container = _build_container(role=role)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(role)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            return client.put("/config/llm", json=body, headers=headers)

    def test_superadmin_can_update_config(self):
        """AC-02: SUPERADMIN receives 200 and reload_status='ok'."""
        resp = self._put_config({"model": "gemini-2.0-pro"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["reload_status"] == "ok"

    def test_response_never_exposes_plaintext_key(self):
        """AC-04: PUT response does not expose plaintext API key."""
        resp = self._put_config({"api_key": "new-secret-key-xyz"})
        assert resp.status_code == 200
        assert "new-secret-key-xyz" not in resp.text
        body = resp.json()
        assert body["config"]["api_key"] == _API_KEY_MASK

    def test_elapsed_ms_is_below_5000(self):
        """AC-03: elapsed_ms < 5000 — hot reload within DEC-A06 budget."""
        resp = self._put_config({"model": "gemini-2.0-flash"})
        assert resp.status_code == 200
        assert resp.json()["elapsed_ms"] < 5000

    def test_admin_gets_403(self):
        """AC-05: ADMIN role cannot PUT /config/llm — receives 403."""
        from app.main import app

        container = _build_container(role=UserRole.ADMIN)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(UserRole.ADMIN)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.put("/config/llm", json={"model": "gemini-2.0-pro"}, headers=headers)

        assert resp.status_code == 403

    def test_partial_update_keeps_unchanged_fields(self):
        """AC-13: Partial PUT only updates model — provider and threshold unchanged."""
        from app.main import app

        container = _build_container(role=UserRole.SUPERADMIN)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(UserRole.SUPERADMIN)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.put("/config/llm", json={"model": "gemini-2.0-pro"}, headers=headers)

        body = resp.json()
        assert body["config"]["provider"] == "gemini"
        assert body["config"]["circuit_breaker_threshold"] == 3

    def test_partial_update_omitting_api_key_keeps_existing_key(self):
        """BR-02: When api_key is absent in request, existing key is preserved (not cleared)."""
        from app.main import app

        container = _build_container(role=UserRole.SUPERADMIN)
        headers = {"Authorization": f"Bearer {make_jwt_for_role(UserRole.SUPERADMIN)}"}

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_llm_config.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.put("/config/llm", json={"model": "gemini-2.0-pro"}, headers=headers)

        # After update, the config in memory should still have the original api_key.
        saved_config = asyncio.run(container.llm_config_provider.get_llm_config())
        assert saved_config.api_key == "plaintext-api-key-001"

    def test_invalid_threshold_returns_422(self):
        """AC-14: circuit_breaker_threshold < 1 returns HTTP 422."""
        resp = self._put_config({"circuit_breaker_threshold": 0})
        assert resp.status_code == 422

    def test_invalid_cooldown_returns_422(self):
        """AC-14: circuit_breaker_cooldown_s < 1 returns HTTP 422."""
        resp = self._put_config({"circuit_breaker_cooldown_s": 0})
        assert resp.status_code == 422
