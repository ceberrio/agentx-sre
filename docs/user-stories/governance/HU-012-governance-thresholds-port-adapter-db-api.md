# HU-012 — Governance Thresholds: Puerto, Adaptador, DB y API

**Module:** Governance
**Epic:** EPIC-004 — Governance & Explainability
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-08

---

## User Story

**Como** operador SRE
**Quiero** que los umbrales de gobernanza del agente (confianza minima, kill switch, severidad de auto-ticket, etc.) esten almacenados en la base de datos y sean editables en tiempo de ejecucion sin redesplegar la aplicacion
**Para** poder ajustar el comportamiento automatizado del agente de triage ante cambios en la situacion operativa sin tocar codigo

---

## Acceptance Criteria

> Cada AC es verificable de forma independiente.

| ID | Criterio | Condicion |
|----|----------|-----------|
| AC-01 | Puerto `IGovernanceProvider` definido | Dado que existe `app/domain/ports/governance_provider.py`, cuando se importa `IGovernanceProvider`, entonces expone los metodos abstractos `get_thresholds()` y `update_threshold(key, value)` con las signaturas exactas del contrato ARCHITECTURE.md §4.11 |
| AC-02 | Entidad `GovernanceThresholds` con valores por defecto | Dado que se instancia `GovernanceThresholds()` sin argumentos, entonces los campos tienen exactamente los valores: `confidence_escalation_min=0.60`, `quality_score_min_for_autoticket=0.65`, `severity_autoticket_threshold="LOW"`, `kill_switch_enabled=False`, `max_rag_docs_to_expose=5` |
| AC-03 | Migracion Alembic crea tabla y siembra defaults | Dado que se ejecuta `alembic upgrade head` sobre una BD vacia, entonces existe la tabla `governance_thresholds` con las 5 filas de configuracion por defecto y `updated_by='system'` |
| AC-04 | `PostgresGovernanceAdapter.get_thresholds()` retorna desde BD | Dado que la tabla existe con valores validos, cuando se llama `get_thresholds()`, entonces retorna un `GovernanceThresholds` hidratado con los valores actuales de la BD |
| AC-05 | Cache TTL controlado por env var | Dado que `GOVERNANCE_CACHE_TTL_S=30` esta seteada, cuando se llama `get_thresholds()` dos veces dentro de 30 segundos, entonces solo se ejecuta 1 query a BD (segunda llamada usa cache); cuando se llama despues de 30s, entonces se ejecuta una nueva query |
| AC-06 | PUT invalida cache inmediatamente | Dado que el cache esta caliente, cuando se llama `update_threshold(key, value)`, entonces el cache se invalida y la siguiente llamada a `get_thresholds()` ejecuta una query fresca a BD |
| AC-07 | `GET /governance/thresholds` retorna JSON con thresholds actuales | Dado que el servicio esta corriendo, cuando se hace `GET /governance/thresholds`, entonces retorna HTTP 200 con body JSON que contiene los 5 campos de `GovernanceThresholds` |
| AC-08 | `PUT /governance/thresholds` valida rangos de campos | Dado que se hace PUT con `{"key": "confidence_escalation_min", "value": "1.5"}`, entonces retorna HTTP 422 con mensaje de error indicando que el valor debe estar en rango 0.0-1.0; con `{"key": "kill_switch_enabled", "value": "notabool"}` retorna HTTP 422 |
| AC-09 | `PUT /governance/thresholds` actualiza y retorna thresholds actualizados | Dado que se hace PUT valido con `{"key": "confidence_escalation_min", "value": "0.75"}`, entonces retorna HTTP 200 con el objeto `GovernanceThresholds` completo con el campo actualizado y `updated_at` refrescado |
| AC-10 | `should_escalate()` implementado con logica real | Dado que `kill_switch_enabled=True`, cuando se llama `should_escalate(state, thresholds)`, entonces retorna `(True, "kill_switch")`; dado que `confidence < confidence_escalation_min`, entonces retorna `(True, "low_confidence")`; en caso contrario retorna `(False, None)` |
| AC-11 | `should_escalate()` es funcion pura sin I/O | Dado cualquier `CaseState` y `GovernanceThresholds`, cuando se llama `should_escalate()`, entonces no realiza ninguna llamada a BD, LLM, ni adapter; es determinista para los mismos inputs |
| AC-12 | Orchestrator inyecta thresholds al inicio del grafo | Dado que el orchestrator inicia el procesamiento de un incidente, cuando llama `IGovernanceProvider.get_thresholds()` una vez al comienzo, entonces pasa el resultado como parametro a `should_escalate()` sin volver a consultar la BD durante el mismo incidente |
| AC-13 | `MemoryGovernanceAdapter` funciona sin BD | Dado que `GOVERNANCE_PROVIDER=memory` esta seteado, cuando se llama `get_thresholds()`, entonces retorna `GovernanceThresholds` con defaults sin ningun query a PostgreSQL |
| AC-14 | `container.py` resuelve el adaptador por env var | Dado que `GOVERNANCE_PROVIDER=postgres` (default), cuando arranca la app, entonces `IGovernanceProvider` se resuelve a `PostgresGovernanceAdapter`; con `GOVERNANCE_PROVIDER=memory` se resuelve a `MemoryGovernanceAdapter` |
| AC-15 | `get_thresholds()` nunca lanza excepcion en produccion | Dado que la BD no esta disponible, cuando se llama `get_thresholds()`, entonces retorna `GovernanceThresholds` con valores por defecto y emite log de ERROR con `incident_id` |
| AC-16 | Prometheus counter de cache registrado | Dado cualquier llamada a `get_thresholds()`, cuando resulta en cache hit, entonces incrementa `sre_governance_cache_hits_total{result="hit"}`; cuando resulta en cache miss, incrementa `sre_governance_cache_hits_total{result="miss"}` |
| AC-17 | `sre_escalations_by_reason_total` incrementado | Dado que `should_escalate()` retorna `True`, cuando el orchestrator procesa el resultado, entonces incrementa `sre_escalations_by_reason_total{reason}` con el reason retornado por `should_escalate()` |

