# HU-P030 — Integración Real con eShopOnWeb — Indexación RAG del Repositorio

**Module:** Config Platform / Triage Context
**Epic:** EPIC-009 — eShop Real Integration
**Priority:** High
**Status:** Approved
**Version:** v2
**Last updated:** 2026-04-08

---

## User Story

**Como** ingeniero SRE que usa la plataforma
**Quiero** que el agente de triage analice incidentes con base en el código fuente real del repositorio eShopOnWeb de Microsoft
**Para** obtener diagnósticos precisos con referencias a archivos y componentes reales del sistema e-commerce, no a documentación estática pre-procesada

---

## Contexto y Decisión de Alcance

### Target seleccionado: eShopOnWeb (no eShopOnContainers)

| Criterio | Decisión |
|---------|---------|
| Repositorio objetivo | `https://github.com/dotnet-architecture/eShopOnWeb` (MIT License) |
| Alternativa descartada | `eShopOnContainers` — demasiada complejidad (~10 microservicios) para indexar en <24h de hackathon |
| Justificación | eShopOnWeb es un monolito ASP.NET modular con estructura predecible. Los archivos clave (Controllers, Services, Domain) son accesibles y relevantes para triage SRE. La indexación FAISS es manejable (~50-80K tokens de código relevante). |
| Impacto en demo | El agente puede referenciar archivos reales como `src/Web/Controllers/OrderController.cs` o `src/ApplicationCore/Services/OrderService.cs` con URLs de GitHub clickeables — impacto visual significativamente mayor que el mock actual. |

### Estado actual del sistema (lo que cambia)

Hoy: `IContextProvider` → implementación estática → lee archivos de `eshop-context/` → construye índice FAISS local.

Con HU-P030: Se crea `GithubContextProvider` que implementa `IContextProvider` → clona o descarga el repo de GitHub → indexa con FAISS → sirve contexto al LLM con referencias reales.

---

## Acceptance Criteria

| ID | Criterio | Condición |
|----|---------|-----------|
| AC-01 | Nuevo adapter `GithubContextProvider` implementa `IContextProvider` | **Given** el sistema está configurado con `context_source = "github"` en `platform_config`, **When** el triage recibe un incidente, **Then** el adapter `GithubContextProvider` es el que provee el contexto RAG — no el adapter estático |
| AC-02 | Indexación del repo eShopOnWeb al iniciar el container | **Given** el contenedor `sre-agent` arranca con `CONTEXT_SOURCE=github` y la URL del repo configurada, **When** el servicio inicia, **Then** el `GithubContextProvider` clona/descarga los archivos relevantes de `eShopOnWeb` y construye el índice FAISS en background durante el startup. Si ya existe un índice previo en disco (volumen persistente), lo reutiliza sin re-descargar el repo. El servicio FastAPI declara readiness (`/health` retorna 200) una vez que el índice está disponible (sea el nuevo construido o el previo cacheado). |
| AC-03 | Fallback a contexto estático si GitHub no disponible | **Given** GitHub no es accesible al iniciar (timeout de red, repo privado, credenciales inválidas), **When** el `GithubContextProvider` falla la descarga, **Then** el sistema cae back al adapter estático (carpeta `eshop-context/`) y loguea un warning `CONTEXT_DEGRADED: using static fallback` |
| AC-04 | El botón "Re-indexar ahora" en HU-P021 trigerea la re-indexación | **Given** un admin accede a la sección "Config Repositorio eCommerce" (HU-P021), **When** hace clic en "Re-indexar ahora", **Then** el backend ejecuta `POST /config/ecommerce-repo/reindex` que lanza la re-indexación en background y retorna `{"status": "indexing", "job_id": "..."}` inmediatamente |
| AC-05 | Indicador de estado del índice en HU-P021 (solo lectura) | **Given** la sección de Config Repositorio está abierta, **When** el admin la visualiza, **Then** ve en modo **solo lectura**: documentos indexados (número), fecha y hora de última indexación, proveedor activo (`github` o `static`), y estado (OK / Error / Indexando). Este panel es informativo — la configuración del eShop no se aplica en caliente sino con reinicio del container (ver BR-07). |
| AC-11 | La UI muestra la URL del eShop pre-configurada para el hackathon | **Given** el sistema se despliega con la imagen Docker del hackathon, **When** el admin abre "Config Repositorio eCommerce", **Then** el campo de URL del repositorio muestra `https://github.com/dotnet-architecture/eShopOnWeb` ya configurado y el índice FAISS pre-construido disponible — los jueces no necesitan configurar ni re-indexar nada para que el demo funcione. |
| AC-06 | Las fuentes RAG incluyen URLs de GitHub clickeables | **Given** un triage completa usando `GithubContextProvider`, **When** se muestra la RAG attribution en HU-P026 (o en la respuesta JSON de `TriageResult`), **Then** `rag_attribution.sources` contiene objetos con: `file_path` (ej: `src/Web/Controllers/OrderController.cs`), `github_url` (URL directa al archivo en GitHub: `https://github.com/dotnet-architecture/eShopOnWeb/blob/main/src/Web/Controllers/OrderController.cs`), `relevance_score` (float 0-1) |
| AC-07 | Archivos a indexar — filtro inteligente | **Given** el repo eShopOnWeb tiene múltiples carpetas, **When** el `GithubContextProvider` indexa, **Then** incluye únicamente: `src/Web/Controllers/`, `src/Web/Services/`, `src/ApplicationCore/Services/`, `src/ApplicationCore/Entities/`, `src/ApplicationCore/Interfaces/`, `src/Infrastructure/Services/`. Excluye: `tests/`, `node_modules/`, `.github/`, archivos `.json`, `.csproj`, `.sln`. |
| AC-08 | El adapter es configurable sin hardcodear la URL | **Given** la URL del repo está configurada en `platform_config` (via HU-P021), **When** el `GithubContextProvider` se instancia, **Then** lee la URL desde `platform_config` (no desde código hardcodeado). Si se cambia la URL en config, la próxima re-indexación usa la nueva URL. |
| AC-09 | El endpoint `GET /config/ecommerce-repo/reindex/status` informa progreso | **Given** una re-indexación está en curso, **When** la UI o el admin consulta el estado, **Then** retorna `{"status": "indexing", "files_processed": N, "files_total": M, "started_at": "..."}` o `{"status": "ok", "completed_at": "...", "files_indexed": N}` o `{"status": "error", "error_message": "..."}` |
| AC-10 | El índice FAISS reconstruido persiste en disco | **Given** el índice FAISS se construye exitosamente, **When** el contenedor se reinicia sin re-indexación, **Then** el índice previo en disco se reutiliza sin volver a descargar el repo. El índice se almacena en el volumen Docker de persistencia. |

