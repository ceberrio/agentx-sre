# C4 — Containers

**Type:** C4 Container
**Purpose:** Show the containers in the Docker Compose stack, their tech, their responsibilities, and which ports are exposed to the host.

```mermaid
graph LR
    Browser([Browser])

    subgraph dc["docker compose (single host)"]
        subgraph agent["sre-agent :8000"]
            UI[HTMX UI<br/>static/templates]
            API[FastAPI routes<br/>/incidents]
            Graph[LangGraph<br/>6-stage state machine]
            Sec[Guardrails<br/>5-layer defense]
            LLMClient[LLM provider<br/>Gemini / OpenRouter]
            Tools[Tool clients<br/>ticket / notify / eshop]
            Obs[Observability<br/>structlog + Langfuse SDK]
        end

        subgraph mocks["mock-services :9000"]
            MockTickets[Tickets API<br/>POST/GET/Resolve]
            MockNotify[Notify webhook<br/>Team + Email]
            MockStore[(In-memory store)]
        end

        subgraph lf["Langfuse :3000"]
            LFWeb[langfuse-web]
            LFDB[(Postgres)]
        end
    end

    Browser -- "HTTP/HTMX" --> UI
    UI --> API
    API --> Graph
    Graph --> Sec
    Graph --> LLMClient
    Graph --> Tools
    Graph -.-> Obs
    Tools -- "HTTP + X-Incident-ID" --> MockTickets
    Tools -- "HTTP + X-Incident-ID" --> MockNotify
    MockTickets --> MockStore
    MockNotify --> MockStore
    Obs -- "spans + traces" --> LFWeb
    LFWeb --> LFDB

    LLMClient -. "HTTPS" .-> Cloud[(LLM provider<br/>external)]

    style agent fill:#cce5ff
    style mocks fill:#ffe5b4
    style lf fill:#d4edda
```

**Exposed host ports:** `8000` (UI/API), `9000` (mock services), `3000` (Langfuse UI). No others.

**Legend:**
- **Blue** → application container
- **Orange** → mock container (production-swap boundary)
- **Green** → observability container
- **Solid arrows** → in-cluster HTTP
- **Dotted arrow** → outbound to public LLM provider

**Why this layout:**
- Agent and mocks are physically separated → the production migration is "change the URL", nothing else.
- Langfuse runs on the same compose so judges can see live traces during the demo without setting up SaaS.
- Only three host ports, matching the brief's "expose only necessary ports" requirement.
