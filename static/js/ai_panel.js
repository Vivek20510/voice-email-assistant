const AIPanel = (() => {
  const history = [];
  let isLoading = false;
  let lastSubmittedQuery = "";
  let latestAssistantTurn = null;

  const inputEl = () => document.getElementById("ai-input");
  const resultsEl = () => document.getElementById("ai-results");
  const sendBtnEl = () => document.getElementById("ai-send-btn");
  const clearBtnEl = () => document.getElementById("ai-clear-btn");

  function emptyStateMarkup() {
    return `
      <div class="ai-placeholder">Ask about the app or your inbox.</div>

      <div class="ai-empty" id="ai-empty">
        <div class="ai-empty-icon">AI</div>

        <div class="ai-empty-text">
          Get app guidance,<br />

          navigation help, summaries,<br />

          filters, and draft support.
        </div>
      </div>
    `;
  }

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
    if (typeof HTMLElement === "undefined" || !(item instanceof HTMLElement)) {
      item.textContent = html
        .replace(/<[^>]*>/g, "")
        .replace(/\s+/g, " ")
        .trim();
    }
    resultsEl().appendChild(item);
    resultsEl().scrollTop = resultsEl().scrollHeight;
    return item;
  }

  function setStarted() {
    const results = resultsEl();
    if (!results.dataset.started) {
      results.innerHTML = "";
      results.dataset.started = "true";
    }
  }

  function setLoadingState(nextLoading) {
    isLoading = nextLoading;
    const sendButton = sendBtnEl();
    const input = inputEl();
    const clearButton = clearBtnEl();

    if (sendButton) sendButton.disabled = nextLoading;
    if (input) input.disabled = nextLoading;
    if (clearButton) clearButton.disabled = nextLoading;

    if (typeof resultsEl().querySelectorAll === "function") {
      resultsEl().querySelectorAll(".ai-regenerate-btn").forEach((button) => {
        button.disabled = nextLoading;
      });
    }
  }

  function showLoading() {
    appendTurn(
      "assistant",
      `
        <div class="ai-loading" aria-live="polite">
          <span>Thinking</span>
          <span class="ai-loading-dots" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
          </span>
        </div>
      `,
    );
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

  function trimLatestHistoryPair(query) {
    const assistantTurn = history[history.length - 1];
    const userTurn = history[history.length - 2];
    if (
      assistantTurn?.role === "assistant" &&
      userTurn?.role === "user" &&
      userTurn.content === query
    ) {
      history.pop();
      history.pop();
    }
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

  function canSkipEmailWait(query) {
    const q = String(query || "").toLowerCase().trim();
    if (/^(hello|hi|hey)(\s+(ai|assistant))?[.!?]*$/.test(q)) return true;
    return [
      "how do",
      "how can",
      "how to",
      "what can",
      "what do",
      "help",
      "explain",
      "guide",
      "connect",
      "open compose",
      "compose email",
      "new email",
      "open settings",
      "go to settings",
      "settings",
    ].some((term) => q.includes(term));
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
    if (!canSkipEmailWait(query)) {
      await waitForEmails();
    }
    const dashboardContext = activeDashboardContext();

    const response = await fetch("/api/ai-panel/query", {
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

    container.querySelectorAll(".ai-copy-btn").forEach((button) => {
      button.addEventListener("click", async () => {
        await copyText(data.response || "");
        const originalLabel = button.textContent;
        button.textContent = "Copied";
        setTimeout(() => {
          button.textContent = originalLabel;
        }, 1200);
      });
    });

    container.querySelectorAll(".ai-regenerate-btn").forEach((button) => {
      button.addEventListener("click", () => {
        regenerateLastAnswer();
      });
    });
  }

  function refreshRegenerateButtons() {
    if (typeof resultsEl().querySelectorAll !== "function") return;
    resultsEl().querySelectorAll(".ai-regenerate-btn").forEach((button) => {
      const turn = button.closest(".ai-turn");
      button.hidden = turn !== latestAssistantTurn;
      button.disabled = isLoading || turn !== latestAssistantTurn;
    });
  }

  async function copyText(text) {
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return;
      } catch {
        // Fall back to the hidden textarea path below.
      }
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }

  function renderAssistant(data, options = {}) {
    clearLoading();
    const cards = Array.isArray(data.cards) ? data.cards : data.emails || [];
    const text = data.response || "No response from server.";
    const container = appendTurn(
      "assistant",
      `
        <div class="ai-response">
          <div class="ai-response-body">${formatText(text)}</div>
          <div class="ai-response-toolbar">
            <button class="ai-tool-btn ai-copy-btn" type="button" title="Copy response">Copy</button>
            <button class="ai-tool-btn ai-regenerate-btn" type="button" title="Regenerate answer">Regenerate</button>
          </div>
        </div>
        ${renderCards(cards)}
        ${renderActions(data.actions)}
      `,
    );
    if (options.trackLatest !== false) {
      latestAssistantTurn = container;
    }
    bindRenderedControls(container, data);
    refreshRegenerateButtons();
  }

  async function submitQuery(query, options = {}) {
    if (isLoading || !query) return;
    setStarted();
    setLoadingState(true);
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
      lastSubmittedQuery = query;

      if (Array.isArray(data.actions)) {
        data.actions.forEach((action) => executeAction(action));
      }
    } catch (err) {
      showError(err.message || "Server error");
    } finally {
      setLoadingState(false);
      if (!options.keepInputDisabled) {
        inputEl()?.focus();
      }
    }
  }

  async function sendQuery() {
    const input = inputEl();
    if (isLoading || !input) return;
    const query = input.value.trim();
    if (!query) return;

    setStarted();
    appendTurn(
      "user",
      `<div class="ai-user-bubble">${formatText(query)}</div>`,
    );
    input.value = "";
    await submitQuery(query);
  }

  async function regenerateLastAnswer() {
    if (isLoading || !lastSubmittedQuery || !latestAssistantTurn) return;

    trimLatestHistoryPair(lastSubmittedQuery);
    latestAssistantTurn.remove();
    latestAssistantTurn = null;
    await submitQuery(lastSubmittedQuery);
  }

  function clearConversation() {
    if (isLoading) return;
    history.length = 0;
    lastSubmittedQuery = "";
    latestAssistantTurn = null;
    resultsEl().innerHTML = emptyStateMarkup();
    delete resultsEl().dataset.started;
    const input = inputEl();
    if (input) {
      input.value = "";
      input.focus();
    }
    refreshRegenerateButtons();
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
    clearConversation,
    regenerateLastAnswer,
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

function clearAiConversation() {
  AIPanel.clearConversation();
}