---

## Business Rules

| ID | Regla |
|----|-------|
| BR-01 | `GithubContextProvider` es un adapter nuevo que implementa la interfaz `IContextProvider` existente. No modifica el adapter estático FAISS existente — ambos coexisten. El container de DI selecciona cuál usar según `platform_config`. |
| BR-02 | El repo eShopOnWeb es público (MIT License) — no requiere credenciales. Si se configura un repo privado en el futuro, HU-P021 ya tiene el campo de credenciales. |
| BR-03 | La re-indexación se ejecuta en un background task (no bloquea requests de triage en curso). Durante la re-indexación, el adapter sigue sirviendo el índice anterior hasta que el nuevo esté listo. |
| BR-04 | El número máximo de archivos a indexar es 200 (protege contra repos muy grandes). Si se supera, se indexan los 200 más relevantes por tamaño/nombre. |
| BR-05 | Las URLs de GitHub en `rag_attribution.sources` deben apuntar a la rama `main` del repo (no a commits específicos), para que los links sean estables. |
| BR-06 | El `GithubContextProvider` NO debe hacer llamadas a la GitHub API autenticada por defecto — usa la API pública o descarga el ZIP del release. Esto evita la necesidad de un GitHub token para repos públicos. |
| BR-07 | Cambiar la URL del repositorio eShop desde la UI requiere ventana de mantenimiento con reinicio del container. La configuración del eShop es un parámetro de producto que se establece una vez al momento de vender/instalar la plataforma. No soporta hot reload (a diferencia de la config LLM de HU-P029). El panel de configuración del repo en la UI es fundamentalmente de solo lectura para el operador, con capacidad de re-indexación bajo demanda (botón "Re-indexar ahora") pero no de cambio de URL sin restart. |
| BR-08 | Para el hackathon, el eShopOnWeb ya está indexado en la imagen Docker — el índice FAISS pre-construido está incluido en el volumen de la imagen. Los jueces del hackathon no necesitan ejecutar ninguna acción de configuración para que el demo de triage funcione con contexto real de eShop. |

---

## Edge Cases

