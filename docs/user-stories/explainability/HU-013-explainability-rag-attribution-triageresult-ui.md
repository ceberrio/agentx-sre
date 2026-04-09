# HU-013 — Explainability: Atribucion RAG en TriageResult y UI

**Module:** Explainability
**Epic:** EPIC-004 — Governance & Explainability
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-08

---

## User Story

**Como** ingeniero SRE que revisa el resultado del triage
**Quiero** ver que documentos de contexto RAG utilizo el agente para llegar a su diagnostico, junto con su puntaje de relevancia
**Para** poder evaluar la confiabilidad del analisis y entender que fragmentos de codigo del eShop fundamentaron la recomendacion

---

## Acceptance Criteria

> Cada AC es verificable de forma independiente.

| ID | Criterio | Condicion |
|----|----------|-----------|
| AC-01 | Entidades de explainability definidas en dominio | Dado que existe `app/domain/entities/explainability.py`, entonces contiene las clases `RagAttribution`, `OutputGrounding`, `ExplainabilityReport` y `FeedbackRecord` con exactamente los campos definidos en ARCHITECTURE.md §4.12 |
| AC-02 | Puerto `IExplainabilityProvider` definido | Dado que existe `app/domain/ports/explainability_provider.py`, entonces expone `compute_report()`, `post_feedback()`, y `post_online_eval()` con las signaturas del contrato §4.12 |
| AC-03 | `TriageResult` extendido con campos de explainability | Dado que se lee `app/domain/entities/triage.py`, entonces `TriageResult` contiene los campos `rag_attribution: list[RagAttribution] = Field(default_factory=list)` y `explainability_report: Optional[ExplainabilityReport] = None` |
| AC-04 | Triage agent popula `rag_attribution` desde resultados FAISS | Dado que el agente de triage obtiene N documentos de contexto via `IContextProvider.search_context()`, cuando construye el `TriageResult`, entonces `rag_attribution` contiene exactamente N entradas `RagAttribution`, una por documento, con `doc_id`, `chunk_preview` (primeros 200 chars), y `relevance_score` derivado de la similitud coseno retornada por FAISS |
| AC-05 | `relevance_score` es float 0.0-1.0 | Dado cualquier `RagAttribution` en un triage no-degradado, cuando se lee `relevance_score`, entonces es un float en `[0.0, 1.0]`; valores fuera de rango son rechazados por validacion Pydantic |
| AC-06 | Lista vacia solo aceptable en modo degradado | Dado que `TriageResult.degraded == False` y `rag_attribution` esta vacia, cuando el orchestrator recibe el resultado, entonces emite un log WARNING con `incident_id` y evento `triage.empty_attribution`; NO lanza excepcion (el pipeline continua) |
| AC-07 | `degraded=True` permite `rag_attribution` vacia sin warning | Dado que `TriageResult.degraded == True`, cuando `rag_attribution` esta vacia, entonces NO se emite warning; es el caso de circuito abierto (ARC-018) |
| AC-08 | `compute_report()` completado antes de cerrar root span | Dado que el triage agent retorna `TriageResult`, cuando el orchestrator lo recibe, entonces llama `IExplainabilityProvider.compute_report()` y espera su resultado ANTES de emitir el span raiz del orchestrator (no es fire-and-forget) |
| AC-09 | `compute_report()` nunca lanza excepcion | Dado que el LLM judge falla durante `compute_report()`, entonces retorna un `ExplainabilityReport` degradado con `overall_grounding_score=0.0` y `output_groundings=[]`, y emite log ERROR |
| AC-10 | UI muestra seccion "Fuentes" con barras de relevancia | Dado que el resultado de triage tiene `rag_attribution` no vacia, cuando se renderiza el panel de resultado HTMX, entonces se muestra una seccion "Fuentes" con una fila por `RagAttribution`; cada fila muestra el nombre del documento y una barra CSS cuyo ancho es `relevance_score * 100%` |
| AC-11 | Seccion "Fuentes" oculta cuando `rag_attribution` vacia | Dado que `rag_attribution` esta vacia (modo degradado), cuando se renderiza el panel, entonces la seccion "Fuentes" NO aparece en el HTML |
| AC-12 | `chunk_preview` truncado en UI | Dado que `chunk_preview` puede tener hasta 200 caracteres, cuando se renderiza en la UI, entonces se muestra truncado si excede 100 caracteres con "..." al final |
| AC-13 | `max_rag_docs_to_expose` limita atribuciones en reporte | Dado que `GovernanceThresholds.max_rag_docs_to_expose=3` y el triage uso 5 docs, cuando `compute_report()` construye `ExplainabilityReport.rag_attributions`, entonces incluye maximo 3 docs (los de mayor `relevance_score`) |
| AC-14 | `container.py` resuelve `EXPLAINABILITY_PROVIDER` | Dado que `EXPLAINABILITY_PROVIDER=langfuse` (default), cuando arranca la app, entonces `IExplainabilityProvider` se resuelve a `LangfuseExplainabilityAdapter`; con `EXPLAINABILITY_PROVIDER=memory` a `MemoryExplainabilityAdapter` |

