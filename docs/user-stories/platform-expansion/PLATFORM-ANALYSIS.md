# PLATFORM-ANALYSIS.md — Análisis de Expansión: Web Platform SRE

**Preparado por:** @product-analyst
**Fecha:** 2026-04-08
**Versión:** v4.0
**Para revisión de:** @architect (viabilidad técnica), @developer (estimación)
**Estado:** CERRADO — Análisis final v4.0. 0 preguntas pendientes críticas. Listo para @architect.
**Versión:** v4.0 — Adición Requisitos D y E (2026-04-08)

> **CAMBIOS EN v2.0:** Se incorporan Requisitos A (Config LLM), B (Integración real eShop) y C (Design System SoftServe). PQ-07 RESUELTA: todo el alcance entra al hackathon. Total HUs: 16 (anteriormente 13). Se añaden HU-P029, HU-P030, HU-P031.
>
> **CAMBIOS EN v3.0 (cierre):** PQ-08, PQ-09, PQ-10 RESUELTAS. Se añaden SA-012, SA-013, SA-014. HU-P029, HU-P030, HU-P031 actualizadas a v2 (Approved). Se añade sección "## Handoff para @architect". 0 preguntas pendientes críticas.
>
> **CAMBIOS EN v4.0:** Se incorporan Requisito D (Configuración centralizada — Config-from-DB) y Requisito E (UI en inglés). Se añaden SA-015 y principio "Config-from-DB". Se crea HU-P032 (Centralized Configuration Page). HU-016 confirmada como Supersedida por HU-P032. Alcance de HU-012 expandido: `IGovernanceProvider` ahora cubre todas las variables de negocio. Se añaden DEC-A08, DEC-A09, DEC-A10 al Handoff. HU-P031 actualizada a v3 con AC-12 y BR-06 (English-only).

---

## Resumen Ejecutivo

El cliente solicita una expansión significativa del sistema actual: convertir el agente SRE (actualmente una API FastAPI + UI mínima en HTMX/Jinja2) en una **plataforma web completa** con:
- Autenticación Google (mock JWT)
- Panel de configuración de todos los puertos/adaptadores
- Interfaz de creación de incidentes
- Dashboard de estado de incidentes y tickets
- Constructor visual tipo drag-and-drop
- Roles y permisos RBAC

Este documento estructura el análisis completo para que `@architect` pueda evaluar viabilidad técnica sin necesidad de re-leer los requisitos originales.

---

## Tabla de Contenidos

