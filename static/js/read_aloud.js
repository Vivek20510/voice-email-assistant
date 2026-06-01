(function () {
  const DEFAULT_LABEL = "▶ Read aloud";
  const STOP_LABEL = "■ Stop";
  const SUMMARY_PLACEHOLDERS = [
    "click \"summarize\"",
    "ai summary will appear",
    "summary is temporarily unavailable",
    "no message content is available",
    "generating ai summary",
    "translating",
  ];

  let currentAudio = null;
  let currentObjectUrl = null;
  let currentButton = null;
  let currentController = null;

  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function notify(message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(message, type);
    } else if (typeof window.alert === "function") {
      window.alert(message);
    }
  }

  function resetButton(button) {
    if (!button) return;
    button.textContent = DEFAULT_LABEL;
    button.dataset.state = "idle";
  }

  function releaseAudio() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.src = "";
    }
    if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
    resetButton(currentButton);
    currentAudio = null;
    currentObjectUrl = null;
    currentButton = null;
  }

  function stop() {
    if (currentController) {
      currentController.abort();
      currentController = null;
    }
    releaseAudio();
  }

  function usableSummary(summaryElement) {
    const summary = clean(summaryElement?.textContent);
    if (!summary || summary.length < 15) return "";
    const lower = summary.toLowerCase();
    if (SUMMARY_PLACEHOLDERS.some((placeholder) => lower.includes(placeholder))) {
      return "";
    }
    return summary;
  }

  function selectText(options) {
    const summary = usableSummary(options.summaryElement);
    if (summary) return { text: summary, translate: false };

    const body = clean(
      options.bodyText ||
        options.bodyElement?.innerText ||
        options.bodyElement?.textContent,
    );
    return { text: body, translate: true };
  }

  function preferredLanguage() {
    try {
      return localStorage.getItem("preferred_language") || "English";
    } catch {
      return "English";
    }
  }

  async function errorMessage(response) {
    try {
      const data = await response.json();
      return data.error || "Read aloud failed.";
    } catch {
      return "Read aloud failed.";
    }
  }

  async function play(options) {
    const button = options.button;
    if (!button) return;

    if (currentButton === button) {
      stop();
      return;
    }
    stop();

    const selection = selectText(options);
    if (!selection.text) {
      notify("No text is available to read aloud.", "warning");
      return;
    }

    const controller = new AbortController();
    currentController = controller;
    currentButton = button;
    button.textContent = STOP_LABEL;
    button.dataset.state = "loading";

    try {
      const response = await fetch("/api/voice/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: selection.text,
          language: options.language || preferredLanguage(),
          translate: selection.translate,
        }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(await errorMessage(response));

      const blob = await response.blob();
      if (!blob.size) throw new Error("Read aloud returned empty audio.");

      currentObjectUrl = URL.createObjectURL(blob);
      const audio = new Audio(currentObjectUrl);
      currentAudio = audio;
      button.dataset.state = "playing";

      audio.onended = releaseAudio;
      audio.onerror = () => {
        releaseAudio();
        notify("Audio playback failed.", "error");
      };
      await audio.play();
    } catch (error) {
      if (error?.name === "AbortError") return;
      releaseAudio();
      notify(error?.message || "Read aloud failed.", "error");
    } finally {
      if (currentController === controller) currentController = null;
    }
  }

  function bindStandalone() {
    const button = document.getElementById("read-aloud-btn");
    const page = document.querySelector(".message-view-page:not(.message-view-page-inline)");
    if (!button || !page) return;
    button.addEventListener("click", () =>
      play({
        button,
        summaryElement: document.getElementById("summary-text"),
        bodyText: page.dataset.ttsBody,
        bodyElement: document.getElementById("message-body"),
      }),
    );
  }

  window.EmailReadAloud = { bindStandalone, play, selectText, stop };
  document.addEventListener("DOMContentLoaded", bindStandalone);
})();
