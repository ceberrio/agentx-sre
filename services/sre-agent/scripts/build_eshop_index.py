"""build_eshop_index.py — Build-time FAISS index for eShopOnWeb.

This script is executed ONLY during `docker build` (as a RUN step in the
indexer stage). It is NOT imported by any FastAPI or LangGraph code at runtime.

Workflow:
  1. Download eShopOnWeb ZIP from GitHub (no auth required — public repo)
  2. Extract to a temp dir
  3. Walk the tree, collect relevant files (filtered by extension and path)
  4. Chunk each file into ~512-token segments with 50-token overlap
  5. Embed each chunk with sentence-transformers all-MiniLM-L6-v2
  6. Build a FAISS IndexFlatIP (cosine similarity via normalized inner product)
  7. Save index + metadata JSON to FAISS_GITHUB_INDEX_PATH

Usage (called from Dockerfile):
  python build_eshop_index.py

Environment variables (optional, defaults shown):
  FAISS_GITHUB_INDEX_PATH   path for the FAISS index file
                            (default: /data/faiss/eshop_github.index)
  ESHOP_ZIP_URL             source ZIP URL
                            (default: eShopOnWeb main branch archive)
  MAX_FILES                 maximum files to index (default: 200)
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import Generator

import numpy as np
import requests

# ---------------------------------------------------------------------------
# Configuration (all overridable via env vars)
# ---------------------------------------------------------------------------
FAISS_INDEX_PATH = Path(
    os.environ.get("FAISS_GITHUB_INDEX_PATH", "/data/faiss/eshop_github.index")
)
ESHOP_ZIP_URL = os.environ.get(
    "ESHOP_ZIP_URL",
    "https://github.com/dotnet-architecture/eShopOnWeb/archive/refs/heads/main.zip",
)
MAX_FILES: int = int(os.environ.get("MAX_FILES", "200"))

# Chunk size in approximate "words" (1 word ≈ 1.3 tokens on average).
# 512 tokens / 1.3 ≈ 394 words; 50-token overlap ≈ 38 words.
CHUNK_WORDS = 394
OVERLAP_WORDS = 38

# ---------------------------------------------------------------------------
# File filter rules (AC-07 + spec from HU-P030)
# ---------------------------------------------------------------------------
INCLUDE_EXTENSIONS = {".md", ".cs", ".json"}
INCLUDE_NAME_PREFIXES = ("README",)

EXCLUDE_DIR_FRAGMENTS = {
    "bin", "obj", ".git", "node_modules", "wwwroot",
    ".github", "tests", "test",
}
EXCLUDE_EXTENSIONS = {".min.js", ".csproj", ".sln"}

MAX_FILE_SIZE_BYTES = 500 * 1024  # 500 KB — skip likely-binary large files


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------
def _download_with_retry(url: str, retries: int = 3) -> bytes:
    """Download url, retrying up to `retries` times with exponential backoff."""
    for attempt in range(1, retries + 1):
        try:
            print(f"[download] attempt {attempt}: {url}", flush=True)
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            if attempt == retries:
                raise RuntimeError(
                    f"Failed to download {url} after {retries} attempts: {exc}"
                ) from exc
            wait = 2 ** attempt
            print(f"[download] error: {exc} — retrying in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError("Unreachable")  # pragma: no cover


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------
def _should_include(path: Path) -> bool:
    """Return True when this file should be indexed."""
    # Check excluded directory fragments in the path parts
    lower_parts = {p.lower() for p in path.parts}
    if lower_parts & EXCLUDE_DIR_FRAGMENTS:
        return False

    name = path.name
    suffix = path.suffix.lower()
    combined_suffix = "".join(path.suffixes).lower()

    # Exclude by compound extension (e.g. .min.js)
    if combined_suffix in EXCLUDE_EXTENSIONS or suffix in EXCLUDE_EXTENSIONS:
        return False

    # Include README* files (regardless of extension)
    if any(name.startswith(prefix) for prefix in INCLUDE_NAME_PREFIXES):
        return True

    # Include by extension
    return suffix in INCLUDE_EXTENSIONS


def _collect_files(root: Path) -> list[Path]:
    """Walk root and return paths that pass the include/exclude filter."""
    collected: list[Path] = []
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file():
            continue
        # Make path relative to root for filter evaluation
        try:
            rel = candidate.relative_to(root)
        except ValueError:
            continue
        if _should_include(rel):
            collected.append(candidate)
    return collected


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping word-window chunks."""
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_WORDS, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += CHUNK_WORDS - OVERLAP_WORDS
    return chunks


# ---------------------------------------------------------------------------
# Metadata type
# ---------------------------------------------------------------------------
class ChunkMeta:
    __slots__ = ("text", "file_path", "chunk_index")

    def __init__(self, text: str, file_path: str, chunk_index: int) -> None:
        self.text = text
        self.file_path = file_path
        self.chunk_index = chunk_index

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "file_path": self.file_path,
            "chunk_index": self.chunk_index,
        }


