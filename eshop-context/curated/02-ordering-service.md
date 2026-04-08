# Ordering.API — Runbook

## Overview
Handles order creation, status management, and integrates with Payment and Inventory services
via the RabbitMQ EventBus.

## Common Incidents

### 502 Bad Gateway after deploy
**Symptom:** Nginx/API Gateway returns 502 for /api/v1/orders requests.
**Root cause:** Pod health check fails during startup — app not ready before Kubernetes
marks it Ready.
**Remediation:**
1. `kubectl rollout status deployment/ordering-api -n eshop`
2. Check startup logs: `kubectl logs -l app=ordering-api --tail=50`
3. Verify readiness probe path `/health/ready` responds 200
4. If DB migration failed on startup: check EF Core migration logs
5. Rollback: `kubectl rollout undo deployment/ordering-api`

### SQL Server Connection Timeout
**Symptom:** Orders fail with "Connection timeout expired" in logs.
**Root cause:** SQL Server connection pool exhausted (usually during traffic spike).
**Remediation:**
1. Check pool metrics: `ConnectionPool.ActiveConnections`, `ConnectionPool.PendingRequests`
2. Verify `Max Pool Size` in connection string (default 100)
3. Check for long-running queries: `SELECT * FROM sys.dm_exec_requests`
4. Scale Ordering.API horizontally if pool is shared: `kubectl scale deployment ordering-api --replicas=3`

### EventBus Processing Failure
**Symptom:** Orders stuck in "Submitted" status, never transition to "Confirmed".
**Root cause:** OrderConfirmed consumer crashed or RabbitMQ connection lost.
**Remediation:**
1. Check consumer status in RabbitMQ Management UI (port 15672)
2. Check dead letter queue: `ordering-deadletter`
3. Restart consumer: `kubectl rollout restart deployment/ordering-api`
4. Replay messages from DLQ if needed

## Key Metrics
- `ordering_orders_submitted_total` — counter of submitted orders
- `ordering_orders_failed_total` — counter of failed orders
- `ordering_processing_duration_seconds` — histogram of processing time
- `ordering_db_query_duration_seconds` — database query latency
