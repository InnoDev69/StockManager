# 📢 NotificationManager - Guía Completa de Uso

Sistema centralizado de notificaciones para **Stockly** con soporte para toasts flotantes, modales/popups y alertas inline.

---

## 📦 Disponibilidad Global

El `NotificationManager` está disponible como variable global en todas las páginas:

```javascript
// Opción 1: Acceso directo
NotificationManager.success("¡Éxito!");

// Opción 2: Alias global
window.Notify.error("Error detectado");
```

---

## 🎯 Toasts (Notificaciones Flotantes)

Las notificaciones toast aparecen en una esquina de la pantalla y desaparecen automáticamente.

### Uso Básico

```javascript
// Toast simple (por defecto: azul/info, 4 segundos)
NotificationManager.toast("Operación completada");
```

### Métodos Rápidos por Tipo

```javascript
// Verde - Éxito
NotificationManager.success("Producto guardado exitosamente");

// Rojo - Error
NotificationManager.error("No se pudo conectar con el servidor");

// Amarillo - Advertencia
NotificationManager.warning("Este cambio no se puede deshacer");

// Azul - Información
NotificationManager.info("Se cargaron 50 productos");
```

### Opciones Completas

```javascript
NotificationManager.toast("Se guardó el cambio", {
  type: 'success',                    // Tipo: 'success' | 'error' | 'warning' | 'info'
  duration: 3000,                     // Duración en ms (0 = permanente)
  title: 'Guardado Exitoso',          // Título adicional (opcional)
  dismissible: true,                  // Mostrar botón X para cerrar
  icon: '🎉',                         // Emoji o SVG personalizado
  onClick: () => {                    // Función al hacer click en el toast
    console.log('Toast clickeado');
  },
  actions: [                          // Botones de acción opcionales
    {
      label: 'Deshacer',
      onClick: () => undoSave(),
      style: 'primary',
      dismissOnClick: true            // Cierra el toast al hacer click
    },
    {
      label: 'Ver',
      onClick: () => goToDetails(),
      style: 'secondary'
    }
  ]
});
```

### Tabla de Opciones

| Opción | Tipo | Descripción | Valor por Defecto |
|--------|------|-------------|-------------------|
| `type` | string | Tipo de notificación | `'info'` |
| `duration` | number | Tiempo de vida en ms (0=infinito) | `4000` |
| `title` | string | Título adicional | `null` |
| `dismissible` | boolean | Permite cerrar manualmente | `true` |
| `icon` | string | Emoji o SVG | Según tipo |
| `onClick` | function | Click en el toast | `null` |
| `actions` | array | Array de botones | `[]` |

### Ejemplo: Operación con Deshacer

```javascript
async function deleteProduct(id) {
  const originalData = { ...product };
  
  await fetch(`/api/products/${id}`, { method: 'DELETE' });
  
  let toastEl = NotificationManager.toast('Producto eliminado', {
    type: 'success',
    title: 'Eliminado',
    actions: [
      {
        label: 'Deshacer',
        onClick: async () => {
          await fetch(`/api/products`, {
            method: 'POST',
            body: JSON.stringify(originalData)
          });
          NotificationManager.success('Producto restaurado');
        }
      }
    ]
  });
}
```

### Cerrar Manualmente

```javascript
// Guardar referencia al toast
const toastEl = NotificationManager.success("Cargando...");

// Cerrar después
setTimeout(() => {
  NotificationManager.dismissToast(toastEl);
}, 2000);
```

---

## 🪟 Modales / Popups

Diálogos que requieren atención del usuario.

### Uso Básico

```javascript
// Modal simple
NotificationManager.modal({
  title: 'Confirmación',
  message: '¿Estás seguro?',
  confirmText: 'Sí',
  cancelText: 'No'
});
```

### Métodos Rápidos

```javascript
// Alerta de información
NotificationManager.alert("Se debe completar todos los campos", "Validación");

// Confirmación (retorna Promise)
const confirmed = await NotificationManager.confirm("¿Eliminar este elemento?");
if (confirmed) {
  // Usuario confirmó
}

// Modales preseteados
NotificationManager.successModal("Cambios guardados", "¡Éxito!");
NotificationManager.errorModal("Error en la operación", "Error");
NotificationManager.warningModal("Datos importantes", "Advertencia");
```

### Opciones Completas

```javascript
NotificationManager.modal({
  title: '¿Eliminar Producto?',
  message: 'Esta acción no se puede deshacer',
  type: 'warning',                    // 'info' | 'success' | 'error' | 'warning' | 'confirm'
  confirmText: 'Eliminar',
  cancelText: 'Cancelar',
  showCancel: true,                   // Mostrar botón cancelar
  size: 'medium',                     // 'small' | 'medium' | 'large'
  content: null,                      // HTML personalizado (reemplaza message)
  icon: null,                         // SVG personalizado
  
  onConfirm: () => {
    console.log('Usuario confirmó');
    deleteProduct();
  },
  
  onCancel: () => {
    console.log('Usuario canceló');
  }
});
```

