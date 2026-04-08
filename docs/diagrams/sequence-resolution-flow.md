# Sequence — Async Resolution Flow

**Type:** Sequence
**Purpose:** Show the asynchronous resolution path triggered by the ticket system webhook. This is intentionally decoupled from the synchronous incident graph (DEC-006 / ARC-014) so the API response time is bounded.

```mermaid
sequenceDiagram
    autonumber
    actor Ops as Ops Engineer
    participant TS as Ticket System (mock or real)
    participant API as FastAPI /webhooks/resolution
    participant ORCH as Orchestrator
    participant RG as build_resolution_graph()
    participant RA as Resolution Agent (subgraph)
    participant LLM as ILLMProvider
    participant N as INotifyProvider
    participant ST as IStorageProvider
    actor R as Reporter

    Ops->>TS: Mark ticket as resolved
    TS->>API: POST /webhooks/resolution {ticket_id, incident_id}
    API->>ORCH: load incident + ticket from storage
    API->>RG: ainvoke(CaseState{status=AWAITING_RESOLUTION})

    RG->>RA: invoke subgraph with ResolutionProjection
    RA->>LLM: summarize(incident, ticket)
    LLM-->>RA: short user-friendly summary
    RA->>N: notify_reporter(email, summary)
    N-->>R: email "Your incident has been resolved"
    RA->>ST: persist final status
    RA-->>RG: AgentEvent("resolution.completed")

    RG->>ORCH: fold event → CaseState.status = RESOLVED
    RG-->>API: final CaseState
    API-->>TS: 200 OK
```

**Legend:**
- **Compiled graph isolation:** the resolution graph is built independently of the synchronous orchestrator graph. They share `CaseState` schema but never share a single execution.
- **Single mutation point:** the orchestrator (not the agent) folds the `AgentEvent` into `CaseState`.
- In the hackathon demo, "Mark as resolved" is a UI button hitting the mock ticket service, which then calls the webhook (DEC-004 + DEC-006).
