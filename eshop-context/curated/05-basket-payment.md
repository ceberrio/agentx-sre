# Basket.API and Payment.API — Runbook

## Basket.API

### Overview
Shopping cart service backed by Redis. Carts are temporary — TTL 30 minutes by default.

### Common Incidents

#### Cart Lost / Empty After Reload
**Symptom:** User reports cart is empty after browser refresh.
**Root cause:** Redis TTL expired or Redis pod restart cleared in-memory data.
**Remediation:**
1. Check Redis persistence config: `CONFIG GET save` — should have persistence enabled
2. Check `basket_cart_expired_total` metric for spike
3. Increase TTL from 30min to 2h if user sessions are longer

#### 503 on Basket Operations
**Symptom:** Add to cart returns 503.
**Root cause:** Redis pod down or network issue.
**Remediation:**
1. `kubectl get pods -l app=basket-redis`
2. `kubectl exec -it <basket-redis-pod> -- redis-cli ping` — should return PONG
3. Check Redis memory: `INFO memory` — `used_memory_human`
4. If OOM: `kubectl describe pod <pod>` → `kubectl edit deployment basket-redis` → increase limits

---

## Payment.API

### Overview
Processes payment authorization. Integrates with external payment provider via EventBus.
Critical path — failures directly impact revenue.

### Common Incidents

#### Payment Timeout
**Symptom:** Orders stuck in "StockConfirmed" state; payment never processes.
**Root cause:** Payment provider timeout or RabbitMQ consumer failure.
**Remediation:**
1. Check RabbitMQ: `payment-queue` consumer count and unacked messages
2. Check Payment.API logs for provider timeout errors
3. Verify external payment provider status (check status page)
4. Manual requeue: use RabbitMQ Management UI to move DLQ messages to main queue

#### Double-charge Risk
**Symptom:** Customer reports charged twice for one order.
**Root cause:** Retry without idempotency on the payment request.
**Remediation (URGENT — P1):**
1. Immediately halt retries: set `PAYMENT_RETRY_ENABLED=false` env var
2. Contact payment provider to reverse duplicate charge
3. Post-mortem: ensure all payment requests include `IdempotencyKey = orderId`

## Key Metrics
- `basket_operations_total{operation}` — add/remove/get operations
- `basket_redis_ping_duration_seconds` — Redis health latency
- `payment_attempts_total{status}` — payment attempts by outcome
- `payment_provider_duration_seconds` — external provider call latency
