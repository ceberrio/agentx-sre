"""Triage Agent — classifies the incident and produces a TriageResult.

Architecture: simplified ReAct loop.
  1. reason — build context from RAG search, call LLM triage
  2. emit   — wrap TriageResult into AgentEvent

The triage agent does one RAG search then calls the LLM once for the
structured analysis. This keeps latency within the P95 SLO (< 30s).

Emits exactly ONE AgentEvent:
    - "triage.completed" with payload {"triage": TriageResult}
    - "agent.error" on failure
"""
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.domain.entities import ContextDoc, TriagePrompt
from app.infrastructure.container import Container
from app.llm.prompt_registry import PROMPT_REGISTRY
from app.observability import tracing
from app.observability.metrics import (
    agent_iterations_bucket,
    incidents_by_severity_total,
    llm_calls_total,
    llm_cost_usd_total,
    rag_hit_rate,
    triage_quality_score_bucket,
)
from app.orchestration.agents.triage.state import TriageState
from app.orchestration.agents.triage.tools import build_triage_tools
from app.orchestration.shared.base_agent import BaseAgent
from app.orchestration.shared.tool_factory import ToolFactory

log = logging.getLogger(__name__)


class TriageAgent(BaseAgent):
    name = "triage"
    max_iterations: int = 3  # RAG queries allowed

    def __init__(self, container: Container) -> None:
        super().__init__(container)
        self.tools = build_triage_tools(ToolFactory(container))

    def build(self):
        g = StateGraph(TriageState)
        g.add_node("fetch_context", self._fetch_context)
        g.add_node("analyze", self._analyze)
        g.add_node("emit", self._emit)

        g.set_entry_point("fetch_context")
        g.add_edge("fetch_context", "analyze")
        g.add_edge("analyze", "emit")
        g.add_edge("emit", END)
        return g.compile()

    # ----- nodes -----

    async def _fetch_context(self, state: TriageState) -> TriageState:
        """RAG: retrieve relevant eShop documentation snippets."""
        proj = state["projection"]
        incident = proj.incident

        query = f"{incident.title} {incident.description[:500]}"
        rag_docs: list[dict] = []
        rag_queries = 0

        try:
            search_fn = self.tools["search_context"]
            docs = await search_fn(query, k=5)
            rag_docs = docs
            rag_queries = 1
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "triage.rag_failed",
                extra={"incident_id": incident.id, "error": str(exc)},
            )

        # Update RAG hit rate gauge — use dynamic provider name (F-014)
        if rag_queries > 0:
            hit_rate = len(rag_docs) / (5 * rag_queries)
            _ctx_provider_name = getattr(self.container.context, "name", "unknown")
            rag_hit_rate.labels(context_provider=_ctx_provider_name).set(hit_rate)

        state["retrieved_context"] = rag_docs
        state["tool_calls"] = rag_queries
        return state

    async def _analyze(self, state: TriageState) -> TriageState:
        """LLM call: structured triage analysis."""
        proj = state["projection"]
        incident = proj.incident
        raw_docs = state.get("retrieved_context", [])

        # Build ContextDoc objects for the prompt
        context_docs = [
            ContextDoc(
                source=d.get("source", ""),
                title=d.get("title", ""),
                content=d.get("content", ""),
                score=d.get("score", 0.0),
            )
            for d in raw_docs
        ]

        triage_prompt = TriagePrompt(
            incident_id=incident.id,
            title=incident.title,
            description=incident.description,
            log_excerpt=incident.log_text,
            image_bytes=incident.image_bytes,
            image_mime="image/jpeg" if incident.has_image else None,
            context_docs=context_docs,
        )

        try:
            result = await self.container.llm.triage(triage_prompt)
            state["triage_result"] = result

            # Emit metrics — use cost_usd populated by the adapter (ARC-002).
            # result.model is set by each adapter to the actual model identifier,
            # so provider identity is always derivable from it regardless of fallback.
            cost = result.cost_usd
            provider = result.model
            try:
                _prompt_tmpl = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
                _prompt_metric_id = _prompt_tmpl.prompt_id
            except KeyError:
                _prompt_metric_id = "triage-analysis-v1.0.0"
            llm_calls_total.labels(provider=provider, prompt_name=_prompt_metric_id).inc()
            llm_cost_usd_total.labels(provider=provider).inc(cost)
            triage_quality_score_bucket.observe(result.confidence)
            incidents_by_severity_total.labels(severity=result.severity.value).inc()

            log.info(
                "triage.completed",
                extra={
                    "incident_id": incident.id,
                    "severity": result.severity.value,
                    "confidence": result.confidence,
                    "fallback": result.used_fallback,
                },
            )
        except Exception as exc:
            log.error(
                "triage.llm_failed",
                extra={"incident_id": incident.id, "error": str(exc)},
            )
            raise

        return state

    async def _emit(self, state: TriageState) -> TriageState:
        """Build the final TriageResult and emit the AgentEvent."""
        proj = state["projection"]
        incident = proj.incident
        triage_result = state.get("triage_result")

        if triage_result is None:
            state["final_event"] = self.emit(
                "agent.error",
                error="triage_result_not_produced",
            )
            return state

        raw_docs = state.get("retrieved_context", [])
        rag_queries = state.get("tool_calls", 0)
        rag_hits = len(raw_docs)
        iterations = rag_queries + 1  # RAG + LLM call

        # Resolve prompt name/version from registry (F-017, ARC-015)
        try:
            _tmpl = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
            _prompt_name = _tmpl.name
            _prompt_version = _tmpl.version
        except KeyError:
            _prompt_name = "triage-analysis"
            _prompt_version = "1.0.0"

        # Emit Langfuse observability span (use cost_usd from adapter, ARC-002)
        with tracing.span_triage(
            incident_id=incident.id,
            context_docs=[d.get("source", "") for d in raw_docs],
            severity=triage_result.severity.value,
            llm_cost_usd=triage_result.cost_usd,
            llm_prompt_name=_prompt_name,
            llm_prompt_version=_prompt_version,
            llm_tokens_in=triage_result.tokens_in,
            llm_tokens_out=triage_result.tokens_out,
            llm_provider_used=triage_result.model,
            llm_fallback_used=triage_result.used_fallback,
            agent_iterations=iterations,
            agent_max_iterations=self.max_iterations,
            agent_rag_queries=rag_queries,
            agent_rag_hits=rag_hits,
            agent_escalated=False,
            agent_tool_calls=["search_context"] if rag_queries > 0 else [],
        ):
            pass

        # Prometheus histogram
        agent_iterations_bucket.labels(agent_name="triage").observe(iterations)

        state["final_event"] = self.emit(
            "triage.completed",
            payload={"triage": triage_result},
        )
        return state


def build_triage_agent(container: Container):
    return TriageAgent(container).build()
