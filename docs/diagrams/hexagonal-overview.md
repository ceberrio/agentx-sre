# Hexagonal Overview — sre-agent

**Type:** Component diagram (hexagonal layering)
**Purpose:** Show how the pure domain depends only on ports, and how `infrastructure/container.py` is the single place that resolves concrete adapters from environment variables.

```mermaid
graph TB
    subgraph API["api/ — FastAPI routes"]
        ROUTES[routes_incidents.py<br/>routes_health.py]
    end

    subgraph ORCH["orchestration/ — LangGraph"]
        GRAPH[graph.py]
        NODES[nodes/<br/>ingest · guardrails · triage<br/>ticket · notify_team · resolve_notify]
    end

    subgraph DOMAIN["domain/ — PURE CORE (no external imports)"]
        ENT[entities/<br/>Incident · Ticket · TriageResult ...]
        PORTS[ports/<br/>ILLMProvider · ITicketProvider<br/>INotifyProvider · IStorageProvider<br/>IContextProvider]
        SVC[services/<br/>TriageService]
    end

    subgraph CONTAINER["infrastructure/container.py — DI resolver"]
        BOOT[bootstrap from env vars]
    end

    subgraph ADAPT["adapters/ — concrete implementations"]
        LLM[llm/<br/>Gemini · OpenRouter · Anthropic<br/>+ LLMCircuitBreaker]
        TICK[ticket/<br/>Mock · GitLab · Jira]
        NOT[notify/<br/>Mock · Slack · Email]
        STO[storage/<br/>Memory · Postgres]
        CTX[context/<br/>Static · FAISS]
    end

    ROUTES --> GRAPH
    ROUTES --> CONTAINER
    GRAPH --> NODES
    NODES -.depends on.-> PORTS
    SVC -.depends on.-> PORTS
    SVC --> ENT
    PORTS --> ENT

    BOOT -. instantiates .-> LLM
    BOOT -. instantiates .-> TICK
    BOOT -. instantiates .-> NOT
    BOOT -. instantiates .-> STO
    BOOT -. instantiates .-> CTX

    LLM -. implements .-> PORTS
    TICK -. implements .-> PORTS
    NOT -. implements .-> PORTS
    STO -. implements .-> PORTS
    CTX -. implements .-> PORTS

    classDef pure fill:#d4f4dd,stroke:#2d8a4a,color:#000
    classDef adapter fill:#fde2e2,stroke:#a83232,color:#000
    classDef infra fill:#e2e8fd,stroke:#3a5ba8,color:#000
    class DOMAIN,ENT,PORTS,SVC pure
    class ADAPT,LLM,TICK,NOT,STO,CTX adapter
    class CONTAINER,BOOT infra
```

**Legend:**
- **Green** = pure domain. Zero framework imports. Unit-testable in isolation.
- **Red** = adapters. Depend on external SDKs (Gemini, httpx, SQLAlchemy, FAISS, ...). Implement port interfaces.
- **Blue** = infrastructure. The only file in the codebase that knows concrete adapter classes.
- Solid arrows = compile-time imports. Dashed arrows = runtime instantiation / interface implementation.

**Rule reminder:** `orchestration/nodes/` and `domain/services/` may import only from `domain/ports/`. They never import a concrete adapter. The container is the seam.