### Ejemplo: Confirmación de Eliminación

```javascript
async function handleDeleteProduct(productId) {
  const modal = NotificationManager.modal({
    title: 'Eliminar Producto',
    message: `¿Estás seguro que deseas eliminar este producto? Esta acción no se puede deshacer.`,
    type: 'warning',
    confirmText: 'Sí, Eliminar',
    cancelText: 'Cancelar',
    size: 'medium',
    
    onConfirm: async () => {
      NotificationManager.info('Eliminando producto...');
      
      try {
        const response = await fetch(`/api/products/${productId}`, {
          method: 'DELETE'
        });
        
        if (response.ok) {
          NotificationManager.success('Producto eliminado exitosamente');
          // Recargar tabla
          loadProducts();
        } else {
          NotificationManager.error('No se pudo eliminar el producto');
        }
      } catch (error) {
        NotificationManager.error(`Error: ${error.message}`);
      }
    }
  });
}
```

### Ejemplo: Confirmación con Promise

```javascript
async function saveChanges() {
  const confirmed = await NotificationManager.confirm(
    "Los cambios se guardarán permanentemente. ¿Continuar?",
    {
      confirmText: 'Guardar',
      cancelText: 'Cancelar'
    }
  );
  
  if (confirmed) {
    await sendToServer();
    NotificationManager.success('Cambios guardados');
  }
}
```

---

## ⚠️ Alertas Inline

Alertas que se insertan directamente en el formulario o contenedor.

### Uso

```javascript
// Crear alerta
const alertEl = NotificationManager.createInlineAlert(
  "Este campo es requerido",
  {
    type: 'error',                  // 'info' | 'success' | 'error' | 'warning'
    dismissible: true,
    icon: '❌'
  }
);

// Insertar en el DOM
document.getElementById('form-error-container').appendChild(alertEl);
```

### Ejemplo: Validación de Formulario

```javascript
function validateForm(formData) {
  const errorContainer = document.getElementById('form-errors');
  errorContainer.innerHTML = ''; // Limpiar errores previos
  
  // Validar nombre
  if (!formData.name.trim()) {
    const alert = NotificationManager.createInlineAlert(
      "El nombre del producto es requerido",
      { type: 'error' }
    );
    errorContainer.appendChild(alert);
  }
  
  // Validar precio
  if (formData.price <= 0) {
    const alert = NotificationManager.createInlineAlert(
      "El precio debe ser mayor a 0",
      { type: 'error' }
    );
    errorContainer.appendChild(alert);
  }
  
  // Mostrar si hay avisos
  if (!formData.stock) {
    const alert = NotificationManager.createInlineAlert(
      "Aviso: Este producto no tiene stock",
      { type: 'warning' }
    );
    errorContainer.appendChild(alert);
  }
}
```

---

## ⚙️ Configuración Global

Personalizar el comportamiento por defecto de todas las notificaciones:

```javascript
NotificationManager.configure({
  toast: {
    duration: 5000,                 // Aumentar duración a 5 segundos
    position: 'top-right',          // Cambiar posición
    maxVisible: 3                   // Máximo de toasts simultáneos
  },
  modal: {
    closeOnOverlay: true,           // Permitir cerrar al clickear el fondo
    closeOnEscape: true             // Permitir cerrar con ESC
  }
});
```

### Posiciones Disponibles para Toasts

- `bottom-right` ⭘ (defecto)
- `bottom-left`
- `top-right`
- `top-left`
- `top-center`
- `bottom-center`

### Ejemplo: Configurar al Inicio

```javascript
// En tu archivo base.html o al cargar la página
document.addEventListener('DOMContentLoaded', () => {
  NotificationManager.configure({
    toast: {
      position: 'top-right',
      duration: 3500,
      maxVisible: 4
    }
  });
});
```

---

## 📚 Casos de Uso Prácticos

### 1️⃣ Guardado de Formulario

```javascript
async function saveProduct() {
  const formData = new FormData(document.getElementById('productForm'));
  
  try {
    NotificationManager.info('Guardando producto...');
    
    const response = await fetch('/api/products', {
      method: 'POST',
      body: formData
    });
    
    if (response.ok) {
      NotificationManager.success('Producto guardado correctamente');
      resetForm();
    } else {
      const error = await response.json();
      NotificationManager.error(error.message || 'Error al guardar');
    }
  } catch (error) {
    NotificationManager.error(`Error de conexión: ${error.message}`);
  }
}
```

