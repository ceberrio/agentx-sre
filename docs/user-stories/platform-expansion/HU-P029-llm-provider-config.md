# HU-P029 — Configuración del Proveedor LLM y Circuit Breaker

**Module:** Config Platform
**Epic:** EPIC-006 — Configuration Platform
**Priority:** High
**Status:** Approved
**Version:** v2
**Last updated:** 2026-04-08

---

## User Story

**Como** administrador de la plataforma SRE
**Quiero** configurar el proveedor LLM, el modelo, la API key, el proveedor de fallback y los parámetros del circuit breaker desde la interfaz de configuración
**Para** cambiar el backbone de inteligencia del agente sin modificar variables de entorno ni redesplegar el sistema

---

## Acceptance Criteria

| ID | Criterio | Condición |
|----|---------|-----------|
| AC-01 | Listar config LLM actual | **Given** un usuario con rol `admin` o `superadmin` autenticado, **When** hace `GET /config/llm`, **Then** recibe HTTP 200 con objeto `{"provider": "gemini", "model": "gemini-2.0-flash", "api_key_masked": "***...ABC", "fallback_provider": "openrouter", "fallback_model": "...", "cb_failure_threshold": 5, "cb_cooldown_seconds": 60}` |
| AC-02 | Actualizar config LLM | **Given** un usuario con rol `admin` o `superadmin`, **When** hace `PUT /config/llm` con payload válido, **Then** la config se persiste en tabla `llm_config` y retorna HTTP 200 con la config actualizada (API key enmascarada) |
| AC-12 | Hot reload — cambio efectivo en < 5 segundos sin reinicio | **Given** un admin guarda una nueva config LLM via `PUT /config/llm`, **When** la operación retorna HTTP 200, **Then** el agente de triage usa el nuevo proveedor/modelo en el siguiente request procesado, con un tiempo de propagación máximo de 5 segundos desde el guardado — sin necesidad de reiniciar el container. El mecanismo de hot reload invalida el cache de governance e reinicializa el adapter LLM en `container.py`. |
| AC-13 | El circuit breaker adopta la nueva config en caliente | **Given** la config del circuit breaker (`cb_failure_threshold`, `cb_cooldown_seconds`) se actualiza via `PUT /config/llm`, **When** el operador guarda los cambios, **Then** el circuit breaker activo comienza a usar los nuevos parámetros en el siguiente ciclo de evaluación — sin restart. Si el circuit breaker está en estado `OPEN` al momento del cambio, continúa en `OPEN` hasta que expire el cooldown anterior, luego usa el nuevo cooldown para los estados subsiguientes. |
| AC-03 | Selector de proveedor con modelos predefinidos | **Given** el formulario de config LLM está abierto, **When** el usuario selecciona un proveedor, **Then** el selector de modelo se actualiza automáticamente con la lista de modelos predefinida para ese proveedor: Gemini → `[gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash]`; OpenRouter → `[openai/gpt-4o, anthropic/claude-3-5-sonnet, meta-llama/llama-3.3-70b-instruct]`; Anthropic → `[claude-3-5-sonnet-20241022, claude-3-haiku-20240307]`; OpenAI → `[gpt-4o, gpt-4o-mini, gpt-4-turbo]` |
| AC-04 | Campo API key enmascarado | **Given** el formulario de config LLM, **When** el usuario ve la API key existente, **Then** se muestra `***...{últimos 4 caracteres}`. El campo de edición es de tipo `password`. Existe un botón "Mostrar" solo para admins que revela el valor por 5 segundos. |
| AC-05 | Test de conexión del proveedor principal | **Given** el usuario completa la config del proveedor principal y hace clic en "Probar conexión", **When** el backend ejecuta una llamada de prueba mínima al LLM configurado (ej: prompt "Responde solo: ok"), **Then** la UI muestra "Conexión exitosa — latencia: Xms" en verde o "Error: [mensaje del proveedor]" en rojo |
| AC-06 | Configuración del proveedor de fallback | **Given** el formulario de config LLM, **When** el usuario activa "Habilitar fallback", **Then** aparece un segundo bloque de config idéntico (proveedor, modelo, API key) para el fallback. El fallback puede desactivarse dejando el campo vacío. |
| AC-07 | Parámetros del circuit breaker | **Given** la sección de circuit breaker en el formulario, **When** el usuario ingresa `cb_failure_threshold` (entero 1-20, default 5) y `cb_cooldown_seconds` (entero 10-3600, default 60), **Then** estos valores se persisten en `llm_config` y son validados en rango en el backend antes de guardar |
| AC-08 | Restricción de roles | **Given** un usuario con rol distinto de `admin` o `superadmin`, **When** intenta acceder a `GET /config/llm` o `PUT /config/llm`, **Then** recibe HTTP 403 |
| AC-09 | Persistencia en tabla `llm_config` | **Given** una configuración guardada, **When** el servicio FastAPI se reinicia, **Then** el agente carga la config LLM desde `llm_config` (con prioridad sobre variables de entorno). Si la tabla no tiene registros, usa las env vars como fallback. |
| AC-10 | API key encriptada en BD | **Given** una API key guardada, **When** se consulta la tabla `llm_config` directamente en PostgreSQL, **Then** el campo `api_key` está encriptado (AES-256 via `CONFIG_ENCRYPTION_KEY` en env var). No se almacena en texto plano. |
| AC-11 | Log de auditoría al cambiar config | **Given** un admin guarda cambios en la config LLM, **When** la operación es exitosa, **Then** se genera un registro de auditoría con: usuario, timestamp, campos cambiados, proveedor anterior y nuevo (sin API keys en el log). |

