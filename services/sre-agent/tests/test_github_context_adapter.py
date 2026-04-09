"""Tests for GithubContextAdapter and /context/* endpoints (HU-P030).

Unit tests:
  AC-01 / BR-01  TC-U-G01: GithubContextAdapter.name == "github"
  AC-01          TC-U-G02: container.build_context returns GithubContextAdapter when
                            context_provider="github"
  AC-02          TC-U-G03: adapter loads pre-built index and enters "ready" status
  AC-03          TC-U-G04: adapter falls back to static when index file is absent
  AC-03          TC-U-G05: fallback logs the CONTEXT_DEGRADED warning
  AC-05 / AC-09  TC-U-G06: get_index_status() returns correct dict in "ready" mode
  AC-05 / AC-09  TC-U-G07: get_index_status() returns correct dict in "fallback" mode
  AC-06          TC-U-G08: search_context returns ContextDoc with source = real file path
  AC-07 / BR-04  TC-U-G09: build_eshop_index._should_include filters correctly
  BR-04          TC-U-G10: build_eshop_index._collect_files caps at MAX_FILES (via
                            the eligible-list trim logic)
  AC-09          TC-U-G11: GET /context/status returns 200 with required fields
  AC-09          TC-U-G12: GET /context/reindex/status returns 200 with required fields
  AC-04          TC-U-G13: POST /context/reindex returns 202-style {"status":"indexing"}
                            and requires API key
  AC-04          TC-U-G14: POST /context/reindex without API key returns 401
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers — minimal fake FAISS index + metadata for unit tests
# ---------------------------------------------------------------------------

_CHUNK_A = {
    "text": "The OrderService handles order placement and fulfillment.",
    "file_path": "src/ApplicationCore/Services/OrderService.cs",
    "chunk_index": 0,
}
_CHUNK_B = {
    "text": "CatalogController exposes the product listing API.",
    "file_path": "src/Web/Controllers/CatalogController.cs",
    "chunk_index": 0,
}
_FAKE_CHUNKS = [_CHUNK_A, _CHUNK_B]
_FAKE_META = {
    "files_processed": 2,
    "total_chunks": 2,
    "chunks": _FAKE_CHUNKS,
}

_DIM = 4  # tiny dimension — sufficient for unit tests


def _fake_faiss_index() -> MagicMock:
    """Return a mock FAISS index whose search() mimics IndexFlatIP."""
    idx = MagicMock()
    scores = np.array([[0.9, 0.7]], dtype="float32")
    indices = np.array([[0, 1]], dtype="int64")
    idx.search.return_value = (scores, indices)
    return idx


def _fake_embed_model() -> MagicMock:
    """Return a mock SentenceTransformer that returns unit-length vectors."""
    model = MagicMock()
    model.encode.return_value = np.ones((1, _DIM), dtype="float32") / (_DIM ** 0.5)
    return model


# ---------------------------------------------------------------------------
# AC-01 — TC-U-G01: adapter name
# ---------------------------------------------------------------------------

class TestAdapterName:
    """AC-01 / BR-01: GithubContextAdapter implements IContextProvider with name=="github"."""

    def test_name_is_github(self, tmp_path: Path) -> None:
        """TC-U-G01: adapter.name must equal 'github'."""
        from app.adapters.context.github_adapter import GithubContextAdapter

        adapter = GithubContextAdapter(
            index_path=tmp_path / "missing.index",
            eshop_context_dir=tmp_path / "eshop-context",
        )
        assert adapter.name == "github"


# ---------------------------------------------------------------------------
# AC-01 — TC-U-G02: container wires GithubContextAdapter
# ---------------------------------------------------------------------------

class TestContainerWiring:
    """AC-01: container.build_context instantiates GithubContextAdapter for 'github'."""

    def test_build_context_returns_github_adapter(self, tmp_path: Path) -> None:
        """TC-U-G02: build_context("github") returns a GithubContextAdapter."""
        from app.adapters.context.github_adapter import GithubContextAdapter
        from app.infrastructure import container as cont_module
        from app.infrastructure.config import Settings

        s = Settings(
            context_provider="github",
            faiss_github_index_path=tmp_path / "missing.index",
            eshop_context_dir=tmp_path / "ctx",
            app_database_url="postgresql+asyncpg://x:x@localhost/x",
        )
        llm_mock = MagicMock()
        adapter = cont_module.build_context(s, llm_mock)
        assert isinstance(adapter, GithubContextAdapter)


# ---------------------------------------------------------------------------
# AC-02 — TC-U-G03: adapter loads pre-built index → "ready"
# ---------------------------------------------------------------------------

class TestIndexLoading:
    """AC-02: adapter enters 'ready' status when index + metadata files exist."""

    def _write_fake_index(self, tmp_path: Path) -> Path:
        """Write a minimal real FAISS index and metadata to tmp_path."""
        faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed in this env")

        index_path = tmp_path / "eshop_github.index"
        meta_path = Path(str(index_path) + ".meta.json")

        # Build a tiny real FAISS index
        vectors = np.ones((2, _DIM), dtype="float32")
        faiss.normalize_L2(vectors)
        idx = faiss.IndexFlatIP(_DIM)
        idx.add(vectors)
        faiss.write_index(idx, str(index_path))

        meta_path.write_text(json.dumps(_FAKE_META), encoding="utf-8")
        return index_path

    def test_status_ready_when_index_exists(self, tmp_path: Path) -> None:
        """TC-U-G03: adapter status == 'ready' after loading a valid index."""
        index_path = self._write_fake_index(tmp_path)

        with patch(
            "app.adapters.context.github_adapter._load_embed_model",
            return_value=_fake_embed_model(),
        ):
            from app.adapters.context.github_adapter import GithubContextAdapter

            adapter = GithubContextAdapter(
                index_path=index_path,
                eshop_context_dir=tmp_path / "ctx",
            )

        assert adapter._status == "ready"
        assert adapter._files_processed == 2
        assert len(adapter._chunks) == 2


# ---------------------------------------------------------------------------
# AC-03 — TC-U-G04 & TC-U-G05: fallback when index absent
# ---------------------------------------------------------------------------

class TestFallbackBehavior:
    """AC-03: adapter falls back gracefully when FAISS index is missing."""

    def test_status_fallback_when_index_missing(self, tmp_path: Path) -> None:
        """TC-U-G04: adapter status == 'fallback' when index file does not exist."""
        from app.adapters.context.github_adapter import GithubContextAdapter

        adapter = GithubContextAdapter(
            index_path=tmp_path / "no_such.index",
            eshop_context_dir=tmp_path / "eshop-context",
        )
        assert adapter._status == "fallback"

    def test_context_degraded_warning_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-U-G05: 'CONTEXT_DEGRADED' appears in logs when falling back."""
        from app.adapters.context.github_adapter import GithubContextAdapter

        with caplog.at_level(logging.WARNING, logger="app.adapters.context.github_adapter"):
            GithubContextAdapter(
                index_path=tmp_path / "no_such.index",
                eshop_context_dir=tmp_path / "eshop-context",
            )

        assert any("CONTEXT_DEGRADED" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# AC-05 / AC-09 — TC-U-G06 & TC-U-G07: get_index_status()
# ---------------------------------------------------------------------------

class TestGetIndexStatus:
    """AC-05 / AC-09: get_index_status() returns the correct shape in both modes."""

    def test_ready_status_fields(self, tmp_path: Path) -> None:
        """TC-U-G06: ready-mode status dict contains all required fields."""
        faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed in this env")

        index_path = tmp_path / "idx.index"
        meta_path = Path(str(index_path) + ".meta.json")
        vectors = np.ones((2, _DIM), dtype="float32")
        faiss.normalize_L2(vectors)
        idx = faiss.IndexFlatIP(_DIM)
        idx.add(vectors)
        faiss.write_index(idx, str(index_path))
        meta_path.write_text(json.dumps(_FAKE_META), encoding="utf-8")

        with patch(
            "app.adapters.context.github_adapter._load_embed_model",
            return_value=_fake_embed_model(),
        ):
            from app.adapters.context.github_adapter import GithubContextAdapter

            adapter = GithubContextAdapter(
                index_path=index_path,
                eshop_context_dir=tmp_path / "ctx",
                eshop_repo_url="https://github.com/dotnet-architecture/eShopOnWeb",
            )

        status = adapter.get_index_status()
        required_keys = {
            "provider", "status", "indexed_files", "total_chunks",
            "index_path", "last_indexed_at", "repo_url",
        }
        assert required_keys <= status.keys()
        assert status["provider"] == "github"
        assert status["status"] == "ready"
        assert status["total_chunks"] == 2

    def test_fallback_status_fields(self, tmp_path: Path) -> None:
        """TC-U-G07: fallback-mode status dict has status='fallback'."""
        from app.adapters.context.github_adapter import GithubContextAdapter

        adapter = GithubContextAdapter(
            index_path=tmp_path / "missing.index",
            eshop_context_dir=tmp_path / "ctx",
        )
        status = adapter.get_index_status()
        assert status["status"] == "fallback"
        assert status["provider"] == "github"


# ---------------------------------------------------------------------------
# AC-06 — TC-U-G08: search_context returns ContextDoc with real source path
# ---------------------------------------------------------------------------

class TestSearchContext:
    """AC-06: search_context returns ContextDoc with file_path as source."""

    @pytest.mark.asyncio
    async def test_search_returns_context_doc_with_source(self, tmp_path: Path) -> None:
        """TC-U-G08: ContextDoc.source reflects the real file path from the index."""
        faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed in this env")

        index_path = tmp_path / "idx.index"
        meta_path = Path(str(index_path) + ".meta.json")
        vectors = np.ones((2, _DIM), dtype="float32")
        faiss.normalize_L2(vectors)
        idx = faiss.IndexFlatIP(_DIM)
        idx.add(vectors)
        faiss.write_index(idx, str(index_path))
        meta_path.write_text(json.dumps(_FAKE_META), encoding="utf-8")

        with patch(
            "app.adapters.context.github_adapter._load_embed_model",
            return_value=_fake_embed_model(),
        ):
            from app.adapters.context.github_adapter import GithubContextAdapter

            adapter = GithubContextAdapter(
                index_path=index_path,
                eshop_context_dir=tmp_path / "ctx",
            )

        # Patch the embed helper so no actual model inference runs
        with patch(
            "app.adapters.context.github_adapter._embed_query",
            return_value=np.ones((1, _DIM), dtype="float32") / (_DIM ** 0.5),
        ):
            results = await adapter.search_context("order service error", k=2)

        assert len(results) > 0
        sources = {r.source for r in results}
        assert "src/ApplicationCore/Services/OrderService.cs" in sources


# ---------------------------------------------------------------------------
# AC-07 — TC-U-G09: file filter correctness
# ---------------------------------------------------------------------------

class TestFileFilter:
    """AC-07: _should_include accepts correct extensions and rejects excluded dirs."""

    def test_accepts_cs_file(self) -> None:
        """TC-U-G09a: .cs files in src/ are accepted."""
        from scripts.build_eshop_index import _should_include

        assert _should_include(Path("src/Web/Controllers/OrderController.cs")) is True

    def test_accepts_md_file(self) -> None:
        """TC-U-G09b: .md files are accepted."""
        from scripts.build_eshop_index import _should_include

        assert _should_include(Path("docs/architecture.md")) is True

    def test_accepts_readme(self) -> None:
        """TC-U-G09c: README files (any extension) are accepted."""
        from scripts.build_eshop_index import _should_include

        assert _should_include(Path("README.md")) is True

    def test_rejects_bin_dir(self) -> None:
        """TC-U-G09d: files in bin/ are excluded."""
        from scripts.build_eshop_index import _should_include

        assert _should_include(Path("src/Web/bin/Debug/App.dll")) is False

    def test_rejects_obj_dir(self) -> None:
        """TC-U-G09e: files in obj/ are excluded."""
        from scripts.build_eshop_index import _should_include

        assert _should_include(Path("src/ApplicationCore/obj/project.assets.json")) is False

    def test_rejects_tests_dir(self) -> None:
        """TC-U-G09f: files in tests/ are excluded."""
        from scripts.build_eshop_index import _should_include

        assert _should_include(Path("tests/UnitTests/OrderServiceTest.cs")) is False

    def test_rejects_node_modules(self) -> None:
        """TC-U-G09g: node_modules/ is excluded."""
        from scripts.build_eshop_index import _should_include

        assert _should_include(Path("src/Web/node_modules/lodash/index.js")) is False

    def test_rejects_unknown_extension(self) -> None:
        """TC-U-G09h: .dll files with no INCLUDE_EXTENSIONS match are excluded."""
        from scripts.build_eshop_index import _should_include

        assert _should_include(Path("src/Web/some.dll")) is False


# ---------------------------------------------------------------------------
# BR-04 — TC-U-G10: chunking helper
# ---------------------------------------------------------------------------

class TestChunking:
    """BR-04 / AC-07: _chunk_text splits text into overlapping word-window chunks."""

    def test_single_chunk_for_short_text(self) -> None:
        """TC-U-G10a: text shorter than CHUNK_WORDS returns exactly one chunk."""
        from scripts.build_eshop_index import _chunk_text

        text = "short text with a few words"
        chunks = _chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_multiple_chunks_for_long_text(self) -> None:
        """TC-U-G10b: text longer than CHUNK_WORDS produces multiple chunks."""
        from scripts.build_eshop_index import _chunk_text, CHUNK_WORDS

        # Generate text longer than one chunk
        text = " ".join(f"word{i}" for i in range(CHUNK_WORDS + 50))
        chunks = _chunk_text(text)
        assert len(chunks) >= 2

    def test_empty_text_returns_no_chunks(self) -> None:
        """TC-U-G10c: empty string produces no chunks."""
        from scripts.build_eshop_index import _chunk_text

        assert _chunk_text("") == []
        assert _chunk_text("   ") == []


# ---------------------------------------------------------------------------
# AC-09 — TC-U-G11 & TC-U-G12: /context/status and /context/reindex/status
# ---------------------------------------------------------------------------

def _make_test_app(mock_context: MagicMock) -> TestClient:
    """Build a minimal FastAPI app with the context router and a mock container."""
    from fastapi import FastAPI
    from app.api.routes_context import router as ctx_router

    app = FastAPI()
    app.include_router(ctx_router)

    container = SimpleNamespace(context=mock_context)

    with patch("app.api.routes_context.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=False)
    return client


class TestContextStatusEndpoint:
    """AC-09 / AC-05: GET /context/status returns 200 with correct shape."""

    def test_status_endpoint_returns_200(self, tmp_path: Path) -> None:
        """TC-U-G11: GET /context/status returns HTTP 200."""
        from app.api.routes_context import router as ctx_router

        fake_status = {
            "provider": "github",
            "status": "ready",
            "indexed_files": 2,
            "total_chunks": 10,
            "index_path": "/data/faiss/eshop_github.index",
            "last_indexed_at": "2025-04-08T12:00:00+00:00",
            "repo_url": "https://github.com/dotnet-architecture/eShopOnWeb",
        }

        mock_context = MagicMock()
        mock_context.get_index_status.return_value = fake_status

        app = FastAPI()
        app.include_router(ctx_router)
        container = SimpleNamespace(context=mock_context)

        with patch("app.api.routes_context.get_container", return_value=container):
            client = TestClient(app)
            response = client.get("/context/status")

        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "github"
        assert body["status"] == "ready"
        assert "total_chunks" in body

    def test_reindex_status_returns_200(self, tmp_path: Path) -> None:
        """TC-U-G12: GET /context/reindex/status returns HTTP 200 with required fields."""
        from app.api.routes_context import router as ctx_router

        mock_context = MagicMock()
        mock_context.get_index_status.return_value = {
            "provider": "github", "status": "ready",
            "indexed_files": 2, "total_chunks": 10,
            "index_path": "/data/faiss/x.index",
            "last_indexed_at": None, "repo_url": "",
        }

        app = FastAPI()
        app.include_router(ctx_router)
        container = SimpleNamespace(context=mock_context)

        fake_settings = MagicMock()
        fake_settings.api_key = "test-key"

        with (
            patch("app.api.routes_context.get_container", return_value=container),
            patch("app.api.deps.settings", fake_settings),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/context/reindex/status", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        body = response.json()
        assert "status" in body


# ---------------------------------------------------------------------------
# AC-04 — TC-U-G13 & TC-U-G14: POST /context/reindex auth + response shape
# ---------------------------------------------------------------------------

class TestReindexEndpoint:
    """AC-04: POST /context/reindex triggers background job and requires API key."""

    def _make_app_with_reindex(self, api_key: str = "test-key") -> tuple[FastAPI, TestClient]:
        from app.api.routes_context import router as ctx_router
        from app.infrastructure.config import Settings

        mock_context = MagicMock()
        mock_context.reindex = AsyncMock()

        app = FastAPI()
        app.include_router(ctx_router)
        container = SimpleNamespace(context=mock_context)

        fake_settings = MagicMock()
        fake_settings.api_key = api_key
        fake_settings.faiss_index_path = Path("/tmp/x.index")
        fake_settings.eshop_repo_url = "https://github.com/dotnet-architecture/eShopOnWeb"

        with (
            patch("app.api.routes_context.get_container", return_value=container),
            patch("app.api.deps.settings", fake_settings),
        ):
            client = TestClient(app, raise_server_exceptions=False)
        return app, client

    def test_reindex_returns_indexing_with_valid_key(self) -> None:
        """TC-U-G13: POST /context/reindex with valid key returns {"status": "indexing"}."""
        from app.api.routes_context import router as ctx_router

        mock_context = MagicMock()
        mock_context.reindex = AsyncMock()

        app = FastAPI()
        app.include_router(ctx_router)
        container = SimpleNamespace(context=mock_context)

        fake_settings = MagicMock()
        fake_settings.api_key = "test-key"
        fake_settings.faiss_index_path = Path("/tmp/x.index")
        fake_settings.eshop_repo_url = "https://github.com/dotnet-architecture/eShopOnWeb"

        with (
            patch("app.api.routes_context.get_container", return_value=container),
            patch("app.api.deps.settings", fake_settings),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/context/reindex", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "indexing"
        assert "job_id" in body

    def test_reindex_returns_401_without_key(self) -> None:
        """TC-U-G14: POST /context/reindex without X-API-Key returns 401."""
        from app.api.routes_context import router as ctx_router

        mock_context = MagicMock()
        mock_context.reindex = AsyncMock()

        app = FastAPI()
        app.include_router(ctx_router)
        container = SimpleNamespace(context=mock_context)

        fake_settings = MagicMock()
        fake_settings.api_key = "test-key"

        with (
            patch("app.api.routes_context.get_container", return_value=container),
            patch("app.api.deps.settings", fake_settings),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/context/reindex")  # no API key header

        assert response.status_code == 401
