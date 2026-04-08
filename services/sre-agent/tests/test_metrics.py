"""Tests for app/observability/metrics.py.

AC: All required Prometheus metrics exist and are the correct type.
BR: Only this module creates metric objects.
"""
from __future__ import annotations

import pytest
from prometheus_client import Counter, Gauge, Histogram

from app.observability import metrics


class TestMetricsExist:
    """AC-01: All required metrics are defined and have correct types."""

    def test_incidents_received_total_is_counter(self):
        assert isinstance(metrics.incidents_received_total, Counter)

    def test_incidents_by_severity_total_is_counter(self):
        assert isinstance(metrics.incidents_by_severity_total, Counter)

    def test_incidents_escalated_total_is_counter(self):
        assert isinstance(metrics.incidents_escalated_total, Counter)

    def test_llm_cost_usd_total_is_counter(self):
        assert isinstance(metrics.llm_cost_usd_total, Counter)

    def test_llm_fallback_activations_total_is_counter(self):
        assert isinstance(metrics.llm_fallback_activations_total, Counter)

    def test_llm_calls_total_is_counter(self):
        assert isinstance(metrics.llm_calls_total, Counter)

    def test_agent_iterations_bucket_is_histogram(self):
        assert isinstance(metrics.agent_iterations_bucket, Histogram)

    def test_triage_quality_score_bucket_is_histogram(self):
        assert isinstance(metrics.triage_quality_score_bucket, Histogram)

    def test_pipeline_duration_seconds_bucket_is_histogram(self):
        assert isinstance(metrics.pipeline_duration_seconds_bucket, Histogram)

    def test_rag_hit_rate_is_gauge(self):
        assert isinstance(metrics.rag_hit_rate, Gauge)

    def test_active_incidents_is_gauge(self):
        assert isinstance(metrics.active_incidents, Gauge)


class TestMetricLabels:
    """AC-02: Metrics with label specs are incremented with correct labels."""

    def test_severity_label_on_incidents_by_severity(self):
        """BR: severity label must accept canonical severity values."""
        for sev in ("P1", "P2", "P3", "P4"):
            metrics.incidents_by_severity_total.labels(severity=sev).inc(0)

    def test_llm_cost_provider_label(self):
        for p in ("gemini", "openrouter"):
            metrics.llm_cost_usd_total.labels(provider=p).inc(0)

    def test_llm_calls_labels(self):
        metrics.llm_calls_total.labels(provider="gemini", prompt_name="triage-analysis-v1.0.0").inc(0)

    def test_agent_iterations_label(self):
        for agent in ("intake_guard", "triage", "integration", "resolution"):
            metrics.agent_iterations_bucket.labels(agent_name=agent).observe(1)

    def test_rag_hit_rate_label(self):
        metrics.rag_hit_rate.labels(context_provider="faiss").set(0.8)