---

## Business Rules

| ID | Regla |
|----|-------|
| BR-01 | Solo roles `superadmin` y `admin` pueden leer o modificar la configuración LLM. |
| BR-02 | Las API keys se almacenan encriptadas con AES-256. La clave de encriptación (`CONFIG_ENCRYPTION_KEY`) debe estar en variables de entorno, nunca en código ni en BD. |
| BR-03 | La tabla `llm_config` tiene exactamente 1 fila activa para el proveedor principal y 1 para el fallback. No hay historial de versiones (se sobreescribe en cada PUT). El log de auditoría es el registro histórico. |
| BR-04 | El proveedor activo en `llm_config` tiene prioridad sobre las variables de entorno `LLM_PROVIDER` y `LLM_MODEL`. Si `llm_config` no tiene registros, las env vars son el fallback. |
| BR-05 | Los parámetros del circuit breaker (`cb_failure_threshold`, `cb_cooldown_seconds`) se aplican en caliente (hot reload) sin reinicio del container. El mecanismo de propagación es: al guardar `PUT /config/llm`, el backend invalida el cache de configuración activo y reinicializa el adapter LLM en `container.py`. El @architect diseña el mecanismo exacto de invalidación (posiblemente evento interno o polling de cache con TTL corto). El cambio debe ser observable en el siguiente request, con propagación máxima de 5 segundos. |
| BR-08 | La transición de proveedor LLM en caliente es atómica: o la nueva config queda activa completamente, o permanece la anterior. No se admiten estados intermedios donde algunos requests usen el proveedor nuevo y otros el anterior durante la misma ventana de propagación. |
| BR-06 | El campo `model` debe ser uno de los valores predefinidos por proveedor. No se aceptan modelos arbitrarios (previene errores de config). |
| BR-07 | La operación de "Probar conexión" NO cuenta como un fallo para el circuit breaker. Es una llamada de diagnóstico independiente. |

---

## Edge Cases

| Escenario | Comportamiento esperado |
|----------|------------------------|
| La API key del proveedor principal es inválida y el admin hace "Probar conexión" | La UI muestra el error del proveedor (ej: "401 Unauthorized — invalid API key") sin exponer el stack trace |
| El admin guarda una config LLM con modelo inválido para el proveedor | El backend retorna HTTP 422 con mensaje "Modelo {model} no válido para proveedor {provider}. Modelos permitidos: [...]" |
| Se guarda config LLM y hay un incidente en progreso en ese momento | El incidente en progreso usa la config anterior hasta que el LangGraph pipeline complete (el pipeline es atómico). El nuevo config se aplica al siguiente request una vez que el hot reload propague los cambios (máximo 5 segundos). |
| El hot reload falla porque `container.py` no puede reinicializarse | El sistema mantiene la config anterior activa, loguea error `LLM_RELOAD_FAILED` con causa, y retorna HTTP 200 al admin con un warning en el body: `{"status": "saved", "warning": "Hot reload failed — config saved but active provider unchanged. Manual restart may be required."}`. |
| `CONFIG_ENCRYPTION_KEY` no está definida en env | El servicio rechaza arrancar y loguea un error crítico. No se permite almacenar config LLM sin encriptación. |
| El admin desactiva el fallback (deja campos vacíos) y el proveedor principal falla | El circuit breaker actúa y el sistema retorna error degradado (misma lógica de hoy). Se muestra alerta en el dashboard de estado del agente. |
| `cb_failure_threshold` = 1 | El circuit breaker se abre tras el primer fallo. Comportamiento válido, el sistema debe aceptarlo aunque sea muy agresivo. |
| El admin intenta guardar `cb_cooldown_seconds` = 0 | El backend retorna HTTP 422: "El cooldown debe ser al menos 10 segundos". |

