# Reporte de Auditoría de Seguridad — SRE Incident Triage Platform

**Fecha:** 2026-04-08
**Alcance:** Full SAST — backend (services/sre-agent) + frontend (services/sre-web)
**Estándares:** OWASP Top 10 (2021), OWASP API Security Top 10 (2023)
**Contexto:** Hackathon, demo pública 2026-04-09 21:00 COT
**Auditoría previa:** commit `b9c2725` — 8 remediaciones previas verificadas

---

## 1. Resumen Ejecutivo

**Veredicto: APTO PARA DEMO CON OBSERVACIONES.**

La plataforma presenta una postura de seguridad sólida para un contexto de hackathon. La arquitectura hexagonal, la separación de responsabilidades, el dual-auth JWT/API-Key, el RBAC mediante `require_role()`, la encriptación Fernet de credenciales en reposo, el input sanitizer con redacción de PII, el whitelist `_ALLOWED_UPDATE_FIELDS`, el uso uniforme de SQLAlchemy ORM (sin SQL dinámico), y la protección de campos `langfuse_*`/`storage_provider` (ARC-025) reflejan un nivel de madurez inusual para una demo.

**Hallazgos:** 0 Critical | 1 High | 4 Medium | 5 Low | 6 Info

Ningún hallazgo impide la demo.

---

## 2. Hallazgos por Severidad

### HIGH

#### VUL-H01 — Autenticación mock permite emisión arbitraria de JWTs
- **Severidad:** High | **OWASP:** A07 Auth Failures, API2
- **Archivo:** `services/sre-agent/app/api/routes_auth.py:75-91`
- **Descripción:** `POST /auth/mock-google-login` acepta cualquier email válido, auto-crea el usuario con rol `operator` y emite un JWT HS256 válido por 8 horas. Si un email con rol privilegiado ya existe en la DB (seeded), cualquiera que conozca ese email obtiene un token con ese rol.
- **Escenario:** Atacante hace `POST /auth/mock-google-login` con email de admin conocido → obtiene JWT de admin → accede a `PUT /config/llm` → exfiltra claves API del LLM.
- **Estado:** Riesgo aceptado para hackathon (DEC-A02, mock auth por diseño). Verificar que no existan usuarios seeded con rol ≥ admin y email adivinable.
- **Remediación post-hackathon:** Integrar Google OAuth2 real.

---

### MEDIUM

#### VUL-M01 — API key default `"sre-demo-key"` otorga SUPERADMIN sintético
- **Severidad:** Medium | **OWASP:** A05 Misconfig, A07
- **Archivo:** `app/infrastructure/config.py:85`; `app/api/deps.py:142-156`
- **Descripción:** `X-API-Key: sre-demo-key` (valor público en `.env.example`) devuelve un User sintético con `role=SUPERADMIN`. Sin validador que lo bloquee fuera de producción.
- **Escenario:** Si el contenedor se expone con el default, cualquier persona puede obtener acceso SUPERADMIN.
- **Remediación antes de demo:** Rotar `SRE_API_KEY` a un valor aleatorio en el `.env` del laptop de demo.

#### VUL-M02 — JWT_SECRET default solo rechazado en APP_ENV=production
- **Severidad:** Medium | **OWASP:** A02 Crypto Failures
- **Archivo:** `app/infrastructure/config.py:89, 116-120`
- **Descripción:** El secreto default `"sre-dev-jwt-secret-change-in-production"` es público en el repo. El validator solo bloquea si `app_env == "production"`. Con `APP_ENV=development`, un atacante puede forjar JWTs con cualquier rol.
- **Remediación antes de demo:** Generar JWT_SECRET aleatorio: `python -c "import secrets; print(secrets.token_hex(32))"` y colocarlo en el `.env` local. No requiere cambio de código.

#### VUL-M03 — IDOR en `GET /incidents/{id}` y `POST /incidents/{id}/resolve`
- **Severidad:** Medium | **OWASP:** API1 Broken Object Level Authz
- **Archivo:** `app/api/routes_incidents.py:129-175`
- **Descripción:** `list_incidents` filtra por `reporter_email` para rol OPERATOR (correcto), pero `get_incident` y `resolve_incident` no aplican el mismo filtro. Un operator puede leer/resolver cualquier incidente si conoce el UUID.
- **Remediación recomendada:** En `get_incident` y `resolve_incident`, si `current_user.role == UserRole.OPERATOR`, verificar `incident.reporter_email == current_user.email`, else 404.
- **Estado:** Recomendado fix antes de demo (≤10 líneas). Si no se aplica, riesgo aceptado sobre la premisa de que los IDs son UUID v4 no enumerables.

#### VUL-M04 — Webhook de resolución protegido con API key compartida (no HMAC)
- **Severidad:** Medium | **OWASP:** API8, A04 Insecure Design
- **Archivo:** `app/api/routes_webhooks.py:116-145`
- **Descripción:** El webhook acepta `X-API-Key`. En un modelo real, webhooks externos validan con HMAC de payload. Combinado con VUL-M01, un atacante puede marcar incidentes como resueltos.
- **Remediación post-hackathon:** Validar firma HMAC por provider. Para demo: mitigado si se rota `SRE_API_KEY`.

---

### LOW

| ID | Hallazgo | Estado |
|----|----------|--------|
| VUL-L01 | `docker-compose.yml` sin TLS | Aceptado — demo local |
| VUL-L02 | JWT en `localStorage` susceptible a XSS | Aceptado — DEC-A02 |
| VUL-L03 | `email` logueado sin redacción en `auth.mock_login` | Menor — considerar hash |
| VUL-L04 | `create_incident` no invoca `input_sanitizer` antes de persistir | Recomendado conectar |
| VUL-L05 | `allow_headers=["*"]` con `allow_credentials=True` en CORS | Aceptable con origins explícitos |

