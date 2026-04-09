# HU-P031 — Design System SoftServe — Tokens de Diseño y Componentes Base React

**Module:** Platform Shell React
**Epic:** EPIC-008 — Platform Shell
**Priority:** High
**Status:** Approved
**Version:** v3
**Last updated:** 2026-04-08

---

## User Story

**Como** desarrollador frontend que implementa la plataforma SRE
**Quiero** tener definidos y disponibles los tokens de diseño de la imagen corporativa SoftServe en el proyecto React
**Para** que todos los componentes de la plataforma sean visualmente consistentes con la marca SoftServe desde el primer componente implementado

> **Nota crítica:** Esta HU es bloqueante para todas las HUs de capa React (HU-P027, HU-P025, HU-P026, HU-P020 a HU-P024, HU-P028, HU-P029). Debe ser la primera HU implementada en la capa frontend.

---

## Identidad Visual SoftServe Documentada

> **AVISO DE VERSIÓN v2 — Corrección de color primario:**
> En v1, el color primario se documentó como `#E3001B` (rojo), inferido de observación superficial de materiales SoftServe. La búsqueda web de v2 (2026-04-08) consultó Brandfetch (`https://brandfetch.com/softserveinc.com`) y logo.com (`https://logo.com/brand/softserve-29i16g/colors`), que son fuentes de extracción automatizada del branding real del sitio. Ambas fuentes reportan el color primario del logo SoftServe como **#454494** (violeta-azul corporativo), no rojo. Este es el valor corregido. Todos los tokens de esta sección reflejan la versión actualizada.
> Si el cliente provee un Brand Guide oficial, esos valores tienen prioridad sobre los documentados aquí. Ver estado de PQ-10 al final de este documento.

### Fuentes consultadas para inferir los tokens

| Fuente | URL | Tipo |
|--------|-----|------|
| Brandfetch — SoftServe brand assets | `https://brandfetch.com/softserveinc.com` | Extracción automatizada del branding real del sitio web |
| logo.com — SoftServe brand colors | `https://logo.com/brand/softserve-29i16g/colors` | Paleta de colores reportada del logo oficial |
| logo.com — SoftServe brand guidelines | `https://logo.com/brand/softserve-29i16g` | Guidelines públicas inferidas |
| SoftServe Press Kit | `https://www.softserveinc.com/en-us/press-kit` | Fuente oficial de assets de marca |
| Wikimedia Commons — SoftServe logo 2017 | `https://commons.wikimedia.org/wiki/File:SoftServe_logo_2017.svg` | SVG oficial del logo |
| seeklogo.com — SoftServe SVG | `https://seeklogo.com/vector-logo/437236/softserve` | Vector del logo en uso |
| Google Fonts — Montserrat | `https://fonts.google.com/specimen/Montserrat` | Tipografía principal (uso verificado en materiales públicos de SoftServe) |

### Paleta de Colores

> **Todos los valores marcados como "inferido" deben ser validados contra el Brand Guide oficial si el cliente lo provee.**

| Token | Valor HEX | Fuente | Uso |
|-------|----------|--------|-----|
| `--color-primary` | `#454494` | Brandfetch + logo.com (color primario del logo SoftServe) — **inferido** | Violeta-azul SoftServe — botones primarios, acciones principales, acentos de navegación |
| `--color-primary-dark` | `#333278` | Derivado de `#454494` oscurecido ~15% — **inferido** | Hover y estados activos del color primario |
| `--color-primary-light` | `#5D5CB0` | Derivado de `#454494` aclarado ~15% — **inferido** | Focus rings, highlights, variante accesible |
| `--color-secondary` | `#FFFFFF` | Estándar de marca corporativa — confirmado en materiales públicos | Fondo de paneles, texto sobre fondo oscuro |
| `--color-neutral-900` | `#1A1A1A` | Estándar para texto principal en marcas corporativas — **inferido** | Texto principal, sidebar oscuro |
| `--color-neutral-700` | `#444444` | Estándar — **inferido** | Texto secundario, labels |
| `--color-neutral-400` | `#9A9A9A` | Estándar — **inferido** | Texto disabled, placeholders |
| `--color-neutral-100` | `#F5F5F5` | Inferido de la web oficial softserveinc.com — **inferido** | Fondo de página, backgrounds de cards |
| `--color-neutral-50` | `#FAFAFA` | Estándar — **inferido** | Alternativa de fondo muy claro |
| `--color-success` | `#28A745` | Semántico estándar, no específico de SoftServe | Estados de éxito, badges "OK", conexión exitosa |
| `--color-warning` | `#FFC107` | Semántico estándar | Estados de advertencia, badges "Warning" |
| `--color-error` | `#DC3545` | Semántico estándar | Estados de error (diferente del primario SoftServe) |
| `--color-info` | `#17A2B8` | Semántico estándar | Información, tooltips, badges informativos |

