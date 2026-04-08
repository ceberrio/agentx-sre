# Multi-Agent Topology

**Type:** Component
**Purpose:** Show the four agents, the orchestrator that owns CaseState, and how each agent depends only on ports (never on adapters). Use this diagram to onboard new contributors to the agent layer in under 60 seconds.

```mermaid
graph TB
    subgraph API["FastAPI"]
        E1["POST /incidents"]
        E2["POST /webhooks/resolution"]
    end

    subgraph ORCH["Orchestrator (CaseState owner)"]
        ROUTER["router.py<br/>(pure routing fns)"]
        SYNC["build_orchestrator_graph()"]
        ASYNC["build_resolution_graph()"]
    end

    subgraph AG["Agent Subgraphs"]
        IG["IntakeGuard Agent<br/>(5-layer defense)"]
        TR["Triage Agent<br/>(ReAct loop)"]
        IN["Integration Agent<br/>(ticket → notify)"]
        RS["Resolution Agent<br/>(async)"]
    end

    subgraph PORTS["Domain Ports"]
        P1["ILLMProvider"]
        P2["IContextProvider"]
        P3["ITicketProvider"]
        P4["INotifyProvider"]
        P5["IStorageProvider"]
    end

    subgraph CONT["Container (only file that knows adapters)"]
        C1["build_llm / build_ticket /<br/>build_notify / build_storage / build_context"]
    end

    E1 --> SYNC
    E2 --> ASYNC
    SYNC --> IG
    SYNC --> TR
    SYNC --> IN
    ASYNC --> RS
    SYNC -. uses .-> ROUTER

    IG --> P1
    TR --> P1
    TR --> P2
    IN --> P3
    IN --> P4
    RS --> P4
    RS --> P5

    P1 -.injected by.-> C1
    P2 -.injected by.-> C1
    P3 -.injected by.-> C1
    P4 -.injected by.-> C1
    P5 -.injected by.-> C1

    classDef green fill:#d4edda,stroke:#155724,color:#000
    classDef yellow fill:#fff3cd,stroke:#856404,color:#000
    classDef blue fill:#cce5ff,stroke:#004085,color:#000
    class ORCH green
    class AG blue
    class PORTS yellow
```

**Legend:**
- **Solid arrows** = runtime invocation (graph edges, port calls).
- **Dashed arrows** = build-time wiring (router consulted by graph; ports populated by container).
- The orchestrator is the **only** writer of `CaseState`. Each agent subgraph receives an immutable `Projection` and returns one `AgentEvent` (ARC-013).
- Note that `IN`tegration and `RS` Resolution live in **different compiled graphs** — Resolution is never on the synchronous path (ARC-014).
