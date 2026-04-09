# HU-015 — Feedback Loop: Endpoint /feedback, Widget UI y Score Langfuse

**Module:** Explainability
**Epic:** EPIC-004 — Governance & Explainability
**Priority:** Medium
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-08

---

## User Story

**Como** ingeniero SRE que reviso el resultado del triage
**Quiero** poder enviar feedback (positivo, negativo o neutral) sobre la calidad del analisis generado por el agente
**Para** que el equipo de ingenieria pueda rastrear la percepcion de calidad real del agente en produccion y mejorar sus prompts y umbrales

---

## Acceptance Criteria

> Cada AC es verificable de forma independiente.

| ID | Criterio | Condicion |
|----|----------|-----------|
| AC-01 | `POST /feedback/{incident_id}` acepta `FeedbackRecord` valido | Dado un `incident_id` existente y body `{"rating": "positive"}`, cuando se hace POST, entonces retorna HTTP 202 Accepted |
| AC-02 | Rating invalido retorna 422 | Dado body con `"rating": "excellent"`, cuando se hace POST, entonces retorna HTTP 422 con mensaje de error indicando valores validos: `positive`, `negative`, `neutral` |
| AC-03 | `incident_id` inexistente retorna 404 | Dado un `incident_id` que no existe en el storage, cuando se hace POST, entonces retorna HTTP 404 con mensaje `"Incident not found"` |
| AC-04 | Feedback duplicado retorna 409 | Dado que ya se envio feedback para `incident_id`, cuando se hace un segundo POST con el mismo `incident_id`, entonces retorna HTTP 409 Conflict con mensaje `"Feedback already submitted for this incident"` |
| AC-05 | Comentario opcional con maximo 500 caracteres | Dado body con `"comment": "[texto de mas de 500 caracteres]"`, cuando se hace POST, entonces retorna HTTP 422; dado comentario de exactamente 500 chars, entonces retorna HTTP 202 |
| AC-06 | `post_feedback()` llama a Langfuse con score correcto | Dado rating `"positive"`, cuando `IExplainabilityProvider.post_feedback()` se ejecuta, entonces posta score `"human_feedback"` con valor `1.0` en el Dataset Run del `incident_id`; `"negative"` mapea a `0.0`; `"neutral"` mapea a `0.5` |
| AC-07 | El endpoint persiste el feedback antes de llamar a Langfuse | Dado que el endpoint recibe un FeedbackRecord valido, entonces primero persiste el feedback (para poder detectar duplicados en AC-04) y luego llama `post_feedback()` como background task |
| AC-08 | Prometheus counter `sre_human_feedback_total{rating}` incrementado | Dado un feedback valido y procesado, entonces `sre_human_feedback_total{rating="positive"}` (o `negative`/`neutral`) se incrementa en 1 |
| AC-09 | Widget de feedback visible solo despues del procesamiento | Dado que el incidente fue procesado y se muestra el panel de resultado, entonces el widget de feedback (botones thumbs up / thumbs down + textarea opcional) aparece debajo del resultado; antes del procesamiento NO es visible |
| AC-10 | Widget envio via HTMX | Dado que el usuario hace click en thumbs up, cuando el form HTMX envia `POST /feedback/{incident_id}`, entonces la UI muestra confirmacion inline sin recargar la pagina |
| AC-11 | Widget deshabilitado despues del envio | Dado que el usuario ya envio feedback, cuando el DOM se actualiza con la respuesta HTMX, entonces los botones thumbs up/down se deshabilitan y se muestra mensaje de confirmacion |
| AC-12 | `MemoryExplainabilityAdapter.post_feedback()` no llama Langfuse | Dado `EXPLAINABILITY_PROVIDER=memory`, cuando se llama `post_feedback()`, entonces no se realiza ninguna llamada HTTP a Langfuse, retorna None, y emite log DEBUG |
| AC-13 | Comment es opcional en el body | Dado body sin campo `comment`, cuando se hace POST, entonces retorna HTTP 202 (comment es `None` en el `FeedbackRecord`) |

---

## Business Rules

