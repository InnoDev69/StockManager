/**
 * feature-highlights.js — Señala elementos nuevos de la UI con un tag
 * "NUEVO" pulsante, aura neón y, opcionalmente, un tooltip corto, hasta
 * que el usuario interactúa con el elemento una vez.
 *
 * MODO 1 — declarativo, vía atributos en el template (el JS escanea el
 * documento solo al cargar):
 *
 *   <span data-feature-id="cloud-backup-v1_9_0"
 *         data-feature-text="Backup automático en la nube"
 *         data-feature-glow="rainbow">
 *     <button class="btn">Backup en la nube</button>
 *   </span>
 *
 *   - data-feature-id: obligatorio, único y estable (se usa para
 *     recordar si el usuario ya lo vio). Convención sugerida:
 *     "<slug>-v<version>".
 *   - data-feature-text: opcional, tooltip, máximo 50 caracteres
 *     visibles (se trunca solo si es más largo, con warning).
 *   - data-feature-glow: opcional. "rainbow" (default si se omite),
 *     "random", o cualquier color CSS válido ("#22d3ee", "lime", ...).
 *
 * MODO 2 — programático, desde otro script o la consola del navegador,
 * sin tocar el HTML:
 *
 *   FeatureHighlights.highlight(elementoOSelector, {
 *     featureId: "cloud-backup-v1_9_0",   // opcional pero recomendado
 *     text: "Backup automático en la nube", // opcional
 *     glow: "random",                       // opcional, default "rainbow"
 *   });
 *
 *   Ejemplos rápidos desde la consola:
 *     FeatureHighlights.highlight("#btn-exportar-pdf");
 *     FeatureHighlights.highlight(document.querySelector(".card-backup"), { glow: "#22d3ee" });
 *
 *   Si no pasás featureId y el elemento tampoco tiene data-feature-id,
 *   se genera uno al azar: sirve para probar el efecto, pero no va a
 *   "recordarse" como visto entre recargas (cada vez sería un id
 *   distinto). Para eso pasá siempre un featureId fijo.
 *
 *   También existe FeatureHighlights.clear(elementoOSelector) para
 *   sacarle el highlight a un elemento a mano (por ejemplo, para
 *   probar el efecto de nuevo sin esperar a que cambie de versión).
 *
 * Requiere: feature-highlights.css cargado, y el blueprint
 * feature_highlights.py registrado en la app (expone
 * GET/POST /api/ui/seen-highlights).
 */
(function () {
  "use strict";

  const SELECTOR = "[data-feature-id]";
  const ENDPOINT = "/api/ui/seen-highlights";
  const MAX_TEXT_LEN = 50;

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

  // Promesa única: tanto el escaneo automático como highlight() llamado
  // a mano (ej: desde la consola, apenas cargó la página) esperan a que
  // el estado "visto" esté cargado antes de decidir si mostrar o no.
  const ready = loadSeen();

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

  function applyGlow(el) {
    const raw = (el.dataset.featureGlow || "#2aa5f7").trim().toLowerCase();

    if (raw === "rainbow" || raw === "") {
      el.dataset.glow = "rainbow";
      return;
    }

    if (raw === "random") {
      el.dataset.glow = "random";
      const hue = Math.floor(Math.random() * 360);
      el.style.setProperty("--fh-glow-color", `hsl(${hue}, 95%, 60%)`);
      return;
    }

    // Cualquier otro valor se toma como color CSS sólido
    // (ej: "#22d3ee", "lime", "rgb(255,0,128)").
    el.dataset.glow = "solid";
    el.style.setProperty("--fh-glow-color", raw);
  }

  function resolveElement(target) {
    if (typeof target === "string") {
      const el = document.querySelector(target);
      if (!el) {
        console.warn(`[feature-highlights] no se encontró ningún elemento para "${target}"`);
      }
      return el;
    }
    if (target instanceof Element) return target;
    console.warn("[feature-highlights] target inválido, debe ser un Element o un selector CSS:", target);
    return null;
  }

  function generateFeatureId() {
    return `manual-${Math.random().toString(36).slice(2, 10)}`;
  }

  function buildBadge(el, featureId, rawText) {
    el.classList.add("fh-anchor");
    el.dataset.featureId = featureId;
    el.dataset.seen = seenSet.has(featureId) ? "true" : "false";
    el.dataset.fhProcessed = "true";
    applyGlow(el);

    // Por si ya tenía badge/tooltip de un highlight() previo sobre el
    // mismo elemento (ej: llamado dos veces desde la consola).
    el.querySelectorAll(":scope > .fh-badge, :scope > .fh-tooltip").forEach((n) => n.remove());

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
    const scope = root || document;
    const nodes = scope.matches && scope.matches(SELECTOR)
      ? [scope, ...scope.querySelectorAll(SELECTOR)]
      : [...scope.querySelectorAll(SELECTOR)];

    nodes.forEach((el) => {
      if (el.dataset.fhProcessed === "true") return;
      const featureId = el.dataset.featureId;
      if (!featureId) return;
      buildBadge(el, featureId, el.dataset.featureText);
    });
  }

  function onInteract(evt) {
    const el = evt.target.closest(SELECTOR);
    if (!el || el.dataset.seen === "true") return;
    const featureId = el.dataset.featureId;
    if (!featureId) return;
    // No se bloquea el click original: el usuario usa el feature con
    // normalidad, solo se apaga el tag/tooltip/aura.
    el.dataset.seen = "true";
    seenSet.add(featureId);
    markSeen(featureId);
  }

  // Captura, para agarrar el click aunque el feature tenga handlers
  // propios que corten la propagación en fase de burbuja.
  document.addEventListener("click", onInteract, true);

  document.addEventListener("DOMContentLoaded", async () => {
    await ready;
    applyHighlights();
  });

  /**
   * API pública, para uso programático (otro script o consola).
   * Aplica el highlight a un elemento puntual sin necesidad de que
   * esté escrito en el template.
   */
  async function highlight(target, options = {}) {
    const el = resolveElement(target);
    if (!el) return null;

    await ready;

    let featureId = options.featureId || el.dataset.featureId;
    if (!featureId) {
      featureId = generateFeatureId();
      console.warn(
        `[feature-highlights] no se pasó featureId, se generó "${featureId}". ` +
          `No va a persistir como "visto" entre recargas de página; pasá ` +
          `{ featureId: "algo-fijo" } si lo necesitás recordar.`
      );
    }

    if (options.text) el.dataset.featureText = options.text;
    if (options.glow) el.dataset.featureGlow = options.glow;

    el.dataset.fhProcessed = "false"; // permite re-procesar si ya se había tocado antes
    buildBadge(el, featureId, el.dataset.featureText);

    return el;
  }

  /** Saca el highlight de un elemento a mano (sin marcarlo como visto en el server). */
  function clear(target) {
    const el = resolveElement(target);
    if (!el) return;
    el.querySelectorAll(":scope > .fh-badge, :scope > .fh-tooltip").forEach((n) => n.remove());
    el.classList.remove("fh-anchor");
    delete el.dataset.seen;
    delete el.dataset.glow;
    delete el.dataset.fhProcessed;
    el.style.removeProperty("--fh-glow-color");
  }

  // Para vistas con contenido inyectado por AJAX (tabs, paginación):
  // llamar refresh(root) después de insertar el HTML nuevo en el DOM.
  window.FeatureHighlights = { refresh: applyHighlights, highlight, clear };
})();