### Tipografía

| Token | Valor | Uso |
|-------|-------|-----|
| `--font-family-primary` | `'Montserrat', 'Inter', sans-serif` | Títulos, headers, navigation labels |
| `--font-family-body` | `'Inter', 'Open Sans', sans-serif` | Cuerpo de texto, formularios, tablas |
| `--font-family-mono` | `'JetBrains Mono', 'Fira Code', monospace` | Código, prompts de agentes, syntax highlighting |
| `--font-size-xs` | `12px` | Labels pequeños, metadata |
| `--font-size-sm` | `14px` | Texto de tabla, labels de formulario |
| `--font-size-base` | `16px` | Texto de párrafo estándar |
| `--font-size-lg` | `18px` | Texto destacado, subtítulos de sección |
| `--font-size-xl` | `24px` | Títulos de página, headings principales |
| `--font-size-2xl` | `32px` | Hero text, nombre de la plataforma |
| `--font-weight-normal` | `400` | Texto corrido |
| `--font-weight-medium` | `500` | Labels, navegación |
| `--font-weight-semibold` | `600` | Subtítulos, énfasis |
| `--font-weight-bold` | `700` | Títulos de página, badges |

### Espaciado y Layout

| Token | Valor | Uso |
|-------|-------|-----|
| `--spacing-1` | `4px` | Espaciado mínimo |
| `--spacing-2` | `8px` | Padding interno de elementos pequeños |
| `--spacing-3` | `12px` | Gap entre elementos relacionados |
| `--spacing-4` | `16px` | Padding estándar de cards y secciones |
| `--spacing-6` | `24px` | Separación entre secciones |
| `--spacing-8` | `32px` | Márgenes de página |
| `--border-radius-sm` | `4px` | Botones, inputs, badges |
| `--border-radius-md` | `8px` | Cards, paneles, modales |
| `--border-radius-lg` | `12px` | Paneles grandes, sidebars |
| `--border-radius-full` | `9999px` | Avatars, chips de rol |
| `--shadow-sm` | `0 1px 3px rgba(0,0,0,0.1)` | Cards en reposo |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.15)` | Cards en hover, dropdowns |
| `--shadow-lg` | `0 8px 24px rgba(0,0,0,0.2)` | Modales, paneles elevados |

---

## Acceptance Criteria

| ID | Criterio | Condición |
|----|---------|-----------|
| AC-01 | Custom theme en Tailwind con tokens corregidos | **Given** el proyecto React tiene Tailwind CSS instalado, **When** `@developer` implementa HU-P031, **Then** `tailwind.config.js` contiene un bloque `theme.extend` con todos los tokens de color, tipografía y espaciado documentados en esta HU (v2). El color primario es `#454494` (violeta-azul SoftServe). Los tokens son accesibles via clases Tailwind como `bg-softserve-primary`, `text-softserve-900`, `font-montserrat`. |
| AC-02 | Variables CSS globales | **Given** la app React está corriendo, **When** se inspecciona el `:root` del CSS, **Then** todas las variables CSS (`--color-primary`, `--font-family-primary`, etc.) están definidas en `src/styles/tokens.css` o equivalente. |
| AC-03 | Fuentes disponibles | **Given** la app carga en el navegador, **When** se renderiza cualquier texto, **Then** Montserrat e Inter están cargadas (via Google Fonts CDN o import local). Si la red es lenta, el fallback es `sans-serif` del sistema. |
| AC-04 | Logo SoftServe en el header | **Given** cualquier pantalla de la plataforma que muestre el header (post-login), **When** el usuario ve la pantalla, **Then** el logo SoftServe aparece en la esquina superior izquierda del sidebar/header. El logo es un SVG o PNG en `public/assets/softserve-logo.svg`. Si el cliente no provee el logo, se usa el wordmark "SoftServe" en Montserrat Bold color `#454494` como placeholder (violeta-azul corporativo confirmado — no rojo). |
| AC-05 | Logo SoftServe en pantalla de login | **Given** el usuario no está autenticado y ve la pantalla de login, **When** la pantalla carga, **Then** el logo SoftServe aparece prominentemente en la parte superior del formulario de login. |
| AC-06 | Componente `Button` base | **Given** se necesita un botón en la UI, **When** el desarrollador usa `<Button variant="primary">`, `<Button variant="secondary">`, o `<Button variant="danger">`, **Then** cada variante aplica automáticamente los colores correctos del Design System (primary = `#454494` fondo, texto blanco; secondary = borde `#454494` fondo transparente, texto `#454494`; danger = `#DC3545` fondo, texto blanco). |
| AC-07 | Componente `Badge` de roles | **Given** se muestra un rol de usuario en la UI, **When** se usa `<RoleBadge role="superadmin|admin|flow_configurator|operator|viewer" />`, **Then** cada rol tiene color distintivo: `superadmin` = violeta-azul SoftServe (`#454494`), `admin` = naranja, `flow_configurator` = azul claro, `operator` = verde, `viewer` = gris. |
| AC-08 | Componente `Card` base | **Given** se necesita un contenedor de sección en la UI, **When** el desarrollador usa `<Card>`, **Then** el card aplica: fondo blanco, border-radius `8px`, sombra suave `shadow-sm`, padding `16px`. En hover, sombra escala a `shadow-md`. |
| AC-09 | Componente `StatusBadge` para incidentes y tickets | **Given** se muestra el estado de un incidente o ticket, **When** se usa `<StatusBadge status="open|closed|processing|error" />`, **Then** cada estado tiene color semántico: `open` = naranja/warning, `closed` = gris/neutro, `processing` = azul/info, `error` = rojo de error (no el primario SoftServe). |
| AC-10 | Componente `Alert` para notificaciones inline | **Given** la UI necesita mostrar mensajes de éxito, advertencia o error, **When** se usa `<Alert type="success|warning|error|info" message="..." />`, **Then** el alert aplica los colores semánticos correctos (`--color-success`, `--color-warning`, `--color-error`, `--color-info`) con icono correspondiente. |
| AC-11 | Storybook o página de design tokens (opcional pero recomendado) | **Given** el Design System está implementado, **When** hay una ruta `/design-system` (solo visible en modo dev) o un Storybook básico, **Then** se pueden ver todos los tokens de color, tipografía y los componentes base en sus variantes. Facilita el desarrollo del resto de las HUs. |
| AC-12 | All UI text in English — no i18n | **Given** any text rendered by any component in the Design System (labels, placeholders, error messages, button text, tooltips, aria-labels), **When** the component is used anywhere in the platform, **Then** all text strings are written in English. No i18n layer (react-i18next, lingui, etc.) is implemented or expected. The platform has a single language: English. This rule applies to all HUs that use this Design System (HU-P025, HU-P026, HU-P027, HU-P028, HU-P029, HU-P032, and all EPIC-006 config HUs). |

