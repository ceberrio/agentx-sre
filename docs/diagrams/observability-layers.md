# Observability Layers — v2

**Type:** Component (Mermaid `graph TD`)
**Purpose:** Show the three observability layers defined in `ARCHITECTURE.md` §4 (infra spans, LLM attributes, agent behavior attributes) and how they fan out to Langfuse (traces) and Prometheus / Grafana (metrics).

```mermaid
graph TD
    subgraph Pipeline["Incident Pipeline (one trace per incident_id)"]
        S1["sre.agent.intake_guard.ingest"]
        S2["sre.agent.intake_guard.guardrails"]
        S3["sre.agent.triage.analysis"]
        S4["sre.agent.integration.ticket_create"]
        S5["sre.agent.integration.notify_team"]
        S6["sre.agent.resolution.notify_reporter"]
        S1 --> S2 --> S3 --> S4 --> S5 -.async webhook.-> S6
    end

    subgraph L1["Layer 1 - Infra spans (per stage)"]
        L1A["incident_id<br/>stage name<br/>duration_ms<br/>status"]
    end

    subgraph L2["Layer 2 - LLM attributes (per LLM call)"]
        L2A["llm.cost_usd<br/>llm.prompt_name<br/>llm.prompt_version<br/>llm.tokens_in / tokens_out<br/>llm.provider_used<br/>llm.fallback_used"]
    end

    subgraph L3["Layer 3 - Agent behavior (per agent)"]
        L3A["agent.name<br/>agent.iterations / max_iterations<br/>agent.rag_queries / rag_hits<br/>agent.escalated<br/>agent.tool_calls"]
    end

    subgraph Q["Quality signals (orchestrator root span)"]
        QA["triage.severity<br/>triage.confidence<br/>triage.quality_score<br/>triage.affected_components<br/>case.status_final<br/>case.total_duration_ms"]
    end

    Pipeline --> L1
    S3 --> L2
    Pipeline --> L3
    Pipeline --> Q

    L1 --> LF[("Langfuse<br/>traces + spans")]
    L2 --> LF
    L3 --> LF
    Q --> LF

    L1 --> PM[("Prometheus<br/>/metrics endpoint")]
    L2 --> PM
    L3 --> PM
    Q --> PM

    PM --> GR[["Grafana<br/>SRE dashboards"]]
    LF --> JU[["Judges / Operators<br/>Langfuse UI"]]

    classDef infra fill:#dbeafe,stroke:#1e3a8a,color:#1e3a8a;
    classDef llm fill:#fef3c7,stroke:#92400e,color:#92400e;
    classDef agent fill:#dcfce7,stroke:#166534,color:#166534;
    classDef quality fill:#fce7f3,stroke:#9d174d,color:#9d174d;
    class L1,L1A infra;
    class L2,L2A llm;
    class L3,L3A agent;
    class Q,QA quality;
```

## Legend

- **Layer 1 (blue)** — Infra spans, one per pipeline stage. Always emitted, even if no LLM is involved.
- **Layer 2 (yellow)** — LLM attributes. Attached to spans that wrap an `ILLMProvider` call.
- **Layer 3 (green)** — Agent behavior. Attached to the root span of each agent subgraph invocation.
- **Quality signals (pink)** — Outcome attributes attached to the orchestrator's root span (one per incident).
- **Langfuse** — Receives full trace tree with all attributes; used by humans for debugging and by the eval pipeline as the run store.
- **Prometheus** — Pulls counters/histograms/gauges from the agent's `/metrics` endpoint for time-series dashboards.

See `ARCHITECTURE.md` §4 for the complete contract and §4.6 for the metrics list.
