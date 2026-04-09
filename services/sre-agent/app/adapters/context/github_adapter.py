"""GithubContextAdapter — serves RAG context from the pre-built eShopOnWeb FAISS index.

The FAISS index is built at Docker build time by scripts/build_eshop_index.py.
At runtime this adapter:
  1. Loads the pre-built FAISS index from FAISS_GITHUB_INDEX_PATH.
  2. Embeds queries using sentence-transformers (same model used at build time).
  3. Returns the top-k most relevant ContextDoc objects.
  4. Falls back to StaticContextAdapter if the index file is missing.

ARC-004: Implements IContextProvider — no imports from orchestration or API layers.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import numpy as np

from app.domain.entities import ContextDoc
from app.domain.ports import IContextProvider

log = logging.getLogger(__name__)

# Embedding model must match the one used in build_eshop_index.py
_EMBED_MODEL = "all-MiniLM-L6-v2"

IndexStatus = Literal["ready", "fallback", "building"]


class GithubContextAdapter(IContextProvider):
    """Runtime adapter that serves queries from the pre-built eShopOnWeb index.

    Falls back gracefully to StaticContextAdapter when the index is absent.
    Thread-safe for concurrent reads; reindex() swaps the index atomically.
    """

    name = "github"

    def __init__(
        self,
        index_path: Path,
        eshop_context_dir: Path,
        eshop_repo_url: str = "https://github.com/dotnet-architecture/eShopOnWeb",
    ) -> None:
        self._index_path = index_path
        self._meta_path = Path(str(index_path) + ".meta.json")
        self._eshop_context_dir = eshop_context_dir
        self._repo_url = eshop_repo_url

        # Runtime state
        self._index: Any = None  # faiss.Index — imported lazily
        self._chunks: list[dict] = []  # list of {text, file_path, chunk_index}
        self._embed_model: Any = None  # SentenceTransformer — imported lazily
        self._status: IndexStatus = "fallback"
        self._files_processed: int = 0
        self._last_indexed_at: Optional[str] = None
        self._fallback: Optional[IContextProvider] = None
        # Lock guards atomic index swap during reindex (BR-03)
        self._lock = asyncio.Lock()

        self._load_index()

    # ------------------------------------------------------------------
    # Index loading
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        """Try to load the pre-built FAISS index from disk. Falls back to static on failure."""
        try:
            self._index, self._chunks, self._files_processed = _read_index(
                self._index_path, self._meta_path
            )
            self._embed_model = _load_embed_model()
            self._status = "ready"
            self._last_indexed_at = _mtime_iso(self._meta_path)
            log.info(
                "github_context.index_loaded",
                extra={
                    "chunks": len(self._chunks),
                    "files": self._files_processed,
                    "path": str(self._index_path),
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "CONTEXT_DEGRADED: using static fallback",
                extra={"reason": str(exc), "index_path": str(self._index_path)},
            )
            self._status = "fallback"
            self._fallback = _build_static_fallback(self._eshop_context_dir)

    # ------------------------------------------------------------------
    # IContextProvider contract
    # ------------------------------------------------------------------

    async def search_context(self, query: str, k: int = 5) -> list[ContextDoc]:
        """Embed query and search the FAISS index. Falls back to static if not ready."""
        async with self._lock:
            if self._status == "fallback" and self._fallback is not None:
                return await self._fallback.search_context(query, k)

            if self._index is None or not self._chunks:
                return []

        # Embed outside the lock (CPU-bound but allows concurrent reads)
        query_vec = await asyncio.get_event_loop().run_in_executor(
            None, _embed_query, self._embed_model, query
        )

        async with self._lock:
            scores, idxs = self._index.search(query_vec, k)

        results: list[ContextDoc] = []
        for score, idx in zip(scores[0], idxs[0]):
            if 0 <= idx < len(self._chunks):
                chunk = self._chunks[idx]
                file_path: str = chunk["file_path"]
                results.append(
                    ContextDoc(
                        source=file_path,
                        title=_title_from_path(file_path),
                        content=chunk["text"],
                        score=float(score),
                        # github_url is available via source; callers construct it using repo_url
                    )
                )
        return results

    # ------------------------------------------------------------------
    # Status (AC-05, AC-09)
    # ------------------------------------------------------------------

    def get_index_status(self) -> dict:
        """Return a status dictionary for the /context/status endpoint."""
        return {
            "provider": self.name,
            "status": self._status,
            "indexed_files": self._files_processed,
            "total_chunks": len(self._chunks),
            "index_path": str(self._index_path),
            "last_indexed_at": self._last_indexed_at,
            "repo_url": self._repo_url,
        }

    # ------------------------------------------------------------------
    # Reindex (AC-04, BR-03)
    # ------------------------------------------------------------------

    async def reindex(self) -> None:
        """Reload the index from disk without interrupting in-flight queries.

        Called after an external process (e.g. the build script running as a
        background job) has written a new index to FAISS_GITHUB_INDEX_PATH.
        Atomically swaps the index under the lock so ongoing searches keep
        using the old index until the new one is fully loaded.
        """
        try:
            new_index, new_chunks, new_files = _read_index(self._index_path, self._meta_path)
            new_model = _load_embed_model()
            new_last = _mtime_iso(self._meta_path)

            async with self._lock:
                self._index = new_index
                self._chunks = new_chunks
                self._files_processed = new_files
                self._embed_model = new_model
                self._last_indexed_at = new_last
                self._status = "ready"
                self._fallback = None

            log.info(
                "github_context.index_reloaded",
                extra={"chunks": len(new_chunks), "files": new_files},
            )
        except Exception as exc:  # noqa: BLE001
            log.error("github_context.reindex_failed", extra={"error": str(exc)})
            raise


# ---------------------------------------------------------------------------
# Private helpers — module-level, importable only from within this adapter
# ---------------------------------------------------------------------------

def _read_index(
    index_path: Path, meta_path: Path
) -> tuple[Any, list[dict], int]:
    """Load a FAISS index and its metadata. Raises on any failure."""
    import faiss  # deferred — only needed at runtime

    if not index_path.exists():
        raise FileNotFoundError(f"FAISS index not found: {index_path}")

    index = faiss.read_index(str(index_path))

    if not meta_path.exists():
        raise FileNotFoundError(f"Index metadata not found: {meta_path}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    chunks: list[dict] = meta.get("chunks", [])
    files_processed: int = meta.get("files_processed", 0)
    return index, chunks, files_processed


def _load_embed_model() -> Any:
    """Load the sentence-transformers model. Deferred to avoid startup cost."""
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    return SentenceTransformer(_EMBED_MODEL)


def _embed_query(model: Any, query: str) -> "np.ndarray":
    """Embed a single query string and return a (1, dim) float32 array."""
    import faiss  # noqa: PLC0415

    vec = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)
    arr = np.array(vec, dtype="float32")
    faiss.normalize_L2(arr)  # belt-and-suspenders normalization
    return arr


def _build_static_fallback(context_dir: Path) -> IContextProvider:
    """Build a StaticContextAdapter for degraded-mode fallback."""
    from app.adapters.context.static_adapter import StaticContextAdapter  # noqa: PLC0415

    return StaticContextAdapter(eshop_context_dir=context_dir)


def _title_from_path(file_path: str) -> str:
    return Path(file_path).stem


def _mtime_iso(path: Path) -> Optional[str]:
    """Return ISO-8601 UTC mtime of path, or None if path doesn't exist."""
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None
