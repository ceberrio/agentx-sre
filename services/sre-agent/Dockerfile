# =============================================================================
# Stage 1 — indexer
# Runs build_eshop_index.py at build time to pre-build the FAISS index.
# Network access is required during this stage only (downloads eShopOnWeb ZIP).
# The resulting index files are copied into the final image — no network needed
# at runtime (DEC-A07, BR-08).
# =============================================================================
FROM python:3.11-slim AS indexer

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Install only the deps needed by the indexing script (kept minimal to speed
# up layer caching — changes to the main requirements.txt don't bust this cache)
RUN pip install --no-cache-dir \
    sentence-transformers>=2.7.0 \
    faiss-cpu>=1.8.0 \
    requests>=2.31.0 \
    numpy>=1.26.0

# Copy the indexing script
COPY scripts/build_eshop_index.py .

# Download eShopOnWeb, chunk, embed, and write the FAISS index.
# Output: /data/faiss/eshop_github.index + /data/faiss/eshop_github.index.meta.json
RUN python build_eshop_index.py

# =============================================================================
# Stage 2 — final runtime image
# =============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

# Copy the pre-built FAISS index from the indexer stage.
# The index ships inside the image — no download at container startup.
COPY --from=indexer /data/faiss/eshop_github.index /data/faiss/eshop_github.index
COPY --from=indexer /data/faiss/eshop_github.index.meta.json /data/faiss/eshop_github.index.meta.json

EXPOSE 8000

# Run as a non-root system user (SEC-MN-010).
# UID 10001 is above the 1000 range reserved for regular users and avoids
# conflicts with host UIDs that might be mapped into the container.
RUN adduser --system --uid 10001 --no-create-home app \
    && chown -R app /app \
    && chown -R app /data

USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
