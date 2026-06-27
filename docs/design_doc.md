# 📘 Manual de Uso Completo: Sistema de Componentes Stockly  
*Documentación técnica 100% para desarrolladores – HTML, CSS y Jinja2*

---

## 🧩 I. Estructura del Proyecto

Antes de programar, conoce los archivos críticos del sistema:

### A. Archivos CSS (`/static/css/`)
| Archivo | Propósito Clave | ¿Cuándo lo tocas? |
| :--- | :--- | :--- |
| `_variables.css` | Define tokens globales (colores, radios, espaciado). **Nunca** valores fijos. | Cambios de diseño base. |
| `_typography.css` | Headings, texto, utilidades tipográficas. | Modificación de fuentes/tamaños. |
| `_components.css` | Botones, badges, cards, forms. | Añadir nuevos componentes UI. |
| `_utilities.css` | Helpers: flex, grid, margin/padding. | Ajustes rápidos de layout. |
| `_layout.css` | Header, container, drawer, modal. | Cambios estructurales del layout. |
| `_responsive.css` | Media queries y accesibilidad. | Adaptación móvil/tablet. |
| `style.css` | Archivo principal (`@import` de los 6 archivos). | **Importar siempre desde aquí**. |

### B. Archivos Jinja2 (`/templates/`)
| Archivo | Propósito | Instrucción Importante |
| :--- | :--- | :--- |
| `base.html` | Template base mejorado, usa componentes. | Heredar desde este archivo. |
| `components.html` | **Macros reutilizables** (la API del sistema). | **Siempre importar aquí primero**: `{% import "components.html" as comp %}` |

---

## 📐 II. Referencia CSS y Variables Globales

### A. Variables (Tokens) – ¡NUNCA valores mágicos!
Todos los cambios de diseño van a `_variables.css`. Usa estas variables **siempre** en tu HTML:

| Variable | Valores Disponibles | Uso Recomendado | Prohibido hacer |
| :--- | :--- | :--- | :--- |
| `--radius-sm` | 8px | Tarjetas de íconos, botones secundarios. | `border-radius: 5px;` (inline) |
| `--radius-md` | 12px | Botones principales, formularios. | `border-radius: 10px;` (inline) |
| `--radius-lg` | 16px | Contenedores destacados. | - |
| `--text-muted` | Ej: `#9aa5b3` | Etiquetas, subtítulos, descripciones secundarias. | `<p style="color: #777">` (inline) |
| `--font-sans` | `Inter, sans-serif` | Aplicado en el `body`. | - |

### B. Clases Utilidad de Layout y Espaciado
Definidas en `_utilities.css`. **Nunca** usar márgenes/paddings inline:

| Clase | Propósito | Ejemplo Correcto | Prohibido hacer |
| :--- | :--- | :--- | :--- |
| `mb-2xl` | Margen abajo grande | `<div class="card mb-2xl">` | `<div margin-bottom="1.5rem">` |
| `mt-lg` | Margen arriba grande | `<h1 class="mt-lg">Título</h1>` | - |
| `flex`, `grid` | Helpers de flexbox/grid | `<div class="flex items-center">` | `<div style="display:flex">` |

**⚠️ Regla de Oro:** Nunca uses `style="..."` en HTML. Si necesitas un estilo, usa una variable (`var(--token-name)`) o una clase utilitaria existente.

---

## 🛠 III. API de Componentes Jinja2 (Macros Principales)

En cualquier archivo `.html` o `base.html`, **siempre** importa primero:
```jinja2
{% import "components.html" as comp %}
```

### 1. Header de Página (`comp.page_header`)
Crea encabezados consistentes para cualquier vista.

| Propiedad | Tipo | Obligatorio | Descripción |
| :--- | :--- | :--- | :--- |
| **`title`** | String | **Sí** | Título principal de la página (ej: `Dashboard`). |
| **`subtitle`** | String | **Sí** | Subtítulo/descripción bajo el título. |

```jinja2
{{ comp.page_header('Crear Nuevo Producto', 'Detalles y gestión de inventario') }}
```

### 2. Botones (`comp.btn`)
Genera botones con funcionalidad, estilo y apariencia específicas.

| Propiedad | Tipo | Obligatorio | Valores / Descripción |
| :--- | :--- | :--- | :--- |
| **`text`** | String | **Sí** | Texto visible del botón. |
| **`type`** | Enum | **No (recomendado)** | `'button'`, `'submit'`, `'link'`. Para formularios: `type='submit'`. |
| **`variant`** | String | No | `'primary'` (default), `'secondary'`, `'ghost'`, `'danger'`. |
| **`href`** | String | No | URL de destino si el botón es un enlace. Ej: `/export`. |
| **`icon`** | String | No | Nombre del ícono junto al texto. |
| **`icon_size`**| String | No | Tamaño del icono (ej: `'16'`, `'24'`). |