---

## Design Reference

| Pantalla / Componente | Referencia | Notas |
|----------------------|-----------|-------|
| Sección "Config LLM" en Config Platform | Pendiente — consistente con HU-P031 (Design System SoftServe) | El formulario sigue el mismo patrón visual de HU-P022 y HU-P023 (config de adaptadores) |
| Selector de proveedor + modelo en cascada | — | Dropdown de proveedor → actualiza opciones de modelo automáticamente (sin reload) |
| Campo API key con máscara y botón revelar | — | Mismo patrón que HU-P021 (credenciales de ecommerce repo) |

*(Sin diseño Figma disponible. Seguir Design System SoftServe de HU-P031.)*

---

## Dependencies

| HU | Tipo de dependencia |
|----|-------------------|
| HU-P017 | Debe completarse antes — provee el mecanismo JWT |
| HU-P018 | Debe completarse antes — provee la autorización de roles |
| HU-P027 | Debe completarse antes — provee el shell React donde se renderiza este módulo |
| HU-P031 | Debe completarse antes — provee los tokens de diseño |
| HU-012 | Referencia — la config LLM NO usa `governance_thresholds`, usa tabla separada `llm_config` |

---

## Technical Notes

- La tabla `llm_config` debe crearse con una migración Alembic. Columnas sugeridas: `id` (PK), `config_type` (enum: `primary`, `fallback`), `provider` (string), `model` (string), `api_key_encrypted` (text), `cb_failure_threshold` (int), `cb_cooldown_seconds` (int), `updated_at` (timestamp), `updated_by` (FK users). El @architect valida este esquema.
- La lista de modelos por proveedor se define como constante en el backend (no en BD), para evitar que un cambio de configuración permita modelos no soportados. Si en el futuro se quiere hacer dinámica, se puede agregar una tabla `llm_supported_models`.
- El circuit breaker existente en `services/sre-agent/app/adapters/llm/circuit_breaker.py` debe ser refactorizado para soportar hot reload. El @architect debe diseñar el mecanismo de recarga: las opciones principales son (a) invalidar una referencia compartida al objeto `CircuitBreaker` en el contenedor de DI y crear una nueva instancia con los nuevos parámetros, o (b) exponer un método `circuit_breaker.reconfigure(threshold, cooldown)` que actualiza los parámetros del breaker activo sin perder su estado de conteo. La opción (b) es preferida para no perder el historial de fallos acumulado durante la transición.
- El mecanismo de hot reload para el provider LLM se centra en `container.py`: al detectar un cambio en `llm_config`, se reconstruye el adapter LLM (o se le inyectan los nuevos parámetros) sin reiniciar el proceso FastAPI completo. Esto puede implementarse con un event bus interno simple (ej: un `asyncio.Event` que el `PUT /config/llm` dispara y que `container.py` escucha) o con un cache con TTL de 5 segundos que se invalida al guardar.
- El endpoint `GET /config/llm` NUNCA retorna la API key en texto plano. Solo retorna `api_key_masked` con los últimos 4 caracteres visibles.

---

## Pending Questions

| # | Pregunta | Dirigida a | Estado |
|---|---------|-----------|--------|
| 1 | (PQ-08) ¿El circuit breaker debe leer su config de `llm_config` en runtime o solo al arrancar? | @architect | **RESUELTA** — Hot reload requerido. Ver AC-12, AC-13, BR-05, BR-08 y Technical Notes. |
| 2 | ¿La tabla `llm_config` tiene el esquema correcto propuesto en Technical Notes, o @architect prefiere un diseño diferente? | @architect | Pendiente — decisión de esquema. No bloquea desarrollo (el esquema propuesto es suficientemente sólido para empezar). |

---

## Change History

| Version | Fecha | Cambio | Motivo |
|---------|-------|--------|--------|
| v1 | 2026-04-08 | Creación inicial | Requisito A del cliente — config LLM en plataforma |
| v2 | 2026-04-08 | PQ-08 RESUELTA: hot reload requerido. Se añaden AC-12, AC-13, BR-08. Se actualizan BR-05 y Technical Notes con mecanismo de hot reload. Se marcan 0 preguntas críticas pendientes. Estado cambia a Approved. | Respuesta del cliente: cambios de proveedor LLM desde UI deben aplicar en < 5 segundos sin reiniciar el container. |
