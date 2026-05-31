(function () {
  const cache = new Map();
  const activeLoads = new WeakMap();
  const REQUEST_TIMEOUT_MS = 15000;
  const EMPTY_TEXT = "No message content is available to summarize.";
  const ERROR_TEXT =
    "Summary is temporarily unavailable. Please review the message body below.";

  function clean(value) {
    return String(value || "").trim();
  }

  function signatureFor(el) {
    const data = el.dataset || {};
    let preferredLanguage = "English";
    try {
      preferredLanguage = localStorage.getItem("preferred_language") || "English";
    } catch {}
    return JSON.stringify({
      url: data.summaryUrl || "/nlp/summarize",
      preferredLanguage,
      subject: clean(data.subject),
      sender: clean(data.sender),
      body: clean(data.body),
    });
  }

  function payloadFor(el) {
    const data = el.dataset || {};
    return {
      subject: clean(data.subject),
      sender: clean(data.sender),
      body: clean(data.body),
    };
  }

  async function load(el) {
    if (!el) return;

    const payload = payloadFor(el);
    if (!payload.subject && !payload.sender && !payload.body) {
      el.dataset.state = "empty";
      el.textContent = EMPTY_TEXT;
      return;
    }

    const signature = signatureFor(el);
    const cached = cache.get(signature);
    if (cached) {
      el.dataset.state = "ready";
      el.textContent = cached;
      return cached;
    }

    const existing = activeLoads.get(el);
    if (existing) {
      if (existing.signature === signature) return existing.promise;
      existing.controller.abort();
    }

    const url = el.dataset.summaryUrl || "/nlp/summarize";
    const controller = new AbortController();
    const timeoutId = window.setTimeout(
      () => controller.abort(),
      REQUEST_TIMEOUT_MS,
    );

    const promise = fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("summary failed");
        const data = await response.json();
        const summary = clean(data.summary);
        if (!summary) throw new Error("empty summary");
        cache.set(signature, summary);
        if (activeLoads.get(el)?.signature === signature) {
          el.dataset.state = "ready";
          el.textContent = summary;
          activeLoads.delete(el);
        }
        return summary;
      })
      .catch((error) => {
        if (error && error.name === "AbortError") {
          if (activeLoads.get(el)?.signature === signature) {
            el.dataset.state = "error";
            el.textContent = ERROR_TEXT;
            activeLoads.delete(el);
          }
          return undefined;
        }

        el.dataset.state = "error";
        el.textContent = ERROR_TEXT;
        activeLoads.delete(el);
        return undefined;
      })
      .finally(() => {
        window.clearTimeout(timeoutId);
      });

    activeLoads.set(el, { signature, controller, promise });
    return promise;
  }

  function clearCache() {
    cache.clear();
  }

  window.EmailSummary = { load, clearCache };
})();
