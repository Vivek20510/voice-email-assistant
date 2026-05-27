const AIPanel = (() => {
  const history = [];

  const inputEl = () => document.getElementById("ai-input");
  const resultsEl = () => document.getElementById("ai-results");

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatText(text) {
    return escapeHtml(text || "")
      .replace(/\n/g, "<br>")
      .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
  }

  function appendTurn(role, html) {
    const item = document.createElement("div");
    item.className = `ai-turn ai-turn-${role}`;
    item.innerHTML = html;
    item.textContent = html
      .replace(/<[^>]*>/g, "")
      .replace(/\s+/g, " ")
      .trim();
    resultsEl().appendChild(item);
    resultsEl().scrollTop = resultsEl().scrollHeight;
    return item;
  }

  function showLoading() {
    appendTurn("assistant", `<div class="ai-loading">Thinking...</div>`);
  }

  function clearLoading() {
    if (typeof resultsEl().querySelector !== "function") return;
    const loading = resultsEl()
      .querySelector(".ai-loading")
      ?.closest(".ai-turn");
    if (loading) loading.remove();
  }

  function showError(msg) {
    clearLoading();
    appendTurn("assistant", `<div class="ai-error">${escapeHtml(msg)}</div>`);
  }

  async function waitForEmails() {
    let retries = 10;
    while (
      (!window.currentEmails || window.currentEmails.length === 0) &&
      retries > 0
    ) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      retries--;
    }
  }

  function activeDashboardContext() {
    const commandCenter = window.AICommandCenter || {};
    return {
      active_view:
        commandCenter.getActiveView?.() ||
        window.currentDashboardView ||
        "sb-inbox",
      active_message_id:
        commandCenter.getActiveMessageId?.() || window.activeMessageId || "",
    };
  }

  async function fetchAI(query) {
    await waitForEmails();
    const dashboardContext = activeDashboardContext();

    const response = await fetch("/nlp/ai-query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        emails: window.currentEmails || [],
        history: history.slice(-12),
        active_view: dashboardContext.active_view,
        active_message_id: dashboardContext.active_message_id,
      }),
    });

    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.error || `API error: ${response.status}`);
    }

    return data;
  }

  function actionPayload(action) {
    return action && typeof action.payload === "object" ? action.payload : {};
  }

  function executeAction(action) {
    const commandCenter = window.AICommandCenter || {};
    const payload = actionPayload(action);

    if (action.type === "open_settings") {
      return commandCenter.navigate?.({ target: "settings", ...payload });
    }
    if (action.type === "open_compose") {
      return commandCenter.navigate?.({ target: "compose", ...payload });
    }
    if (action.type === "prefill_compose") {
      return commandCenter.prefillCompose?.(payload);
    }
    if (action.type === "open_message") {
      return commandCenter.openMessage?.(payload);
    }
    if (action.type === "filter_view") {
      return commandCenter.applyFilter?.(payload);
    }
    if (action.type === "mark_read_local") {
      return commandCenter.markReadLocal?.(payload);
    }
    if (action.type === "summarize_message") {
      if (!payload.message_id) return false;
      commandCenter.openMessage?.(payload);
      return true;
    }

    return false;
  }

  function cardMarkup(card) {
    const meta = [
      card.channel ? card.channel.toUpperCase() : "",
      card.unread ? "Unread" : "",
      card.has_attachments ? "Attachment" : "",
    ]
      .filter(Boolean)
      .join(" · ");

    return `
      <button class="ai-card" type="button" data-message-id="${escapeHtml(card.id)}">
        <span class="ai-card-subject">${escapeHtml(card.subject || "No subject")}</span>
        <span class="ai-card-sender">${escapeHtml(card.sender || "Unknown sender")}</span>
        <span class="ai-card-snippet">${escapeHtml(card.snippet || "")}</span>
        <span class="ai-card-meta">${escapeHtml(meta)}</span>
      </button>
    `;
  }

  function renderCards(cards) {
    if (!Array.isArray(cards) || !cards.length) return "";
    return `<div class="ai-card-list">${cards.map(cardMarkup).join("")}</div>`;
  }

  function renderActions(actions) {
    if (!Array.isArray(actions) || !actions.length) return "";
    return `
      <div class="ai-action-row">
        ${actions
          .map(
            (action, index) =>
              `<button class="ai-action-btn" type="button" data-action-index="${index}">${escapeHtml(
                action.label || action.type,
              )}</button>`,
          )
          .join("")}
      </div>
    `;
  }

  function bindRenderedControls(container, data) {
    if (typeof container.querySelectorAll !== "function") return;
    container.querySelectorAll(".ai-card").forEach((cardEl) => {
      cardEl.addEventListener("click", () => {
        const messageId = cardEl.dataset.messageId;
        if (messageId) {
          executeAction({
            type: "open_message",
            payload: { message_id: messageId },
          });
        }
      });
    });

    container.querySelectorAll(".ai-action-btn").forEach((button) => {
      button.addEventListener("click", () => {
        const action = data.actions?.[Number(button.dataset.actionIndex)];
        if (action) executeAction(action);
      });
    });
  }

  function renderAssistant(data) {
    clearLoading();
    const cards = Array.isArray(data.cards) ? data.cards : data.emails || [];
    const text = data.response || "No response from server.";
    const container = appendTurn(
      "assistant",
      `
        <div class="ai-response">${formatText(text)}</div>
        ${renderCards(cards)}
        ${renderActions(data.actions)}
      `,
    );
    bindRenderedControls(container, data);
  }

  async function sendQuery() {
    const input = inputEl();
    const query = input.value.trim();
    if (!query) return;

    resultsEl().dataset = resultsEl().dataset || {};
    if (!resultsEl().dataset.started) {
      resultsEl().innerHTML = "";
      resultsEl().dataset.started = "true";
    }

    appendTurn(
      "user",
      `<div class="ai-user-bubble">${formatText(query)}</div>`,
    );
    input.value = "";
    showLoading();

    try {
      const data = await fetchAI(query);
      if (!data || data.success === false) {
        showError(data?.error || "No response from server");
        return;
      }

      renderAssistant(data);
      history.push({ role: "user", content: query });
      history.push({ role: "assistant", content: data.response || "" });

      if (Array.isArray(data.actions)) {
        data.actions.forEach((action) => executeAction(action));
      }
    } catch (err) {
      showError(err.message || "Server error");
    }
  }

  function handleKey(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      sendQuery();
    }
  }

  function prefill(text) {
    inputEl().value = text;
    inputEl().focus();
  }

  return {
    sendQuery,
    handleKey,
    prefill,
    history,
  };
})();

if (typeof window !== "undefined") {
  window.AIPanel = AIPanel;
}

function sendAiQuery() {
  AIPanel.sendQuery();
}

function handleAiKey(event) {
  AIPanel.handleKey(event);
}

function prefillAi(text) {
  AIPanel.prefill(text);
}
