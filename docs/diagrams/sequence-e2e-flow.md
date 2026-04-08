# Sequence — End-to-End Incident Flow (Multi-Agent)

**Type:** Sequence
**Purpose:** Show the synchronous incident flow as it traverses the orchestrator and the three sync agents (IntakeGuard → Triage → Integration). Resolution lives in `sequence-resolution-flow.md` because it is async (ARC-014).

```mermaid
sequenceDiagram
    autonumber
    actor R as Reporter
    participant UI as HTMX UI
    participant API as FastAPI /incidents
    participant ORCH as Orchestrator
    participant IG as IntakeGuard (subgraph)
    participant TR as Triage (subgraph, ReAct)
    participant IN as Integration (subgraph)
    participant LLM as ILLMProvider
    participant CTX as IContextProvider
    participant TKT as ITicketProvider
    participant NTF as INotifyProvider
    participant LF as Langfuse
    actor Ops as On-call

    R->>UI: Fill form + upload screenshot/log
    UI->>API: POST /incidents (multipart)
    API->>ORCH: build_orchestrator_graph().ainvoke(CaseState{NEW})

    Note over ORCH,IG: IntakeGuard
    ORCH->>IG: invoke(IntakeProjection)
    IG->>IG: deterministic checks (PII, injection, off-topic)
    alt ambiguous
        IG->>LLM: judge(text)
        LLM-->>IG: allow|block
    end
    IG-->>ORCH: AgentEvent(intake.passed | intake.blocked)
    ORCH->>LF: span agent.intake_guard
    alt blocked
        ORCH-->>API: CaseState{INTAKE_BLOCKED}
        API-->>UI: 200 with blocked reason
    end

    Note over ORCH,TR: Triage (ReAct loop)
    ORCH->>TR: invoke(TriageProjection)
    loop ReAct (max N iters)
        TR->>LLM: reason(scratchpad, tools=[search_context])
        LLM-->>TR: thought + (tool call OR final answer)
        opt tool call
            TR->>CTX: search_context(query)
            CTX-->>TR: top-k snippets
        end
    end
    TR-->>ORCH: AgentEvent(triage.completed, payload=TriageResult)
    ORCH->>LF: span agent.triage

    Note over ORCH,IN: Integration
    ORCH->>IN: invoke(IntegrationProjection)
    IN->>TKT: create_ticket(...)
    TKT-->>IN: ticket_id
    IN->>NTF: notify_team(ticket)
    NTF-->>Ops: page on-call (mocked)
    IN-->>ORCH: AgentEvent(integration.team_notified, payload.events=[...])
    ORCH->>LF: span agent.integration

    ORCH-->>API: CaseState{NOTIFIED → AWAITING_RESOLUTION}
    API-->>UI: 200 with ticket_id, severity
    UI-->>R: "Ticket #abc-123 created"

    Note over Ops: Resolution flow continues asynchronously
    Note over Ops: → see sequence-resolution-flow.md
```

**Legend:**
- **The orchestrator is the single mutation point for `CaseState`** (ARC-013). Each agent returns ONE `AgentEvent`; the orchestrator folds it into state.
- **Every agent invocation emits a Langfuse span** keyed on `case_id`, so the full multi-agent run is one trace.
- **Resolution is intentionally absent** from this diagram — it lives in `sequence-resolution-flow.md` and runs in `build_resolution_graph()`, triggered by webhook.
- **ReAct cap:** the Triage Agent enforces `max_iterations` (see `BaseAgent.max_iterations`) to prevent runaway loops.
