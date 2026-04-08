# eShop on Containers — Architecture Overview

## Services

The eShop is a microservices-based e-commerce application running on Kubernetes.
Key services:

- **Catalog.API** — product catalog, PostgreSQL backend, Redis cache
- **Basket.API** — shopping cart, Redis backend
- **Ordering.API** — order processing, SQL Server, EventBus integration
- **Identity.API** — authentication via IdentityServer4, SQL Server
- **Payment.API** — payment processing, EventBus integration
- **WebApp** — Blazor front-end, aggregates API calls
- **API Gateway** — Envoy-based routing, load balancing

## Communication Patterns

- Synchronous: REST/gRPC between services via API Gateway
- Asynchronous: RabbitMQ EventBus for domain events
  - OrderStarted, OrderStockConfirmed, OrderPaid, OrderShipped

## Common Failure Modes

### Database Connectivity
- PostgreSQL connection pool exhaustion (Catalog, Identity)
- SQL Server deadlocks (Ordering during high order volume)
- Redis connection timeouts (Basket, Catalog caching)

### Message Bus Issues
- RabbitMQ queue backlog causes processing delays
- Event consumer not acknowledging messages → repeated delivery
- Dead letter queue accumulation

### API Gateway
- Circuit breaker open → downstream 503 responses
- Rate limiting → 429 Too Many Requests
- Upstream timeout → 504 Gateway Timeout

## Kubernetes Deployment

All services run as Kubernetes Deployments in the `eshop` namespace.
Health checks: /health/live and /health/ready on each service.