```jinja2
{{ comp.btn('Guardar', type='submit') }}
{{ comp.btn('Cancelar', variant='ghost') }}
{{ comp.btn('Descargar', href='/export', icon='download', icon_size='16') }}
```

### 3. Iconos (`comp.icon`)
Inserta íconos centralizados sin librerías externas (Hardcoded y reutilizables).

| Propiedad | Tipo | Obligatorio | Descripción |
| :--- | :--- | :--- | :--- |
| **`name`** | String | **Sí** | Nombre del icono (ej: `'plus'`, `'search'`, `'settings'`). |
| **`size`** | String | No | Tamaño en píxeles o variable. Ej: `'24'`, `'16'`. |

```jinja2
{{ comp.icon('plus', size='24') }}
{{ comp.icon('search') }}
{{ comp.icon('settings') }}
{{ comp.icon('download') }}
{{ comp.icon('chart') }}
```

### 4. Campos de Formulario (`comp.form_field`)
Estandariza entradas, garantiza validación consistente y etiquetas automáticas.

| Propiedad | Tipo | Obligatorio | Valores / Descripción |
| :--- | :--- | :--- | :--- |
| **`label`** | String | **Sí** | Texto visible para el usuario (Etiqueta). Ej: `'Nombre Producto'`. |
| **`name`** | String | **Sí** | Atributo `name` del input para envío. Ej: `'sku'`. |
| **`type`** | String | No | `'text'`, `'email'`, `'number'`, `'textarea'`. |
| **`required`** | Bool | No | Si es obligatorio (`true`). |
| **`maxlength`**| Int/Str | No | Límite de caracteres (solo texto). Ej: `'50'`. |
| **`min`** | String/Int | No | Valor mínimo (para `type='number'`). |
| **`max`** | String/Int | No | Valor máximo (para `type='number'`). |

```jinja2
{{ comp.form_field('Nombre Producto', 'product_name', required=true) }}
{{ comp.form_field('Descripción', 'description', type='textarea') }}
{{ comp.form_field('Stock Actual', 'stock', type='number', min='0', max='1000') }}
```

### 5. Accesos Rápidos (`comp.quick_access_item`)
Crea widgets en cuadrículas (Grid) para acciones frecuentes.

| Propiedad | Tipo | Obligatorio | Descripción |
| :--- | :--- | :--- | :--- |
| **`title`** | String | **Sí** | Título del widget (ej: `'Venta'`). |
| **`description`**| String | No | Texto descriptivo corto. |
| **`href`** | String | Sí (si es clickeable) | URL de destino. |
| **`icon`** | String | No (recomendado) | Icono del widget. |
| **`color`** | Variable/String | No | Color/variante (ej: `'var(--success)'`). |

```jinja2
<div class="quick-access-grid mb-4">
  {{ comp.quick_access_item('Nueva Venta', 'Registrar transacción.', '/sales/new', 'cart', 'var(--success)') }}
  {{ comp.quick_access_item('Nuevo Producto', 'Agregar items al inventario.', '/product/new', 'plus') }}
</div>
```

### 6. Footer de Formulario (`comp.form_footer`)
Bloque estandarizado para botones de acción al final del formulario (Guardar, Cancelar).

| Propiedad | Tipo | Obligatorio | Descripción |
| :--- | :--- | :--- | :--- |
| **`submit`** | String/Bool | Sí | Texto del botón principal o `true`. |
| **`secondary`**| String | No | Texto del botón secundario (ej: `'Cancelar'`). |

```jinja2
{{ comp.form_footer(submit='Guardar Producto', secondary='Cancelar') }}
```

---

## 🧪 IV. Ejemplo Práctico: Página de Crear Producto

Combina todos los elementos en una implementación completa y moderna:

```jinja2
{# ======================================== #}
{# IMPORTAR COMPONENTES (Siempre al inicio) #}
{% import "components.html" as comp %}
{% endimport %}
{# ======================================== #}

<!-- 1. HEADER DE PÁGINA (Título + Subtítulo) -->
{{ comp.page_header('Crear Nuevo Producto', 'Detalles y gestión de inventario') }}

<div class="container mt-2xl">
    <form action="/product/new" method="POST">

        <!-- 2. Accesos Rápidos en la Parte Superior -->
        <h3 class="mb-lg">Acciones Rápidas</h3>
        <div class="quick-access-grid mb-4">
            {{ comp.quick_access_item('Venta', 'Registrar nueva venta.', '/sales/new', 'cart', 'var(--success)') }}
            {{ comp.quick_access_item('Proveedores', 'Gestionar inventario de proveedores.', '/suppliers/list', 'person', 'var(--info)') }}
        </div>

        <!-- 3. Contenedor del Formulario -->
        <div class="card p-lg mb-4">
            <h4>Datos Base</h4>
            
            <!-- Campos de formulario estándar -->
            <div class="mb-2xl">
                {{ comp.form_field('Nombre Producto', 'product_name', required=true) }}
            </div>
            
            <div class="mb-2xl">
                {{ comp.form_field('Descripción', 'description', type='textarea') }}
            </div>

            <!-- Componente avanzado de número con límites -->
            <div class="mb-2xl">
                {{ comp.form_field('Stock Inicial', 'stock_qty', type='number', min='0', max='10000', required=true) }}
            </div>
        </div>

        <!-- 4. Footer con Botones de Acción -->
        {{ comp.form_footer(submit='Crear Producto', secondary='Cancelar') }}

    </form>
</div>
```

