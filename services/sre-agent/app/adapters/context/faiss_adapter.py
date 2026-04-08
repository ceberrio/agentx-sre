"""FAISSContextAdapter — semantic RAG over eShop docs.

Builds an in-process FAISS index at startup using ILLMProvider.embed().
The index is persisted to FAISS_INDEX_PATH so cold starts are fast on rebuild.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from app.domain.entities import ContextDoc
from app.domain.ports import IContextProvider, ILLMProvider

log = logging.getLogger(__name__)


class FAISSContextAdapter(IContextProvider):
    name = "faiss"

    def __init__(
        self,
        eshop_context_dir: Path,
        embedder: ILLMProvider,
        index_path: Optional[Path] = None,
    ) -> None:
        self._dir = eshop_context_dir
        self._embedder = embedder
        self._index_path = index_path
        self._docs: list[ContextDoc] = []
        self._index = None  # populated by build()

    async def build(self) -> None:
        """Index every .md file in the eshop-context dir. Called once at startup."""
        import faiss

        self._docs = []
        for path in sorted(self._dir.rglob("*.md")):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            self._docs.append(
                ContextDoc(
                    source=str(path.relative_to(self._dir)),
                    title=path.stem,
                    content=content,
                )
            )

        if not self._docs:
            log.warning("faiss.no_docs_found", extra={"dir": str(self._dir)})
            return

        embeddings = await self._embedder.embed([d.content for d in self._docs])
        vectors = np.array(embeddings, dtype="float32")
        dim = vectors.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        faiss.normalize_L2(vectors)
        self._index.add(vectors)
        log.info("faiss.indexed", extra={"docs": len(self._docs), "dim": dim})

        if self._index_path is not None:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self._index, str(self._index_path))

    async def search_context(self, query: str, k: int = 5) -> list[ContextDoc]:
        import faiss

        if self._index is None or not self._docs:
            return []
        query_vec = np.array(await self._embedder.embed([query]), dtype="float32")
        faiss.normalize_L2(query_vec)
        scores, idxs = self._index.search(query_vec, k)
        out: list[ContextDoc] = []
        for score, idx in zip(scores[0], idxs[0]):
            if 0 <= idx < len(self._docs):
                out.append(self._docs[idx].model_copy(update={"score": float(score)}))
        return out
