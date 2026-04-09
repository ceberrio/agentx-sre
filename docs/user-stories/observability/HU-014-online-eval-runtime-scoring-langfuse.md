# HU-014 — Online Eval: Scoring Automatico en Runtime a Langfuse

**Module:** Observability
**Epic:** EPIC-004 — Governance & Explainability
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-08

---

## User Story

**Como** equipo de ingenieria que opera el agente SRE en produccion
**Quiero** que cada incidente procesado genere automaticamente un registro de evaluacion en Langfuse con puntuaciones de grounding y confianza
**Para** monitorear la calidad del agente en tiempo real sin necesidad de evaluaciones manuales periodicas

---

## Acceptance Criteria

> Cada AC es verificable de forma independiente.

| ID | Criterio | Condicion |
|----|----------|-----------|
| AC-01 | `LangfuseExplainabilityAdapter.post_online_eval()` implementado | Dado que `EXPLAINABILITY_PROVIDER=langfuse`, cuando se llama `post_online_eval(incident_id, report, triage_result)`, entonces crea o reutiliza el dataset `sre-online-evals` en Langfuse y registra un Dataset Run con nombre `incident-{incident_id}` |
| AC-02 | Dataset Run contiene los campos correctos | Dado un run creado en `sre-online-evals`, entonces el item de input es `{"incident_id": ..., "severity": ..., "confidence": ...}` y el expected output es `null` |
| AC-03 | Scores `grounding_score` y `confidence_score` publicados | Dado un run completado, entonces tiene dos scores: `grounding_score = ExplainabilityReport.overall_grounding_score` y `confidence_score = TriageResult.confidence`, ambos como floats 0.0-1.0 |
| AC-04 | `post_online_eval()` corre como background task | Dado que el orchestrator termina de cerrar su root span de Langfuse, cuando registra el resultado final, entonces llama `post_online_eval()` como `BackgroundTask` de FastAPI (no bloquea la respuesta HTTP al cliente) |
| AC-05 | Fallo en produccion: log ERROR + Prometheus, sin excepcion | Dado que `app_env=production` y Langfuse no esta disponible, cuando `post_online_eval()` falla, entonces emite log ERROR con `incident_id` y evento `online_eval.post_failed`, incrementa `sre_online_eval_post_failures_total`, y NO lanza excepcion (ARC-019) |
| AC-06 | Fallo en development: log WARNING, sin excepcion | Dado que `app_env=development` y Langfuse falla, cuando `post_online_eval()` falla, entonces emite log WARNING y NO lanza excepcion; `sre_online_eval_post_failures_total` NO se incrementa |
| AC-07 | Modo test (memory adapter): silencioso | Dado que `EXPLAINABILITY_PROVIDER=memory`, cuando se llama `post_online_eval()`, entonces no se realiza ninguna llamada HTTP a Langfuse y no se emite ninguna metrica ni log |
| AC-08 | Prometheus histogram `sre_grounding_score_bucket` observado | Dado que `post_online_eval()` se ejecuta exitosamente, cuando el `overall_grounding_score` esta disponible, entonces se llama `sre_grounding_score_bucket.observe(overall_grounding_score)` |
| AC-09 | Counter de cache de governance no se sobreescribe | Dado cualquier llamada a `IGovernanceProvider.get_thresholds()`, entonces `sre_governance_cache_hits_total{result="hit"}` o `{result="miss"}` se incrementa segun corresponda; el histograma de grounding NO interfiere con este counter |
| AC-10 | Dataset `sre-online-evals` creado si no existe | Dado que el dataset no existe en Langfuse, cuando se hace la primera llamada a `post_online_eval()`, entonces el adaptador lo crea antes de registrar el run; las llamadas subsiguientes reutilizan el dataset existente |
| AC-11 | Background task no bloquea respuesta al usuario | Dado que `post_online_eval()` toma hasta 2 segundos en condiciones normales, cuando el endpoint `POST /incidents` procesa el incidente, entonces el cliente recibe la respuesta HTTP antes de que `post_online_eval()` complete |
| AC-12 | `post_online_eval()` del memory adapter no lanza excepcion | Dado `MemoryExplainabilityAdapter`, cuando se llama `post_online_eval()`, entonces retorna None inmediatamente sin lanzar excepcion |

