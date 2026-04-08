"""StaticContextAdapter — keyword match over curated eShop excerpts on disk.

Used as the FAISS-free fallback (CONTEXT_PROVIDER=static).
"""
from __future__ import annotations

from pathlib import Path

from app.domain.entities import ContextDoc
from app.domain.ports import IContextProvider


class StaticContextAdapter(IContextProvider):
    name = "static"

    def __init__(self, eshop_context_dir: Path) -> None:
        self._dir = eshop_context_dir
        self._docs: list[ContextDoc] = self._load_all()

    def _load_all(self) -> list[ContextDoc]:
        if not self._dir.exists():
            return []
        out: list[ContextDoc] = []
        for path in sorted(self._dir.rglob("*.md")):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            out.append(
                ContextDoc(
                    source=str(path.relative_to(self._dir)),
                    title=path.stem,
                    content=content,
                )
            )
        return out

    async def search_context(self, query: str, k: int = 5) -> list[ContextDoc]:
        terms = [t.lower() for t in query.split() if len(t) > 3]
        scored: list[tuple[float, ContextDoc]] = []
        for doc in self._docs:
            text = doc.content.lower()
            score = sum(text.count(t) for t in terms)
            if score > 0:
                scored.append((float(score), doc.model_copy(update={"score": float(score)})))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:k]]
