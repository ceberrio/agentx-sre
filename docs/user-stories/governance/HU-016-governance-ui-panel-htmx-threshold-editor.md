# HU-016 — Panel UI de Governance: Editor HTMX de Umbrales en Vivo

**Module:** Governance
**Epic:** EPIC-004 — Governance & Explainability
**Priority:** Medium
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-08

---

## User Story

**Como** operador SRE con acceso al panel de administracion del agente
**Quiero** una pagina web donde pueda ver y editar los umbrales de gobernanza del agente en tiempo real sin acceder a la base de datos ni redesplegar
**Para** poder responder rapidamente ante situaciones operativas (por ejemplo, activar el kill switch durante un incidente mayor o ajustar el umbral de confianza)

---

## Acceptance Criteria

> Cada AC es verificable de forma independiente.

| ID | Criterio | Condicion |
|----|----------|-----------|
| AC-01 | `GET /governance/` renderiza pagina HTML con valores actuales | Dado que el servicio esta corriendo, cuando se hace `GET /governance/`, entonces retorna HTTP 200 con el template `governance.html` renderizado con los valores actuales de `GovernanceThresholds` pre-rellenados en los inputs |
| AC-02 | Cada umbral tiene su propio formulario HTMX inline | Dado que se renderiza `governance.html`, entonces cada uno de los 5 campos tiene un form separado con `hx-put="/governance/thresholds"` y `hx-swap` que actualiza solo el valor mostrado al recibir la respuesta |
| AC-03 | `kill_switch_enabled` se renderiza como toggle switch | Dado que `governance.html` esta abierto, entonces el campo `kill_switch_enabled` aparece como un toggle switch (checkbox estilizado); cuando esta `True`, la pagina muestra un banner rojo prominente con texto "KILL SWITCH ACTIVADO — Todos los incidentes seran escalados manualmente" |
| AC-04 | Kill switch tiene modal de confirmacion | Dado que el kill switch esta en `False` y el operador lo activa, cuando hace click en el toggle, entonces aparece un dialogo de confirmacion antes de enviar el PUT; el dialogo puede cancelarse sin efectuar cambios |
| AC-05 | Inputs de confianza validados client-side | Dado que `confidence_escalation_min` y `quality_score_min_for_autoticket` son inputs numericos, entonces tienen atributos HTML `min="0" max="1" step="0.01"`; el browser bloquea envio si el valor esta fuera de rango |
| AC-06 | `severity_autoticket_threshold` es dropdown | Dado que se renderiza el campo `severity_autoticket_threshold`, entonces aparece como un elemento `<select>` con opciones `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` y el valor actual pre-seleccionado |
| AC-07 | Actualizacion exitosa muestra nuevo valor inline | Dado que se hace PUT valido via HTMX, cuando el servidor retorna HTTP 200 con el threshold actualizado, entonces el valor mostrado en la UI se actualiza inline sin recarga completa de la pagina |
| AC-08 | Error de validacion mostrado inline | Dado que se hace PUT con valor invalido (e.g., `confidence = 1.5`), cuando el servidor retorna HTTP 422, entonces el mensaje de error aparece inline junto al input correspondiente sin recargar la pagina |
| AC-09 | Boton "Restablecer a valores por defecto" | Dado que se hace click en "Restablecer a valores por defecto", cuando el usuario confirma el dialogo de confirmacion, entonces se hace PUT de los 5 campos con sus valores seed originales y la pagina se actualiza con los defaults |
| AC-10 | Governance enlazada desde navegacion principal | Dado que el usuario esta en cualquier pagina de la aplicacion, cuando ve la barra de navegacion, entonces existe un enlace visible a "Governance" que lleva a `GET /governance/` |
| AC-11 | `last_updated` y `updated_by` visibles por campo | Dado que un campo fue actualizado previamente, entonces junto al valor se muestra la ultima actualizacion con timestamp UTC y el `updated_by` correspondiente |
| AC-12 | `GET /governance/thresholds` (JSON) disponible separado del HTML | Dado que se hace `GET /governance/thresholds`, entonces retorna el JSON de `GovernanceThresholds`; este endpoint es el mismo que usan los tests y otros clientes; es independiente del endpoint HTML |
| AC-13 | Sin autenticacion en hackathon con aviso visible | Dado que cualquier usuario accede a `GET /governance/`, entonces no se requiere autenticacion; la pagina muestra un aviso visible indicando que en produccion se debe agregar autenticacion |

