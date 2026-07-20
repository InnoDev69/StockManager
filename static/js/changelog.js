/**
 * changelog.js — Página de Novedades.
 *
 * Espera un endpoint GET que devuelva:
 *   { "changelog": ["## Changelog\n...markdown...", "..."] }
 * (el array viene ordenado del release más nuevo al más viejo, tal
 * cual lo devuelve la API de GitHub).
 *
 * Cada string es el body crudo del release. No siempre trae la
 * versión de forma explícita: las entradas viejas la tienen adentro
 * de la línea "Full Changelog: .../compare/vX...vY" (se extrae con
 * regex), pero la más nueva no tiene esa línea — para esa se usa
 * data-current-version del contenedor (ver changelog.html).
 */
(function () {
  "use strict";

  const ENDPOINT = "/api/changelog";
  const PAGE_SIZE = 5;

  const listEl = document.getElementById("changelog-list");
  const emptyEl = document.getElementById("changelog-empty");
  const loadMoreBtn = document.getElementById("changelog-load-more");

  if (!listEl) return;

  const currentVersion = listEl.dataset.currentVersion || "";
  const COMPARE_RE = /compare\/v?[\w.\-]+\.\.\.(v[\w.\-]+)/i;

  let entries = [];
  let rendered = 0;

  // ---------- markdown-lite → HTML ----------
  // Cubre lo que realmente aparece en estos release notes: encabezados
  // "## ", listas "- " / "1. ", **negrita**, `código en línea`,
  // ```bloques de código```, [links](url) y párrafos sueltos. No es un
  // parser de markdown completo a propósito — para este contenido
  // (notas de release de GitHub) alcanza y sobra.
  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function inline(text) {
    let out = escapeHtml(text);
    out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    return out;
  }

  function markdownLiteToHtml(md) {
    const lines = md.replace(/\r\n/g, "\n").split("\n");
    let html = "";
    let listType = null; // "ul" | "ol" | null
    let inCodeBlock = false;
    let codeBuffer = [];

    function closeList() {
      if (listType) {
        html += listType === "ul" ? "</ul>" : "</ol>";
        listType = null;
      }
    }

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();

      if (line.trim().startsWith("```")) {
        if (inCodeBlock) {
          html += `<pre><code>${escapeHtml(codeBuffer.join("\n"))}</code></pre>`;
          codeBuffer = [];
          inCodeBlock = false;
        } else {
          closeList();
          inCodeBlock = true;
        }
        continue;
      }
      if (inCodeBlock) {
        codeBuffer.push(rawLine);
        continue;
      }

      if (!line.trim()) {
        closeList();
        continue;
      }

      const heading = line.match(/^#{2,4}\s+(.*)$/);
      if (heading) {
        closeList();
        html += `<h4>${inline(heading[1])}</h4>`;
        continue;
      }

      const bullet = line.match(/^[-*]\s+(.*)$/);
      if (bullet) {
        if (listType !== "ul") {
          closeList();
          html += "<ul>";
          listType = "ul";
        }
        html += `<li>${inline(bullet[1])}</li>`;
        continue;
      }

      const numbered = line.match(/^\d+\.\s+(.*)$/);
      if (numbered) {
        if (listType !== "ol") {
          closeList();
          html += "<ol>";
          listType = "ol";
        }
        html += `<li>${inline(numbered[1])}</li>`;
        continue;
      }

      closeList();
      html += `<p>${inline(line)}</p>`;
    }

    closeList();
    if (inCodeBlock && codeBuffer.length) {
      html += `<pre><code>${escapeHtml(codeBuffer.join("\n"))}</code></pre>`;
    }
    return html;
  }

  // ---------- versión por entrada ----------
  function extractVersion(body, index) {
    const match = body.match(COMPARE_RE);
    if (match) return match[1];
    if (index === 0 && currentVersion) return currentVersion;
    return null;
  }

  // ---------- render ----------
  function buildCard(body, index) {
    const version = extractVersion(body, index);

    const card = document.createElement("article");
    card.className = "card changelog-card";

    const header = document.createElement("div");
    header.className = "changelog-card-header";

    const badge = document.createElement("span");
    badge.className = "badge " + (index === 0 ? "badge-success" : "");
    badge.textContent = version || (index === 0 ? "Más reciente" : "Versión anterior");
    header.appendChild(badge);

    card.appendChild(header);

    const body_el = document.createElement("div");
    body_el.className = "changelog-body";
    body_el.innerHTML = markdownLiteToHtml(body);
    card.appendChild(body_el);

    return card;
  }

  function renderNextPage() {
    const slice = entries.slice(rendered, rendered + PAGE_SIZE);
    slice.forEach((body, i) => {
      listEl.appendChild(buildCard(body, rendered + i));
    });
    rendered += slice.length;

    loadMoreBtn.hidden = rendered >= entries.length;

    if (window.FeatureHighlights) {
      window.FeatureHighlights.refresh(listEl);
    }
  }

  async function init() {
    try {
      const res = await fetch(ENDPOINT);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      entries = Array.isArray(data.changelog) ? data.changelog : [];
    } catch (err) {
      console.warn("[changelog] no se pudo cargar:", err);
      emptyEl.hidden = false;
      return;
    }

    if (!entries.length) {
      emptyEl.hidden = false;
      return;
    }

    renderNextPage();
  }

  loadMoreBtn.addEventListener("click", renderNextPage);
  init();
})();