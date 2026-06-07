(function () {
  const HANDOFF_KEY = "replySuggestionDraft";

  function clean(value) {
    return String(value || "").trim();
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function notify(message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(message, type);
    }
  }

  function originalEmail(text) {
    let cleaned = clean(text);
    [
      /^From:.*$/im,
      /^Sent:.*$/im,
      /^To:.*$/im,
      /^Subject:.*$/im,
      /^On .* wrote:$/im,
      /^---+$/m,
    ].forEach((marker) => {
      cleaned = cleaned.split(marker)[0];
    });
    return cleaned.trim();
  }

  function prefillCompose(text) {
    const body = clean(text);
    if (!body) return;

    if (window.AICommandCenter?.prefillCompose) {
      window.AICommandCenter.prefillCompose({ body });
      return;
    }

    const composeBody =
      document.getElementById("compose-message") ||
      document.getElementById("compose-body") ||
      document.getElementById("message");
    if (composeBody) {
      composeBody.value = body;
      composeBody.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }

    try {
      localStorage.setItem(HANDOFF_KEY, body);
    } catch {}
    window.location.href = "/auth/compose";
  }

  function bindUseButtons(list) {
    if (!list) return;
    list.querySelectorAll(".use-btn").forEach((button) => {
      if (button.dataset.replyBound === "true") return;
      button.dataset.replyBound = "true";
      button.addEventListener("click", () => {
        const text = button
          .closest(".suggestion-item")
          ?.querySelector(
            ".message-detail-suggestion-text, .suggestion-text",
          )?.textContent;
        prefillCompose(text);
      });
    });
  }

  function renderSuggestions(list, suggestions) {
    const replies = Object.entries(suggestions || {});
    if (!replies.length) throw new Error("No reply suggestions were returned.");

    list.innerHTML = replies
      .map(
        ([tone, suggestion]) => `
          <div class="suggestion-item message-detail-suggestion-item">
            <div class="message-detail-suggestion-tone">${escapeHtml(tone)}</div>
            <span class="message-detail-suggestion-text">${escapeHtml(suggestion)}</span>
            <button type="button" class="use-btn message-detail-use-btn">Use</button>
          </div>`,
      )
      .join("");
    bindUseButtons(list);
  }

  async function generate(options) {
    const list = options.list || document.getElementById("suggestions-list");
    const button = options.button;
    const emailBody = originalEmail(options.bodyText);
    if (!list || !emailBody) {
      notify("No email content is available for reply suggestions.", "warning");
      return;
    }

    if (button) {
      button.disabled = true;
      button.textContent = "Generating...";
    }
    list.dataset.state = "loading";

    try {
      const response = await fetch("/nlp/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: emailBody }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "Failed to generate replies.");
      }
      renderSuggestions(list, data.suggestions);
      list.dataset.state = "ready";
    } catch (error) {
      list.dataset.state = "error";
      list.innerHTML =
        '<span class="message-detail-suggestions-error">Failed to generate replies.</span>';
      notify(error?.message || "Failed to generate replies.", "error");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = "✦ Generate Replies";
      }
    }
  }

  function bindGenerator(button, options) {
    if (!button || button.dataset.replyBound === "true") return;
    button.dataset.replyBound = "true";
    button.addEventListener("click", () => generate({ ...options, button }));
  }

  function bindStandalone() {
    const page = document.querySelector(
      ".message-view-page:not(.message-view-page-inline)",
    );
    if (!page) return;
    const list = document.getElementById("suggestions-list");
    bindUseButtons(list);
    bindGenerator(document.getElementById("generate-replies-btn"), {
      list,
      bodyText: page.dataset.replyBody,
    });
  }

  function restoreComposeHandoff() {
    const composeBody = document.getElementById("message");
    if (!composeBody) return;
    let body = "";
    try {
      body = localStorage.getItem(HANDOFF_KEY) || "";
      localStorage.removeItem(HANDOFF_KEY);
    } catch {}
    if (body) {
      composeBody.value = body;
      composeBody.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  window.EmailReplySuggestions = {
    bindGenerator,
    bindStandalone,
    bindUseButtons,
    generate,
    originalEmail,
    prefillCompose,
    restoreComposeHandoff,
  };

  document.addEventListener("DOMContentLoaded", () => {
    bindStandalone();
    restoreComposeHandoff();
  });
})();