# ---------------------------------------------------------------------------
# Main indexing pipeline
# ---------------------------------------------------------------------------
def build_index() -> None:
    import faiss
    from sentence_transformers import SentenceTransformer

    # 1. Download ZIP
    print(f"[index] downloading eShopOnWeb from {ESHOP_ZIP_URL}", flush=True)
    zip_bytes = _download_with_retry(ESHOP_ZIP_URL)
    print(f"[index] downloaded {len(zip_bytes) / 1024:.1f} KB", flush=True)

    # 2. Extract to in-memory ZipFile, walk contents
    print("[index] extracting ZIP in memory", flush=True)
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    zip_names = zf.namelist()

    # The ZIP root is typically eShopOnWeb-main/; we need relative paths from there
    zip_root_prefix = zip_names[0].split("/")[0] + "/" if zip_names else ""

    # 3. Collect eligible entries
    eligible: list[str] = []
    for name in zip_names:
        if not name.endswith("/"):  # skip directory entries
            rel_name = name[len(zip_root_prefix):] if name.startswith(zip_root_prefix) else name
            rel_path = Path(rel_name)
            if _should_include(rel_path):
                eligible.append(name)

    print(f"[index] eligible files before cap: {len(eligible)}", flush=True)

    # 4. Apply BR-04: cap at MAX_FILES (prefer smaller files — sort by size)
    if len(eligible) > MAX_FILES:
        sizes = [(zf.getinfo(n).file_size, n) for n in eligible]
        sizes.sort()
        eligible = [n for _, n in sizes[:MAX_FILES]]
        print(f"[index] capped to {MAX_FILES} files (smallest by size)", flush=True)

    # 5. Read, chunk, embed
    model = SentenceTransformer("all-MiniLM-L6-v2")
    chunks: list[ChunkMeta] = []
    files_processed = 0
    files_skipped = 0

    for zip_entry in eligible:
        info = zf.getinfo(zip_entry)

        # Skip large files (likely binary or auto-generated)
        if info.file_size > MAX_FILE_SIZE_BYTES:
            print(
                f"[skip] {zip_entry} — {info.file_size / 1024:.1f} KB > 500 KB limit",
                flush=True,
            )
            files_skipped += 1
            continue

        # Read with UTF-8; skip on encoding error
        try:
            raw = zf.read(zip_entry)
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            print(f"[skip] {zip_entry} — non-UTF-8 encoding", flush=True)
            files_skipped += 1
            continue

        if not text.strip():
            files_skipped += 1
            continue  # skip empty files silently

        # Build relative file path (strip zip root prefix)
        rel_path = zip_entry
        if rel_path.startswith(zip_root_prefix):
            rel_path = rel_path[len(zip_root_prefix):]

        file_chunks = _chunk_text(text)
        for idx, chunk_text in enumerate(file_chunks):
            chunks.append(ChunkMeta(text=chunk_text, file_path=rel_path, chunk_index=idx))

        files_processed += 1

    if not chunks:
        print("[error] no chunks produced — index not written", flush=True)
        sys.exit(1)

    print(
        f"[index] files processed={files_processed}, skipped={files_skipped}, "
        f"chunks={len(chunks)}",
        flush=True,
    )

    # 6. Embed all chunks
    print("[index] embedding chunks (this may take a few minutes)...", flush=True)
    texts = [c.text for c in chunks]
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,  # pre-normalize for cosine via IndexFlatIP
        convert_to_numpy=True,
    )
    vectors = np.array(embeddings, dtype="float32")

    # 7. Build FAISS index (IndexFlatIP — dot product on unit vectors == cosine)
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    print(f"[index] FAISS IndexFlatIP built: dim={dim}, vectors={index.ntotal}", flush=True)

    # 8. Save index + metadata
    FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    print(f"[index] saved FAISS index → {FAISS_INDEX_PATH}", flush=True)

    meta_path = Path(str(FAISS_INDEX_PATH) + ".meta.json")
    meta_payload = {
        "files_processed": files_processed,
        "total_chunks": len(chunks),
        "chunks": [c.to_dict() for c in chunks],
    }
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False), encoding="utf-8")
    print(f"[index] saved metadata → {meta_path}", flush=True)

    # 9. Summary
    print(
        f"\n=== Index build complete ===\n"
        f"  Files processed : {files_processed}\n"
        f"  Files skipped   : {files_skipped}\n"
        f"  Total chunks    : {len(chunks)}\n"
        f"  FAISS index dim : {dim}\n"
        f"  Index path      : {FAISS_INDEX_PATH}\n",
        flush=True,
    )


if __name__ == "__main__":
    build_index()