---

## Business Rules

| ID | Regla |
|----|-------|
| BR-01 | Los cambios via UI van al mismo endpoint `PUT /governance/thresholds` definido en HU-012; la UI no tiene acceso directo a BD. |
| BR-02 | El kill switch requiere confirmacion explicita del operador antes del envio (modal de confirmacion). |
| BR-03 | "Restablecer a valores por defecto" tambien requiere confirmacion explicita. |
| BR-04 | La pagina usa HTMX + Tailwind CDN (mismo stack que el resto de la UI); no se agregan nuevas dependencias de JS. |
| BR-05 | No se requiere autenticacion para el hackathon; esto DEBE estar documentado en la UI con un aviso visible al operador. |
| BR-06 | El template `governance.html` vive en `app/ui/templates/`; el route handler en `app/api/routes_governance.py`. |

---

## Edge Cases

| Escenario | Comportamiento esperado |
|-----------|------------------------|
| BD no disponible al cargar la pagina | Se muestran los valores por defecto de `GovernanceThresholds` con un banner amarillo "Usando valores por defecto — BD no disponible" |
| PUT falla por BD no disponible | HTMX muestra inline: "Error al guardar. Intenta nuevamente." — no se pierde el valor actual mostrado |
| Dos operadores editan el mismo campo simultaneamente | Ultimo PUT gana (last-write-wins). La UI del primer operador muestra el valor que envio; si recarga ve el del segundo |
| Kill switch ya esta activo al cargar la pagina | El banner rojo aparece inmediatamente al renderizar; no hay interaccion necesaria del usuario para activarlo |
| `max_rag_docs_to_expose` con valor 0 o negativo | Validacion server-side retorna 422; client-side el input tiene `min="1"` |
| Navegador sin soporte HTMX (JS deshabilitado) | Los forms hacen submit tradicional con recarga completa; funcionalidad preservada, experiencia degradada |

---

## Design Reference

| Pantalla / Componente | Referencia | Notas |
|----------------------|-----------|-------|
| Template HTML | `app/ui/templates/governance.html` | Jinja2 + HTMX + Tailwind CDN |
| Navegacion principal | Template base existente de la app | Agregar enlace "Governance" en el nav |
| Banner kill switch | Div rojo fijo en la parte superior de la pagina | Solo visible cuando `kill_switch_enabled=True` |
| Toggle switch CSS | Tailwind + CSS custom (no libreria extra) | |

---

## Dependencies

| HU | Tipo de dependencia |
|----|-------------------|
| HU-012 | Debe completarse antes — esta HU consume los endpoints `GET /governance/thresholds` y `PUT /governance/thresholds` creados en HU-012; sin ellos la UI no puede funcionar |

---

## Out of Scope

- Autenticacion o control de acceso al panel de governance (limitacion documentada para post-hackathon).
- Historico de cambios de umbrales / audit trail UI (la tabla tiene `updated_at` y `updated_by` pero no hay UI de historial).
- Notificaciones push cuando otro operador cambia un umbral.
- Exportar/importar configuracion de umbrales como JSON.

---

## Technical Notes

- El route `GET /governance/` retorna HTML (Jinja2 render); `GET /governance/thresholds` retorna JSON. Ambos viven en `routes_governance.py` con rutas distintas.
- Para el toggle kill switch: el estado actual se inyecta como variable Jinja2 `{{ thresholds.kill_switch_enabled }}` en el template.
- El modal de confirmacion del kill switch puede implementarse con un `<dialog>` HTML nativo (no requiere libreria JS).
- El boton "Restablecer a valores por defecto" puede implementarse como un HTMX form que hace PUT batch con los 5 defaults en un solo request: `{"updates": [{"key": "confidence_escalation_min", "value": "0.60"}, ...]}`.

---

## Pending Questions

Ninguna — contratos y estructura definidos en ARCHITECTURE.md §4.11.

---

## Change History

| Version | Fecha | Cambio | Razon |
|---------|-------|--------|-------|
| v1 | 2026-04-08 | Creacion inicial | Arquitectura v3 — EPIC-004 |