---

## Business Rules

| ID | Regla |
|----|-------|
| BR-01 | Todo `TriageResult` producido en produccion DEBE tener `rag_attribution` poblada, excepto cuando `degraded=True` (ARC-018). El reviewer rechaza cualquier construccion `TriageResult(rag_attribution=[])` en codigo de produccion sin `degraded=True`. |
| BR-02 | `relevance_score` se deriva de la similitud coseno retornada por FAISS; no se inventa ni se reemplaza con un valor constante. |
| BR-03 | `chunk_preview` son los primeros 200 caracteres del contenido del chunk; no se resume con LLM. |
| BR-04 | `compute_report()` es sincrono respecto al pipeline — bloquea hasta completar antes de que el orchestrator cierre su root span. |
| BR-05 | `ExplainabilityReport.generated_at` usa UTC datetime. |
| BR-06 | Los archivos en `app/domain/entities/explainability.py` NO importan nada fuera de stdlib, pydantic y otros `app/domain/` (ARC-001). |

---

## Edge Cases

| Escenario | Comportamiento esperado |
|-----------|------------------------|
| FAISS retorna 0 documentos (consulta sin hits) | `rag_attribution=[]` y `degraded` debe ser True o se emite warning; el pipeline no falla |
| `relevance_score` retornado por FAISS es negativo (similitud coseno puede ser negativa) | Se hace `max(0.0, score)` al construir `RagAttribution`; nunca se almacena valor negativo |
| LLM judge timeout durante `compute_report()` | Se retorna reporte degradado con `overall_grounding_score=0.0`; log ERROR; pipeline continua |
| `chunk_preview` del documento es None o string vacio | Se almacena string vacio `""`; no falla la construccion de `RagAttribution` |
| Mas de `max_rag_docs_to_expose` docs en triage | `rag_attribution` en `TriageResult` puede tener N docs; `ExplainabilityReport.rag_attributions` esta limitado al maximo configurado |
| Instancia `MemoryExplainabilityAdapter.compute_report()` | Retorna un `ExplainabilityReport` con `overall_grounding_score=1.0` (stub optimista para tests); no llama LLM |

---

## Design Reference

| Pantalla / Componente | Referencia | Notas |
|----------------------|-----------|-------|
| Panel de resultado HTMX | `app/ui/templates/result_partial.html` (o equivalente) | Agregar bloque "Fuentes" con barras de relevancia |
| Barra de relevancia | CSS inline: `style="width: {score*100}%"` | Usar clase Tailwind `bg-blue-500 h-2 rounded` |

---

## Dependencies

| HU | Tipo de dependencia |
|----|-------------------|
| HU-004 | Debe completarse antes — el triage agent es quien popula `rag_attribution`; `IContextProvider` debe estar funcionando |
| HU-005 | Debe completarse antes — el panel de resultado UI donde se muestra la seccion "Fuentes" pertenece a esta HU |
| HU-012 | Debe completarse antes — `max_rag_docs_to_expose` se lee de `GovernanceThresholds` via `IGovernanceProvider` |
| HU-014 | Corre en paralelo — consume `ExplainabilityReport` producido aqui |
| HU-015 | Corre en paralelo — el widget de feedback se agrega al mismo panel de resultado |

---

## Technical Notes

- La edicion de `triage.py` agrega dos campos al modelo Pydantic existente; no rompe compatibilidad porque ambos tienen defaults (`Field(default_factory=list)` y `Optional[...] = None`).
- `IExplainabilityProvider` es un puerto de dominio puro; `LangfuseExplainabilityAdapter` es el adaptador que llama al LLM judge y a la SDK de Langfuse.
- El LLM judge en `compute_report()` usa `ILLMProvider` (via inyeccion del container) — no crea un cliente Gemini directamente.
- Dominio puro: `app/domain/entities/explainability.py` y `app/domain/ports/explainability_provider.py` NO importan Langfuse, FastAPI ni SQLAlchemy.

---

## Pending Questions

Ninguna — contratos definidos en ARCHITECTURE.md §4.12 y ARC-018.

---

## Change History

| Version | Fecha | Cambio | Razon |
|---------|-------|--------|-------|
| v1 | 2026-04-08 | Creacion inicial | Arquitectura v3 — EPIC-004 |