---

## Business Rules

| ID | Regla |
|----|-------|
| BR-01 | Todos los componentes React de la plataforma (HU-P025 a HU-P028, HU-P020 a HU-P024, HU-P029) DEBEN usar los componentes base de este Design System. Está prohibido usar clases Tailwind de color hardcodeadas (ej: `bg-purple-700`, `bg-red-600`) cuando existe un equivalente en el Design System (ej: `bg-softserve-primary`). El color primario es `#454494` — no `#E3001B` (corrección de v1). |
| BR-02 | El logo SoftServe provisto por el cliente (si existe) tiene prioridad sobre el wordmark placeholder. En ningún caso se inventa o modifica el logo. Si no hay logo oficial disponible, el wordmark en Montserrat Bold color `#454494` (violeta-azul corporativo confirmado vía Brandfetch) es el placeholder aceptado para el hackathon. No usar rojo (`#E3001B`) como color del wordmark — el primario SoftServe es violeta-azul según las fuentes web consultadas. |
| BR-03 | Los valores de color documentados en esta HU son la fuente de verdad hasta que el cliente provea un Brand Guide oficial (PQ-10). Si el cliente provee el Brand Guide, los tokens se actualizan y todas las HUs React que consumen los tokens se benefician automáticamente (sin cambios en los componentes). |
| BR-04 | Las fuentes deben estar disponibles offline para el demo del hackathon (no depender de Google Fonts CDN durante la demo). Deben descargarse y servirse localmente o incluirse en el build. |
| BR-05 | El Design System no incluye animaciones complejas (no hay motion design en v1). Los únicos efectos de transición son: `transition-colors duration-150` en hover de botones y links, y `transition-shadow duration-150` en cards. |
| BR-06 | **English-only UI:** All user-visible text across the entire platform must be in English. No i18n or multilingual support is implemented in v1. Developers must not use Spanish strings, mixed-language labels, or placeholder text in languages other than English in any component that uses this Design System. |

