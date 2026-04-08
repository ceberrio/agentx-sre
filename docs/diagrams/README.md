# Diagrams Index

> Architecture diagrams for the SRE Incident Triage Agent. All in Mermaid — render natively on GitHub.

| Diagram | Type | Purpose |
|---|---|---|
| [hexagonal-overview.md](hexagonal-overview.md) | Component | Hexagonal layering: pure domain ↔ ports ↔ adapters ↔ container |
| [c4-context.md](c4-context.md) | C4 — Context | Who interacts with the system and what external systems it touches |
| [c4-container.md](c4-container.md) | C4 — Container | Containers in the Docker Compose stack and their responsibilities |
| [multi-agent-topology.md](multi-agent-topology.md) | Component | Four agents + orchestrator + ports + container — the agent layer at a glance |
| [sequence-e2e-flow.md](sequence-e2e-flow.md) | Sequence | Synchronous multi-agent flow: IntakeGuard → Triage (ReAct) → Integration |
| [sequence-resolution-flow.md](sequence-resolution-flow.md) | Sequence | Async resolution flow triggered by ticket-system webhook (ARC-014) |
| [state-case-lifecycle.md](state-case-lifecycle.md) | State | CaseState status machine driven by AgentEvents |
| [observability-layers.md](observability-layers.md) | Component | Three observability layers (infra spans + LLM attrs + agent behavior) → Langfuse + Prometheus/Grafana |
| [eval-pipeline.md](eval-pipeline.md) | Flow | Golden dataset → eval runner → Triage Agent → TriageJudge → Langfuse Dataset Experiment + CI gate |

---

## How to add a diagram

1. Create `<type>-<name>.md` in this folder, in kebab-case
2. Use a Mermaid code block (```mermaid)
3. Include a "Purpose" sentence and a "Legend" section
4. Add a row to the table above
5. Reference it from `ARCHITECTURE.md` section 2
