/**
 * feature-highlights.js — Señala elementos nuevos de la UI con un tag
 * "NUEVO" pulsante y, opcionalmente, un tooltip con texto corto, hasta
 * que el usuario interactúa con el elemento una vez.
 *
 * Uso en templates (solo el atributo data-feature-id es obligatorio;
 * el JS agrega toda la clase/estructura visual solo, no hace falta
 * agregar ninguna clase CSS a mano):
 *
 *   <span data-feature-id="cloud-backup-v1_9_0"
 *         data-feature-text="Backup automático en la nube">
 *     <button class="btn">Backup en la nube</button>
 *   </span>
 *
 * data-feature-text es opcional, máximo 50 caracteres visibles (si es
 * más largo se trunca y se avisa por consola). Si no lo ponés, solo se
 * ve el tag "NUEVO" sin tooltip.
 *
 * Requiere: feature-highlights.css cargado, y el blueprint
 * feature_highlights.py registrado en la app (expone
 * GET/POST /api/ui/seen-highlights).
 */
(function () {
  "use strict";

  const SELECTOR = "[data-feature-id]";
  const ENDPOINT = "/api/ui/seen-highlights";
  const MAX_TEXT_LEN = 100;

  let seenSet = new Set();
  const pendingSaves = new Set();

  async function loadSeen() {
    try {
        const res = await fetch(ENDPOINT);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        (data.seen || []).forEach((id) => seenSet.add(id));
    } catch (err) {
      console.warn("[feature-highlights] no se pudo cargar el estado:", err);
    }
  }

  function markSeen(featureId) {
    if (pendingSaves.has(featureId)) return;
    pendingSaves.add(featureId);
    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feature_id: featureId }),
    })
      .catch((err) => console.warn("[feature-highlights] no se pudo guardar:", err))
      .finally(() => pendingSaves.delete(featureId));
  }

  function buildBadge(el, featureId, rawText) {
    el.classList.add("fh-anchor");
    el.dataset.seen = seenSet.has(featureId) ? "true" : "false";

    const badge = document.createElement("span");
    badge.className = "fh-badge";
    badge.textContent = "NUEVO";
    badge.setAttribute("aria-hidden", "true");
    el.appendChild(badge);

    if (rawText && rawText.trim()) {
      let text = rawText.trim();
      if (text.length > MAX_TEXT_LEN) {
        console.warn(
          `[feature-highlights] el texto de "${featureId}" supera ${MAX_TEXT_LEN} ` +
            `caracteres (${text.length}), se trunca.`
        );
        text = text.slice(0, MAX_TEXT_LEN - 1).trimEnd() + "…";
      }
      const tooltip = document.createElement("span");
      tooltip.className = "fh-tooltip";
      tooltip.textContent = text;
      el.appendChild(tooltip);
    }
  }

  function applyHighlights(root) {
    (root || document).querySelectorAll(SELECTOR).forEach((el) => {
      if (el.dataset.fhProcessed === "true") return;
      const featureId = el.dataset.featureId;
      if (!featureId) return;
      el.dataset.fhProcessed = "true";
      buildBadge(el, featureId, el.dataset.featureText);
    });
  }

  function getFeatureIds(root) {
    return [...(root || document).querySelectorAll(SELECTOR)]
      .map((el) => el.dataset.featureId)
      .filter(Boolean);
  }

  function onInteract(evt) {
    const el = evt.target.closest(SELECTOR);
    if (!el || el.dataset.seen === "true") return;
    const featureId = el.dataset.featureId;
    if (!featureId) return;
    el.dataset.seen = "true";
    seenSet.add(featureId);
    markSeen(featureId);
  }

  document.addEventListener("click", onInteract, true);

  document.addEventListener("DOMContentLoaded", async () => {
    const isNew = await fetch("/api/ui/is-new")
      .then((res) => (res.ok ? res.json() : { is_new: false }))
      .then((data) => Boolean(data.is_new));

    if (isNew) {
      const featureIds = [...new Set(getFeatureIds())];
      featureIds.forEach((featureId) => seenSet.add(featureId));
      applyHighlights();
      await Promise.all(featureIds.map((featureId) => markSeen(featureId)));
    } else {
        await loadSeen();
        applyHighlights();
    }
  });

  // Para vistas con contenido inyectado por AJAX (tabs, paginación):
  // llamar después de insertar el HTML nuevo en el DOM.
  window.FeatureHighlights = { refresh: applyHighlights };
})();