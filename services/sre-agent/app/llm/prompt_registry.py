"""Prompt Registry — ARC-015 compliance.

Every LLM prompt MUST be resolved through this module.
Inline prompt strings inside app/orchestration/agents/**  are FORBIDDEN.

Each YAML file in app/llm/prompts/ declares:
    name:    logical prompt id  (e.g. "triage-analysis")
    version: semver             (e.g. "1.0.0")
    prompt:  the actual template (may include {variables})
    model_hint: preferred model (informational; LLM adapter may ignore)

Usage:
    from app.llm.prompt_registry import PROMPT_REGISTRY
    template = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
    text = template.render(incident_title="...", context="...")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class PromptTemplate:
    """A resolved, versioned prompt template."""

    name: str
    version: str
    prompt: str
    model_hint: str = "gemini-2.0-flash"

    def render(self, **kwargs: str) -> str:
        """Substitute named variables in the prompt template.

        Variables are delimited with single braces: {variable_name}.
        Missing keys raise KeyError — fail fast.
        """
        return self.prompt.format(**kwargs)

    @property
    def prompt_id(self) -> str:
        return f"{self.name}-v{self.version}"


class PromptRegistry:
    """Loads and caches all prompt YAML files from the prompts directory."""

    def __init__(self, prompts_dir: Path = PROMPTS_DIR) -> None:
        self._dir = prompts_dir
        self._store: dict[tuple[str, str], PromptTemplate] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self._dir.exists():
            log.warning("prompt_registry.dir_missing", extra={"dir": str(self._dir)})
            self._loaded = True
            return
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                tmpl = PromptTemplate(
                    name=raw["name"],
                    version=raw["version"],
                    prompt=raw["prompt"],
                    model_hint=raw.get("model_hint", "gemini-2.0-flash"),
                )
                self._store[(tmpl.name, tmpl.version)] = tmpl
                log.info(
                    "prompt_registry.loaded",
                    extra={"id": tmpl.prompt_id, "file": path.name},
                )
            except Exception as e:  # noqa: BLE001
                log.error(
                    "prompt_registry.load_failed",
                    extra={"file": path.name, "error": str(e)},
                )
        self._loaded = True

    def get(self, name: str, version: str = "1.0.0") -> PromptTemplate:
        """Retrieve a prompt template by name and version.

        Raises:
            KeyError: if the requested prompt/version combo does not exist.
        """
        self._ensure_loaded()
        key = (name, version)
        if key not in self._store:
            available = [f"{n}-v{v}" for n, v in self._store]
            raise KeyError(
                f"Prompt '{name}' v{version} not found in registry. "
                f"Available: {available}"
            )
        return self._store[key]

    def list_all(self) -> list[PromptTemplate]:
        """Return all registered prompts."""
        self._ensure_loaded()
        return list(self._store.values())


# Module-level singleton — import and use directly
PROMPT_REGISTRY = PromptRegistry()