| Escenario | Comportamiento esperado |
|----------|------------------------|
| El repo de GitHub cambia su estructura (ej: carpetas renombradas) | El filtro de carpetas a indexar (AC-07) no encuentra las carpetas esperadas → loguea warning y indexa lo que encuentra. El triage funciona con el contexto parcial disponible. |
| La re-indexación falla a mitad de proceso | El índice anterior permanece intacto y activo. El estado en la UI muestra "Error: [mensaje]". El admin puede reintentar via el botón "Re-indexar ahora". |
| Se solicita un triage MIENTRAS la re-indexación está en progreso | El triage usa el índice anterior (pre-re-indexación). No se interrumpe la re-indexación. |
| El repo no existe o la URL está mal configurada | El `GithubContextProvider` loguea error y cae back al adapter estático. El estado en UI muestra "Error: repo no encontrado". |
| El índice FAISS en disco está corrupto (ej: apagado abrupto durante escritura) | Al detectar corrupción al cargar, el adapter descarta el índice corrupto y re-indexa automáticamente desde cero. |
| El volumen Docker no tiene suficiente espacio para el índice | El proceso de indexación falla con error de disco. Se loguea y se alerta en el estado de HU-P021. Se usan los 200 archivos más pequeños como fallback parcial. |
| `CONTEXT_SOURCE` no está definido en `platform_config` ni en env vars | El sistema usa el adapter estático por defecto (comportamiento actual). No hay error. |

---

## Design Reference

| Pantalla / Componente | Referencia | Notas |
|----------------------|-----------|-------|
| Sección expandida de "Config Repositorio eCommerce" en EPIC-006 | HU-P021 expandida | Añade: indicador de estado del índice, botón "Re-indexar ahora", progreso de indexación |
| RAG Attribution en Incident Dashboard | HU-P026 | Las fuentes ahora tienen URLs clickeables a GitHub. El componente de barras de relevancia permanece igual, se añade un link en cada fuente. |

*(Sin diseño Figma disponible. Seguir Design System SoftServe de HU-P031.)*

---

## Dependencies

| HU | Tipo de dependencia |
|----|-------------------|
| HU-004 | Referencia — `IContextProvider` es el contrato que `GithubContextProvider` debe implementar. HU-004 no cambia. |
| HU-013 | Enriquecida — `rag_attribution.sources` ahora incluye `github_url`. HU-013 backend no cambia, solo el contenido del dato. La UI de HU-P026 sí cambia para renderizar el link. |
| HU-P021 | Expandida — se añaden los ACs de re-indexación e indicador de estado a la HU de config del repo. Debe completarse en coordinación con HU-P030. |
| HU-P018 | Debe completarse antes — el endpoint `/config/ecommerce-repo/reindex` requiere JWT y rol `admin+`. |
| HU-P027 | Debe completarse antes — la UI de estado de indexación se renderiza dentro del shell React. |

---

## Technical Notes

- El mecanismo de descarga del repo puede ser: (a) descarga del ZIP del branch `main` via `https://github.com/{owner}/{repo}/archive/refs/heads/main.zip` — sin auth, sin git instalado; o (b) `git clone --depth=1` — requiere git en el contenedor pero es más robusto. El @architect elige. El ZIP es la opción más simple para el hackathon.
- El índice FAISS se guarda en un path configurable via env var `FAISS_INDEX_PATH` (ej: `/app/data/faiss_index/`). Este path debe estar en un volumen Docker persistente.
- El `GithubContextProvider` se registra en el container de DI de la misma forma que el adapter estático. La selección entre ambos se hace con una factory que lee `platform_config.context_source`.
- La re-indexación background puede implementarse con `asyncio.create_task()` o `BackgroundTasks` de FastAPI. No requiere Celery para el hackathon.
- Ver PQ-09 para la decisión de startup indexing vs. indexación bajo demanda.

---

## Pending Questions

| # | Pregunta | Dirigida a | Estado |
|---|---------|-----------|--------|
| 1 | (PQ-09) ¿La indexación de eShopOnWeb se hace al inicio del contenedor (startup) o solo cuando el admin hace clic en "Re-indexar"? | @architect / @developer | **RESUELTA** — Indexación en startup del container (no bajo demanda ni automática al guardar). Si existe índice previo en disco, se reutiliza. Ver AC-02, BR-07, BR-08. |
| 2 | ¿Cuál es el mecanismo de descarga del repo preferido: ZIP via HTTPS (sin git) o `git clone --depth=1`? | @architect | Pendiente — decisión técnica de @architect. No bloquea el diseño de HU. La opción ZIP es la recomendada para el hackathon (sin dependencia de git en el contenedor). |

---

## Change History

| Version | Fecha | Cambio | Motivo |
|---------|-------|--------|--------|
| v1 | 2026-04-08 | Creación inicial | Requisito B del cliente — integración real con eShop Microsoft. Target: eShopOnWeb (justificación en sección de Contexto). |
| v2 | 2026-04-08 | PQ-09 RESUELTA: estrategia de indexación definida como startup. Se añaden AC-11 (URL pre-configurada en demo), BR-07 (restart policy para cambio de URL), BR-08 (pre-indexado en imagen Docker). AC-02 actualizado para reflejar indexación en startup. AC-05 actualizado como panel de solo lectura. Estado cambia a Approved. | Respuesta del cliente: configuración se hace una vez al instalar (no hot reload). Para hackathon, eShop pre-configurado y listo. Jueces no necesitan tocar nada. |