1. [Análisis de Conflictos y Ambigüedades](#1-análisis-de-conflictos-y-ambigüedades)
2. [Supuestos Explícitos](#2-supuestos-explícitos)
3. [Modelo de Roles y Permisos (RBAC)](#3-modelo-de-roles-y-permisos-rbac)
4. [Estructura de Nuevas HUs por Epic](#4-estructura-de-nuevas-hus-por-epic)
5. [Impacto en HUs Existentes (HU-001 a HU-016)](#5-impacto-en-hus-existentes-hu-001-a-hu-016)
6. [Mapa de Dependencias](#6-mapa-de-dependencias)
7. [Preguntas Pendientes para el Cliente](#7-preguntas-pendientes-para-el-cliente)
8. [Índice de Nuevas HUs Propuestas](#8-índice-de-nuevas-hus-propuestas)
9. [Requisitos Adicionales v2.0](#9-requisitos-adicionales-v20)
10. [Handoff para @architect](#10-handoff-para-architect)

---

## 1. Análisis de Conflictos y Ambigüedades

### 1.1 Contradicciones con HUs Existentes

| Conflicto ID | HU Afectada | Descripción del Conflicto | Resolución Propuesta |
|-------------|------------|--------------------------|---------------------|
| CONF-001 | **HU-016** | HU-016 especifica una UI de gobernanza en **HTMX/Jinja2** (`governance.html`). El nuevo requisito exige una plataforma en **React**. Esto es una contradicción directa de tecnología de presentación. | HU-016 queda **Supersedida** por HU-P024 (Módulo de Configuración de Agentes en React). Los endpoints backend de HU-012 (`GET/PUT /governance/thresholds`) se mantienen sin cambio — solo el frontend cambia. |
| CONF-002 | **HU-001, HU-002** | HU-001/HU-002 especifican un formulario de reporte de incidentes en HTMX. El nuevo requisito pide "crear informe de fallo a través de interfaz amigable" en React. | HU-001 y HU-002 son **Modificadas**: la UI pasa a React, pero los endpoints `POST /incidents` permanecen sin cambio. Se crea HU-P031 (Incident Report UI en React) que los reemplaza en el frontend. |
| CONF-003 | **HU-005, HU-013, HU-015** | Los paneles de resultado, RAG attribution y feedback widget están especificados como HTMX partials (`result_partial.html`). El nuevo requisito incluye un módulo de visualización de estado de incidentes en React. | HU-005 y HU-013 son **Modificadas** en su capa de presentación. La lógica de backend (endpoints, entidades) se mantiene. Los templates HTMX son reemplazados por componentes React. |
| CONF-004 | **ARCHITECTURE.md §1** | La arquitectura v3 describe el sre-agent como "FastAPI app hosting UI + API + LangGraph agent". Con React, la UI deja de estar embebida — pasa a ser un SPA separado. Esto impacta el modelo de despliegue (Docker Compose). | Requiere decisión de @architect: ¿Se agrega un nuevo contenedor `sre-web` para React, o se sirve el SPA desde FastAPI como archivos estáticos? Ver CONF-004-impacto abajo. |
| CONF-005 | **DEC-004** | DEC-004 dice "Manual UI endpoint como trigger de resolución (POST /tickets/:id/resolve)". Este endpoint sigue siendo válido, pero el trigger ahora viene de React, no de HTMX. | No hay conflicto lógico. El endpoint permanece. La UI que lo llama cambia de tecnología. Actualizar DEC-004 para reflejar que el cliente ahora es React. |
| CONF-006 | **HU-008** | HU-008 tiene una pregunta pendiente: "¿El email del reporter es requerido u opcional?". Con la nueva UI en React que incluye un módulo de resolución con notificación al creador, **el email se vuelve crítico**. | Este campo pasa a ser **requerido** en el nuevo flujo. HU-008 debe actualizarse: AC que hoy dice "opcional con warning" cambia a "requerido en formulario React". |

### 1.2 Ambigüedades en los Nuevos Requisitos

| ID | Requisito Ambiguo | Análisis | Resolución / Supuesto |
|----|------------------|----------|----------------------|
| AMB-001 | **"UI último en tendencia: tipo constructor (Arrastrar y poner elementos)"** | Hay tres interpretaciones posibles: (a) constructor de layout del dashboard — el usuario puede reorganizar paneles/widgets, (b) constructor visual de flujos de agentes — el usuario dibuja conexiones entre nodos (tipo Node-RED), (c) wizard de configuración con pasos reordenables via drag. La opción (b) es extremadamente compleja (XL, requiere librería como React Flow, gestión de estado del grafo, serialización). | **SUPUESTO EXPLÍCITO SA-001:** Se interpreta como (a) — dashboard con widgets reordenables por el usuario. El layout se guarda en base de datos por usuario/rol. La opción (b) se documenta como **fuera de alcance v1** y se considera una fase futura. Ver sección 2. |
| AMB-002 | **"Configuración de agentes: mostrar cómo están configurados, las instrucciones y las skills. Permitir editar segmentos seguros"** | ¿Qué es un "segmento seguro" de un agente? Los prompts en YAML son el config de agentes hoy. ¿Se permite editar los prompts directamente? ¿O solo metadatos como nombre, descripción, umbrales de gobernanza? | **SUPUESTO EXPLÍCITO SA-002:** Los "segmentos seguros" son: (1) metadatos del agente (nombre display, descripción), (2) umbrales de gobernanza (ya gestionados por HU-012), (3) parámetros de prompt editables (variables de los YAML, no la estructura del prompt). La edición directa de la estructura de prompts queda **fuera de alcance v1** por riesgo de romper el comportamiento del agente. |
| AMB-003 | **"Mock para simular el token JWT con Google"** | ¿El mock devuelve siempre el mismo usuario? ¿O permite seleccionar usuarios predefinidos? ¿El mock está solo en desarrollo o también en el hackathon demo? | **SUPUESTO EXPLÍCITO SA-003:** El mock de Google OAuth devuelve tokens JWT para usuarios predefinidos en base de datos (uno por rol al menos). El endpoint `/auth/google/mock` acepta un `email` como query param y genera un JWT firmado localmente. Para el hackathon, esto es el mecanismo de login en todos los entornos. |
| AMB-004 | **"Configurar cuál es el sistema de tickets a usar"** | ¿Esto reemplaza la variable de entorno `TICKET_PROVIDER`? ¿O es una UI que persiste la selección en base de datos y la app la lee al iniciar? | **SUPUESTO EXPLÍCITO SA-004:** La selección del sistema de tickets se persiste en una tabla `platform_config` en PostgreSQL. La app lee esta config al iniciar (y puede recargarse sin redeploy vía endpoint admin). La variable de entorno sigue siendo el fallback si no hay config en BD. |
| AMB-005 | **"Tipos de archivos permitidos/no permitidos"** | ¿Esta configuración afecta la validación que hoy hace HU-002 (multimodal file attachment)? ¿Se sincroniza con el guardrails de HU-003? | **SUPUESTO EXPLÍCITO SA-005:** Sí, la configuración de tipos de archivo persiste en `platform_config` y es leída por el adaptador de validación de archivos (actualmente hardcodeado en HU-002/HU-003). El nuevo módulo de config unifica ese control. |
| AMB-006 | **"Si está cerrado que mande el correo al creador del ticket y se muestre que está cerrado"** | El flujo de resolución ya existe (HU-008). ¿Se está pidiendo que el módulo de dashboard muestre el estado del ticket en tiempo real (polling/websocket)? ¿O solo al cargar la página? | **SUPUESTO EXPLÍCITO SA-006:** El dashboard hace polling cada 30 segundos al endpoint `GET /incidents/{id}/status` para actualizar el estado del ticket. No se implementa WebSocket en v1 (complejidad innecesaria para hackathon). |
| AMB-007 | **"Configurar redirección del problema al equipo técnico"** | ¿"Configurar cuál es el sistema de tickets" incluye seleccionar entre los adaptadores existentes (Mock, GitLab, Jira) desde la UI? | **SUPUESTO EXPLÍCITO SA-007:** Sí. La UI muestra los adaptadores disponibles como opciones. Al seleccionar uno, se habilitan los campos de configuración específicos de ese adaptador (API key, URL, etc.). La selección se guarda en `platform_config`. |
| AMB-008 | **"Genera en base de datos los usuarios con correo de Google"** | ¿Se auto-provisionan usuarios nuevos al hacer login con un correo de Google no existente? ¿O solo los usuarios pre-creados por el admin pueden acceder? | **SUPUESTO EXPLÍCITO SA-008:** En el mock, el admin pre-crea usuarios. El auto-provisioning queda como **fuera de alcance v1** para no complicar el modelo RBAC. Un usuario no creado por el admin recibe un error de "acceso no autorizado". |

### 1.3 Riesgos de Alcance

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| React SPA requiere nuevo contenedor Docker + build pipeline | Alta | Alto | @architect debe decidir arquitectura de despliegue antes de que @developer empiece (ver CONF-004) |
| El "constructor drag-and-drop" subestimado | Alta | Alto | SA-001 acota a dashboard layout únicamente — el constructor de flujos de agentes es v2 |
| La configuración de adaptadores desde UI implica cambios en la capa de infraestructura de la app | Media | Alto | El módulo de config debe escribir en `platform_config` y la app debe tener un mecanismo de recarga sin restart |
| El email del reporter como campo requerido puede romper tests existentes | Media | Medio | HU-001 y HU-008 deben actualizarse antes de que se implemente el formulario React |
| CORS: el SPA React en puerto diferente necesita configuración CORS en FastAPI | Alta | Medio | Agregar a los requerimientos técnicos de EPIC-008 |
| Tiempo: el hackathon tiene deadline 2026-04-09 21:00 COT — esta expansión es significativa | Muy alta | Crítico | Ver sección de estimaciones de complejidad por HU |

---

## 2. Supuestos Explícitos (SA)

Todos los supuestos documentados arriba, consolidados:

| ID | Supuesto | Impacto |
|----|----------|---------|
| SA-001 | El "constructor drag-and-drop" = layout de dashboard con widgets reordenables. NO es un constructor visual de flujos de agentes. | Reduce complejidad de XL a L para EPIC-008 |
| SA-002 | "Segmentos seguros" de agentes = metadatos + umbrales de gobernanza + variables de prompt. No edición de estructura de prompts YAML. | Reduce riesgo de ruptura del comportamiento del agente |
| SA-003 | El mock Google OAuth acepta email por query param y genera JWT firmado localmente. | Simplifica EPIC-005 considerablemente |
| SA-004 | La configuración de adaptadores se persiste en tabla `platform_config` en PostgreSQL. La env var es fallback. | Requiere nueva entidad de dominio y migración Alembic |
| SA-005 | La config de tipos de archivo persiste en `platform_config` y sincroniza con la validación de HU-002/HU-003. | Modifica HU-002 y HU-003 |
| SA-006 | Dashboard actualiza estado por polling cada 30s. No WebSocket en v1. | Simplifica frontend |
| SA-007 | La UI permite seleccionar el adaptador de tickets activo entre los adaptadores existentes. | Requiere endpoint de management en la API |
| SA-008 | Los usuarios se pre-crean por admin. No auto-provisioning. | Simplifica modelo de seguridad |
| SA-009 | La configuración LLM se almacena en tabla nueva `llm_config` (no en `governance_thresholds`). `@architect` valida esta decisión. | Requiere migración Alembic nueva. Separa concerns de gobernanza e infraestructura LLM. |
| SA-010 | El target de integración real es **eShopOnWeb** (`https://github.com/dotnet-architecture/eShopOnWeb`), no eShopOnContainers. El adapter se implementa como `GithubContextProvider` nuevo que implementa `IContextProvider`. El adapter estático FAISS existente es el fallback. | Menor complejidad de indexación. Demo más coherente. Riesgo menor en <24h. |
| SA-011 | El Design System SoftServe se implementa como custom theme en `tailwind.config.js` con los tokens documentados en HU-P031. HU-P031 bloquea HU-P027 (el shell no puede construirse sin los tokens). Si el cliente provee un Brand Guide oficial, los valores se actualizan. | Colores inferidos de materiales públicos de SoftServe. Requiere confirmación del cliente. |
| SA-012 | **Hot reload LLM (PQ-08 RESUELTA — 2026-04-08):** Los cambios de proveedor LLM desde la UI aplican en caliente (< 5 segundos sin reiniciar el container). El circuit breaker adopta los nuevos parámetros en el siguiente ciclo de evaluación tras el guardado. El @architect debe diseñar el mecanismo de hot reload en `container.py` (opciones: event bus interno con `asyncio.Event`, o cache con TTL de 5s invalidado al `PUT /config/llm`). El refactor de `circuit_breaker.py` debe exponer `reconfigure(threshold, cooldown)` para no perder el historial de fallos acumulado. | Impacta HU-P029 (AC-12, AC-13, BR-05, BR-08 actualizados en v2). Impacta arquitectura de `container.py` y `circuit_breaker.py`. |
| SA-013 | **Política de restart para eShop (PQ-09 RESUELTA — 2026-04-08):** La indexación de eShopOnWeb ocurre en el startup del container, no bajo demanda ni automáticamente al guardar en la UI. Si existe un índice previo en disco, se reutiliza. Cambiar la URL del eShop requiere ventana de mantenimiento con reinicio del container — es configuración de instalación, no operacional. Para el hackathon, el eShopOnWeb ya está indexado en la imagen Docker y los jueces no necesitan tocar nada. | Impacta HU-P030 (AC-02, AC-05, AC-11, BR-07, BR-08 actualizados en v2). El panel de config del repo en la UI es principalmente de solo lectura durante operación normal. |
| SA-014 | **Brand Guide SoftServe (PQ-10 RESUELTA — 2026-04-08):** No hay Brand Guide oficial disponible. El @product-analyst realizó búsqueda web (Brandfetch `https://brandfetch.com/softserveinc.com`, logo.com `https://logo.com/brand/softserve-29i16g/colors`). **Corrección crítica: el color primario de SoftServe es `#454494` (violeta-azul corporativo), NO `#E3001B` (rojo)**. Esta corrección ya está aplicada en HU-P031 v2. Los tokens se marcan como "inferidos — pendiente validación con Brand Guide oficial si disponible". | Impacta HU-P031 (todos los tokens de color actualizados en v2). El @developer debe usar `#454494` como `--color-primary`. Si el cliente eventualmente provee el Brand Guide, solo hay que actualizar los tokens en `tailwind.config.js` — los componentes no cambian. |
| SA-015 | **UI en inglés — no i18n (Requisito E — 2026-04-08):** Toda la interfaz de usuario de la plataforma (todas las HUs React: HU-P017 a HU-P032) debe estar en inglés. No se implementa una capa de internacionalización (i18n, react-i18next, lingui, etc.) en v1. Esta es una decisión global que aplica a: labels, descripciones, placeholders, mensajes de error y validación, textos de botones, mensajes toast, headers de sección, y cualquier otro texto visible por el usuario. Todos los componentes del Design System (HU-P031) deben asumir inglés como único idioma. | Impacta HU-P031 v3 (AC-12, BR-06 añadidos). Impacta HU-P025, HU-P026, HU-P027, HU-P028, HU-P032 y todas las HUs de EPIC-006: deben incluir BR "All UI text must be in English — no i18n layer required". El @developer no debe crear ninguna estructura de traducción ni archivos de locale. |

### Principio de Diseño: Config-from-DB

> **Establecido en v4.0 — 2026-04-08 — Requisito D del cliente.**

**"Config-from-DB":** After initial bootstrap (DB connection, app environment, Langfuse host), all system behavior is governed by database-stored configuration managed through the platform UI (`/config`). `.env` contains only infrastructure bootstrap variables. No business logic value may be hardcoded in Python files or `.env` after HU-P032 is implemented.

**Variables que permanecen en `.env` (bootstrap únicamente):**

| Variable | Motivo |
|----------|--------|
| `APP_DATABASE_URL` | Requerida antes de que la BD esté disponible para leer configuración |
| `APP_ENV` | Determina el comportamiento de validación en el arranque (`_reject_stub_in_production`) |
| `LANGFUSE_HOST` | Dirección del servidor Langfuse — necesaria para conectar antes de leer config de BD |
| `SRE_API_KEY` | Legacy — para compatibilidad hacia atrás durante la migración al JWT |
| `MOCK_SERVICES_URL` | Infraestructura — dirección del contenedor mock, no es config de negocio |
| `JWT_SECRET` | Secret criptográfico — nunca debe estar en la BD |
| `CONFIG_ENCRYPTION_KEY` | Clave de cifrado para credentials en BD — nunca puede estar en la BD que protege |

**Todas las demás variables de `config.py`** migran a la base de datos y se gestionan desde la UI de HU-P032. Ver tabla completa de clasificación en `HU-P032-centralized-config-page.md` sección "Variable Classification".

---

## 3. Modelo de Roles y Permisos (RBAC)

### 3.1 Definición de Roles

#### SUPERADMIN
**Propósito:** Control total del sistema. Solo debe existir 1-2 instancias.

| Puede | No puede |
|-------|----------|
| Gestionar todos los usuarios (crear, editar, eliminar, cambiar rol) | — |
| Eliminar/resetear todos los datos (incidentes, configuraciones) | — |
| Acceder a todos los módulos de configuración | — |
| Editar umbrales de gobernanza | — |
| Editar configuración de agentes | — |
| Ver logs de auditoría del sistema | — |
| Activar/desactivar kill switch | — |
| Cambiar adaptadores activos (ticket, notify, LLM) | — |
| Crear/editar incidentes | — |
| Ver dashboard de incidentes | — |

**Módulos visibles:** Todos (Config, Incident Management, Dashboard, Admin de usuarios, Logs de auditoría)

---

#### ADMIN
**Propósito:** Administrador operacional. Gestiona la plataforma sin poder afectar a otros admins ni hacer reset destructivo.

| Puede | No puede |
|-------|----------|
| Crear/editar usuarios con rol `flow_configurator` o `operator` o `viewer` | Gestionar usuarios con rol `superadmin` o `admin` |
| Acceder a todos los módulos de configuración | Eliminar datos de forma masiva |
| Editar umbrales de gobernanza | Cambiar el email de otro admin |
| Editar configuración de agentes (segmentos seguros) | Eliminar incidentes cerrados |
| Configurar adaptadores (ticket system, notificaciones, ecommerce repo) | — |
| Configurar tipos de archivos permitidos | — |
| Ver logs de auditoría | — |
| Ver y comentar incidentes | — |
| Activar/desactivar kill switch | — |

**Módulos visibles:** Config Platform, Incident Dashboard, User Management (limitado), Audit Logs

---

#### FLOW_CONFIGURATOR
**Propósito:** Técnico que configura los flujos del agente SRE sin acceso a gestión de usuarios ni datos sensibles.

| Puede | No puede |
|-------|----------|
| Ver y editar configuración de agentes (segmentos seguros) | Gestionar usuarios |
| Editar umbrales de gobernanza | Cambiar adaptadores activos |
| Ver configuración de adaptadores (solo lectura) | Eliminar incidentes |
| Configurar tipos de archivos permitidos | Ver logs de auditoría completos |
| Ver dashboard de incidentes (solo lectura) | Activar kill switch |

**Módulos visibles:** Agent Config (R/W), Governance Thresholds (R/W), Adapter Config (R), Incident Dashboard (R), File Type Config (R/W)

---

#### OPERATOR
**Propósito:** Ingeniero SRE que usa la plataforma para reportar incidentes y hacer seguimiento.

| Puede | No puede |
|-------|----------|
| Crear reportes de incidente | Gestionar usuarios |
| Ver estado de sus propios incidentes y tickets | Ver/editar configuración de agentes |
| Enviar feedback (thumbs up/down) sobre resultados de triage | Ver configuración de adaptadores |
| Ver el dashboard de incidentes de su equipo | Activar kill switch |
| Adjuntar archivos al reporte de incidente | Editar umbrales |
| Ver RAG attribution de sus incidentes | Eliminar incidentes |

**Módulos visibles:** Incident Form (R/W), Incident Dashboard (propio equipo), Incident Status (R)

---

#### VIEWER
**Propósito:** Stakeholder o auditor que necesita visibilidad sin capacidad de acción.

| Puede | No puede |
|-------|----------|
| Ver dashboard de incidentes (todos) | Crear incidentes |
| Ver estado de tickets | Editar nada |
| Ver métricas agregadas | Configurar ningún módulo |
| Ver resultados de triage (sin datos PII) | Acceder a logs de auditoría |

**Módulos visibles:** Incident Dashboard (R, sin PII), Metrics/Reports (R)

---

### 3.2 Matriz de Permisos por Módulo

| Módulo | SUPERADMIN | ADMIN | FLOW_CONFIGURATOR | OPERATOR | VIEWER |
|--------|-----------|-------|------------------|----------|--------|
| Gestión de usuarios | R/W/D | R/W (excl. SA/Admin) | — | — | — |
| Config: Tipos de archivo | R/W | R/W | R/W | — | — |
| Config: Repo ecommerce | R/W | R/W | R (vista) | — | — |
| Config: Sistema de tickets | R/W | R/W | R (vista) | — | — |
| Config: Notificaciones | R/W | R/W | R (vista) | — | — |
| Config: Agentes | R/W | R/W | R/W (seguro) | — | — |
| Umbrales de gobernanza | R/W | R/W | R/W | — | — |
| Crear incidente | R/W | R/W | — | R/W | — |
| Dashboard incidentes | R/W | R/W | R | R (propio) | R |
| Estado del ticket | R/W | R/W | R | R (propio) | R |
| Feedback de triage | R/W | R/W | — | R/W (propio) | — |
| Logs de auditoría | R | R | — | — | — |
| Kill switch | R/W | R/W | — | — | — |
| Layout del dashboard | R/W | R/W | R/W | R/W | R/W |

---

### 3.3 HUs Existentes Afectadas por RBAC

| HU | Impacto RBAC |
|----|-------------|
| HU-001 (Incident Form) | Solo `operator`, `admin`, `superadmin` pueden crear incidentes |
| HU-002 (File Attachment) | La lista de tipos permitidos proviene de config RBAC-protegida (admin+ puede modificar) |
| HU-003 (Guardrails) | Sin cambio — opera a nivel de API, independiente de rol |
| HU-004 (LLM Triage) | Sin cambio — operación interna del agente |
| HU-005 (Technical Summary) | Vista disponible para operator (propio), admin, superadmin |
| HU-006 (Ticket Creation) | Sin cambio — operación interna |
| HU-007 (Team Notification) | Sin cambio — operación interna |
| HU-008 (Resolution Notification) | Sin cambio — operación interna |
| HU-009/HU-010 (Observability) | Sin cambio — cross-cutting concern |
| HU-011 (Mock Services) | Sin cambio — infraestructura |
| HU-012 (Governance Thresholds) | `PUT /governance/thresholds` requiere rol `flow_configurator` o superior |
| HU-013 (Explainability/RAG) | Vista de RAG attribution disponible para operator (propio), admin, superadmin |
| HU-014 (Online Eval) | Sin cambio — tarea de fondo |
| HU-015 (Feedback Widget) | Feedback solo para `operator` y superior sobre sus propios incidentes |
| HU-016 (Governance UI HTMX) | **Supersedida** — reemplazada por módulo React con restricción `flow_configurator+` |

---

## 4. Estructura de Nuevas HUs por Epic

### EPIC-005 — Auth & RBAC

**Objetivo:** Autenticación mock con Google OAuth, gestión de sesiones JWT, modelo de usuarios con roles, y control de acceso a endpoints y módulos UI.

---

#### HU-P017 — Mock Google OAuth Login y generación de JWT

**Como** usuario de la plataforma SRE
**Quiero** poder iniciar sesión con mi correo de Google (via mock en esta fase)
**Para** acceder a los módulos de la plataforma según mi rol asignado

**Criterios de Aceptación Clave:**
- AC-01: `GET /auth/google/callback?email={email}` retorna un JWT firmado con HS256 (secret via env var `JWT_SECRET`)
- AC-02: El JWT incluye claims: `sub` (email), `role`, `exp` (24h), `iat`
- AC-03: Si el email no existe en la tabla `users`, retorna HTTP 401 con mensaje "Usuario no autorizado"
- AC-04: Si el email existe, retorna HTTP 200 con `{"access_token": "...", "token_type": "Bearer"}`
- AC-05: El endpoint `/auth/google/mock` en la UI React muestra un selector de usuarios predefinidos (uno por rol) para facilitar el demo del hackathon
- AC-06: La tabla `users` tiene al menos 5 registros seed (uno por rol)

**Dependencias:** Ninguna (primera HU de la plataforma)
**Roles que la usan:** Todos (es el punto de entrada)
**Complejidad:** M

---

#### HU-P018 — Middleware de autenticación y autorización en FastAPI

**Como** arquitecto del sistema
**Quiero** que todos los endpoints de la API estén protegidos por el JWT emitido en HU-P017
**Para** garantizar que solo usuarios autenticados con el rol correcto puedan ejecutar cada operación

**Criterios de Aceptación Clave:**
- AC-01: Todos los endpoints que hoy usan `X-API-Key` migran a `Authorization: Bearer {JWT}` (excepto `/health`, `/metrics`, `/auth/*`)
- AC-02: Un decorador/dependency `require_role(*roles)` permite anotar endpoints con los roles permitidos
- AC-03: Solicitud sin token retorna HTTP 401
- AC-04: Solicitud con rol insuficiente retorna HTTP 403 con mensaje descriptivo
- AC-05: `GET /governance/thresholds` requiere `flow_configurator` o superior
- AC-06: `PUT /governance/thresholds` requiere `flow_configurator` o superior
- AC-07: `POST /incidents` requiere `operator` o superior
- AC-08: `POST /feedback/{id}` requiere `operator` o superior
- AC-09: `GET /incidents` requiere cualquier rol autenticado
- AC-10: El JWT expirado retorna HTTP 401 con error `token_expired`

**Dependencias:** HU-P017
**Roles que la usan:** Todos (infraestructura)
**Complejidad:** M

---

#### HU-P019 — Gestión de Usuarios (CRUD admin)

**Como** administrador de la plataforma
**Quiero** poder crear, editar, desactivar y asignar roles a usuarios
**Para** controlar quién tiene acceso a la plataforma y con qué nivel de permisos

**Criterios de Aceptación Clave:**
- AC-01: `POST /admin/users` crea un usuario con email, nombre, rol. Solo `admin` y `superadmin`.
- AC-02: `GET /admin/users` lista todos los usuarios con su rol. Solo `admin` y `superadmin`.
- AC-03: `PATCH /admin/users/{id}` actualiza nombre, rol o estado (activo/inactivo). `admin` no puede editar usuarios con rol `admin` o `superadmin`.
- AC-04: `DELETE /admin/users/{id}` desactiva (soft delete) al usuario. Solo `superadmin` puede desactivar admins.
- AC-05: Un usuario desactivado que intenta hacer login recibe HTTP 401 con error `user_disabled`
- AC-06: La tabla `users` tiene columnas: `id`, `email`, `name`, `role`, `is_active`, `created_at`, `updated_at`, `created_by`
- AC-07: La UI React muestra la lista de usuarios con filtro por rol y botones de acción según permisos del usuario actual

**Dependencias:** HU-P017, HU-P018
**Roles que la usan:** SUPERADMIN (completo), ADMIN (limitado)
**Complejidad:** M

---

### EPIC-006 — Configuration Platform

**Objetivo:** Módulo de configuración centralizado donde admins y flow_configurators pueden parametrizar todos los puertos/adaptadores del sistema SRE.

---

#### HU-P020 — Configuración de tipos de archivos permitidos

**Como** administrador
**Quiero** configurar desde la UI qué tipos de archivos pueden cargarse al reportar incidentes
**Para** controlar los formatos que el agente SRE procesa y prevenir cargas no deseadas

**Criterios de Aceptación Clave:**
- AC-01: `GET /config/file-types` retorna la lista actual de tipos MIME permitidos y bloqueados
- AC-02: `PUT /config/file-types` actualiza la lista. Requiere `admin` o superior.
- AC-03: La configuración se persiste en tabla `platform_config` con `key='allowed_file_types'` y `key='blocked_file_types'`
- AC-04: El validador de HU-002 lee esta configuración al validar archivos adjuntos (se integra con SA-005)
- AC-05: La UI muestra dos listas (permitidos / bloqueados) con chips de tipo MIME y opción de agregar/eliminar por drag-and-drop entre listas
- AC-06: Los tipos de archivo por defecto (image/png, image/jpeg, text/plain, application/json, application/pdf) se siembran en la BD al iniciar

**Dependencias:** HU-P017, HU-P018, HU-P027 (shell React)
**Roles que la usan:** SUPERADMIN, ADMIN, FLOW_CONFIGURATOR (R/W)
**Complejidad:** S

---

#### HU-P021 — Configuración del repositorio de e-commerce (eShop)

**Como** administrador
**Quiero** configurar desde la UI la URL y credenciales del repositorio de e-commerce que el agente analiza
**Para** poder cambiar el contexto del agente sin modificar variables de entorno ni redesplegar

**Criterios de Aceptación Clave:**
- AC-01: `GET /config/ecommerce-repo` retorna la configuración actual (URL, tipo de acceso, usuario enmascarado). Requiere `admin` o superior.
- AC-02: `PUT /config/ecommerce-repo` actualiza URL, tipo de acceso (`api_key`, `user_password`, `public`), y credenciales. Requiere `admin` o superior.
- AC-03: Las credenciales se almacenan encriptadas en `platform_config` (AES-256 o similar via env var `CONFIG_ENCRYPTION_KEY`)
- AC-04: `flow_configurator` puede ver la URL y tipo de acceso pero NO las credenciales
- AC-05: El campo de credencial en la UI muestra asteriscos (`***`) con opción de "revelar" solo para admins
- AC-06: La configuración guardada se usa por `IContextProvider` al siguiente request (recarga sin restart)

**Dependencias:** HU-P017, HU-P018, HU-P027
**Roles que la usan:** SUPERADMIN, ADMIN (R/W); FLOW_CONFIGURATOR (R sin credenciales)
**Complejidad:** M

---

#### HU-P022 — Configuración del sistema de tickets

**Como** administrador
**Quiero** seleccionar y configurar el sistema de tickets desde la UI (Mock, GitLab, Jira, etc.)
**Para** conectar el agente SRE con el sistema de tracking de incidentes de mi organización

**Criterios de Aceptación Clave:**
- AC-01: `GET /config/ticket-system` retorna el adaptador activo y su configuración. Requiere `admin` o superior.
- AC-02: `PUT /config/ticket-system` actualiza el adaptador seleccionado y sus parámetros. Requiere `admin` o superior.
- AC-03: La UI muestra un selector con las opciones: Mock (GitLab-compatible), GitLab, Jira. Al seleccionar uno, aparecen los campos específicos (API key, URL base, proyecto/board).
- AC-04: Al guardar, la app recarga el `TICKET_PROVIDER` sin restart (el container.py lee de `platform_config` con prioridad sobre env var)
- AC-05: Existe un botón "Probar conexión" que hace un request de prueba al sistema de tickets seleccionado y muestra éxito/error
- AC-06: Las API keys se almacenan encriptadas. La UI muestra máscara `***`.

**Dependencias:** HU-P017, HU-P018, HU-P027
**Roles que la usan:** SUPERADMIN, ADMIN (R/W)
**Complejidad:** M

---

#### HU-P023 — Configuración de notificaciones (e-mail y team webhook)

**Como** administrador
**Quiero** configurar los canales de notificación (email SMTP, Slack webhook, etc.) desde la UI
**Para** garantizar que las alertas lleguen al equipo técnico y al reportador original

**Criterios de Aceptación Clave:**
- AC-01: `GET /config/notifications` retorna los canales configurados y sus estados. Requiere `admin` o superior.
- AC-02: `PUT /config/notifications` actualiza la configuración de canales. Requiere `admin` o superior.
- AC-03: La UI separa dos secciones: "Notificación al equipo técnico" (webhook/Slack) y "Notificación al reportador" (email SMTP)
- AC-04: Para cada canal hay campos: URL/servidor, credencial (encriptada), template de mensaje (texto editable)
- AC-05: Botón "Enviar notificación de prueba" verifica la conexión con un mensaje de prueba
- AC-06: El `NOTIFY_PROVIDER` se recarga desde `platform_config` sin restart

**Dependencias:** HU-P017, HU-P018, HU-P027
**Roles que la usan:** SUPERADMIN, ADMIN (R/W)
**Complejidad:** M

---

#### HU-P024 — Configuración y visualización de agentes SRE

**Como** flow_configurator
**Quiero** ver la configuración de cada agente SRE (nombre, instrucciones, skills habilitadas) y editar los parámetros seguros
**Para** ajustar el comportamiento del sistema sin tocar código ni archivos YAML directamente

**Criterios de Aceptación Clave:**
- AC-01: `GET /config/agents` retorna la lista de agentes con: nombre, descripción, skills activas, umbrales de gobernanza asociados, versión del prompt. Requiere `flow_configurator` o superior.
- AC-02: `GET /config/agents/{agent_name}` retorna el detalle completo del agente incluyendo los parámetros editables. Requiere `flow_configurator` o superior.
- AC-03: `PUT /config/agents/{agent_name}` permite editar únicamente: descripción display, metadatos de activación de skills, y umbrales de gobernanza relacionados. Requiere `flow_configurator` o superior.
- AC-04: La estructura de prompts YAML **NO es editable** desde esta UI (SA-002). La UI muestra el prompt como solo lectura con syntax highlighting.
- AC-05: La UI muestra una tarjeta por agente: `intake_guard`, `triage`, `integration`, `resolution`. Cada tarjeta tiene: nombre, badge de estado (activo/degradado), lista de skills, botón "Editar parámetros".
- AC-06: Los cambios en umbrales de gobernanza se persisten via el endpoint existente `PUT /governance/thresholds` de HU-012.
- AC-07: Un cambio guardado genera un log de auditoría con: usuario, timestamp, agente modificado, campo cambiado, valor anterior, valor nuevo.

**Dependencias:** HU-P017, HU-P018, HU-P027, HU-012 (backend de governance ya existe)
**Roles que la usan:** SUPERADMIN, ADMIN, FLOW_CONFIGURATOR (R/W); VIEWER (R)
**Complejidad:** L

---

### EPIC-007 — Incident Management UI

**Objetivo:** Interfaz React para el flujo completo de gestión de incidentes: creación, seguimiento, visualización de resultado del triage, estado del ticket, y notificaciones.

---

#### HU-P025 — Migración del formulario de reporte de incidente a React

**Como** operador SRE
**Quiero** crear reportes de incidente a través de una interfaz React amigable y moderna
**Para** documentar fallas del sistema e-commerce de forma eficiente y con mejor experiencia de usuario

**Criterios de Aceptación Clave:**
- AC-01: El formulario React replica y mejora los campos de HU-001: descripción del problema, severidad, email del reportador (ahora **requerido**), archivo adjunto opcional
- AC-02: El formulario valida en tiempo real: email con formato válido, descripción mínima de 10 caracteres, tipo de archivo válido según config de HU-P020
- AC-03: Al enviar, el formulario llama `POST /incidents` con token JWT en el header `Authorization: Bearer {token}`
- AC-04: Tras una respuesta exitosa (HTTP 200), el usuario es redirigido automáticamente al módulo de estado del incidente (HU-P026) con el `incident_id` recibido
- AC-05: Un indicador de progreso (spinner + mensaje de etapa) muestra el avance del pipeline: Recibiendo → Analizando → Creando ticket → Notificando
- AC-06: En caso de error HTTP, se muestra un mensaje descriptivo al usuario sin exponer stack traces

**Dependencias:** HU-P017, HU-P018, HU-P027, HU-001 (backend), HU-002 (backend)
**Reemplaza en frontend:** HU-001 (HTMX form), HU-002 (HTMX file attachment)
**Roles que la usan:** OPERATOR, ADMIN, SUPERADMIN
**Complejidad:** M

---

#### HU-P026 — Dashboard de estado de incidente y ticket

**Como** operador SRE
**Quiero** ver el resultado del análisis de triage, el ticket asignado, las notificaciones enviadas y el estado actual del ticket en un panel unificado
**Para** hacer seguimiento completo de un incidente desde su reporte hasta su resolución

**Criterios de Aceptación Clave:**
- AC-01: El dashboard muestra para cada incidente: ID, descripción resumida, severidad (badge con color), estado del ticket, timestamp de creación, estado actual (open/closed)
- AC-02: Al seleccionar un incidente, se muestra el detalle: resultado del triage (summary, affected_components, root_cause), RAG attribution (fuentes usadas con barras de relevancia), ticket asignado (ID, URL al sistema de tickets)
- AC-03: Se muestran las notificaciones enviadas: al equipo (timestamp, destinatarios) y al reportador (si aplica)
- AC-04: El estado del ticket se refresca automáticamente cada 30 segundos via `GET /incidents/{id}/status` (SA-006)
- AC-05: Cuando el estado del ticket cambia a "cerrado", se muestra un badge "CERRADO" prominente y un mensaje "Notificación de resolución enviada a {email}"
- AC-06: El widget de feedback (thumbs up/down + comentario) está disponible en el detalle del incidente para el operator que lo creó
- AC-07: La lista de incidentes muestra: el `operator` ve solo los suyos, el `admin`/`superadmin` ve todos
- AC-08: La paginación es de 20 incidentes por página con filtros por severidad, estado, y rango de fechas

**Dependencias:** HU-P017, HU-P018, HU-P025, HU-P027, HU-005 (backend), HU-006 (backend), HU-008 (backend), HU-013 (RAG attribution), HU-015 (feedback)
**Reemplaza en frontend:** HU-005 (HTMX result panel), HU-013 (HTMX RAG attribution), HU-015 (HTMX feedback widget)
**Roles que la usan:** OPERATOR (propio), ADMIN, SUPERADMIN (todos), VIEWER (todos, sin PII)
**Complejidad:** L

---

#### HU-P027-EXTRA — Nuevo endpoint: GET /incidents/{id}/status

> Nota: Esta es una HU técnica de backend necesaria para HU-P026. No tiene UI propia.

**Como** desarrollador
**Quiero** exponer un endpoint liviano de status de incidente
**Para** que el dashboard pueda hacer polling sin cargar todo el objeto de incidente

**Criterios de Aceptación Clave:**
- AC-01: `GET /incidents/{id}/status` retorna `{"incident_id": "...", "case_status": "...", "ticket_id": "...", "ticket_status": "open|closed", "updated_at": "..."}`
- AC-02: El ticket_status se obtiene del sistema de tickets configurado via `ITicketProvider.get_ticket(ticket_id)`
- AC-03: Retorna HTTP 404 si el incident_id no existe
- AC-04: Requiere cualquier rol autenticado. El operator solo puede consultar sus propios incidentes.
- AC-05: El endpoint tiene cache de 15 segundos para evitar sobrecarga en polling concurrente

**Dependencias:** HU-006 (ITicketProvider), HU-P018
**Complejidad:** S

---

### EPIC-008 — Platform Shell

**Objetivo:** Aplicación React base que contenga la navegación, el sistema de diseño, la autenticación, y el layout personalizable por el usuario.

---

#### HU-P027 — Shell de la aplicación React (estructura base)

**Como** usuario de la plataforma
**Quiero** navegar entre los módulos de la plataforma a través de un menú lateral con navegación clara
**Para** acceder rápidamente a cualquier función según mi rol

**Criterios de Aceptación Clave:**
- AC-01: La aplicación React se inicializa en su propio contenedor Docker (`sre-web`) sirviendo en el puerto `3001` (o servida como build estático desde FastAPI — decisión de @architect)
- AC-02: La navegación lateral muestra solo los módulos accesibles por el rol del usuario autenticado (RBAC en frontend)
- AC-03: La pantalla de login es la landing page para usuarios no autenticados. Muestra el mock Google login con selector de usuario de demo.
- AC-04: El token JWT se almacena en `httpOnly` cookie o `localStorage` (decisión de @architect para el hackathon — si localStorage: agregar nota de seguridad)
- AC-05: El shell incluye un header con: logo de la plataforma, nombre del usuario autenticado, badge de rol, botón de logout
- AC-06: El logout elimina el token y redirige al login
- AC-07: Las rutas protegidas redirigen a login si el token ha expirado
- AC-08: El sistema de diseño usa **Tailwind CSS** (consistente con el Tailwind ya usado en los templates HTMX existentes)
- AC-09: La app maneja CORS correctamente (FastAPI debe tener `CORSMiddleware` configurado para el origen del SPA)

**Dependencias:** HU-P017, HU-P018
**Roles que la usan:** Todos
**Complejidad:** L

---

#### HU-P028 — Layout personalizable por el usuario (dashboard drag-and-drop)

**Como** usuario de la plataforma
**Quiero** reorganizar los paneles/widgets del dashboard de incidentes arrastrando y soltando
**Para** personalizar la vista de información según mi flujo de trabajo

**Criterios de Aceptación Clave:**
- AC-01: El dashboard de incidentes soporta reordenamiento de widgets via drag-and-drop usando **react-beautiful-dnd** o **dnd-kit**
- AC-02: Los widgets disponibles son: Lista de incidentes, Métricas de severidad (conteo por tipo), Estado del agente (health), Actividad reciente
- AC-03: El layout personalizado del usuario se guarda en `localStorage` y opcionalmente en `user_preferences` en BD
- AC-04: El layout tiene una opción "Restablecer por defecto"
- AC-05: El drag-and-drop funciona en desktop. En móvil, el layout es fijo (responsive sin drag).
- AC-06: Cada widget puede minimizarse (collapse) sin desaparecer del layout
- AC-07: La librería de drag-and-drop elegida debe ser aprobada por @architect (nueva dependencia npm)

**Dependencias:** HU-P027, HU-P026
**Roles que la usan:** Todos
**Complejidad:** M

> **Nota al @architect:** Esta HU implementa el "constructor drag-and-drop" del requisito del cliente bajo el supuesto SA-001 (dashboard layout, no constructor de flujos de agentes). Si el cliente quiere un constructor visual de flujos de agentes (Node-RED style), eso es una HU XL adicional que se cataloga como v2.

---

## 5. Impacto en HUs Existentes (HU-001 a HU-016)

| HU | Título | Impacto | Detalle |
|----|--------|---------|---------|
| **HU-001** | Incident Report Form UI | **MODIFICADA** | La UI HTMX es reemplazada por el formulario React de HU-P025. Los endpoints backend (`POST /incidents`) permanecen sin cambio. El campo `reporter_email` pasa de opcional a **requerido** (resuelve AMB-001 y CONF-006). |
| **HU-002** | Multimodal File Attachment | **MODIFICADA** | La UI de adjunto de archivos pasa a React (HU-P025). La lógica de validación de tipos de archivo se parametriza via HU-P020 en lugar de ser hardcodeada. El backend de procesamiento de archivos permanece. |
| **HU-003** | Input Guardrails | **SIN IMPACTO** | Opera a nivel de API. Independiente del frontend. La lista de tipos MIME válidos puede sincronizarse con HU-P020 como mejora opcional. |
| **HU-004** | LLM Triage Analysis | **SIN IMPACTO** | Lógica interna del agente. Sin cambios. |
| **HU-005** | Technical Summary Output | **MODIFICADA** | El panel HTMX de resultado (`result_partial.html`) es reemplazado por el componente React en HU-P026. Los endpoints de backend y el modelo `TriageResult` permanecen sin cambio. |
| **HU-006** | Ticket Creation | **SIN IMPACTO** | Backend puro. Sin cambios. La configuración del sistema de tickets ahora se puede hacer desde HU-P022. |
| **HU-007** | Team Notification | **SIN IMPACTO** | Backend puro. La configuración del canal de notificación ahora se puede hacer desde HU-P023. |
| **HU-008** | Resolution Notification | **MODIFICADA** | El campo `reporter_email` pasa a ser **requerido** (CONF-006). El trigger de resolución (`POST /tickets/:id/resolve`) sigue existiendo, ahora llamado desde React en HU-P026. La pregunta pendiente de HU-008 queda resuelta: email es requerido. |
| **HU-009** | Structured Stage Logging | **SIN IMPACTO** | Cross-cutting concern de observabilidad. Sin cambios. |
| **HU-010** | Trace Correlation | **SIN IMPACTO** | Cross-cutting concern. Sin cambios. |
| **HU-011** | Mock Services Container | **SIN IMPACTO** | Infraestructura de mock. Sin cambios. |
| **HU-012** | Governance Thresholds (backend) | **EXPANDIDA (v4.0)** | Los endpoints `GET/PUT /governance/thresholds` son consumidos ahora por HU-P032 (Centralized Config Page, sección Governance & Thresholds) en lugar de por HU-016 (HTMX). **Expansión de scope por Requisito D:** El puerto `IGovernanceProvider` ya no gestiona solo los 5 umbrales originales. Con HU-P032, el concepto de "configuración gobernable" se extiende a TODAS las variables de negocio. @architect debe decidir si `IGovernanceProvider` se expande o si se crean puertos adicionales (`ILLMConfigProvider`, `IPlatformConfigProvider`). Los endpoints `GET/PUT /governance/thresholds` continúan cubriendo solo los thresholds de gobernanza — los nuevos módulos (LLM, Tickets, Notificaciones, Seguridad, Almacenamiento, Observabilidad) tienen sus propios endpoints. Ver DEC-A08 en sección Handoff. |
| **HU-013** | Explainability/RAG Attribution | **MODIFICADA** | El bloque "Fuentes" con barras de relevancia se mueve del template HTMX al componente React de HU-P026. El backend y el modelo `ExplainabilityReport` permanecen. |
| **HU-014** | Online Eval Langfuse | **SIN IMPACTO** | Background task. Sin cambios. |
| **HU-015** | Feedback Widget | **MODIFICADA** | El widget de feedback (thumbs up/down) se mueve del template HTMX al componente React de HU-P026. El endpoint `POST /feedback/{incident_id}` permanece. El auth cambia de API key a JWT (HU-P018). |
| **HU-016** | Panel UI Governance (HTMX) | **SUPERSEDIDA** | HU-016 es completamente reemplazada por HU-P024. La UI React con autenticación RBAC sustituye el template HTMX. El backend de HU-012 (que HU-016 consumía) permanece intacto. Si HU-016 ya fue implementada, el template `governance.html` puede eliminarse una vez HU-P024 esté listo. |

### Impacto adicional por Requisitos v2.0

| HU | Requisito que genera el impacto | Tipo de impacto | Detalle |
|----|--------------------------------|----------------|---------|
| **HU-012** (Governance Thresholds) | Requisito A (Config LLM) | **CLARIFICACIÓN** | La config LLM NO se almacena en `governance_thresholds`. Se crea tabla separada `llm_config` (SA-009). HU-012 queda sin cambios en su diseño. El `@architect` debe confirmar esta decisión antes de la migración Alembic de HU-P029. |
| **HU-013** (RAG Attribution) | Requisito B (eShop real) | **ENRIQUECIDA** | El contenido de `rag_attribution.sources` cambia de nombres de archivos estáticos locales a rutas reales del repo de GitHub con URLs clickeables (ej: `https://github.com/dotnet-architecture/eShopOnWeb/blob/main/src/Web/Controllers/OrderController.cs`). La lógica de HU-013 no cambia, solo el contenido del dato. Mejora significativa del impacto en demo. |
| **HU-P021** (Config repo ecommerce) | Requisito B (eShop real) | **EXPANDIDA** | HU-P021 ya contemplaba configurar la URL del repo. Con HU-P030, se agrega: (a) botón "Re-indexar ahora" que trigerea el `GithubContextProvider`, (b) indicador de estado del índice (última indexación, número de archivos indexados, estado: OK/Error). |
| **HU-P027** (Shell React) | Requisito C (Design System SoftServe) | **BLOQUEADA hasta HU-P031** | HU-P027 AC-08 especificaba Tailwind CSS como sistema. Con HU-P031, los tokens de diseño SoftServe deben estar definidos en `tailwind.config.js` ANTES de que se construya el shell. El orden de implementación cambia: HU-P031 → HU-P027. |
| **HU-016** (Governance UI HTMX) | Requisito D (Config-from-DB) | **SUPERSEDIDA COMPLETA (v4.0)** | HU-P032 reemplaza completamente HU-016. El template HTMX `governance.html` se elimina una vez HU-P032 pasa QA. Los endpoints backend de HU-012 permanecen. |
| **HU-P031** (Design System) | Requisito E (UI en inglés) | **EXPANDIDA (v4.0 — v3)** | Se añaden AC-12 (English-only UI, no i18n) y BR-06 (English-only rule global). Aplica a todos los componentes y todas las HUs que consumen el Design System. |
| **HU-P025, HU-P026, HU-P027, HU-P028, HU-P032 y todas EPIC-006** | Requisito E (UI en inglés) | **REGLA GLOBAL AÑADIDA** | Todas estas HUs deben incluir una Business Rule: "All UI text must be in English — no i18n layer required." Esta regla se implementa a nivel del Design System (HU-P031 v3) y es heredada por todos los componentes. No se necesita actualizar cada HU individualmente — la BR de HU-P031 es la fuente de verdad. |

### Resumen de impacto (v4.0)

| Categoría | Cantidad | HUs |
|-----------|---------|-----|
| Sin impacto | 7 | HU-003, HU-004, HU-006, HU-007, HU-009, HU-010, HU-011, HU-014 |
| Modificadas (backend intacto, frontend cambia) | 6 | HU-001, HU-002, HU-005, HU-008, HU-013, HU-015 |
| Supersedidas (completamente reemplazadas) | 1 | HU-016 (por HU-P032) |
| Expandidas de scope (Requisito D — v4.0) | 1 | HU-012 (`IGovernanceProvider` cubre ahora toda la config de negocio) |
| Enriquecidas (misma lógica, dato más completo) | 1 | HU-013 |
| Expandidas (HU existente ampliada por nuevo requisito) | 2 | HU-P021 (botón re-indexar), HU-P031 (v3 — English-only AC/BR) |
| Bloqueadas hasta nueva HU | 1 | HU-P027 (bloqueada hasta HU-P031) |
| Nuevas HUs añadidas en v4.0 | 1 | HU-P032 (Centralized Configuration Page) |

---

## 6. Mapa de Dependencias

### Orden de implementación sugerido (v2.0)

```
IMPORTANTE (v2.0): HU-P031 (Design System SoftServe) es ahora el punto de partida
obligatorio para toda la capa React. HU-P027 no puede iniciarse sin los tokens.

Fase 0 — Design System (BLOQUEA TODO LO VISUAL):
  HU-P031 (Design System SoftServe — tailwind.config.js con tokens)
  HU-P030 (Integración eShopOnWeb — GithubContextProvider, se puede correr en paralelo
           con Fase 0 ya que es backend puro)

Fase 1 (paralela — requiere HU-P031):
  HU-P017 (Mock Google Auth — backend puro, no requiere P031)
  HU-P027 (React Shell base — AHORA requiere HU-P031 para tokens)

Fase 2 (requiere Fase 1):
  HU-P018 (JWT Middleware FastAPI)
  HU-P029 (Config LLM — backend + UI, requiere P027 para pantalla)
  → HU-P019 (User Management)

Fase 3 (requiere Fase 2):
  HU-P020 (File Types Config)
  HU-P021 (Ecommerce Repo Config — ahora expandida con botón Re-indexar)
  HU-P022 (Ticket System Config)
  HU-P023 (Notifications Config)
  HU-P024 (Agent Config)
  [pueden correr en paralelo]

Fase 4 (requiere Fase 3 + HU-P027):
  HU-P027-EXTRA (endpoint /status)
  HU-P025 (Incident Form React)
  → HU-P026 (Incident Dashboard)
  → HU-P028 (Drag-and-drop layout)
```

### Tabla de dependencias de nuevas HUs (v2.0)

| HU | Depende de |
|----|-----------|
| HU-P017 | — |
| HU-P018 | HU-P017 |
| HU-P019 | HU-P017, HU-P018 |
| HU-P020 | HU-P017, HU-P018, HU-P027 |
| HU-P021 | HU-P017, HU-P018, HU-P027, HU-P030 (para botón re-indexar) |
| HU-P022 | HU-P017, HU-P018, HU-P027 |
| HU-P023 | HU-P017, HU-P018, HU-P027 |
| HU-P024 | HU-P017, HU-P018, HU-P027, HU-012 |
| HU-P025 | HU-P017, HU-P018, HU-P027, HU-001 (backend), HU-002 (backend) |
| HU-P026 | HU-P017, HU-P018, HU-P025, HU-P027, HU-P027-EXTRA |
| **HU-P027** | HU-P017, **HU-P031** (NUEVO — requiere tokens de diseño) |
| HU-P027-EXTRA | HU-006, HU-P018 |
| HU-P028 | HU-P027, HU-P026 |
| **HU-P029** | HU-P017, HU-P018, HU-P027 |
| **HU-P030** | HU-P004 (IContextProvider existente), HU-P021 (config repo) |
| **HU-P031** | — (primera HU a implementar en la capa React) |

---

## 7. Preguntas Pendientes para el Cliente

> Estas preguntas DEBEN ser respondidas antes de que @architect apruebe la arquitectura y @developer inicie implementación.

| # | Pregunta | Impacto | Urgencia |
|---|---------|---------|---------|
| PQ-01 | ¿El SPA React se sirve como contenedor separado (`sre-web` en Docker Compose, puerto 3001) o se construye como build estático y se sirve desde FastAPI (misma URL, rutas `/app/*`)? | Define la arquitectura de despliegue y el modelo de CORS | CRÍTICA — @architect debe decidir |
| PQ-02 | ¿El JWT se almacena en `httpOnly` cookie (más seguro) o en `localStorage` (más simple para el hackathon)? | Afecta la implementación del cliente React y la configuración del servidor | Alta — @architect |
| PQ-03 | ¿El "constructor drag-and-drop" que el cliente menciona es solo para reorganizar widgets del dashboard (SA-001), o en algún momento se necesita un constructor visual de flujos de agentes estilo Node-RED? | Si es el segundo: HU adicional XL estimada en 3-5 días de desarrollo | Alta — @cliente/PO |
| PQ-04 | ¿El campo `reporter_email` debe ser requerido en el formulario React para todos los incidentes (SA-008)? Esto resuelve la pregunta pendiente de HU-008. | Rompe tests existentes si se hace requerido sin actualizar fixtures | Alta — PO |
| PQ-05 | ¿Las credenciales de adaptadores (API keys, passwords) deben encriptarse en BD (requiere `CONFIG_ENCRYPTION_KEY`)? ¿O para el hackathon se almacenan en texto plano con nota de seguridad? | Afecta HU-P021, HU-P022, HU-P023 | Media — @architect |
| PQ-06 | ¿El sistema de diseño React debe seguir exactamente el estilo visual actual (Tailwind CSS)? ¿O hay libertad de diseño para las pantallas nuevas? | Afecta HU-P027 (shell y design system) | Media — @cliente |
| PQ-07 | **Deadline:** Dado que el hackathon tiene fecha límite 2026-04-09 21:00 COT y el proyecto ya está en fase de submission, ¿esta expansión de plataforma es para la entrega del hackathon o es una fase post-hackathon? | Si es para el hackathon: implica un cambio radical de alcance en menos de 24 horas. Si es post-hackathon: se puede diseñar con más cuidado. | **RESUELTA — 2026-04-08:** Todo el alcance entra al hackathon. La opción "post-hackathon" no aplica. Se implementa todo. |
| PQ-08 | **Requisito A — Circuit breaker runtime config:** ¿El circuit breaker existente en `adapters/llm/circuit_breaker.py` debe leer `cb_failure_threshold` y `cb_cooldown_seconds` de la tabla `llm_config` en tiempo de ejecución (requiere refactor del circuit breaker)? ¿O estos parámetros se leen solo al arrancar el servicio? | Si es en runtime: el circuit breaker necesita acceso a la BD o a un cache. Si es al arrancar: es más simple pero requiere restart para aplicar cambios. | **RESUELTA — 2026-04-08:** Hot reload requerido. Los cambios aplican en < 5 segundos sin reiniciar el container. El circuit breaker adopta nuevos parámetros en el siguiente ciclo. Ver SA-012. HU-P029 actualizada a v2 con AC-12, AC-13, BR-05 (modificado), BR-08 (nuevo). |
| PQ-09 | **Requisito B — Estrategia de indexación eShopOnWeb:** ¿La indexación del repo GitHub se hace una sola vez en el startup del contenedor (carga inicial lenta) o existe un botón "Re-indexar" en HU-P021 que el admin trigerea bajo demanda (servicio arranca con índice anterior o estático como fallback)? | Impacta la experiencia de primer arranque del demo y el diseño del `GithubContextProvider`. | **RESUELTA — 2026-04-08:** Indexación en startup del container (no bajo demanda). Si existe índice previo, se reutiliza. Cambiar la URL requiere restart (ventana de mantenimiento). Para el hackathon, eShop pre-configurado y pre-indexado en la imagen Docker. Ver SA-013. HU-P030 actualizada a v2. |
| PQ-10 | **Requisito C — Brand Guide SoftServe:** ¿El cliente tiene acceso al Brand Guide oficial de SoftServe (documento PDF, Figma de marca, o similar)? Si existe, reemplaza los valores inferidos documentados en HU-P031 y en la sección 9.3. | Los colores y tipografías documentados son inferidos de materiales públicos. Una fuente oficial elimina riesgo de inconsistencia con la marca real. | **RESUELTA — 2026-04-08:** No hay Brand Guide disponible. Se realizó búsqueda web (Brandfetch, logo.com). Corrección crítica: color primario es `#454494` (violeta-azul), no rojo. Ver SA-014. HU-P031 actualizada a v2. |

> **Estado de preguntas:** 0 preguntas críticas pendientes. Todas las PQs están resueltas. El análisis está cerrado y listo para @architect.

---

## 8. Índice de Nuevas HUs Propuestas

> v4.0 — actualizado el 2026-04-08. Incluye HU-P029, HU-P030, HU-P031, HU-P032.

| ID | Epic | Título | Complejidad | Estado |
|----|------|--------|------------|--------|
| HU-P017 | EPIC-005 | Mock Google OAuth Login y JWT | M | Draft |
| HU-P018 | EPIC-005 | Middleware JWT y autorización FastAPI | M | Draft |
| HU-P019 | EPIC-005 | Gestión de usuarios CRUD (admin) | M | Draft |
| HU-P020 | EPIC-006 | Configuración de tipos de archivos permitidos | S | Draft |
| HU-P021 | EPIC-006 | Configuración del repositorio e-commerce | M | Draft |
| HU-P022 | EPIC-006 | Configuración del sistema de tickets | M | Draft |
| HU-P023 | EPIC-006 | Configuración de notificaciones | M | Draft |
| HU-P024 | EPIC-006 | Configuración y visualización de agentes SRE | L | Draft |
| HU-P025 | EPIC-007 | Formulario de incidente en React | M | Draft |
| HU-P026 | EPIC-007 | Dashboard de estado de incidente y ticket | L | Draft |
| HU-P027-EXTRA | EPIC-007 | Endpoint GET /incidents/{id}/status | S | Draft |
| HU-P027 | EPIC-008 | Shell React (estructura base, navegación, login) | L | Draft |
| HU-P028 | EPIC-008 | Layout personalizable drag-and-drop | M | Draft |
| **HU-P029** | EPIC-006 | Configuración del proveedor LLM y circuit breaker | M | **Approved** |
| **HU-P030** | EPIC-009 | Integración real con eShopOnWeb — indexación RAG | L | **Approved** |
| **HU-P031** | EPIC-008 | Design System SoftServe — tokens y componentes base React | M | **Approved v3** |
| **HU-P032** | EPIC-006 | Centralized Configuration Page — Config-from-DB | L | **Approved** |

**Total nuevas HUs:** 17
**HUs Approved:** HU-P029, HU-P030, HU-P031 (v3), HU-P032
**HUs Draft (pendientes de refinamiento formal):** HU-P017 a HU-P028 (definidas en este análisis, refinamiento completo pendiente)
**Complejidad total estimada (v4.0):** 2S + 7M + 5L = escenario hackathon acotado, se requiere priorización dura.

> **Nota de alcance v4.0:** HU-P032 es la UI unificada de configuración. Absorbe la capa UI de HU-P029 (LLM config), supersede HU-016 (Governance HTMX), y proporciona la interfaz para todas las secciones de configuración de EPIC-006. El orden de implementación sugerido se actualiza: HU-P031 → HU-P027 → HU-P017 → HU-P018 → HU-P029 (backend) → HU-P030 → HU-P032 (UI unificada) → HU-P025 → HU-P026 → resto EPIC-006.

---

## 9. Requisitos Adicionales v2.0

### 9.1 Requisito A — Configuración de proveedor LLM en la plataforma

**Origen:** Solicitud del cliente 2026-04-08
**Epic asignado:** EPIC-006 (Configuration Platform)
**HU creada:** HU-P029

**Descripción:**
Se añade al módulo de configuración (EPIC-006) una sección específica para configurar el proveedor LLM que usa el agente de triage. Esto permite cambiar el proveedor (Gemini, OpenRouter, Anthropic, OpenAI), el modelo específico, la API key, el proveedor de fallback, y los parámetros del circuit breaker — todo desde la UI, sin redesplegar.

**Decisión de almacenamiento — tabla pendiente de @architect:**
Hay dos opciones para persistir la config LLM:
- **Opción A (tabla nueva):** Crear tabla `llm_config` en PostgreSQL con columnas `provider`, `model`, `api_key_encrypted`, `is_fallback`, `cb_failure_threshold`, `cb_cooldown_seconds`. Esta opción es más limpia y semánticamente separada de los umbrales de gobernanza.
- **Opción B (tabla existente):** Almacenar las claves en `governance_thresholds` con prefijo `llm_*` (ej: `llm_provider`, `llm_model`). Esta opción evita una migración nueva pero acopla concerns distintos.

**Recomendación del @product-analyst:** Opción A — tabla `llm_config` separada. El LLM es un adaptador de infraestructura, no una regla de gobernanza. Mezclarlos en `governance_thresholds` viola el principio de responsabilidad única.

**Roles con acceso:** Solo `superadmin` y `admin` pueden modificar esta sección.

**Impacto en HUs existentes:**
- `HU-012` (Governance Thresholds): Sin cambio en backend. Nota: la config LLM NO usa `governance_thresholds` — va a tabla separada `llm_config` (decisión de @architect mediante Opción A recomendada).
- `HU-P024` (Agent Config): La sección de configuración LLM es un módulo separado dentro de EPIC-006, no un subsection de HU-P024. HU-P024 sigue siendo config de agentes (prompts, skills). HU-P029 es config de infraestructura LLM.

**Nueva ambigüedad (PQ-08):**
- ¿El circuit breaker ya implementado en `services/sre-agent/app/adapters/llm/circuit_breaker.py` debe leer su configuración de `llm_config` en BD en lugar de variables de entorno? Si es así, requiere que el circuit breaker sea refactorizado para ser configurable en runtime. Esto es una decisión de @architect.

---

### 9.2 Requisito B — Integración real con eShop de Microsoft

**Origen:** Solicitud del cliente 2026-04-08
**Epic asignado:** EPIC-009 (nuevo) — eShop Real Integration
**HU creada:** HU-P030

#### 9.2.1 Recomendación: eShopOnWeb vs eShopOnContainers

| Criterio | eShopOnWeb | eShopOnContainers |
|---------|-----------|------------------|
| **Complejidad del repo** | Media — ASP.NET MVC/Razor, monolito modular | Alta — ~10 microservicios, Docker Compose propio complejo |
| **Volumen de código a indexar** | ~50-80K tokens de código relevante | ~300-500K tokens distribuidos en múltiples servicios |
| **Estructura de carpetas** | Plana, predecible, fácil de rastrear | Profunda, por servicio, difícil de rastrear sin heurísticas |
| **Relevancia para demo SRE** | Alta — un sistema monolítico e-commerce con errores claros | Alta pero dispersa — los incidentes típicos son de comunicación entre servicios |
| **Tiempo de indexación RAG** | Rápido (~2-5 min para FAISS) | Lento (~15-30 min para indexar todos los repos) |
| **Acceso** | Repositorio público GitHub, sin credenciales | Repositorio público GitHub, sin credenciales |
| **Impacto en demo hackathon** | Muy alto — el agente puede razonar sobre código concreto y real | Alto pero arriesgado — la complejidad puede generar respuestas inconsistentes |
| **Riesgo de implementación en <24h** | Bajo-Medio | Alto |

**Recomendación final: eShopOnWeb (`https://github.com/dotnet-architecture/eShopOnWeb`)**

Justificación: Para el hackathon (menos de 24h de implementación), eShopOnWeb ofrece el mejor ratio impacto-en-demo / riesgo-de-implementación. El código es accesible, estructurado y manejable para indexación FAISS. El agente SRE puede hacer referencias concretas a archivos como `OrderService.cs`, `BasketController.cs`, etc., lo que hace el triage mucho más impresionante que referencias genéricas a "un microservicio X". eShopOnContainers es la evolución natural para una v2 real del producto.

**Impacto en la arquitectura del adapter `IContextProvider`:**

La situación actual:
- `IContextProvider` tiene una implementación estática que lee archivos de `eshop-context/` (carpeta de archivos estáticos pre-procesados) y los sirve al LLM como contexto FAISS.
- La integración real requiere que `IContextProvider` lea el repositorio de GitHub directamente (o clone localmente) e indexe los archivos de código fuente.

Dos estrategias posibles para @architect:
- **Estrategia 1 (nuevo adapter):** Crear `GithubContextProvider` que implementa `IContextProvider`, usa la GitHub API (o `git clone` temporal) para obtener los archivos y los indexa con FAISS al iniciar / bajo demanda. El adapter existente estático permanece como fallback.
- **Estrategia 2 (extensión del FAISS adapter):** El adapter FAISS existente se parametriza con una fuente: `static` (carpeta local) o `github` (URL + credenciales). Al arrancar o cuando el admin triggerea "Re-indexar", el adapter descarga el repo y reconstruye el índice FAISS.

**Recomendación del @product-analyst:** Estrategia 1 (nuevo adapter `GithubContextProvider`) — más limpia, no rompe el adapter estático existente (que puede servir como fallback si GitHub no está disponible), y sigue el patrón de hexagonal architecture ya establecido en el proyecto.

**Lo que cambia en HU-013 (RAG attribution):**
HU-013 no cambia en su lógica — sigue mostrando las fuentes del RAG con barras de relevancia. Lo que cambia es el contenido de `rag_attribution.sources`: en lugar de ser nombres de archivos estáticos locales, ahora serán rutas de archivos reales del repo (`src/Web/Controllers/OrderController.cs`, etc.) con URLs de GitHub incluidas. Esto enriquece significativamente la experiencia de demo — el usuario puede hacer clic en la fuente y ver el código real en GitHub.

**Lo que cambia en HU-P021 (config repo ecommerce):**
HU-P021 se convierte en la UI que permite configurar la URL del repo de GitHub (`https://github.com/dotnet-architecture/eShopOnWeb`), tipo de acceso (public = sin credenciales), y triggerea la re-indexación. HU-P021 ya estaba planificada — HU-P030 la complementa con la implementación real del adapter.

**Nueva ambigüedad (PQ-09):**
- ¿La indexación del repo de GitHub se hace una sola vez al arrancar el contenedor (startup indexing) o existe un botón "Re-indexar" en la UI de HU-P021 que el admin puede triggear? Si se hace en startup, el primer arranque puede ser lento. Si es bajo demanda, el agente funciona con el índice estático hasta que el admin actualiza. Para el hackathon se recomienda startup indexing con fallback a contexto estático si falla.

---

### 9.3 Requisito C — Imagen corporativa SoftServe en la UI

**Origen:** Solicitud del cliente 2026-04-08
**Epic asignado:** EPIC-008 (Platform Shell React)
**HU creada:** HU-P031

#### 9.3.1 Identidad visual SoftServe documentada

| Elemento | Valor | Fuente |
|---------|-------|--------|
| Color primario | `#E3001B` (rojo SoftServe) | Conocido públicamente / sitio web softserveinc.com |
| Color secundario | `#FFFFFF` (blanco) | Paleta estándar SoftServe |
| Color terciario / neutro | `#1A1A1A` (gris muy oscuro, casi negro) | Uso en texto y fondos oscuros |
| Color de fondo | `#F5F5F5` (gris claro) o `#FFFFFF` | Uso en paneles y backgrounds |
| Color de acento / interactivo | `#B5000F` (rojo oscuro — hover states) | Derivado del primario |
| Color de texto principal | `#222222` | Texto sobre fondos claros |
| Tipografía principal | **Montserrat** (Google Fonts, OFL) — sans-serif moderno, usado extensamente por SoftServe en materiales públicos | softserveinc.com, LinkedIn, decks públicos |
| Tipografía alternativa | **Inter** o **Open Sans** como fallback system font | Si Montserrat no carga |
| Bordes / border-radius | `4px` o `8px` — estilo corporativo limpio, no excesivamente redondeado | Inferido de la web de SoftServe |
| Iconografía | Material Icons o Heroicons (simple, sans-serif style) | Compatible con la estética SoftServe |
| Sombras | Sutiles — `box-shadow: 0 2px 8px rgba(0,0,0,0.1)` | Estilo corporativo moderno |

**Fuentes de referencia para el desarrollador:**
- Sitio web oficial: `https://www.softserveinc.com` — observar paleta real en producción
- LinkedIn SoftServe: materiales de marca aplicada
- Archivos públicos de presentaciones SoftServe disponibles en slideshare / eventos tech

**Advertencia:** SoftServe no tiene un design system público documentado (como Atlassian Design System o Material Design). Los valores arriba son inferidos de observación de materiales públicos. Si el cliente tiene acceso a un brand guide interno de SoftServe, debe compartirlo antes de que @developer inicie HU-P031.

**Nueva pregunta pendiente (PQ-10):**
- ¿El cliente tiene acceso al Brand Guide oficial de SoftServe (PDF, Figma, etc.)? Si existe, es la fuente de verdad y reemplaza los valores inferidos. Si no, se usan los valores documentados arriba.

**Impacto en HU-P027 (Shell React):**
HU-P027 AC-08 decía "el sistema de diseño usa Tailwind CSS". Esto se mantiene — Tailwind es el sistema de implementación. HU-P031 define los tokens de diseño (colores, tipografía, espaciado) que se configuran en `tailwind.config.js` como custom theme. HU-P031 debe ejecutarse ANTES de HU-P027 para que el shell ya use los tokens correctos desde el inicio.

---

### 9.4 Requisito D — Configuración centralizada: todo desde la UI, cero variables quemadas

**Origen:** Solicitud del cliente 2026-04-08
**Epic asignado:** EPIC-006 (Configuration Platform)
**HU creada:** HU-P032

**Descripción:**
Todo lo que hoy está como variable de entorno o configuración en `config.py` (excepto las variables de bootstrap) debe ser gestionable desde la UI de la plataforma, en la sección Configuración (`/config`). Los campos deben estar agrupados por secciones, con un label descriptivo en inglés y una descripción breve para cada variable.

**Principio arquitectónico resultante — "Config-from-DB":**
Ver sección "Principio de Diseño: Config-from-DB" en la sección 2 de este documento.

**Clasificación de variables:**
La clasificación completa (Bootstrap vs UI, con label, tipo de input y descripción) está documentada en `HU-P032-centralized-config-page.md`, sección "Variable Classification".

**Impacto en HUs:**
- **HU-016** (Governance UI HTMX): **Supersedida** por HU-P032. El template `governance.html` se elimina.
- **HU-P029** (Config LLM): La UI de HU-P029 queda absorbida por HU-P032 (sección LLM Configuration). El backend de HU-P029 (tabla `llm_config`, hot reload) sigue siendo válido como contrato de backend.
- **HU-012** (Governance Port+DB): El scope del puerto `IGovernanceProvider` se expande. Ya no gestiona solo los 5 thresholds originales — ahora la config de negocio es más amplia. @architect debe decidir si ampliar el puerto o crear nuevos puertos dedicados. Ver DEC-A08 en sección 10.

**Decisión de arranque en frío (DEC-A08):**
¿Cómo gestiona el sistema el arranque en frío cuando la BD está vacía de config? La migración de Alembic que ya existe para `governance_thresholds` debe extenderse para sembrar los defaults de `llm_config` y todos los keys de `platform_config` que HU-P032 requiere. Sin este seed, la página de config podría arrancar en blanco. Ver DEC-A08 en sección 10.

---

### 9.5 Requisito E — Idioma de la UI: todo en inglés

**Origen:** Solicitud del cliente 2026-04-08
**Decisión global:** SA-015

**Descripción:**
Toda la interfaz de usuario de la plataforma (todas las HUs React, EPIC-005 a EPIC-008) debe estar en inglés. No se implementa ninguna capa de internacionalización (i18n) en v1.

**Alcance de la decisión:**
Esta es una decisión arquitectónica transversal que afecta a todos los componentes React. Se implementa a nivel del Design System (HU-P031 v3, AC-12, BR-06) y es heredada implícitamente por todas las HUs que consumen el Design System.

**Impacto directo en HUs:**
- **HU-P031** (Design System): Actualizada a v3. Se añaden AC-12 y BR-06 explícitamente.
- **HU-P025, HU-P026, HU-P027, HU-P028, HU-P032 y HUs de EPIC-006:** La BR "All UI text must be in English — no i18n layer required" aplica a todas ellas por herencia del Design System. No se necesita actualizar cada HU individualmente.

**Lo que NO se implementa:**
- No se instalan librerías i18n (react-i18next, lingui, FormatJS, etc.)
- No se crean archivos de locale (`.json` de traducciones)
- No se añaden atributos `lang` dinámicos ni selectores de idioma
- No se implementa ninguna lógica de detección de idioma del navegador

---

## 10. Handoff para @architect

> **Preparado por:** @product-analyst
> **Fecha:** 2026-04-08
> **Estado:** Análisis cerrado — 0 preguntas pendientes críticas. Listo para revisión arquitectónica.

Este documento es el insumo completo para que @architect pueda:
1. Validar la viabilidad técnica de las 16 HUs propuestas.
2. Tomar las decisiones técnicas pendientes que se identifican abajo.
3. Aprobar o ajustar el orden de implementación.
4. Iniciar el diseño arquitectónico con `@developer`.

---

### 10.1 Decisiones técnicas que @architect debe tomar

> Estas decisiones no bloquean el inicio de desarrollo en HU-P031 (primera HU a implementar), pero deben resolverse antes del inicio de las HUs marcadas en la columna "Bloquea".

| ID | Decisión requerida | Opciones identificadas | Bloquea | Urgencia |
|----|-------------------|----------------------|---------|---------|
| DEC-A01 | **Despliegue del SPA React:** ¿Contenedor separado `sre-web` (puerto 3001) o build estático servido desde FastAPI? | (a) `sre-web` en Docker Compose: más limpio, CORS explícito, build pipeline separado. (b) Servir desde FastAPI (`/app/*`): mismo origen, sin CORS, build integrado al contenedor. Para hackathon: opción (b) reduce complejidad de Docker Compose. | HU-P027 | CRÍTICA antes de HU-P027 |
| DEC-A02 | **Almacenamiento del JWT en cliente:** `httpOnly` cookie vs `localStorage` | Cookie: más seguro (no accesible por JS), requiere config `SameSite`/`Secure` en FastAPI. LocalStorage: más simple para hackathon, riesgo de XSS aceptable para demo. | HU-P027 | Alta antes de HU-P027 |
| DEC-A03 | **Mecanismo de hot reload LLM en `container.py`:** Event bus interno vs cache con TTL | (a) `asyncio.Event` disparado por `PUT /config/llm` que reinicializa el adapter LLM en `container.py`. (b) Cache singleton con TTL de 5s que se invalida explícitamente al guardar. Opción (a) es más inmediata; opción (b) es más simple de implementar. | HU-P029 | Alta antes de HU-P029 |
| DEC-A04 | **Refactor de `circuit_breaker.py` para hot reload:** Método `reconfigure()` vs nueva instancia | (a) Exponer `circuit_breaker.reconfigure(threshold, cooldown)` — mantiene historial de fallos acumulado. (b) Crear nueva instancia del CircuitBreaker con nuevos parámetros — pierde el estado actual. Recomendación: opción (a). | HU-P029 | Alta antes de HU-P029 |
| DEC-A05 | **Mecanismo de descarga del repo eShopOnWeb:** ZIP via HTTPS vs `git clone --depth=1` | ZIP: sin dependencia de git en el Dockerfile, descarga directa via `requests`. `git clone`: más robusto para repos grandes, requiere instalar git en la imagen. Para hackathon: ZIP es la opción más simple. | HU-P030 | Media antes de HU-P030 |
| DEC-A06 | **Esquema de tabla `llm_config`:** Confirmar o ajustar el esquema propuesto en HU-P029 Technical Notes | Esquema propuesto: `id, config_type (primary|fallback), provider, model, api_key_encrypted, cb_failure_threshold, cb_cooldown_seconds, updated_at, updated_by`. ¿Se acepta o hay ajustes? Impacta la migración Alembic. | HU-P029 | Media — no bloquea inicio de HU-P031 |
| DEC-A07 | **Librería de drag-and-drop para React:** `react-beautiful-dnd` vs `dnd-kit` | `dnd-kit`: más moderno, mejor soporte de accesibilidad, activamente mantenido. `react-beautiful-dnd`: más conocido, más ejemplos, pero mantenimiento reducido desde 2022. Requiere aprobación de @architect como nueva dependencia npm. | HU-P028 | Baja — HU-P028 es última prioridad |
| **DEC-A08** | **Arranque en frío — seed de defaults en Alembic:** Cuando la BD no tiene filas en `llm_config` ni en `platform_config`, la página HU-P032 arranca en blanco. ¿Cómo se gestiona? La migración Alembic que ya existe para `governance_thresholds` debe extenderse para sembrar defaults en `llm_config` y todos los keys de `platform_config` usados por HU-P032. ¿Se hace en una sola migración extendida o en migraciones separadas por tabla? ¿El seed se ejecuta siempre o solo si la tabla está vacía (idempotente)? | HU-P032 | **CRÍTICA antes de HU-P032** |
| **DEC-A09** | **Scope del puerto `IGovernanceProvider` post-HU-P032:** ¿Se amplía `IGovernanceProvider` para cubrir toda la config de negocio (una sola interfaz grande), o se crean puertos separados (`ILLMConfigProvider`, `IPlatformConfigProvider`, `IObservabilityConfigProvider`)? La arquitectura hexagonal sugiere separación de concerns. Ampliar `IGovernanceProvider` es más rápido pero viola la responsabilidad única. | HU-P032, HU-012 | **Alta — antes de HU-P032** |
| **DEC-A10** | **`storage_provider` en la UI de HU-P032:** ¿El toggle `memory/postgres` debe aparecer en la UI de configuración? Cambiar `storage_provider` a `memory` en producción es destructivo (pérdida de datos en reinicio). Opciones: (a) Mostrar con confirmación y advertencia prominente. (b) Ocultar completamente en la UI — dejarlo como bootstrap (`.env`). Recomendación del @product-analyst: opción (b) — `storage_provider` es config de instalación, no operacional. | HU-P032 | Media — no bloquea inicio |

---

### 10.2 HUs que impactan la arquitectura existente

| HU | Cambio específico requerido en la arquitectura | Riesgo |
|----|-----------------------------------------------|--------|
| **HU-P017** | Nuevo endpoint `GET /auth/google/callback?email={email}` en FastAPI. Nueva tabla `users` con migración Alembic. Generación de JWT HS256 con `python-jose` o equivalente. | Bajo — es additive |
| **HU-P018** | Migración de `X-API-Key` a `Authorization: Bearer JWT` en TODOS los endpoints existentes. Puede romper tests que usen la API key directamente. | **Alto** — afecta todos los endpoints de HU-001 a HU-016 |
| **HU-P029** | Refactor de `services/sre-agent/app/adapters/llm/circuit_breaker.py` para soportar hot reload. Cambios en `container.py` para invalidar y reinicializar el adapter LLM. Nueva tabla `llm_config` con migración Alembic. | **Alto** — modifica infraestructura central del agente |
| **HU-P030** | Nuevo adapter `GithubContextProvider` implementando `IContextProvider`. El container de DI necesita una factory que seleccione el adapter según `platform_config.context_source`. Volumen Docker para persistir el índice FAISS. | Medio — es additive (el adapter estático permanece) |
| **HU-P027** | Si se elige DEC-A01 opción (a): nuevo servicio `sre-web` en Docker Compose. `CORSMiddleware` en FastAPI. Si opción (b): build pipeline de React integrado al contenedor `sre-agent`. | **Alto** — impacta el modelo de despliegue completo |
| **HU-P021 (expandida)** | El endpoint `POST /config/ecommerce-repo/reindex` debe lanzar re-indexación en background (`asyncio.create_task` o `BackgroundTasks`). El endpoint `GET /config/ecommerce-repo/reindex/status` debe retornar el estado del job. | Medio — nuevo patrón de background tasks |
| **HU-P032 (nueva — v4.0)** | Requiere nuevos endpoints: `GET/PUT /config/observability`, `GET/PUT /config/security`, y potencialmente `GET/PUT /config/storage`. Todos los endpoints de configuración deben protegerse con `require_role("admin", "superadmin")` excepto Governance & Thresholds que admite `flow_configurator`. La migración Alembic de seed debe extenderse a `llm_config` y `platform_config`. El `pydantic-settings` `Settings` en `config.py` puede simplificarse post-implementación eliminando las variables migradas a BD. | **Alto** — modifica todas las capas: BD (seed), API (nuevos endpoints), frontend (página unificada), infraestructura (`.env` reducida) |

---

### 10.3 Nuevas HUs — complejidad, dependencias y orden de implementación

> Orden sugerido para maximizar impacto en demo del hackathon (deadline 2026-04-09 21:00 COT).

| Prioridad | HU | Título | Complejidad | Depende de | Puede empezar |
|-----------|-----|--------|-------------|-----------|---------------|
| 1 | **HU-P031** | Design System SoftServe (tokens + componentes base) | M | — | INMEDIATAMENTE |
| 2 | **HU-P030** | Integración eShopOnWeb — GithubContextProvider | L | — (backend puro) | En paralelo con HU-P031 |
| 3 | **HU-P017** | Mock Google Auth + JWT | M | — (backend puro) | En paralelo con HU-P031 |
| 4 | **HU-P027** | Shell React base (navegación, login, layout) | L | HU-P031, DEC-A01, DEC-A02 | Tras HU-P031 + decisiones de @architect |
| 5 | **HU-P018** | Middleware JWT y autorización FastAPI | M | HU-P017 | Tras HU-P017 |
| 6 | **HU-P029** | Config LLM + hot reload circuit breaker | M | HU-P017, HU-P018, HU-P027, DEC-A03, DEC-A04 | Tras Fase 1 completa |
| 7 | **HU-P019** | Gestión de usuarios CRUD | M | HU-P017, HU-P018, HU-P027 | Tras Fase 1 completa |
| 8 | **HU-P025** | Formulario de incidente en React | M | HU-P017, HU-P018, HU-P027 | Tras Fase 1 |
| 9 | **HU-P026** | Dashboard de incidentes + ticket status | L | HU-P025, HU-P027-EXTRA | Tras HU-P025 |
| 10 | **HU-P027-EXTRA** | Endpoint GET /incidents/{id}/status | S | HU-P018 | Puede ir en paralelo con HU-P025 |
| 11 | **HU-P021** (expandida) | Config repo eCommerce + botón re-indexar | M | HU-P017, HU-P018, HU-P027, HU-P030 | Tras HU-P030 |
| 12 | **HU-P020** | Config tipos de archivo | S | HU-P017, HU-P018, HU-P027 | Tras Fase 1 |
| 13 | **HU-P022** | Config sistema de tickets | M | HU-P017, HU-P018, HU-P027 | Tras Fase 1 |
| 14 | **HU-P023** | Config notificaciones | M | HU-P017, HU-P018, HU-P027 | Tras Fase 1 |
| 15 | **HU-P024** | Config y visualización de agentes SRE | L | HU-P017, HU-P018, HU-P027, HU-012 | Tras Fase 1 |
| 16 | **HU-P028** | Layout drag-and-drop | M | HU-P027, HU-P026 | Última prioridad |
| 6b | **HU-P032** | Centralized Configuration Page (UI unificada) | L | HU-P017, HU-P018, HU-P027, HU-P029 (backend), HU-P031 | Tras HU-P029 backend — absorbe UI de HU-P022, HU-P023, HU-P024 secciones correspondientes |

---

### 10.4 Estado de preguntas pendientes

| PQ | Pregunta | Estado |
|----|---------|--------|
| PQ-01 | ¿SPA React en contenedor separado o servido desde FastAPI? | **Pendiente — @architect** (DEC-A01) |
| PQ-02 | ¿JWT en `httpOnly` cookie o `localStorage`? | **Pendiente — @architect** (DEC-A02) |
| PQ-03 | ¿Drag-and-drop = solo widgets o constructor de flujos de agentes? | **Resuelta** — SA-001: solo widgets de dashboard. Constructor de flujos = v2 fuera de alcance. |
| PQ-04 | ¿`reporter_email` requerido? | **Resuelta** — SA-008: requerido. HU-001 y HU-008 a actualizar. |
| PQ-05 | ¿Credenciales de adaptadores encriptadas en BD? | **Resuelta** — SA-004: AES-256 via `CONFIG_ENCRYPTION_KEY`. |
| PQ-06 | ¿Libertad de diseño o seguir estilo actual? | **Resuelta** — SA-011 + HU-P031 v2: Tailwind + Design System SoftServe (`#454494`). |
| PQ-07 | ¿Esta expansión es para el hackathon o post-hackathon? | **Resuelta** — Todo entra al hackathon (deadline 2026-04-09 21:00 COT). |
| PQ-08 | ¿Circuit breaker hot reload o solo en startup? | **Resuelta** — Hot reload < 5s. Ver SA-012, HU-P029 v2. |
| PQ-09 | ¿Indexación eShop en startup o bajo demanda? | **Resuelta** — Startup. Ver SA-013, HU-P030 v2. |
| PQ-10 | ¿Brand Guide SoftServe disponible? | **Resuelta** — No disponible. Color primario corregido a `#454494`. Ver SA-014, HU-P031 v2. |

**Preguntas críticas pendientes para @architect antes de arrancar:** PQ-01 (DEC-A01) y PQ-02 (DEC-A02).
**Las demás decisiones técnicas** (DEC-A03 a DEC-A07) pueden resolverse en paralelo al arranque del desarrollo de HU-P031.

---

*Documento cerrado a v3.0 por @product-analyst el 2026-04-08.*

*Documento actualizado a v4.0 por @product-analyst el 2026-04-08. Se incorporan Requisitos D (Config-from-DB, HU-P032) y E (UI en inglés, SA-015). Se añaden DEC-A08, DEC-A09, DEC-A10. Total HUs plataforma: 17. HU-P031 actualizada a v3. HU-016 confirmada Supersedida por HU-P032. Scope HU-012 expandido.*
*Versión v1.0 generada el 2026-04-08. Versión v2.0: incorporación de Requisitos A, B, C. Versión v3.0: cierre de análisis — PQ-08, PQ-09, PQ-10 resueltas, Handoff a @architect añadido.*
