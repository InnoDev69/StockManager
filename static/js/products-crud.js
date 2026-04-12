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

// ===== SUBMIT FORM PRODUCTO =====
function initProductFormSubmit() {
  const form = document.getElementById('product-form');
  if (!form) return;
  
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Limpiar errores previos
    document.querySelectorAll('.field-error').forEach(el => el.textContent = '');
    document.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
    
    const data = getProductFormData(form);
    
    try {
      const response = await fetch('/api/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        Notify.success('Producto agregado exitosamente');
        clearProductForm(form);
      } else {
        handleProductFormError(result);
      }
    } catch (error) {
      console.error('Error:', error);
      Notify.error('Error de conexión al servidor');
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
  if (result.field) {
    const errorSpan = document.querySelector(`.field-error[data-field="${result.field}"]`);
    const input = errorSpan?.closest('.field')?.querySelector('input');
    if (errorSpan) errorSpan.textContent = result.error;
    if (input) input.classList.add('input-error');
  } else {
    Notify.error(result.error || 'Error al agregar producto');
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