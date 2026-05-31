const AIPanel = (() => {
  const history = [];
  let isLoading = false;
  let canStopGeneration = false;
  let activeAIRequest = null;
  let nextRequestId = 0;
  let lastSubmittedQuery = "";
  let latestAssistantTurn = null;

  const inputEl = () => document.getElementById("ai-input");
  const resultsEl = () => document.getElementById("ai-results");
  const sendBtnEl = () => document.getElementById("ai-send-btn");
  const clearBtnEl = () => document.getElementById("ai-clear-btn");
  const askBtnEl = () => document.getElementById("ai-ask-btn");

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

  function setLoadingState(nextLoading, options = {}) {
    isLoading = nextLoading;
    canStopGeneration = nextLoading && options.canStopGeneration === true;
    const sendButton = sendBtnEl();
    const input = inputEl();
    const clearButton = clearBtnEl();
    const askButton = askBtnEl();
    const results = resultsEl();

    if (sendButton) {
      sendButton.disabled = nextLoading && !canStopGeneration;
      sendButton.classList?.toggle("ai-stop-btn", canStopGeneration);
      sendButton.textContent = canStopGeneration ? "■" : "↑";
      sendButton.title = canStopGeneration ? "Stop generating" : "Send message";
      sendButton.setAttribute?.(
        "aria-label",
        canStopGeneration ? "Stop generating" : "Send message",
      );
    }
    if (input) input.disabled = nextLoading;
    if (clearButton) clearButton.disabled = nextLoading;
    if (askButton) askButton.disabled = nextLoading;
    results?.setAttribute?.("aria-busy", String(nextLoading));

    if (typeof document.querySelectorAll === "function") {
      document.querySelectorAll(".ai-chip").forEach((button) => {
        button.disabled = nextLoading;
      });
    }

    if (typeof resultsEl().querySelectorAll === "function") {
      resultsEl()
        .querySelectorAll(".ai-regenerate-btn")
        .forEach((button) => {
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

  function showStopped() {
    clearLoading();
    appendTurn(
      "assistant",
      `<div class="ai-stopped" role="status">Response stopped.</div>`,
    );
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

  function abortError() {
    const error = new Error("Request aborted");
    error.name = "AbortError";
    return error;
  }

  function wait(ms, signal) {
    if (signal?.aborted) return Promise.reject(abortError());
    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(resolve, ms);
      signal?.addEventListener(
        "abort",
        () => {
          clearTimeout(timeoutId);
          reject(abortError());
        },
        { once: true },
      );
    });
  }

  async function waitForEmails(signal) {
    let retries = 10;
    while (
      (!window.currentEmails || window.currentEmails.length === 0) &&
      retries > 0
    ) {
      await wait(300, signal);
      retries--;
    }
  }

  function canSkipEmailWait(query) {
    const q = String(query || "")
      .toLowerCase()
      .trim();
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

  async function fetchAI(query, signal) {
    if (!canSkipEmailWait(query)) {
      await waitForEmails(signal);
    }
    if (signal?.aborted) throw abortError();
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
      signal,
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
    resultsEl()
      .querySelectorAll(".ai-regenerate-btn")
      .forEach((button) => {
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
    const requestState = {
      controller: new AbortController(),
      id: ++nextRequestId,
      stopped: false,
    };
    activeAIRequest = requestState;
    setStarted();
    setLoadingState(true, { canStopGeneration: true });
    showLoading();

    try {
      const data = await fetchAI(query, requestState.controller.signal);
      if (activeAIRequest !== requestState || requestState.stopped) return;
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
      if (err?.name === "AbortError") {
        if (activeAIRequest === requestState && !requestState.stopped) {
          showStopped();
        }
        return;
      }
      if (activeAIRequest !== requestState || requestState.stopped) return;
      showError(err.message || "Server error");
    } finally {
      if (activeAIRequest === requestState) {
        activeAIRequest = null;
        setLoadingState(false);
        if (!options.keepInputDisabled) {
          inputEl()?.focus();
        }
      }
    }
  }

  function stopGeneration() {
    const requestState = activeAIRequest;
    if (!requestState || !canStopGeneration) return;
    requestState.stopped = true;
    activeAIRequest = null;
    requestState.controller.abort();
    showStopped();
    setLoadingState(false);
    inputEl()?.focus();
  }

  function handlePrimaryAction() {
    if (canStopGeneration) {
      stopGeneration();
      return;
    }
    sendQuery();
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
    if (isLoading) return;
    inputEl().value = text;
    inputEl().focus();
  }

  // ------------------------------------------------
  // VOICE: record → transcribe → submit
  // ------------------------------------------------

  let _mediaRecorder = null;
  let _speechRecognition = null;
  let _audioChunks = [];
  let _isRecording = false;
  const RECORD_MAX_MS = 10000;

  function _setAskBtnLabel(recording) {
    const btn = document.getElementById("ai-ask-btn");
    if (!btn) return;
    btn.textContent = recording ? "⏹ Stop" : "🎤 Ask";
    btn.title = recording ? "Stop recording" : "Ask with voice";
    btn.setAttribute?.(
      "aria-label",
      recording ? "Stop recording" : "Ask with voice",
    );
    // reuse existing hover style — just swap background inline while recording
    btn.style.background = recording ? "#fee2e2" : "";
    btn.style.borderColor = recording ? "#ef4444" : "";
    btn.style.color = recording ? "#dc2626" : "";
  }

  function _showVoiceStatus(msg) {
    setStarted();
    appendTurn(
      "assistant",
      `<div class="ai-error" style="background:#f0f9ff;border-color:#bae6fd;color:#0369a1;">${escapeHtml(msg)}</div>`,
    );
  }

  async function askWithVoice() {
    // Toggle stop if already recording
    if (_isRecording) {
      if (_speechRecognition) {
        _speechRecognition.stop();
      } else {
        _mediaRecorder?.stop();
      }
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      _askWithBrowserSpeech(SpeechRecognition);
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      _showVoiceStatus(
        "Your browser does not support microphone access. Please type your query.",
      );
      return;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      _showVoiceStatus(
        "Microphone access denied. Please allow microphone permissions and try again.",
      );
      return;
    }

    _audioChunks = [];
    _isRecording = true;
    _setAskBtnLabel(true);
    _showVoiceStatus("🎤 Recording… click Stop or wait 10 seconds.");

    const mimeType = MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "";

    _mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});

    _mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) _audioChunks.push(e.data);
    };

    _mediaRecorder.onstop = async () => {
      _isRecording = false;
      _setAskBtnLabel(false);
      stream.getTracks().forEach((t) => t.stop());

      const blob = new Blob(_audioChunks, {
        type: mimeType || "audio/webm",
      });
      await _uploadAndTranscribe(blob);
    };

    const autoStop = setTimeout(() => {
      if (_isRecording) _mediaRecorder.stop();
    }, RECORD_MAX_MS);

    _mediaRecorder.addEventListener("stop", () => clearTimeout(autoStop), {
      once: true,
    });

    _mediaRecorder.start();
  }

  function _askWithBrowserSpeech(SpeechRecognition) {
    const recognition = new SpeechRecognition();
    _speechRecognition = recognition;
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;

    recognition.onstart = () => {
      _isRecording = true;
      _setAskBtnLabel(true);
      _showVoiceStatus("Listening... click Stop when you finish.");
    };

    recognition.onresult = async (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();
      await _submitTranscript(transcript);
    };

    recognition.onerror = (event) => {
      const denied =
        event.error === "not-allowed" || event.error === "service-not-allowed";
      _showVoiceStatus(
        denied
          ? "Microphone access denied. Please allow microphone permissions and try again."
          : "Could not hear anything. Please try again or type your query.",
      );
    };

    recognition.onend = () => {
      _speechRecognition = null;
      _isRecording = false;
      _setAskBtnLabel(false);
    };

    try {
      recognition.start();
    } catch (err) {
      _speechRecognition = null;
      _isRecording = false;
      _setAskBtnLabel(false);
      _showVoiceStatus("Voice recognition could not start. Please try again.");
    }
  }

  async function _submitTranscript(transcript) {
    if (!transcript) {
      _showVoiceStatus(
        "Could not hear anything. Please try again or type your query.",
      );
      setLoadingState(false);
      return;
    }

    setStarted();
    appendTurn(
      "user",
      `<div class="ai-user-bubble">${escapeHtml(transcript)}</div>`,
    );

    const input = inputEl();
    if (input) input.value = "";

    setLoadingState(false);
    await submitQuery(transcript);
  }

  async function _uploadAndTranscribe(blob) {
    setLoadingState(true);

    // Remove voice status messages
    resultsEl()
      ?.querySelectorAll(".ai-turn")
      .forEach((turn) => {
        if (turn.querySelector("[style*='#0369a1']")) turn.remove();
      });

    try {
      const form = new FormData();
      form.append("audio", blob, "recording.webm");

      const resp = await fetch("/api/voice/transcribe", {
        method: "POST",
        body: form,
      });

      const data = await resp.json();

      if (!resp.ok || !data.success) {
        _showVoiceStatus(
          data.error || "Transcription failed. Please type your query.",
        );
        setLoadingState(false);
        return;
      }

      await _submitTranscript((data.transcript || "").trim());
    } catch (err) {
      _showVoiceStatus(
        "Network error during transcription. Please type your query.",
      );
      setLoadingState(false);
    }
  }

  return {
    sendQuery,
    handleKey,
    prefill,
    clearConversation,
    regenerateLastAnswer,
    askWithVoice,
    handlePrimaryAction,
    stopGeneration,
    history,
  };
})();

if (typeof window !== "undefined") {
  window.AIPanel = AIPanel;
}

function sendAiQuery() {
  AIPanel.handlePrimaryAction();
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

function askAiWithVoice() {
  AIPanel.askWithVoice();
}