---

## Edge Cases

| Escenario | Comportamiento esperado |
|----------|------------------------|
| El cliente provee un Brand Guide con colores diferentes a los documentados (ej: el primario no es `#454494`) | Los tokens en `tailwind.config.js` y `tokens.css` se actualizan. Todos los componentes que usan los tokens se actualizan automáticamente sin cambios de código. La fuente oficial tiene prioridad absoluta sobre los valores inferidos de v2. |
| El logo provisto por el cliente es un PNG de baja resolución | Se usa el PNG disponible para el hackathon y se documenta que se necesita el logo en SVG para producción. |
| Un desarrollador usa `bg-red-600` en lugar de `bg-softserve-primary` | Esto es una violación de BR-01. El @tech-lead-code-quality debe marcarlo en el review. |
| Montserrat no carga en la máquina del jurado del hackathon (sin internet) | BR-04 ya lo previene — las fuentes se sirven localmente. Si no se implementó BR-04, el fallback `Inter, sans-serif` debe ser visualmente aceptable. |
| Un componente necesita un color que no está en el Design System | No se hardcodea. Se añade el color al Design System con un nombre semántico, se documenta en esta HU (versionado), y entonces se usa. |

---

## Design Reference

| Pantalla / Componente | Referencia | Notas |
|----------------------|-----------|-------|
| Sitio web SoftServe | `https://www.softserveinc.com` | Fuente de observación de la paleta real en producción |
| Materiales públicos SoftServe | LinkedIn, SlideShare de eventos tech | Tipografía Montserrat confirmada en presentaciones |
| Brandfetch — SoftServe brand assets | `https://brandfetch.com/softserveinc.com` | Extracción automatizada del branding: color primario `#454494` confirmado |
| logo.com — SoftServe colors | `https://logo.com/brand/softserve-29i16g/colors` | Paleta del logo: `#454494` (Victoria), `#FFFFFF`, `#000000` |
| SoftServe Press Kit | `https://www.softserveinc.com/en-us/press-kit` | Assets oficiales de media y marca |
| Wikimedia Commons — logo SVG | `https://commons.wikimedia.org/wiki/File:SoftServe_logo_2017.svg` | SVG del logo 2017 (versión vigente para el hackathon) |
| Brand Guide oficial | Pendiente del cliente (PQ-10) | Si existe, reemplaza todos los valores inferidos. **PQ-10 RESUELTA: no hay Brand Guide disponible — usar valores inferidos de fuentes web.** |

---

## Dependencies

| HU | Tipo de dependencia |
|----|-------------------|
| HU-P027 | Bloqueada hasta que HU-P031 esté completa — el shell necesita los tokens |
| HU-P025 | Bloqueada hasta que HU-P031 esté completa |
| HU-P026 | Bloqueada hasta que HU-P031 esté completa |
| HU-P028 | Bloqueada hasta que HU-P031 esté completa |
| HU-P020 a HU-P024 | Bloqueadas hasta que HU-P031 esté completa (módulos de config) |
| HU-P029 | Bloqueada hasta que HU-P031 esté completa |

