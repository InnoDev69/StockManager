/**
 * Products CRUD - Gestión de productos
 * Maneja formularios de creación, edición y eliminación de productos
 */

// ===== INICIALIZACION =====
function initProductsForm() {
  initProductFormSubmit();
  initNumberInputLimits();
  initDatePicker();
  initBarcodeAutofill();
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
  if (price === 0) errors.push('El precio está en 0 - ¿Es intencional?');

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
        const message = document.createElement('strong');
        message.textContent = 'Por favor, corrige los siguientes errores:';

        const list = document.createElement('ul');
        list.style.cssText = 'margin: 0.5rem 0 0; padding-left: 1.5rem;';
        errors.forEach(errorText => {
          const item = document.createElement('li');
          item.textContent = errorText;
          list.appendChild(item);
        });

        globalError.replaceChildren(message, list);
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
      globalError.textContent = result.error;
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
  resetBarcodeAutofillState();
}

// ======================================================================
// AUTOCOMPLETAR DESDE OPENFOODFACTS (GET /api/products/info/<barcode>)
// ======================================================================
// Al salir del campo de código de barras, se consulta la API. Si hay
// datos disponibles, se le pregunta al usuario (modal) si quiere
// completar el formulario con esa información antes de tocar nada.
// Solo se sobrescriben campos que el usuario todavía no completó.
// ======================================================================

let lastCheckedBarcode = null;
let autofillRequestToken = 0;

function initBarcodeAutofill() {
  const barcodeInput = document.getElementById('barrs_code');
  if (!barcodeInput) return;

  barcodeInput.addEventListener('blur', function() {
    const barcode = barcodeInput.value.trim();
    handleBarcodeBlur(barcode);
  });
}

function resetBarcodeAutofillState() {
  lastCheckedBarcode = null;
  const statusEl = document.getElementById('barcode-info-status');
  if (statusEl) statusEl.remove();
}

function handleBarcodeBlur(barcode) {
  if (!barcode || barcode.length < 3) return;
  if (barcode === lastCheckedBarcode) return;
  // Códigos autogenerados por "Generar" (PRD######) no existen en OpenFoodFacts
  if (/^PRD\d+$/i.test(barcode)) return;

  lastCheckedBarcode = barcode;
  fetchProductInfo(barcode);
}

function getBarcodeStatusEl() {
  let el = document.getElementById('barcode-info-status');
  if (!el) {
    el = document.createElement('small');
    el.id = 'barcode-info-status';
    el.style.cssText = 'display:block; font-size:0.8rem; margin-top:0.35rem; transition:opacity .4s ease;';
    const barcodeInput = document.getElementById('barrs_code');
    if (barcodeInput && barcodeInput.parentElement) {
      barcodeInput.parentElement.appendChild(el);
    }
  }
  el.style.opacity = '1';
  return el;
}

function setBarcodeStatus(text, color, autoFade) {
  const el = getBarcodeStatusEl();
  el.textContent = text;
  el.style.color = color || 'var(--text-muted)';
  if (autoFade) {
    setTimeout(() => { el.style.opacity = '0'; }, 2500);
  }
}

async function fetchProductInfo(barcode) {
  const requestToken = ++autofillRequestToken;
  setBarcodeStatus('Buscando información del producto...', 'var(--text-muted)', false);

  try {
    const res = await fetch(`/api/products/info/${encodeURIComponent(barcode)}`, {
      credentials: 'same-origin'
    });

    if (requestToken !== autofillRequestToken) return;

    if (res.status === 404) {
      setBarcodeStatus('No se encontró información externa para este código.', 'var(--text-muted)', true);
      return;
    }

    if (!res.ok) {
      setBarcodeStatus('', null, false);
      return;
    }

    const data = await res.json();
    setBarcodeStatus('', null, false);

    if (!data.name && !data.description) return;

    showAutofillConfirmModal(data);

  } catch (error) {
    if (requestToken !== autofillRequestToken) return;
    console.error('Error consultando información del producto:', error);
    setBarcodeStatus('', null, false);
  }
}

