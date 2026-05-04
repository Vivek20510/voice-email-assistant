(function () {
  const DEFAULT_SUMMARY_URL = "/nlp/summarize";
  const EMPTY_SUMMARY = "No message content is available to summarize.";
  const ERROR_SUMMARY =
    "Summary is temporarily unavailable. Please review the message body below.";
  const LOADING_SUMMARY = "Generating summary...";
  const SUMMARY_REQUEST_TIMEOUT_MS = 35000;
  const summaryCache = new Map();
  const inFlightByElement = new WeakMap();

  function setSummaryState(summaryEl, state, text) {
    summaryEl.dataset.state = state;
    summaryEl.textContent = text;
  }

  function cleanValue(value) {
    return String(value || "").trim();
  }

  function buildPayload(summaryEl) {
    return {
      subject: cleanValue(summaryEl.dataset.subject),
      sender: cleanValue(summaryEl.dataset.sender),
      body: cleanValue(summaryEl.dataset.body),
    };
  }

  function buildCacheKey(url, payload) {
    return JSON.stringify({
      url,
      subject: payload.subject,
      sender: payload.sender,
      body: payload.body,
    });
  }

  function cancelElementRequest(summaryEl) {
    const activeRequest = inFlightByElement.get(summaryEl);
    if (activeRequest) {
      window.clearTimeout(activeRequest.timeoutId);
      activeRequest.abortController.abort();
      inFlightByElement.delete(summaryEl);
    }
  }

  async function loadEmailSummary(summaryEl) {
    if (!summaryEl || summaryEl.dataset.state === "ready") {
      return;
    }

    const payload = buildPayload(summaryEl);
    if (!payload.subject && !payload.body) {
      cancelElementRequest(summaryEl);
      setSummaryState(summaryEl, "empty", EMPTY_SUMMARY);
      return;
    }

    const summaryUrl = summaryEl.dataset.summaryUrl || DEFAULT_SUMMARY_URL;
    const cacheKey = buildCacheKey(summaryUrl, payload);
    const cachedSummary = summaryCache.get(cacheKey);
    if (cachedSummary) {
      cancelElementRequest(summaryEl);
      setSummaryState(summaryEl, "ready", cachedSummary);
      return;
    }

    const activeRequest = inFlightByElement.get(summaryEl);
    if (activeRequest) {
      if (activeRequest.cacheKey === cacheKey) {
        return;
      }
      activeRequest.abortController.abort();
    }

    const abortController = new AbortController();
    const timeoutId = window.setTimeout(() => {
      abortController.abort();
    }, SUMMARY_REQUEST_TIMEOUT_MS);
    inFlightByElement.set(summaryEl, { abortController, cacheKey, timeoutId });
    setSummaryState(summaryEl, "loading", LOADING_SUMMARY);

    try {
      const response = await fetch(summaryUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        credentials: "same-origin",
        body: JSON.stringify(payload),
        signal: abortController.signal,
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok || !data.summary) {
        throw new Error(data.error || "Summary request failed.");
      }

      if (inFlightByElement.get(summaryEl)?.cacheKey !== cacheKey) {
        return;
      }

      summaryCache.set(cacheKey, data.summary);
      setSummaryState(summaryEl, "ready", data.summary);
    } catch (error) {
      if (error.name === "AbortError") {
        console.warn("Email summary fetch timed out or was cancelled.", error);
        if (inFlightByElement.get(summaryEl)?.cacheKey === cacheKey) {
          setSummaryState(summaryEl, "error", ERROR_SUMMARY);
        }
        return;
      }
      console.warn("Email summary fetch failed.", error);
      setSummaryState(summaryEl, "error", ERROR_SUMMARY);
    } finally {
      const activeRequest = inFlightByElement.get(summaryEl);
      if (activeRequest?.cacheKey === cacheKey) {
        window.clearTimeout(activeRequest.timeoutId);
        inFlightByElement.delete(summaryEl);
      }
    }
  }

  function initEmailSummaries(root) {
    const scope = root || document;
    scope
      .querySelectorAll("[data-summary-url][data-state]")
      .forEach((summaryEl) => loadEmailSummary(summaryEl));
  }

  window.EmailSummary = {
    cancel: cancelElementRequest,
    clearCache: () => summaryCache.clear(),
    init: initEmailSummaries,
    load: loadEmailSummary,
  };

  document.addEventListener("DOMContentLoaded", () => {
    initEmailSummaries();
  });
})();