---

## 🔍 V. Guía de Migración (De HTML Antigo a Stockly)

### Antes (Incorrecto – Estilos Inline + HTML Repetitivo):
```html
<header style="margin-bottom: 1.5rem;">
  <h1 style="margin: 0 0 0.5rem 0; font-size: 1.75rem; font-weight: 700;">Dashboard</h1>
  <p class="text-muted" style="margin: 0;">Gestiona tu inventario</p>
</header>

<div class="card" style="margin-bottom: 1.5rem;">
  <button class="btn">Nuevo producto</button>
</div>
```

### Después (Correcto – Componentes + Utilidades):
```jinja2
{% import "components.html" as comp %}

{{ comp.page_header('Dashboard', 'Gestiona tu inventario') }}

<div class="card mb-2xl">
  {{ comp.btn('Nuevo producto', type='button') }}
</div>
```

---

## ✅ VI. Lista de Chequeo para Nuevas Páginas

Antes de guardar, verifica que tu código cumpla:

1.  [ ] **¿Importé `components.html`?**  
    *Sí:* `{% import "components.html" as comp %}` al inicio del bloque Jinja2.
    *No:* **Error**. No funcionarán los macros.

2.  [ ] **¿Uso variables CSS en vez de valores fijos?**  
    ✅ `border-radius: var(--radius-md);` (Correcto)  
    ❌ `border-radius: 12px;` (Incorrecto - a menos que sea para debugging).

3.  [ ] **¿Tengo estilos inline?**  
    ❌ `<button style="background-blue">` → **Prohibido**. Usa `.btn` o una variante específica.

4.  [ ] **¿Estoy duplicando componentes UI?**  
    Si ves 5 botones con clases distintas, ¿por qué? Deberías estar usando `comp.btn()` siempre.

---

## 🚀 VII. Iconos Disponibles (Hardcoded en el Sistema)

Estos nombres funcionarán directamente con `comp.icon()`:

| Ícono | Descripción | Uso Principal |
| :--- | :--- | :--- |
| `plus` | Añadir/Crear | Botón de nuevo registro, acceso rápido. |
| `search` | Buscar | Barra de búsqueda, filtros. |
| `settings` | Configuración | Menú de ajustes, perfil. |
| `download` | Descargar | Exportar datos, reports. |
| `chart` | Gráfica/Analítica | Dashboard, estadísticas. |

**Para más íconos:**  
Los iconos están hardcodeados en el sistema actual. Si necesitas añadir más, edita los archivos fuente de la librería de iconos (ej: Feather Icons) y actualiza las referencias aquí.

---

## 📞 VIII. Preguntas Frecuentes (FAQ Técnica)

**Q: ¿Puedo mezclar estilos custom con estos componentes?**  
A: Puedes, pero **solo mediante clases utilitarias en `_utilities.css`**. Nunca inline. Si necesitas crear un nuevo componente (ej: `.card-custom`), añade el CSS a `_components.css` y la clase estará disponible globalmente.

**Q: ¿Cómo agrego una nueva variable de color?**  
A: Abre `_variables.css` y define:
```css
--color-primary-accent: #3b82f6; /* Valor hex */
/* Luego usa en tus templates: comp.form_field(color='var(--color-primary-accent)') */
```

**Q: ¿Los archivos CSS son cacheados?**  
A: Sí, `style.css` importa los otros 6. Para cambios críticos, recarga la página con Ctrl+F5 (hard refresh).

---

## 📜 IX. Reglas de Estilo (Style Guide Rápida)

| Elemento | Clases/Componentes Obligatorios | Prohibido |
| :--- | :--- | :--- |
| **Botones** | `{{ comp.btn() }}` | `<button class="btn">` sin macro. |
| **Formularios** | `{{ comp.form_field() }}` | `<input type="text" />`. |
| **Encabezados** | `{{ comp.page_header() }}` | `<header><h