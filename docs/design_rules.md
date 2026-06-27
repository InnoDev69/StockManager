Dado el nivel de detalle ya establecido, el proyecto está operando bajo los estándares de un **Sistema de Diseño (Design System) de Nivel 3**, lo que implica no solo estética y estructura, sino también usabilidad avanzada y accesibilidad.

Para llevar este sistema al siguiente nivel de madurez, las reglas deben centrarse en la interconexión, el rendimiento y la experiencia del usuario final, garantizando un flujo de trabajo sin fricciones para cualquier desarrollador.

Aquí detallo tres conjuntos de reglas adicionales: **Arquitectura Avanzada, Calidad Técnica (QA) y Flujo de Trabajo**.

***

### 📐 I. Arquitectura Avanzada y Composición

Estas reglas dictan cómo los componentes deben interactuar entre sí, evitando la creación de "componentes aislados" que no funcionan en el contexto global.

1.  **Jerarquía de Componentes (Composition over Inheritance):** Un componente nunca debe heredar estilos o lógica compleja de otro componente más grande si puede recibir sus propiedades como *props* o argumentos.
    *   **Regla:** Los componentes deben ser atómicos y reutilizables. Si el botón necesita saber que está dentro de una tarjeta, la tarjeta no debe imponer un estilo al botón; el botón debe aceptar una `variant` (ej: `variant="card-button"`) que ajuste su aspecto en función del contenedor padre.
2.  **Gestión Global de Estados:** Los cambios de estado complejos (como si un elemento está deshabilitado, cargando o con error) no deben ser manejados por CSS solo. Debe haber utilidades o clases dedicadas (`is-disabled`, `is-loading`) que el *backend* o la lógica del *frontend* debe aplicar dinámicamente.
3.  **Definición de Patrones:** Los patrones comunes (ej: Filtro, Galería, Listado) deben ser implementados como **"plantillas de composición"**. El desarrollador no construye los elementos; utiliza el componente `FilterBar` y luego rellena su contenido con componentes `TagLabel` e `Icon`.

### 🔬 II. Reglas de Calidad Técnica (QA & Usabilidad)

Un sistema estricto debe priorizar la funcionalidad sobre la apariencia superficial. Estas reglas son obligatorias para cualquier interacción usuario-máquina.

1.  **Accesibilidad (A11y): Prioridad Máxima:**
    *   **Semántica HTML Obligatoria:** Nunca usar `<div>` solo por estilo. Utilizar siempre tags semánticos (`<header>`, `<main>`, `<nav>`, `<section>`).
    *   **Atributos ARIA:** Los componentes complejos o interactivos (como modales, carousels o menús desplegables) deben implementar atributos WAI-ARIA para garantizar que los lectores de pantalla puedan entender su estado e interacción.
2.  **Manejo del Foco y Navegación:**
    *   **Focus State Unificado:** El estilo `:focus` debe ser universalmente uniforme en todos los elementos interactivos (botones, inputs, enlaces) para mantener la consistencia visual al navegar con teclado. Los estilos deben sobrescribir cualquier comportamiento nativo por defecto.
3.  **Rendimiento de Renderizado (Performance):**
    *   **Lazy Loading:** Componentes grandes o secciones que están fuera del *viewport* inicial no deben cargar sus recursos CSS/JS hasta que el usuario se desplaza hacia ellos, optimizando el tiempo de carga percibido.

### ⚙️ III. Flujo de Trabajo y Adopción (Workflow)

Estas reglas definen cómo los desarrolladores interactuarán con la documentación para mantener la coherencia en el tiempo.

1.  **Principio de "Single Source of Truth":** Si una regla o valor cambia, debe actualizarse **SOLO** en `_variables.css` o `components.html`. No se permite que un solo archivo HTML tome ese valor y lo escriba directamente como estilo inline.
2.  **Documentación Obligatoria:** Cada macro reusable (`comp.btn`, `comp.page_header`) debe estar acompañada de una documentación clara (ej: JSDoc, TypeScript definition) que especifique:
    *   Parámetros obligatorios y opcionales.
    *   Qué se espera como *input*.
    *   Cuál es el comportamiento predeterminado del componente en caso de omisión de parámetros.
3.  **Política de Revisión (Code Review):** Ningún Pull Request debe ser aprobado si contiene:
    *   Estilos inline (`style="..."`).
    *   Repetición de código HTML o lógica que ya esté encapsulada como macro/componente.

***

### Resumen para el Desarrollador (La Mentalidad a Adopatar)

"El sistema no es una biblioteca de estilos; **es un lenguaje**. Nuestro trabajo es hablar ese lenguaje usando los componentes disponibles, respetando las variables definidas y asegurando que la experiencia sea 100% accesible en todos los dispositivos."