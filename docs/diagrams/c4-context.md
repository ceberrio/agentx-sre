# C4 — System Context

**Type:** C4 Context
**Purpose:** Show who uses the SRE Incident Triage Agent and which external systems it integrates with (real and mocked).

```mermaid
graph TB
    Reporter([Reporter<br/>dev / ops / customer support])
    TechTeam([Technical Team<br/>SRE on-call])

    subgraph "SRE Incident Triage Agent (this system)"
        System[SRE Agent<br/>FastAPI + LangGraph<br/>multimodal LLM pipeline]
    end

    LLM[(LLM Provider<br/>Gemini / OpenRouter)]
    Mock[(Mock Services<br/>GitLab API + Webhook + Email<br/>swappable for real systems)]
    Lang[(Langfuse<br/>self-hosted observability)]
    eShop[(eShop codebase<br/>Microsoft, MIT<br/>triage context source)]

    Reporter -- "Submits incident<br/>(text + image/log)" --> System
    System -- "Multimodal triage call" --> LLM
    System -- "Reads curated excerpts" --> eShop
    System -- "Creates ticket<br/>POST /tickets" --> Mock
    System -- "Notifies team<br/>POST /notify/team<br/>POST /notify/email" --> Mock
    Mock -- "Notification fan-out" --> TechTeam
    System -- "Traces, logs, metrics<br/>(per stage)" --> Lang
    System -- "Resolution notification" --> Reporter

    style System fill:#1f6feb,color:#fff
    style Mock fill:#f0ad4e
    style Lang fill:#5cb85c,color:#fff
```

**Legend:**
- **Blue** → the system being built
- **Orange** → mocked dependency (production-swap path documented in `SCALING.md`)
- **Green** → observability backbone
- **Gray** → external real-world entities

**Notes:**
- The reporter and the technical team are real human actors but interact only via the UI and the (mocked) notification channels.
- eShop is the *target codebase the agent analyzes for context*, NOT the codebase of this project.
- All "Mock Services" arrows point to a single container that swaps cleanly for real GitLab + Slack + email in production.