| ID | Regla |
|----|-------|
| BR-01 | Cada incidente acepta exactamente un registro de feedback. Intentos subsiguientes retornan 409. |
| BR-02 | Los valores validos de `rating` son exclusivamente: `"positive"`, `"negative"`, `"neutral"` (en minusculas). |
| BR-03 | `comment` tiene maximo 500 caracteres. Se valida con Pydantic antes de llegar al adapter. |
| BR-04 | El score Langfuse para `human_feedback`: `positive=1.0`, `neutral=0.5`, `negative=0.0`. Mapeo fijo; no configurable en tiempo de ejecucion. |
| BR-05 | La llamada a `post_feedback()` es fire-and-forget (background task). El fallo en Langfuse no debe retornar error al usuario si el feedback fue persistido correctamente. |
| BR-06 | No se requiere autenticacion para el endpoint de feedback en el scope del hackathon (documentado como limitacion conocida). |
| BR-07 | `submitted_at` en `FeedbackRecord` lo asigna el servidor al recibir la request (timezone UTC); el cliente no lo envia. |

---

## Edge Cases

| Escenario | Comportamiento esperado |
|-----------|------------------------|
| Langfuse falla al postar `human_feedback` | Se loggea ERROR; el feedback ya fue persistido localmente; el usuario recibio 202; no se notifica el error al usuario |
| `incident_id` del path no coincide con el del body | Se usa el `incident_id` del path URL como fuente de verdad; el del body se ignora o se sobreescribe |
| Usuario envia feedback positivo y luego intenta enviar negativo | Segundo POST retorna 409; el primer feedback se mantiene |
| `MemoryStorageAdapter` sin BD: persistencia de duplicados | El adapter de memoria mantiene un set de `incident_ids` con feedback enviado durante la sesion |
| Widget HTMX si JS esta deshabilitado | Fallback graceful: el form hace POST tradicional y redirige al resultado; no es error critico para el hackathon |
| `comment` con caracteres especiales (HTML, SQL) | Validado y escapado por Pydantic + FastAPI antes de almacenar; no se ejecuta como SQL ni HTML |

---

## Design Reference

| Pantalla / Componente | Referencia | Notas |
|----------------------|-----------|-------|
| Widget de feedback | Seccion inferior del panel de resultado HTMX | Botones thumbs up / down, textarea opcional, form HTMX `hx-post="/feedback/{incident_id}"` |
| Respuesta inline | Swap HTMX del widget por mensaje de confirmacion | `hx-target="#feedback-widget"` `hx-swap="outerHTML"` |

---

## Dependencies

| HU | Tipo de dependencia |
|----|-------------------|
| HU-013 | Debe completarse antes — el widget de feedback se agrega al mismo panel de resultado donde se muestran las atribuciones RAG; el `incident_id` esta disponible en el contexto del resultado |
| HU-014 | Debe completarse antes — `post_feedback()` posta el score sobre el Dataset Run creado por `post_online_eval()`; si el run no existe el score podria fallar silenciosamente |

---

## Out of Scope

- Autenticacion del endpoint `/feedback` (documentado como limitacion conocida para produccion).
- Agregacion o analisis del feedback en un dashboard interno (seria una HU separada post-hackathon).
- Feedback en tiempo real visible para otros usuarios (no hay WebSockets en este stack).

---

## Technical Notes

- La persistencia del "feedback ya enviado" puede usar el `IStorageProvider` existente (agregar campo `feedback_submitted: bool` al objeto `Incident` almacenado) o un set en memoria en el `MemoryExplainabilityAdapter`.
- `routes_feedback.py` es un nuevo archivo en `app/api/`; no se agrega el endpoint a `routes_incidents.py`.
- El endpoint usa `BackgroundTasks` de FastAPI para `post_feedback()` identicamente al patron de `post_online_eval()` en HU-014.
- `FeedbackRecord.submitted_by` es opcional; para el hackathon se envia como `None` (anonimo).

---

## Pending Questions

Ninguna — contratos definidos en ARCHITECTURE.md §4.12 y §4.13.

---

## Change History

| Version | Fecha | Cambio | Razon |
|---------|-------|--------|-------|
| v1 | 2026-04-08 | Creacion inicial | Arquitectura v3 — EPIC-004 |
