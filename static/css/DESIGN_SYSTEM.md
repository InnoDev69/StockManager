# Sistema de Componentes UI - Stockly

## 📋 Descripción

Se ha implementado un sistema modular, flexible y mantenible para la UI de Stockly. Incluye:

- ✅ **Componentes Jinja2 reutilizables** (`templates/components.html`)
- ✅ **CSS modularizado** en 6 archivos separados
- ✅ **Iconos centralizados** como macros
- ✅ **Sistema de espaciado y tipografía** consistentes
- ✅ **Utilidades CSS** para layouts rápidos

---

## 📂 Estructura

### CSS (`/static/css/`)
```
_variables.css    → Variables de colores, espaciado, z-index
_typography.css   → Tipografía, headings, utilidades de texto
_components.css   → Botones, badges, cards, forms
_utilities.css    → Clases helper (flex, grid, margin, padding, etc)
_layout.css       → Header, container, drawer, modal, etc
_responsive.css   → Media queries y accesibilidad
style.css         → Archivo principal (@import de todos)
```

### Templates (`/templates/`)
```
base.html        → Template base mejorada (usa components)
components.html  → Macros reutilizables
```

---

## 🎨 Cómo usar los componentes

### 1. Importar
```jinja2
{% import "components.html" as comp %}
```

### 2. Iconos
```jinja2
{{ comp.icon('plus', size='24') }}
{{ comp.icon('search') }}
{{ comp.icon('settings') }}
{{ comp.icon('download') }}
{{ comp.icon('chart') }}
```

### 3. Botones
```jinja2
{{ comp.btn('Guardar', type='submit') }}
{{ comp.btn('Cancelar', variant='ghost') }}
{{ comp.btn('Descargar', href='/export', icon='download', icon_size='16') }}
```

### 4. Campos de formulario
```jinja2
{{ comp.form_field('nombre', 'name', required=true, maxlength='50') }}
{{ comp.form_field('Descripción', 'description', type='textarea') }}
{{ comp.form_field('Stock', 'stock', type='number', min='0', max='1000') }}
```

### 5. Headers de página
```jinja2
{{ comp.page_header('Administrar Productos', 'Edita y gestiona tu inventario') }}
```

### 6. Quick Access Items
```jinja2
<div class="quick-access-grid">
  {{ comp.quick_access_item('Nueva Venta', 'Registrar transacción', '/sales/new', 'cart', 'var(--success)') }}
  {{ comp.quick_access_item('Nuevo Producto', 'Agregar items', '/product/new', 'plus') }}
</div>
```

### 7. Stats Grid
```jinja2
{{ comp.stats_grid([
  {'label': 'Total Productos', 'value': '123', 'subtitle': 'en inventario'},
  {'label': 'Stock Bajo', 'value': '5'},
  {'label': 'Sin Stock', 'value': '2'},
]) }}
```

### 8. Badges
```jinja2
{{ comp.badge('En Stock', 'success') }}
{{ comp.badge('Stock Bajo', 'warning') }}
{{ comp.badge('Sin Stock', 'danger') }}
```

### 9. Module Headers & Modals
```jinja2
{{ comp.modal_header('Detalles del Producto', 'close-btn-id') }}
{{ comp.meta_label('SKU', 'ABC-123', mono=true) }}
{{ comp.form_actions(cancel_id='btn-cancel') }}
```

---

## 🎯 Utilidades CSS (Clases Helper)

### Display
```html
<div class="hidden"></div>           <!-- display: none -->
<div class="flex items-center"></div> <!-- flexbox + align -->
<div class="grid"></div>              <!-- display: grid -->
```

### Flexbox
```html
<div class="flex flex-row items-center justify-between gap-md"></div>
```

### Espaciado
```html
<div class="mt-lg mb-xl px-md py-lg"></div>
<!-- m = margin, p = padding, t/b/l/r = top/bottom/left/right -->
<!-- xs=4px, sm=8px, md=12px, lg=16px, xl=20px, 2xl=24px, 3xl=32px -->
```

### Responsive
```html
<div class="text-sm md:text-base lg:text-lg"></div>
```

---

## 🛠️ Variables CSS (Sin prefijo '`--`')

### Colores
- `var(--bg)` - Fondo principal
- `var(--panel)` - Panel/card fondo
- `var(--text)` - Texto principal
- `var(--text-muted)` - Texto secundario
- `var(--brand)` - Color primario (indigo)
- `var(--success)` - Verde
- `var(--warning)` - Ámbar
- `var(--danger)` - Rojo

### Espaciado
- `var(--spacing-xs)` → 4px
- `var(--spacing-sm)` → 8px
- `var(--spacing-md)` → 12px
- `var(--spacing-lg)` → 16px
- `var(--spacing-xl)` → 20px
- `var(--spacing-2xl)` → 24px

### Radios
- `var(--radius-sm)` → 8px
- `var(--radius-md)` → 12px
- `var(--radius-lg)` → 16px

---

## 📝 Ejemplo: Refactorizar un template antiguo

### Antes (inline styles + HTML repetitivo)
```html
<header style="margin-bottom: 1.5rem;">
  <h1 style="margin: 0 0 0.5rem 0; font-size: 1.75rem; font-weight: 700;">Dashboard</h1>
  <p class="text-muted" style="margin: 0;">Gestiona tu inventario</p>
</header>

<div class="card" style="margin-bottom: 1.5rem;">
  <button class="btn">Nuevo producto</button>
</div>
```

### Después (componentes + utilidades)
```html
{% import "components.html" as comp %}

{{ comp.page_header('Dashboard', 'Gestiona tu inventario') }}

<div class="card mb-2xl">
  {{ comp.btn('Nuevo producto', type='button') }}
</div>
```

---

## ✨ Beneficios

| Antes | Después |
|-------|---------|
| Estilos inline por todas partes | Clases consistentes |
| HTML repetitivo | Macros reutilizables |
| Difícil mantener colores | Variables CSS centralizadas |
| CSS monolítico (1000+ líneas) | CSS modularizado en 6 archivos |
| Iconos hardcodeados en HTML | Macro de iconos centralizada |

---

## 🔄 Migración gradual

No necesitas cambiar todo de una vez. Puedes:

1. Usar componentes en templates nuevos
2. Gradualmente refactorizar templates existentes
3. Los estilos viejos seguirán funcionando durante la transición

---

## 💡 Tips

- **Utilidades primero**: Para layouts rápidos usa `flex`, `grid`, `gap-md`, etc
- **Componentes para lógica**: Use macros para cosas con lógica (botones con condicionales, etc)
- **Una sola vista**: Importa componentes una sola vez al inicio del template
- **Combina**: `{{ comp.btn(...) }}` + `class="mt-lg"` funciona perfectamente

---

Preguntas? Revisa `templates/components.html` y `static/css/_layout.css` 🚀
