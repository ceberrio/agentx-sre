"""Prometheus metrics — single registry for the entire sre-agent.

Naming convention (ARCHITECTURE.md §4.6):
    sre_<noun>_<unit> + OpenMetrics suffix (_total, _seconds, _usd)

IMPORTANT: This is the ONLY file allowed to create metric objects (ARC-015
analogue for metrics). All other modules must import from here, never call
prometheus_client directly.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, REGISTRY

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

incidents_received_total = Counter(
    "sre_incidents_received_total",
    "Total incident submissions received by the API",
)

incidents_by_severity_total = Counter(
    "sre_incidents_by_severity_total",
    "Incidents broken down by triage severity",
    ["severity"],
)

incidents_escalated_total = Counter(
    "sre_incidents_escalated_total",
    "Incidents where should_escalate() returned True",
    ["agent_name"],
)

llm_cost_usd_total = Counter(
    "sre_llm_cost_usd_total",
    "Cumulative LLM spend in USD",
    ["provider"],
)

llm_fallback_activations_total = Counter(
    "sre_llm_fallback_activations_total",
    "Number of times the circuit breaker fell over to the fallback provider",
    ["from_provider", "to_provider"],
)

llm_calls_total = Counter(
    "sre_llm_calls_total",
    "Total LLM calls (all methods)",
    ["provider", "prompt_name"],
)

incidents_blocked_total = Counter(
    "sre_incidents_blocked_total",
    "Incidents rejected by IntakeGuard (injection / PII / policy)",
    ["layer"],  # heuristic | llm_judge | policy
)

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------

agent_iterations_bucket = Histogram(
    "sre_agent_iterations",
    "ReAct loop iterations consumed per agent invocation",
    ["agent_name"],
    buckets=[1, 2, 3, 4, 5, 6, 8, 10],
)

triage_quality_score_bucket = Histogram(
    "sre_triage_quality_score",
    "LLM triage confidence (0.0–1.0)",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

pipeline_duration_seconds_bucket = Histogram(
    "sre_pipeline_duration_seconds",
    "Wall-clock seconds for the full sync pipeline (intake → triage → integration)",
    buckets=[1, 2, 5, 10, 15, 20, 30, 45, 60],
)

# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------

rag_hit_rate = Gauge(
    "sre_rag_hit_rate",
    "Moving hit rate for context retrieval (docs returned / docs requested)",
    ["context_provider"],
)

active_incidents = Gauge(
    "sre_active_incidents",
    "Number of incidents currently in a non-terminal state",
)

# ---------------------------------------------------------------------------
# Resolution counters
# ---------------------------------------------------------------------------

incidents_total = Counter(
    "sre_incidents_total",
    "Total incidents by final pipeline status",
    ["status"],  # resolved | failed | blocked | notified
)

# ---------------------------------------------------------------------------
# Additional metrics from Observability Contract (F-007)
# ---------------------------------------------------------------------------

escalations_by_reason_total = Counter(
    "sre_escalations_by_reason_total",
    "Escalations broken down by trigger reason",
    ["reason"],
)

human_feedback_total = Counter(
    "sre_human_feedback_total",
    "Human feedback submissions (positive / negative) on triage results",
    ["rating"],
)

governance_cache_hits_total = Counter(
    "sre_governance_cache_hits_total",
    "Governance config reads that were served from in-process cache",
)

grounding_score_bucket = Histogram(
    "sre_grounding_score",
    "RAG grounding quality score per triage invocation (0.0–1.0)",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

online_eval_post_failures_total = Counter(
    "sre_online_eval_post_failures_total",
    "Failures posting online evaluation results to Langfuse",
)
