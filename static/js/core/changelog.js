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

  function appendInlineContent(parent, text) {
    const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))/g;
    let lastIndex = 0;

    for (let match = pattern.exec(text); match; match = pattern.exec(text)) {
      if (match.index > lastIndex) {
        parent.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      }

      const token = match[0];
      if (token.startsWith("`")) {
        const code = document.createElement("code");
        code.textContent = token.slice(1, -1);
        parent.appendChild(code);
      } else if (token.startsWith("**")) {
        const strong = document.createElement("strong");
        strong.textContent = token.slice(2, -2);
        parent.appendChild(strong);
      } else {
        const link = document.createElement("a");
        link.textContent = match[2];
        link.href = match[3];
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        parent.appendChild(link);
      }

      lastIndex = pattern.lastIndex;
    }

    if (lastIndex < text.length) {
      parent.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
  }

  function markdownLiteToFragment(md) {
    const lines = md.replace(/\r\n/g, "\n").split("\n");
    const fragment = document.createDocumentFragment();
    let listType = null;
    let listEl = null;
    let inCodeBlock = false;
    let codeBuffer = [];

    function closeList() {
      if (listType) {
        listType = null;
        listEl = null;
      }
    }

    function openList(type) {
      if (listType !== type) {
        closeList();
        listType = type;
        listEl = document.createElement(type);
        fragment.appendChild(listEl);
      }
    }

    function appendListItem(text) {
      const li = document.createElement("li");
      appendInlineContent(li, text);
      listEl.appendChild(li);
    }

    function appendHeading(text) {
      const heading = document.createElement("h4");
      appendInlineContent(heading, text);
      fragment.appendChild(heading);
    }

    function appendParagraph(text) {
      const paragraph = document.createElement("p");
      appendInlineContent(paragraph, text);
      fragment.appendChild(paragraph);
    }

    function appendCodeBlock(buffer) {
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = buffer.join("\n");
      pre.appendChild(code);
      fragment.appendChild(pre);
    }

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();

      if (line.trim().startsWith("```")) {
        if (inCodeBlock) {
          appendCodeBlock(codeBuffer);
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
        appendHeading(heading[1]);
        continue;
      }

      const bullet = line.match(/^[-*]\s+(.*)$/);
      if (bullet) {
        openList("ul");
        appendListItem(bullet[1]);
        continue;
      }

      const numbered = line.match(/^\d+\.\s+(.*)$/);
      if (numbered) {
        openList("ol");
        appendListItem(numbered[1]);
        continue;
      }

      closeList();
      appendParagraph(line);
    }

    closeList();
    if (inCodeBlock && codeBuffer.length) {
      appendCodeBlock(codeBuffer);
    }

    return fragment;
  }

  function extractVersion(body, index) {
    const match = body.match(COMPARE_RE);
    if (match) return match[1];
    if (index === 0 && currentVersion) return currentVersion;
    return null;
  }

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

    const bodyEl = document.createElement("div");
    bodyEl.className = "changelog-body";
    bodyEl.appendChild(markdownLiteToFragment(body));
    card.appendChild(bodyEl);

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