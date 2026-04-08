# Catalog.API — Runbook

## Overview
Serves product catalog data. PostgreSQL for persistence, Redis for caching frequently
accessed items. High read traffic — cache hit rate is critical.

## Common Incidents

### High Latency on Product Listing
**Symptom:** GET /api/v1/catalog/items responds in >2s (SLO: <500ms).
**Root cause candidates:**
1. Redis cache cold (after restart) — all requests hit PostgreSQL
2. PostgreSQL slow query on products table (missing index or full table scan)
3. Large payload size — too many items returned without pagination

**Remediation:**
1. Check cache hit rate: `catalog_cache_hit_rate` metric
2. If cache cold: warmup script runs automatically on startup; wait 2-3 min
3. Check slow query log: `EXPLAIN ANALYZE SELECT * FROM catalog_items WHERE ...`
4. Enforce pagination: pageSize max 20 (already in API, check client compliance)

### PostgreSQL Connection Error
**Symptom:** 500 error, logs show "could not connect to server: Connection refused".
**Root cause:** PostgreSQL pod crashed or network policy blocking connection.
**Remediation:**
1. `kubectl get pods -l app=catalog-db -n eshop` — check pod status
2. `kubectl describe pod <catalog-db-pod>` — look for OOMKilled or failed mounts
3. Check persistent volume: `kubectl get pvc -n eshop`
4. Restart: `kubectl rollout restart deployment/catalog-db`

### Redis Cache Eviction Storm
**Symptom:** Sudden spike in PostgreSQL queries, Redis `evicted_keys` counter high.
**Root cause:** Redis memory limit reached, LRU eviction removing hot keys.
**Remediation:**
1. Check Redis memory: `INFO memory` → `used_memory_human`
2. If at limit: increase maxmemory in Redis config or scale Redis
3. Review TTL settings — catalog items can have longer TTL (products rarely change)

## Key Metrics
- `catalog_cache_hit_rate` — Redis hit ratio (target: >85%)
- `catalog_db_query_duration_seconds` — PostgreSQL query latency
- `catalog_items_served_total` — total catalog items served
- `catalog_errors_total{type}` — errors by type (db, cache, validation)
