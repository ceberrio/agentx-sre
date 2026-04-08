"""Tests for app/llm/prompt_registry.py.

AC-01: Registry loads all YAML prompts from the prompts directory.
AC-02: get() returns a PromptTemplate with the correct fields.
AC-03: render() substitutes variables correctly.
AC-04: Missing prompt raises KeyError.
BR-01: prompt_id is formatted as "<name>-v<version>".
"""
from __future__ import annotations

import pytest

from app.llm.prompt_registry import PROMPT_REGISTRY, PromptTemplate, PromptRegistry


class TestPromptRegistryLoad:
    """AC-01: All YAML prompts are loaded."""

    def test_registry_loads_intake_guard(self):
        tmpl = PROMPT_REGISTRY.get("intake-guard", "1.0.0")
        assert tmpl is not None

    def test_registry_loads_triage_analysis(self):
        tmpl = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
        assert tmpl is not None

    def test_registry_loads_resolution_summary(self):
        tmpl = PROMPT_REGISTRY.get("resolution-summary", "1.0.0")
        assert tmpl is not None

    def test_registry_loads_judge(self):
        tmpl = PROMPT_REGISTRY.get("judge", "1.0.0")
        assert tmpl is not None

    def test_list_all_returns_all_prompts(self):
        prompts = PROMPT_REGISTRY.list_all()
        names = {p.name for p in prompts}
        assert "intake-guard" in names
        assert "triage-analysis" in names
        assert "resolution-summary" in names


class TestPromptTemplateFields:
    """AC-02: PromptTemplate has required fields."""

    def test_triage_template_has_name(self):
        tmpl = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
        assert tmpl.name == "triage-analysis"

    def test_triage_template_has_version(self):
        tmpl = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
        assert tmpl.version == "1.0.0"

    def test_triage_template_has_nonempty_prompt(self):
        tmpl = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
        assert len(tmpl.prompt) > 50

    def test_triage_template_has_model_hint(self):
        tmpl = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
        assert tmpl.model_hint


class TestPromptRender:
    """AC-03: render() substitutes variables."""

    def test_triage_render_fills_variables(self):
        tmpl = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
        rendered = tmpl.render(
            incident_title="Test incident",
            incident_description="Something broke",
            log_section="",
            image_section="",
            context_docs="No context.",
        )
        assert "Test incident" in rendered
        assert "Something broke" in rendered

    def test_intake_guard_render_fills_incident_text(self):
        tmpl = PROMPT_REGISTRY.get("intake-guard", "1.0.0")
        rendered = tmpl.render(incident_text="Sample incident")
        assert "Sample incident" in rendered


class TestPromptRegistryErrors:
    """AC-04 / BR-01: Missing prompt raises KeyError; prompt_id format is correct."""

    def test_get_missing_prompt_raises_key_error(self):
        with pytest.raises(KeyError, match="nonexistent-prompt"):
            PROMPT_REGISTRY.get("nonexistent-prompt", "1.0.0")

    def test_prompt_id_format(self):
        tmpl = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
        assert tmpl.prompt_id == "triage-analysis-v1.0.0"

    def test_get_wrong_version_raises_key_error(self):
        with pytest.raises(KeyError):
            PROMPT_REGISTRY.get("triage-analysis", "99.0.0")
