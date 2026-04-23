let inboxMessagesCache = [];
let currentMessageId = null;

function setInboxContent(html) {
  const container = document.getElementById("inbox-content");
  if (container) {
    container.innerHTML = html;
  }
}

function setDashboardMessageMode(isMessageMode) {
  const dashboardBody = document.getElementById("dashboard-body");
  const aiPanel = document.getElementById("dashboard-ai-panel");
  const title = document.getElementById("dashboard-title");
  const toolbarActions = document.getElementById("dashboard-toolbar-actions");

  if (dashboardBody) {
    dashboardBody.classList.toggle("message-mode", isMessageMode);
  }
  if (aiPanel) {
    aiPanel.hidden = isMessageMode;
  }
  if (title) {
    title.textContent = isMessageMode ? "Message" : "Inbox";
  }
  if (toolbarActions) {
    toolbarActions.hidden = isMessageMode;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTimestamp(value) {
  if (!value) {
    return "Unknown time";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderInboxLoading() {
  setDashboardMessageMode(false);
  setInboxContent(`
    <div class="inbox-feedback" data-state="loading">
      <h3>Loading inbox...</h3>
      <p>Fetching your latest Gmail messages.</p>
    </div>
  `);
}

function renderInboxEmpty() {
  setDashboardMessageMode(false);
  setInboxContent(`
    <div class="inbox-feedback" data-state="empty">
      <h3>No emails yet</h3>
      <p>Your inbox is connected, but there are no messages to show right now.</p>
    </div>
  `);
}

function renderInboxNeedsConnect() {
  setDashboardMessageMode(false);
  setInboxContent(`
    <div class="inbox-feedback" data-state="disconnected">
      <h3>Connect Gmail to load your inbox</h3>
      <p>Your dashboard will show live messages as soon as Gmail is connected.</p>
      <a class="btn-save inbox-cta" href="/auth/settings">Open Gmail settings</a>
    </div>
  `);
}

function renderInboxError(message) {
  setDashboardMessageMode(false);
  setInboxContent(`
    <div class="inbox-feedback" data-state="error">
      <h3>Could not load inbox</h3>
      <p>${escapeHtml(message || "Something went wrong while loading your emails.")}</p>
      <button type="button" class="btn-save inbox-retry" onclick="loadInboxMessages()">Retry</button>
    </div>
  `);
}

function renderInboxMessages(messages) {
  setDashboardMessageMode(false);
  const rows = messages
    .map((message) => {
      const sender = message.sender || message.sender_email || "Unknown sender";
      const subject = message.subject || "(No subject)";
      const snippet = message.snippet || "No preview available.";
      const labels = Array.isArray(message.labels) ? message.labels : [];
      const unreadClass = message.unread ? " is-unread" : "";
      const labelMarkup = labels.length
        ? `<div class="inbox-meta">${labels.slice(0, 3).map((label) => `<span class="inbox-chip">${escapeHtml(label)}</span>`).join("")}</div>`
        : "";

      return `
        <article class="inbox-item${unreadClass}" data-message-id="${escapeHtml(message.id)}">
          <div class="inbox-item-head">
            <strong class="inbox-sender">${escapeHtml(sender)}</strong>
            <span class="inbox-time">${escapeHtml(formatTimestamp(message.received_at))}</span>
          </div>
          <div class="inbox-subject">${escapeHtml(subject)}</div>
          <p class="inbox-snippet">${escapeHtml(snippet)}</p>
          ${labelMarkup}
        </article>
      `;
    })
    .join("");

  setInboxContent(`<div class="inbox-list">${rows}</div>`);
}

function getAvatarInitials(name) {
  const parts = String(name || "")
    .split(" ")
    .map((part) => part.trim())
    .filter(Boolean);

  if (!parts.length) {
    return "NA";
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function renderMessageLoading() {
  setDashboardMessageMode(true);
  setInboxContent(`
    <div class="inbox-feedback" data-state="loading">
      <h3>Loading message...</h3>
      <p>Fetching the selected email details.</p>
    </div>
  `);
}

function renderMessageError(message) {
  setDashboardMessageMode(true);
  setInboxContent(`
    <div class="inbox-feedback" data-state="error">
      <h3>Could not load message</h3>
      <p>${escapeHtml(message || "Something went wrong while loading this email.")}</p>
      <div class="msg-actions-row">
        <button type="button" class="action-btn primary" onclick="restoreInboxList()">Back to Inbox</button>
      </div>
    </div>
  `);
}

function renderMessageView(message) {
  setDashboardMessageMode(true);
  const sender = message.sender || message.sender_email || "Unknown sender";
  const subject = message.subject || "(No subject)";
  const bodyText = message.body_text || "";
  const bodyHtml = message.body_html || "";
  const safeBody = bodyText
    ? bodyText
        .split(/\n{2,}/)
        .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
        .join("")
    : bodyHtml
      ? `<pre>${escapeHtml(bodyHtml)}</pre>`
      : "<p>No message body available.</p>";
  const suggestions = [
    "Thanks, I have received this and will review it shortly.",
    "Got it. I will respond with a detailed update soon.",
    "Received. I will follow up after I review the message fully.",
  ];
  const suggestionMarkup = suggestions
    .map(
      (suggestion) => `
        <div class="suggestion-item message-detail-suggestion-item">
          <span class="message-detail-suggestion-text">${escapeHtml(suggestion)}</span>
          <button type="button" class="use-btn message-detail-use-btn">Use</button>
        </div>
      `
    )
    .join("");

  setInboxContent(`
    <section class="message-view-page message-view-page-inline" data-message-id="${escapeHtml(message.id)}">
      <div class="message-view-wrap message-view-wrap-inline">
        <div class="message-detail-topbar message-detail-topbar-inline">
          <button type="button" class="back-btn message-detail-back" onclick="restoreInboxList()">← Back</button>
          <h2 class="message-detail-title">Message</h2>
        </div>

        <div class="message-detail-shell message-detail-shell-inline">
          <div class="summary-card message-detail-summary-card">
            <div>
              <div class="summary-badge message-detail-summary-badge">✦ AI Summary</div>
              <h3 class="message-detail-summary-sender">${escapeHtml(sender)}</h3>
              <div id="summary-text" class="summary-text message-detail-summary-text">
                AI summary will appear here once this feature is wired.
              </div>
            </div>
            <button id="read-aloud-btn" type="button" class="read-aloud-btn message-detail-ghost-btn">▶ Read aloud</button>
          </div>

          <div class="message-card message-detail-card">
            <div class="sender-row message-detail-sender-row">
              <div class="sender-av message-detail-avatar">${escapeHtml(getAvatarInitials(sender))}</div>
              <div class="sender-info message-detail-sender-info">
                <div class="sender-name message-detail-sender-name">
                  ${escapeHtml(sender)}
                  <span class="msg-tag tag-email message-detail-channel-tag">${escapeHtml(message.channel || "gmail")}</span>
                </div>
                <div class="sender-email message-detail-address">
                  ${escapeHtml(message.sender_email || "Unknown sender")} → ${escapeHtml(message.to || "Unknown recipient")}
                </div>
              </div>
              <div class="msg-timestamp message-detail-timestamp">${escapeHtml(formatTimestamp(message.received_at))}</div>
            </div>

            <div class="msg-subject-bar message-detail-subject">${escapeHtml(subject)}</div>

            <div id="message-body" class="msg-body-content message-detail-body">
              ${safeBody}
            </div>

            <div class="msg-actions-row message-detail-actions">
              <button id="reply-btn" type="button" class="action-btn primary message-detail-primary-btn">↩ Reply</button>
              <button id="forward-btn" type="button" class="action-btn message-detail-secondary-btn">↪ Forward</button>
              <button id="archive-btn" type="button" class="action-btn message-detail-secondary-btn">Archive</button>
              <button id="delete-btn" type="button" class="action-btn message-detail-secondary-btn message-detail-danger-btn">Delete</button>
            </div>
          </div>

          <div class="suggestions-card message-detail-suggestions-card">
            <div class="suggestions-header message-detail-suggestions-header">
              <div class="suggestions-title message-detail-suggestions-title"><span class="message-detail-star">✦</span> AI-Suggested Replies</div>
              <div class="ai-badge message-detail-ai-badge">AI</div>
            </div>

            <div id="suggestions-list" class="message-detail-suggestions-list">
              ${suggestionMarkup}
            </div>
          </div>
        </div>
      </div>
    </section>
  `);
}

function restoreInboxList() {
  currentMessageId = null;
  if (inboxMessagesCache.length) {
    renderInboxMessages(inboxMessagesCache);
    return;
  }
  loadInboxMessages();
}

async function loadMessageDetail(messageId) {
  currentMessageId = messageId;
  renderMessageLoading();

  try {
    const response = await fetch(`/api/messages/${encodeURIComponent(messageId)}`, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }

    if (!response.ok) {
      renderMessageError(payload.error || "Unable to load this message.");
      return;
    }

    renderMessageView(payload);
  } catch (error) {
    renderMessageError("Network error while loading this message.");
  }
}

async function loadInboxMessages() {
  renderInboxLoading();

  try {
    const response = await fetch("/api/messages?limit=10", {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }

    if (!response.ok) {
      if (response.status === 409) {
        renderInboxNeedsConnect();
        return;
      }
      renderInboxError(payload.error || "Unable to load your inbox.");
      return;
    }

    const messages = Array.isArray(payload.messages)
      ? payload.messages
      : Array.isArray(payload.emails)
        ? payload.emails
        : [];

    inboxMessagesCache = messages;

    if (!messages.length) {
      renderInboxEmpty();
      return;
    }

    renderInboxMessages(messages);
  } catch (error) {
    renderInboxError("Network error while loading inbox.");
  }
}

function applyInitialDashboardState() {
  const stateEl = document.getElementById("dashboard-state");
  if (!stateEl) {
    return;
  }

  const initialPage = stateEl.dataset.initialPage || "dashboard";
  const initialTab = stateEl.dataset.initialTab || "profile";

  if (typeof switchPage === "function" && initialPage !== "dashboard") {
    switchPage(initialPage);
  }

  if (initialPage === "settings" && typeof activateSettingsTabByName === "function") {
    activateSettingsTabByName(initialTab);
  }
}

function bindDashboardInteractions() {
  const inboxContent = document.getElementById("inbox-content");
  if (!inboxContent) {
    return;
  }

  inboxContent.addEventListener("click", (event) => {
    const messageRow = event.target.closest(".inbox-item");
    if (messageRow) {
      const messageId = messageRow.dataset.messageId;
      if (messageId) {
        loadMessageDetail(messageId);
      }
      return;
    }

    const placeholderButton = event.target.closest(
      "#read-aloud-btn, #reply-btn, #forward-btn, #archive-btn, #delete-btn, .use-btn"
    );
    if (placeholderButton) {
      event.preventDefault();
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  applyInitialDashboardState();
  bindDashboardInteractions();
  loadInboxMessages();
});