---

## Business Rules

| ID | Regla |
|----|-------|
| BR-01 | Los umbrales de gobernanza NUNCA se hardcodean como literales Python en nodes, agents, routers o services (ARC-017). La unica excepcion es el umbral de eval CI (`avg_overall_score >= 0.70`) que es propiedad de `@architect`. |
| BR-02 | `confidence_escalation_min` debe estar en rango `[0.0, 1.0]`. `quality_score_min_for_autoticket` idem. |
| BR-03 | `kill_switch_enabled` es bool; valores aceptados en API: `"true"`, `"false"`, `"1"`, `"0"` (case-insensitive). |
| BR-04 | `severity_autoticket_threshold` debe ser uno de: `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"CRITICAL"`. |
| BR-05 | `max_rag_docs_to_expose` debe ser entero >= 1. |
| BR-06 | La tabla `governance_thresholds` tiene exactamente 5 filas (una por campo). No se agregan filas arbitrarias sin cambio de esquema. |
| BR-07 | El TTL de cache por defecto es 60 segundos. El operador puede sobreescribir via `GOVERNANCE_CACHE_TTL_S`. |
| BR-08 | En `kill_switch_enabled=True`: todos los incidentes se escalan, la generacion automatica de tickets se pausa. |

---

## Edge Cases

| Escenario | Comportamiento esperado |
|-----------|------------------------|
| BD no disponible al arrancar la app | `get_thresholds()` retorna defaults, log ERROR; la app NO falla el startup |
| PUT con key inexistente en `GovernanceThresholds` | `update_threshold()` lanza `ValueError`; API retorna HTTP 422 con mensaje descriptivo |
| PUT con value que no puede castearse al tipo del campo | `update_threshold()` lanza `TypeError`; API retorna HTTP 422 |
| `GOVERNANCE_CACHE_TTL_S=0` | Cache deshabilitado; cada llamada va a BD directamente |
| Dos requests PUT concurrentes sobre el mismo key | Ultimo write gana (last-write-wins via `updated_at`); cache invalidado por ambos |
| `CaseState` sin `triage_result` (triage no completo) | `should_escalate()` evalua solo `kill_switch_enabled`; si es False retorna `(False, None)` |
| `confidence` igual exactamente a `confidence_escalation_min` | `confidence < threshold` es False (boundary exclusivo); NO se escala |

---

## Design Reference

| Pantalla / Componente | Referencia | Notas |
|----------------------|-----------|-------|
| Governance HTML | `app/ui/templates/governance.html` | Ver HU-016 para el template |
| API governance | `app/api/routes_governance.py` | Endpoints del contrato §4.11 |

---

## Dependencies

| HU | Tipo de dependencia |
|----|-------------------|
| HU-004 | Debe completarse antes — la logica de triage produce el `confidence` que `should_escalate()` evalua |
| HU-009 | Debe completarse antes — los logs estructurados y spans de Langfuse deben estar disponibles para instrumentar la capa de governance |
| HU-016 | Corre en paralelo — HU-016 consume los endpoints creados aqui |

---

## Technical Notes

- La funcion `should_escalate()` en `router.py` cambia su firma de `(state: CaseState) -> bool` a `(state: CaseState, thresholds: GovernanceThresholds) -> tuple[bool, str | None]`. Todos los sitios que la llamen deben actualizarse.
- `PostgresGovernanceAdapter` usa la misma conexion async SQLAlchemy definida en `infrastructure/database.py`. No crea su propia engine.
- El cache en memoria es un atributo de instancia del adaptador (dict + timestamp). No se usa Redis ni cache externo.
- La migracion Alembic debe ser idempotente: `INSERT ... ON CONFLICT DO NOTHING` para el seed.
- Dominio puro: `app/domain/entities/governance.py` y `app/domain/ports/governance_provider.py` NO importan SQLAlchemy, FastAPI ni httpx (ARC-001).

---

## Pending Questions

Ninguna — todos los contratos estan definidos en ARCHITECTURE.md §4.11 y ARC-017.

---

## Change History

| Version | Fecha | Cambio | Razon |
|---------|-------|--------|-------|
| v1 | 2026-04-08 | Creacion inicial | Arquitectura v3 — EPIC-004 |
