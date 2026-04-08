# Identity.API — Runbook

## Overview
IdentityServer4-based authentication and authorization service. Issues JWT tokens,
manages user accounts. SQL Server backend.

## Common Incidents

### Token Validation Failures / 401 Unauthorized
**Symptom:** All API calls return 401, users cannot log in.
**Root cause candidates:**
1. Identity.API pod restarted — signing keys are ephemeral by default
2. Token issuer URL mismatch (IdentityServer `Issuer` != token validation config)
3. Clock skew between Identity.API and consumer services

**Remediation:**
1. Check Identity.API health: `kubectl logs -l app=identity-api --tail=30`
2. Verify signing key persistence: should be stored in SQL Server `DataProtectionKeys`
3. Check `ValidIssuer` config on all services matches `IDENTITY_URL`
4. Clock sync: `kubectl exec -it <pod> -- date` vs host time

### Login Page 503
**Symptom:** Browser shows 503 when navigating to /connect/authorize.
**Root cause:** Identity.API pod is down or not ready.
**Remediation:**
1. `kubectl get pods -l app=identity-api`
2. Describe pod for events: OOMKilled → increase memory limit
3. SQL Server connectivity: check identity-db pod status
4. Scale up: `kubectl scale deployment identity-api --replicas=2`

### High Login Latency
**Symptom:** Login takes >3s.
**Root cause:** SQL Server query on AspNetUsers table (no index on Email).
**Remediation:**
1. Check query plan for `SELECT * FROM AspNetUsers WHERE Email = @email`
2. Ensure index exists: `CREATE INDEX IX_AspNetUsers_Email ON AspNetUsers(NormalizedEmail)`
3. Check for N+1 in claims loading — use eager loading for UserClaims

## Key Metrics
- `identity_login_duration_seconds` — login flow latency histogram
- `identity_token_issued_total` — tokens issued counter
- `identity_login_failed_total{reason}` — failed logins (invalid_password, user_not_found, etc.)
- `identity_db_query_duration_seconds` — database query latency
