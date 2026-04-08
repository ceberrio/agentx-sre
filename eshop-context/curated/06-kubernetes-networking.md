# Kubernetes & Networking — Runbook

## Kubernetes Health Check Patterns

### Pod CrashLoopBackOff
**Diagnosis:**
```
kubectl get pods -n eshop                          # find crashing pods
kubectl describe pod <pod-name> -n eshop           # check events + exit codes
kubectl logs <pod-name> -n eshop --previous        # logs from crashed container
```
**Common exit codes:**
- Exit 1: application error (check logs)
- Exit 137: OOMKilled → increase memory limits
- Exit 143: SIGTERM not handled → increase terminationGracePeriodSeconds

### OOMKilled Recovery
1. Identify current limit: `kubectl get deployment <name> -o yaml | grep memory`
2. Patch: `kubectl patch deployment <name> -p '{"spec":{"template":{"spec":{"containers":[{"name":"<name>","resources":{"limits":{"memory":"512Mi"}}}]}}}}'`
3. Monitor: `kubectl top pods -n eshop`

### ImagePullBackOff
1. Check registry credentials: `kubectl get secret regcred -n eshop`
2. Verify image tag exists in registry
3. Check network policy allows egress to registry

## Common Network Failures

### DNS Resolution Failure
**Symptom:** Logs show "Name or service not known" for internal service names.
**Root cause:** CoreDNS pod crashed or misconfigured.
**Remediation:**
1. `kubectl get pods -n kube-system -l k8s-app=kube-dns`
2. `kubectl logs -l k8s-app=kube-dns -n kube-system --tail=20`
3. Restart CoreDNS: `kubectl rollout restart deployment/coredns -n kube-system`
4. Test DNS: `kubectl exec -it <any-pod> -- nslookup catalog-api.eshop.svc.cluster.local`

### Service Mesh / Envoy Issues
**Symptom:** 503 errors without any application logs.
**Root cause:** Envoy sidecar (if Istio used) or API Gateway circuit breaker open.
**Remediation:**
1. Check Envoy admin: `kubectl port-forward <pod> 15000` → `/clusters` → check circuit breaker state
2. Reset circuit breaker: force rolling restart of the upstream service
3. Check mTLS certificate expiry: `istioctl proxy-config secret <pod>`

## Alerting Thresholds (eShop SLOs)

| Service | SLO Metric | Threshold |
|---------|-----------|-----------|
| Catalog.API | P99 latency | < 1s |
| Ordering.API | Error rate | < 0.1% |
| Identity.API | Login latency P95 | < 500ms |
| Basket.API | Redis availability | 99.9% |
| Payment.API | Success rate | > 99.5% |

When any SLO breaches for >5 minutes → P2 incident.
When breach affects >50% of requests for >1 minute → P1 incident.