> HU-P031 no depende de ninguna otra HU. Es el punto de partida de toda la capa React.

---

## Technical Notes

- Implementar en: `services/sre-web/src/styles/tokens.css` (variables CSS), `services/sre-web/tailwind.config.js` (custom theme), `services/sre-web/src/components/ui/` (componentes base).
- Los componentes base recomendados para crear en esta HU: `Button`, `Card`, `Badge`, `RoleBadge`, `StatusBadge`, `Alert`, `Input`, `Select`, `Spinner`. El resto de componentes se crean en las HUs específicas que los necesitan.
- Montserrat via Google Fonts: `@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap')`. Para offline: descargar y poner en `public/fonts/`.
- El logo SoftServe puede obtenerse de: Wikipedia (si hay versión SVG), el meta tag `og:image` del sitio oficial (PNG), o LinkedIn de la empresa. El cliente debe confirmar si puede proveer el asset oficial.
- Tailwind config con tema SoftServe:
  ```js
  // tailwind.config.js (fragmento)
  theme: {
    extend: {
      colors: {
        'softserve': {
          primary: '#454494',        // Violeta-azul corporativo (fuente: Brandfetch + logo.com)
          'primary-dark': '#333278', // Derivado oscurecido ~15% — para hover
          'primary-light': '#5D5CB0', // Derivado aclarado ~15% — para focus rings
          900: '#1A1A1A',
          700: '#444444',
          400: '#9A9A9A',
          100: '#F5F5F5',
          50: '#FAFAFA',
        }
      },
      fontFamily: {
        montserrat: ['Montserrat', 'Inter', 'sans-serif'],
        inter: ['Inter', 'Open Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      }
    }
  }
  ```

---

## Pending Questions

| # | Pregunta | Dirigida a | Estado |
|---|---------|-----------|--------|
| 1 | (PQ-10) ¿El cliente tiene acceso al Brand Guide oficial de SoftServe (PDF, Figma, o documento de marca)? | @cliente | **RESUELTA** — No hay Brand Guide oficial disponible. El agente consultó fuentes web públicas (Brandfetch, logo.com, press kit oficial). Color primario corregido a `#454494`. Tokens documentados en esta HU v2 son los valores a usar. |
| 2 | ¿El cliente puede proveer el logo SoftServe en formato SVG o PNG de alta resolución para usarlo en el header y el login? | @cliente | Pendiente — no bloquea desarrollo. Se usa wordmark placeholder en Montserrat Bold `#454494` hasta recibir el asset. El logo SVG puede obtenerse de Wikimedia Commons (`https://commons.wikimedia.org/wiki/File:SoftServe_logo_2017.svg`) como alternativa pública. |

---

## Change History

| Version | Fecha | Cambio | Motivo |
|---------|-------|--------|--------|
| v1 | 2026-04-08 | Creación inicial. Color primario documentado como `#E3001B` (rojo) — inferido sin fuente web directa. | Requisito C del cliente — imagen corporativa SoftServe en la UI React. |
| v2 | 2026-04-08 | PQ-10 RESUELTA: no hay Brand Guide disponible. Se realizó búsqueda web en Brandfetch y logo.com. **Corrección crítica: color primario cambia de `#E3001B` (rojo) a `#454494` (violeta-azul corporativo real de SoftServe)**. Tokens `primary-dark` y `primary-light` derivados del nuevo primario. Se añade tabla de fuentes consultadas con URLs. Se actualizan AC-01, AC-06, AC-07, BR-01, BR-02, tailwind.config.js en Technical Notes. Estado cambia a Approved. | Corrección basada en fuentes web verificadas. El color rojo no es el primario corporativo de SoftServe. |
| v3 | 2026-04-08 | Requisito E — UI en inglés. Se añade AC-12 (English-only UI, no i18n) y BR-06 (English-only rule). Aplica a todos los componentes del Design System y a todas las HUs que lo consumen. | Decisión del cliente: toda la UI de la plataforma debe estar en inglés. No se implementa i18n en v1. |