### 2️⃣ Importación de Datos

```javascript
async function importProducts(file) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    NotificationManager.toast('Importando archivo...', {
      type: 'info',
      duration: 0  // Permanente hasta completar
    });
    
    const response = await fetch('/api/import', {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    
    NotificationManager.successModal(
      `Se importaron ${result.count} productos exitosamente`,
      '¡Importación Completa!'
    );
  } catch (error) {
    NotificationManager.errorModal(
      `Error: ${error.message}`,
      'Error en la Importación'
    );
  }
}
```

### 3️⃣ Trabajos en Segundo Plano

```javascript
function scheduleReport() {
  NotificationManager.toast('Reporte programado para las 8:00 AM', {
    type: 'info',
    duration: 4000,
    actions: [
      {
        label: 'Editar',
        onClick: () => openScheduleModal(),
        style: 'primary'
      },
      {
        label: 'Cancelar',
        onClick: async () => {
          await fetch('/api/reports/cancel', { method: 'DELETE' });
          NotificationManager.info('Reporte cancelado');
        },
        style: 'secondary'
      }
    ]
  });
}
```

### 4️⃣ Cambios en Tiempo Real

```javascript
function onProductUpdated(product) {
  NotificationManager.toast(
    `${product.name} fue actualizado por otro usuario`,
    {
      type: 'info',
      icon: '🔄',
      actions: [
        {
          label: 'Recargar',
          onClick: () => window.location.reload()
        }
      ]
    }
  );
}
```

### 5️⃣ Validación Compleja

```javascript
async function validateAndSave(data) {
  // Validación cliente
  const errors = [];
  
  if (!data.name) errors.push("Nombre requerido");
  if (!data.email) errors.push("Email requerido");
  if (data.price < 0) errors.push("Precio negativo");
  
  if (errors.length > 0) {
    NotificationManager.errorModal(
      errors.join('<br>'),
      'Errores de Validación'
    );
    return;
  }
  
  // Si todo está bien, guardar
  try {
    const response = await fetch('/api/save', {
      method: 'POST',
      body: JSON.stringify(data)
    });
    
    if (response.ok) {
      NotificationManager.success('Guardado exitosamente');
    }
  } catch (e) {
    NotificationManager.error('Error al guardar');
  }
}
```

---

## ♿ Accesibilidad

El sistema tiene accesibilidad incorporada:

✅ Atributos ARIA (`role="alert"`, `role="dialog"`)  
✅ Navegación con teclado (Tab, Enter, ESC)  
✅ Anuncios vivos (`aria-live`)  
✅ Etiquetas accesibles (`aria-label`)  
✅ Contraste de colores

---

## 🎨 Tipos de Notificación

| Tipo | Color | Uso | Icono |
|------|-------|-----|-------|
| `success` | Verde | Operación exitosa | ✓ |
| `error` | Rojo | Error o fallo | ✕ |
| `warning` | Amarillo | Advertencia importante | ⚠ |
| `info` | Azul | Información general | ℹ |
| `confirm` | Púrpura | Requiere confirmación | ❓ |

---

## 🚀 Tips y Mejores Prácticas

### ✅ Haz

```javascript
// Mensajes claros y concisos
NotificationManager.success("Producto guardado");

// Acciones útiles
NotificationManager.toast("Se eliminó el producto", {
  actions: [{ label: "Deshacer", onClick: restore }]
});

// Configurar globalmente una sola vez
NotificationManager.configure({ toast: { position: 'top-right' } });

// Usar Promise para confirmaciones
const confirmed = await NotificationManager.confirm("¿Continuar?");
```

### ❌ No Hagas

```javascript
// Mensajes vagos
NotificationManager.success("OK");

// Demasiadas notificaciones simultáneas
for (let i = 0; i < 100; i++) {
  NotificationManager.info(`Notificación ${i}`);
}

// HTML no sanitizado de usuarios
NotificationManager.toast(userInput);  // ¡RIESGO DE XSS!
```

---

## 📋 Resumen Rápido

```javascript
// TOASTS
Notify.success("Mensaje");
Notify.error("Mensaje");
Notify.warning("Mensaje");
Notify.info("Mensaje");

// MODALES
Notify.modal({ title, message, type, onConfirm, onCancel });
Notify.alert("Mensaje");
const result = await Notify.confirm("¿Estás seguro?");
Notify.successModal("Mensaje", "Título");

// INLINE
const alert = Notify.createInlineAlert("Mensaje", { type: 'error' });
element.appendChild(alert);

// CONFIG
Notify.configure({ toast: { position, duration }, modal: { closeOnEscape } });
```

---

**¡Listo! Ya puedes usar el NotificationManager en todo tu proyecto.** 🎉
