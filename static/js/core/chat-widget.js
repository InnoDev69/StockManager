(() => {
  const widget = document.querySelector('[data-chat-widget]');
  if (!widget) return;

  const trigger = widget.querySelector('[data-chat-trigger]');
  const panel = widget.querySelector('[data-chat-panel]');
  const close = widget.querySelector('[data-chat-close]');
  const form = widget.querySelector('[data-chat-form]');
  const input = widget.querySelector('[data-chat-input]');
  const messages = widget.querySelector('[data-chat-messages]');

  const sessionKey = 'stockly_chat_session_id';
  let sessionId = localStorage.getItem(sessionKey);

  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(sessionKey, sessionId);
  }

  function setOpen(open) {
    panel.hidden = !open;
    trigger.setAttribute('aria-expanded', String(open));

    if (open) {
      input.focus();
      messages.scrollTop = messages.scrollHeight;
    }
  }

  function addMessage(text, type) {
    const message = document.createElement('div');
    message.className = `chat-message chat-message--${type}`;
    message.textContent = text;
    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
  }

  function setLoading(loading) {
    input.disabled = loading;
    form.querySelector('button').disabled = loading;
  }

  trigger.addEventListener('click', (event) => {
    event.stopPropagation();
    setOpen(panel.hidden);
  });

  close.addEventListener('click', () => {
    setOpen(false);
    trigger.focus();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const message = input.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    input.value = '';
    setLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message,
          session_id: sessionId
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'No se pudo consultar StocklyBot.');
      }
      const confidence = Number(data.confidence);
      const confidenceText = Number.isFinite(confidence)
        ? `\n\nConfianza: ${(confidence * 100).toFixed(1)}%`
        : '';

      /*addMessage(`${data.text}${confidenceText}`, 'bot');
      addMessage(`Entidades: ${JSON.stringify(data.entities)}`, 'bot');
      addMessage(`Decisión: ${data.decision}`, 'bot');
      addMessage(`Debug: ${JSON.stringify(data.debug)}`, 'bot');
      */

      addMessage(data.text, 'bot');

    } catch (error) {
      addMessage(error.message, 'error');
    } finally {
      setLoading(false);
      input.focus();
    }
  });

  document.addEventListener('click', (event) => {
    if (!widget.contains(event.target)) {
      setOpen(false);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      setOpen(false);
    }
  });
})();