---

### INFORMATIONAL

| ID | Observación |
|----|-------------|
| INFO-01 | Langfuse keys `pk-lf-demo`/`sk-lf-demo` en `.env.example` — ARC-025 los mantiene bootstrap-only |
| INFO-02 | `JWTAdapter.verify_token` no valida `iss`/`aud` — aceptable para HS256 single-tenant mock |
| INFO-03 | `jwt_expire_minutes=480` (8h) — amplio; producción debería usar 15 min + refresh |
| INFO-04 | `POST /auth/logout` es no-op server-side — conocido por diseño JWT stateless |
| INFO-05 | `contains_credentials()` existe en sanitizer pero no es hard-block en el endpoint HTTP |
| INFO-06 | `GET /context/status` (público) devuelve `repo_url`, `index_path` — fingerprinting leve aceptable |

---

## 3. Cobertura OWASP

| Categoría | Estado | Hallazgos |
|-----------|--------|-----------|
| A01 Broken Access Control | Parcial | VUL-M03, VUL-M04 |
| A02 Cryptographic Failures | Parcial | VUL-M02 (JWT secret), VUL-L01 (TLS) |
| A03 Injection | Mitigado | SQLAlchemy ORM, Pydantic, sanitizer, prompt injection guard |
| A04 Insecure Design | Parcial | VUL-H01 (mock auth by design), VUL-M04 |
| A05 Security Misconfig | Parcial | VUL-M01 (API key default), VUL-L05 (CORS) |
| A06 Vulnerable Components | Sin hallazgos | — |
| A07 Auth Failures | Parcial | VUL-H01, VUL-M01, VUL-M02 |
| A08 Integrity Failures | Mitigado | Audit log ARC-026, campos forbidden ARC-025 |
| A09 Logging/Monitoring | Parcial | VUL-L03 (PII en logs) |
| A10 SSRF | Mitigado | Webhook no dereferencia URLs del payload |
| API1 BOLA | Parcial | VUL-M03 |
| API2 Broken Auth | Parcial | VUL-H01 |
| API3 BOPLA | Mitigado | `_mask_credentials`, Pydantic response models |
| API4 Unrestricted Resource | Mitigado | `_read_limited`, 413 |
| API5 BFLA | Mitigado | `require_role()` uniforme |
| API8 Misconfig | Parcial | VUL-M01, VUL-L05 |

---

## 4. Riesgos Aceptados

| ID | Riesgo | Justificación |
|----|--------|---------------|
| DEC-A02 | JWT en `localStorage` (XSS) | Demo hackathon, no producción |
| Mock auth | `/auth/mock-google-login` sin verificación | Sustituye Google OAuth real, explícito en README |
| No TLS | `docker-compose` sin HTTPS | Demo local, no pública en internet |
| API Key default en `.env.example` | Backward compat CI/scripts | Debe rotarse antes de exponer el servicio |

---

## 5. Controles de Seguridad Bien Implementados

1. **SQLAlchemy ORM uniforme** — sin `execute(text(...))` con concatenación; inmune a SQLi.
2. **`_ALLOWED_UPDATE_FIELDS` whitelist** — previene mass-assignment en updates.
3. **ARC-025 — Raw JSON parsing antes de Pydantic** en `update_observability_config` — captura campos forbidden que Pydantic ignoraría silenciosamente.
4. **ARC-026 — Audit log transaccional** — garantía de consistencia en config updates.
5. **Fernet encryption de credenciales** con validación de `InvalidToken`.
6. **`_read_limited`** — protección DoS real contra uploads.
7. **`_mask_credentials`** + Pydantic response model — doble barrera contra leak.
8. **`require_role()`** como factory — RBAC enforcement consistente.
9. **Three-layer prompt injection defense** — sanitize → heuristic → LLM judge.
10. **`_reject_stub_in_production`** — rechaza misconfiguraciones en producción.

---

## 6. Acciones Antes de la Demo

### Críticas (obligatorias)
1. **Rotar `JWT_SECRET`** en el `.env` local: `python -c "import secrets; print(secrets.token_hex(32))"`
2. **Rotar `SRE_API_KEY`** a un valor aleatorio en el `.env` local
3. **Verificar usuarios seeded** — ningún usuario con rol `admin`/`superadmin` debe tener email adivinable

### Recomendadas (≤30 min)
4. Agregar filtro IDOR en `get_incident` y `resolve_incident` para rol OPERATOR (VUL-M03)
5. Conectar `input_sanitizer.sanitize()` en `create_incident` antes de `save_incident` (VUL-L04)

### Post-hackathon
- Google OAuth2 real, httpOnly cookies, HMAC webhooks, TLS, rotación de JWT, validar `iss`/`aud`

---

## 7. Veredicto Final

```
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   APTO PARA DEMO CON OBSERVACIONES                       ║
║                                                          ║
║   Con las 3 acciones críticas de configuración           ║
║   (rotar JWT_SECRET, rotar SRE_API_KEY, verificar        ║
║   usuarios seeded), la plataforma es segura para         ║
║   demostrar bajo el modelo de amenazas declarado.        ║
║                                                          ║
║   Los controles implementados reflejan un nivel de       ║
║   ingeniería de seguridad superior al típico en          ║
║   un hackathon.                                          ║
║                                                          ║
║   App Security Analyst — 2026-04-08                      ║
╚══════════════════════════════════════════════════════════╝
```
