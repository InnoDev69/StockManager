/**
 * Products CRUD - Gestión de productos
 * Maneja formularios de creación, edición y eliminación de productos
 */

// ===== INICIALIZACION =====
function initProductsForm() {
  initProductFormSubmit();
  initNumberInputLimits();
  initDatePicker();
}

// ===== LIMITAR INPUTS NUMÉRICOS =====
function initNumberInputLimits() {
  document.querySelectorAll('input[type="number"][max]').forEach(input => {
    input.addEventListener('input', function() {
      const max = parseFloat(this.max);
      const min = parseFloat(this.min) || 0;
      let value = parseFloat(this.value);
      
      if (value > max) this.value = max;
      if (value < min) this.value = min;
    });
  });
}

// ===== DATE PICKER =====
function initDatePicker() {
  const expirationInput = document.querySelector('input[name="expiration_date"]');
  if (expirationInput && typeof CalendarPicker !== 'undefined') {
    const minYear = parseInt(expirationInput.dataset.calendarMinYear) || 2020;
    const maxYear = parseInt(expirationInput.dataset.calendarMaxYear) || 2030;
    new CalendarPicker('input[name="expiration_date"]', {
      minYear: minYear,
      maxYear: maxYear
    });
  }
}

// ===== VALIDAR FORMULARIO CLIENTE =====
function validateProductForm(form) {
  const errors = [];
  const barrs_code = form.barrs_code.value.trim();
  const name = form.name.value.trim();
  const quantity = parseInt(form.quantity.value) || 0;
  const min_quantity = parseInt(form.min_quantity.value) || 0;
  const price = parseFloat(form.price.value) || 0;
  
  if (!barrs_code) errors.push('El código de barras es obligatorio');
  if (barrs_code.length < 3) errors.push('El código de barras debe tener al menos 3 caracteres');
  if (!name) errors.push('El nombre del producto es obligatorio');
  if (name.length < 2) errors.push('El nombre debe tener al menos 2 caracteres');
  if (quantity < 0) errors.push('El stock no puede ser negativo');
  if (min_quantity < 0) errors.push('El stock mínimo no puede ser negativo');
  if (quantity < min_quantity) errors.push('El stock inicial no puede ser menor que el stock mínimo');
  if (price < 0) errors.push('El precio no puede ser negativo');
  if (price === 0) errors.push('⚠️ El precio está en 0 - ¿Es intencional?');
  
  return errors;
}

// ===== SUBMIT FORM PRODUCTO =====
function initProductFormSubmit() {
  const form = document.getElementById('product-form');
  if (!form) return;
  
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Limpiar errores previos
    document.querySelectorAll('.field-error').forEach(el => el.textContent = '');
    document.querySelectorAll('input').forEach(el => el.classList.remove('input-error'));
    const globalError = document.getElementById('form-validation-error');
    if (globalError) globalError.style.display = 'none';
    
    // Validar en cliente
    const errors = validateProductForm(form);
    if (errors.length > 0) {
      if (globalError) {
        globalError.innerHTML = '<strong>Por favor, corrige los siguientes errores:</strong><ul style="margin: 0.5rem 0 0; padding-left: 1.5rem;">' + 
          errors.map(e => `<li>${e}</li>`).join('') + '</ul>';
        globalError.style.display = 'block';
      }
      return;
    }
    
    const data = getProductFormData(form);
    
    try {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Guardando...';
      }
      
      const response = await fetch('/api/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        NotificationManager.success('Producto agregado exitosamente', { duration: 3000 });
        clearProductForm(form);
      } else {
        handleProductFormError(result);
      }
    } catch (error) {
      console.error('Error:', error);
      NotificationManager.error('Error de conexión al servidor');
    } finally {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Agregar Producto';
      }
    }
  });
}

// ===== OBTENER DATOS DEL FORMULARIO =====
function getProductFormData(form) {
  return {
    barcode: form.barrs_code.value.trim(),
    name: form.name.value.trim(),
    description: form.description.value.trim(),
    quantity: parseInt(form.quantity.value) || 0,
    min_quantity: parseInt(form.min_quantity.value) || 0,
    price: parseFloat(form.price.value) || 0,
    expiration_date: form.expiration_date?.value ? convertDateFormat(form.expiration_date.value) : null
  };
}

// ===== CONVERTIR FORMATO DE FECHA =====
function convertDateFormat(dateStr) {
  // Convierte DD/MM/YYYY a YYYY-MM-DD
  const [d, m, y] = dateStr.split('/');
  return `${y}-${m}-${d}`;
}

// ===== MANEJAR ERRORES DEL FORMULARIO =====
function handleProductFormError(result) {
  if (result.error) {
    const globalError = document.getElementById('form-validation-error');
    if (globalError) {
      globalError.textContent = '❌ ' + result.error;
      globalError.style.display = 'block';
    }
    NotificationManager.error(result.error);
  } else {
    NotificationManager.error('Error al agregar producto');
  }
}

// ===== LIMPIAR FORMULARIO =====
function clearProductForm(form) {
  document.querySelectorAll('input').forEach(input => input.value = '');
  document.querySelectorAll('.field-error').forEach(el => el.textContent = '');
}

// ===== INICIAR AL CARGAR EL DOM =====
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initProductsForm);
} else {
  initProductsForm();
}