---

## Business Rules

| ID | Regla |
|----|-------|
| BR-01 | En `production`: `post_online_eval()` es tarea de fondo obligatoria. El reviewer rechaza cualquier remocion del BackgroundTask en el nodo terminal del orchestrator (ARC-019). |
| BR-02 | En `development`: best-effort; el fallo se loggea como WARNING pero no interrumpe el flujo. |
| BR-03 | En `test` (memory_adapter): cero llamadas a Langfuse. Garantiza aislamiento de tests. |
| BR-04 | El score `human_feedback` NO se posta en `post_online_eval()`; se posta en `post_feedback()` cuando el operador envia feedback (HU-015). |
| BR-05 | `sre_online_eval_post_failures_total` es un counter Prometheus; solo se incrementa en `production`. |
| BR-06 | El nombre del dataset es exactamente `sre-online-evals` (con guiones, no underscores). |

---

## Edge Cases

| Escenario | Comportamiento esperado |
|-----------|------------------------|
| Langfuse SDK lanza timeout al crear dataset | Se captura la excepcion; se loggea segun `app_env`; el counter `sre_online_eval_post_failures_total` se incrementa si `production` |
| `overall_grounding_score` es NaN o None | Se usa `0.0` como fallback antes de observar el histograma; se emite log WARNING |
| Dos llamadas concurrentes con el mismo `incident_id` | La SDK de Langfuse maneja idempotencia del Dataset Run por nombre; si falla, se loggea como error duplicado |
| `app_env` no esta seteada | Se asume `development` como fallback seguro |
| `post_online_eval()` llamado con `TriageResult` degradado | Se posta igualmente con `confidence_score = triage_result.confidence` y `grounding_score = 0.0` (del reporte degradado) |

---

## Design Reference

| Pantalla / Componente | Referencia | Notas |
|----------------------|-----------|-------|
| Langfuse Dataset UI | Dataset `sre-online-evals` en la instancia Langfuse del proyecto | Solo visible en Langfuse; no hay UI propia |
| Diagrama de pipeline de eval | `docs/diagrams/eval-pipeline.md` | Referencia arquitectural |

---

## Dependencies

| HU | Tipo de dependencia |
|----|-------------------|
| HU-013 | Debe completarse antes — `ExplainabilityReport` (con `overall_grounding_score`) es producido por `IExplainabilityProvider.compute_report()` definido en HU-013 |
| HU-009 | Debe completarse antes — el root span del orchestrator (cuyo cierre dispara el background task) es parte del contrato de observabilidad de HU-009 |
| HU-010 | Debe completarse antes — la correlacion de traza via `incident_id` conecta el Dataset Run de Langfuse con el trace correcto |
| HU-015 | Corre en paralelo — HU-015 postea el score `human_feedback` sobre el run creado por esta HU |

---

## Technical Notes

- El background task se registra en el nodo terminal del orchestrator usando `BackgroundTasks` de FastAPI inyectado como dependencia en el route handler de `POST /incidents`.
- `LangfuseExplainabilityAdapter` usa el cliente oficial Langfuse Python SDK. No se instancia directamente en el adaptador — se recibe via inyeccion del container.
- El adaptador debe verificar si el dataset existe antes de crear; la SDK puede ofrecer metodo `get_or_create_dataset()`.
- `sre_grounding_score_bucket` usa los mismos buckets estandar de Prometheus: `[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]`.
- `app_env` se lee de `infrastructure/config.py` (pydantic-settings); el valor proviene de la variable de entorno `APP_ENV`.

---

## Pending Questions

Ninguna — comportamiento por ambiente definido en ARCHITECTURE.md §4.13 y ARC-019.

---

## Change History

| Version | Fecha | Cambio | Razon |
|---------|-------|--------|-------|
| v1 | 2026-04-08 | Creacion inicial | Arquitectura v3 — EPIC-004 |
