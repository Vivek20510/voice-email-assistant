/**
 * ai.js — AI Summary + Suggested Replies + Read Aloud
 * All AI-powered features: summarize, generate reply suggestions, text-to-speech.
 * Depends on: dashboard.js (state), message.js (DOM IDs)
 */

// ── Summary ───────────────────────────────────────────────────────────────────
async function generateSummary() {
  const summaryEl = document.getElementById("summary-text");
  const btn = document.getElementById("summarize-btn");
  if (!summaryEl || !currentMessageId) return;
  if (btn?.disabled) return;

  const message = findCachedMessage(currentMessageId);
  if (!message) {
    summaryEl.textContent = "Unable to summarize this message.";
    return;
  }

  const textToSummarize =
    message.body_text || toPreviewText(message.snippet) || "";
  if (!textToSummarize || textToSummarize.length < 30) {
    summaryEl.textContent = "Message is too short to summarize.";
    return;
  }

  // Loading state
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Generating...";
  }
  summaryEl.textContent = "Generating AI summary…";

  try {
    const response = await fetch("/ai/summary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: textToSummarize }),
    });

    const data = await response.json();
    if (!response.ok) {
      summaryEl.textContent = data.error || "Failed to generate summary.";
      return;
    }

    summaryEl.textContent = data.summary || "No summary returned.";
  } catch {
    summaryEl.textContent = "Network error while generating summary.";
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "✨ Summarize";
    }
  }
}

// ── Generate Replies ──────────────────────────────────────────────────────────

/**
 * Called from message.js after the message view is rendered.
 * Binds the "Generate Replies" button for the given message object.
 */
function bindGenerateRepliesButton(message) {
  const generateBtn = document.getElementById("generate-replies-btn");
  if (!generateBtn || !window.EmailReplySuggestions) return;
  window.EmailReplySuggestions.bindGenerator(generateBtn, {
    list: document.getElementById("suggestions-list"),
    bodyText: message.body_text || message.snippet || "",
  });
}

// ── Read Aloud (TTS) ──────────────────────────────────────────────────────────
async function handleReadAloud() {
  const btn = document.getElementById("read-aloud-btn");
  if (!btn || !currentMessageId) return;

  const message = findCachedMessage(currentMessageId);
  if (!message) return;

  if (!window.EmailReadAloud) return;
  return window.EmailReadAloud.play({
    button: btn,
    summaryElement: document.getElementById("summary-text"),
    bodyText: message.body_text || message.snippet || "",
  });
}