function showAutofillConfirmModal(data) {
  const existing = document.getElementById('autofillModal');
  if (existing) existing.remove();

  const form = document.getElementById('product-form');
  if (!form) return;

  const canFillName = !!data.name && !form.name.value.trim();
  const canFillDescription = !!data.description && !form.description.value.trim();

  if (!canFillName && !canFillDescription) return;

  const extraInfo = [data.brands, data.categories].filter(Boolean).join(' · ');
  const someFieldsSkipped = (!!data.name && !canFillName) || (!!data.description && !canFillDescription);

  const modalEl = document.createElement('div');
  modalEl.id = 'autofillModal';
  modalEl.dataset.featureId = 'product-autofill';
  modalEl.dataset.featureText = 'Caracteristica de autocompletado';
  modalEl.setAttribute('data-feature-glow', '');
  modalEl.style.cssText = 'position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; z-index:1001; animation:fadeIn .2s ease; padding: 1rem;';

  const dialog = document.createElement('div');
  dialog.style.cssText = 'background:var(--card); border-radius:12px; box-shadow:var(--shadow-lg); width:100%; max-width:440px; animation:slideDown .3s ease; border:1px solid var(--border);';

  const header = document.createElement('div');
  header.style.cssText = 'display:flex; align-items:center; gap:1rem; padding:1.5rem; background:color-mix(in srgb, var(--brand) 10%, transparent); border-bottom:2px solid color-mix(in srgb, var(--brand) 30%, transparent); border-radius:12px 12px 0 0;';

  if (data.image_url) {
    const image = document.createElement('img');
    image.src = data.image_url;
    image.alt = '';
    image.width = 48;
    image.height = 48;
    image.style.cssText = 'border-radius:8px; object-fit:cover; flex-shrink:0; border:1px solid var(--border);';
    image.addEventListener('error', () => {
      image.style.display = 'none';
    });
    header.appendChild(image);
  } else {
    const placeholder = document.createElement('div');
    placeholder.style.cssText = 'width:48px; height:48px; border-radius:50%; flex-shrink:0; background:color-mix(in srgb, var(--brand) 12%, transparent); border:2px solid var(--brand); display:flex; align-items:center; justify-content:center; color:var(--brand);';
    const svgNs = 'http://www.w3.org/2000/svg';
    const icon = document.createElementNS(svgNs, 'svg');
    icon.setAttribute('width', '22');
    icon.setAttribute('height', '22');
    icon.setAttribute('fill', 'none');
    icon.setAttribute('stroke', 'currentColor');
    icon.setAttribute('stroke-width', '2');
    icon.setAttribute('viewBox', '0 0 24 24');

    const circle = document.createElementNS(svgNs, 'circle');
    circle.setAttribute('cx', '11');
    circle.setAttribute('cy', '11');
    circle.setAttribute('r', '8');

    const line = document.createElementNS(svgNs, 'line');
    line.setAttribute('x1', '21');
    line.setAttribute('y1', '21');
    line.setAttribute('x2', '16.65');
    line.setAttribute('y2', '16.65');

    icon.appendChild(circle);
    icon.appendChild(line);
    placeholder.appendChild(icon);
    header.appendChild(placeholder);
  }

  const titleWrap = document.createElement('div');
  titleWrap.style.cssText = 'flex:1; min-width:0;';
  const title = document.createElement('h3');
  title.style.cssText = 'margin:0; font-size:1rem; font-weight:700; color:var(--text);';
  title.textContent = 'Información encontrada';
  const subtitle = document.createElement('p');
  subtitle.style.cssText = 'margin:0.2rem 0 0; font-size:0.8rem; color:var(--text-muted);';
  subtitle.textContent = 'vía OpenFoodFacts';
  titleWrap.appendChild(title);
  titleWrap.appendChild(subtitle);
  header.appendChild(titleWrap);

  const body = document.createElement('div');
  body.style.cssText = 'padding:1.5rem; color:var(--text); font-size:.9rem; line-height:1.5;';

  const prompt = document.createElement('p');
  prompt.style.cssText = 'margin:0 0 0.75rem;';
  prompt.textContent = 'Encontramos datos para este código de barras. ¿Querés completar el formulario con esta información?';
  body.appendChild(prompt);

  const summary = document.createElement('div');
  summary.style.cssText = 'background:var(--panel-2); border-radius:8px; padding:0.75rem 1rem; font-size:0.85rem;';

  if (data.name) {
    const line = document.createElement('div');
    const strong = document.createElement('strong');
    strong.textContent = 'Nombre:';
    line.appendChild(strong);
    line.appendChild(document.createTextNode(' ' + data.name));
    summary.appendChild(line);
  }

  if (data.description) {
    const line = document.createElement('div');
    line.style.marginTop = '0.35rem';
    const strong = document.createElement('strong');
    strong.textContent = 'Descripción:';
    line.appendChild(strong);
    line.appendChild(document.createTextNode(' ' + data.description));
    summary.appendChild(line);
  }

  if (extraInfo) {
    const line = document.createElement('div');
    line.style.cssText = 'margin-top:0.35rem; color:var(--text-muted);';
    line.textContent = extraInfo;
    summary.appendChild(line);
  }

  body.appendChild(summary);

  if (someFieldsSkipped) {
    const note = document.createElement('p');
    note.style.cssText = 'margin:0.75rem 0 0; font-size:0.8rem; color:var(--text-muted);';
    note.textContent = 'Solo se completarán los campos que todavía estén vacíos.';
    body.appendChild(note);
  }

  const footer = document.createElement('div');
  footer.style.cssText = 'display:flex; gap:.75rem; padding:1rem 1.5rem; border-top:1px solid var(--border); background:var(--panel); border-radius:0 0 12px 12px;';

  const rejectBtn = document.createElement('button');
  rejectBtn.type = 'button';
  rejectBtn.id = 'autofillRejectBtn';
  rejectBtn.style.cssText = 'flex:1; padding:.65rem; border:1px solid var(--border); background:transparent; border-radius:8px; cursor:pointer; font-weight:600; font-size:.9rem; color:var(--text);';
  rejectBtn.textContent = 'No, gracias';

  const acceptBtn = document.createElement('button');
  acceptBtn.type = 'button';
  acceptBtn.id = 'autofillAcceptBtn';
  acceptBtn.style.cssText = 'flex:1; padding:.65rem; border:none; background:var(--brand); border-radius:8px; cursor:pointer; font-weight:600; font-size:.9rem; color:#fff;';
  acceptBtn.textContent = 'Completar campos';

  footer.appendChild(rejectBtn);
  footer.appendChild(acceptBtn);

  dialog.appendChild(header);
  dialog.appendChild(body);
  dialog.appendChild(footer);
  modalEl.appendChild(dialog);
  document.body.appendChild(modalEl);

  function closeAutofillModal() {
    modalEl.remove();
  }

  modalEl.addEventListener('click', (e) => {
    if (e.target.id === 'autofillModal') closeAutofillModal();
  });

  rejectBtn.addEventListener('click', closeAutofillModal);

  acceptBtn.addEventListener('click', () => {
    applyAutofill(data, { canFillName, canFillDescription });
    closeAutofillModal();
  });
}

function applyAutofill(data, flags) {
  const form = document.getElementById('product-form');
  if (!form) return;

  let filledCount = 0;

  if (flags.canFillName && data.name) {
    form.name.value = data.name;
    filledCount++;
  }
  if (flags.canFillDescription && data.description) {
    form.description.value = data.description;
    filledCount++;
  }

    if (filledCount > 0 && typeof NotificationManager !== 'undefined') {
    NotificationManager.success('Formulario completado con la información encontrada.');
  }
}

// ===== INICIAR AL CARGAR EL DOM =====
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initProductsForm);
} else {
  initProductsForm();
}