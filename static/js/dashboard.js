let inboxMessagesCache = [];
const inboxMessagesCacheByChannel = {};
let currentMessageId = null;
let currentDashboardView = "sb-inbox";

const dashboardViewTitles = {
  "sb-inbox": "Inbox",
  "sb-emails": "Email",
  "sb-draft": "Draft",
  "sb-sent": "Sent",
  "sb-archive": "Archive",
  "sb-trash": "Trash",
  "sb-whatsapp": "WhatsApp",
  "sb-telegram": "Telegram",
  "sb-outlook": "Outlook",
  "sb-work": "Work",
  "sb-personal": "Personal",
  "sb-promos": "Promotions",
};

const mailViews = new Set(["sb-inbox", "sb-emails", "sb-outlook"]);

function channelForView(viewId) {
  if (viewId === "sb-outlook") {
    return "outlook";
  }
  if (viewId === "sb-emails") {
    return "gmail";
  }
  return "all";
}

function setInboxContent(html) {
  const container = document.getElementById("inbox-content");
  if (container) {
    container.innerHTML = html;
    container.classList.toggle("has-feedback", html.includes("inbox-feedback"));
  }
}

function setDashboardMessageMode(isMessageMode) {
  const dashboardBody = document.getElementById("dashboard-body");
  const aiPanel = document.getElementById("dashboard-ai-panel");
  const title = document.getElementById("dashboard-title");
  const toolbarActions = document.getElementById("dashboard-toolbar-actions");
  const toolbar = document.getElementById("dashboard-toolbar");

  if (dashboardBody) {
    dashboardBody.classList.toggle("message-mode", isMessageMode);
  }
  if (toolbar) {
    toolbar.hidden = isMessageMode;
    toolbar.style.display = isMessageMode ? "none" : "";
  }
  if (aiPanel) {
    aiPanel.hidden = isMessageMode;
  }
  if (title) {
    title.textContent = isMessageMode
      ? "Message"
      : dashboardViewTitles[currentDashboardView] || "Inbox";
  }
  if (toolbarActions) {
    toolbarActions.hidden = isMessageMode;
    toolbarActions.style.display = isMessageMode ? "none" : "";
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

function setActiveSidebarItem(itemId) {
  document.querySelectorAll(".sidebar-item").forEach((item) => {
    item.classList.toggle("active", item.id === itemId);
  });
}

function updateInboxUnreadBadge() {
  const badge = document.getElementById("inbox-unread-badge");
  if (!badge) {
    return;
  }

  const messages = inboxMessagesCacheByChannel.all || inboxMessagesCache || [];
  const unreadCount = messages.filter((message) => message.unread).length;
  badge.textContent = String(unreadCount);
  badge.hidden = unreadCount === 0;
}

function decodeHtmlEntities(value) {
  const textarea = document.createElement("textarea");
  textarea.innerHTML = String(value ?? "");
  return textarea.value;
}

function toPreviewText(value) {
  return decodeHtmlEntities(value)
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function formatMessageLabel(label) {
  const value = String(label || "").trim();
  const hiddenLabels = new Set([
    "INBOX",
    "UNREAD",
    "SENT",
    "DRAFT",
    "TRASH",
    "SPAM",
    "IMPORTANT",
    "CATEGORY_UPDATES",
  ]);
  const friendlyLabels = {
    CATEGORY_FORUMS: "Forums",
    CATEGORY_PERSONAL: "Personal",
    CATEGORY_PROMOTIONS: "Promotions",
    CATEGORY_SOCIAL: "Social",
    STARRED: "Starred",
  };

  if (!value || hiddenLabels.has(value)) {
    return "";
  }

  if (friendlyLabels[value]) {
    return friendlyLabels[value];
  }

  return value
    .replace(/^Label_/, "")
    .replace(/^CATEGORY_/, "")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatPlainMessageBody(bodyText) {
  const text = String(bodyText || "").trim();
  if (!text) {
    return "";
  }

  return text
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function buildEmailHtmlDocument(bodyHtml) {
  return `<!doctype html>
    <html>
      <head>
        <base target="_blank">
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          html, body { margin: 0; padding: 0; background: #fff; color: #222; }
          body { font: 16px/1.6 Arial, Helvetica, sans-serif; overflow-wrap: anywhere; }
          img, table { max-width: 100%; }
          pre { white-space: pre-wrap; overflow-wrap: anywhere; }
        </style>
      </head>
      <body>${bodyHtml || ""}</body>
    </html>`;
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

function formatInboxTime(value) {
  if (!value) {
    return "";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfToday.getDate() - 1);

  if (parsed >= startOfToday) {
    return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  if (parsed >= startOfYesterday) {
    return "Yesterday";
  }

  return parsed.toLocaleDateString([], { month: "short", day: "numeric" });
}

function getInboxGroupLabel(value) {
  if (!value) {
    return "Earlier";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Earlier";
  }

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfToday.getDate() - 1);

  if (parsed >= startOfToday) {
    return "Today";
  }

  if (parsed >= startOfYesterday) {
    return "Yesterday";
  }

  return parsed.toLocaleDateString([], { month: "long", day: "numeric" });
}

function formatChannelName(channel) {
  const value = String(channel || "gmail").trim().toLowerCase();
  if (value === "gmail") {
    return "Gmail";
  }
  if (value === "outlook") {
    return "Outlook";
  }

  return value.charAt(0).toUpperCase() + value.slice(1);
}

function renderInboxLoading() {
  setDashboardMessageMode(false);
  setInboxContent(`
    <div class="inbox-feedback" data-state="loading">
      <h3>Loading inbox...</h3>
      <p>Fetching your latest email messages.</p>
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

function renderEmptyView(viewId) {
  currentMessageId = null;
  currentDashboardView = viewId;
  setDashboardMessageMode(false);
  const title = dashboardViewTitles[viewId] || "This tab";

  setInboxContent(`
    <div class="inbox-feedback" data-state="empty">
      <h3>No messages</h3>
      <p>${escapeHtml(title)} messages will appear here when this channel is connected.</p>
    </div>
  `);
}

function renderInboxNeedsConnect(channel = "all") {
  const serviceName = channel === "outlook" ? "Outlook" : channel === "gmail" ? "Gmail" : "Gmail or Outlook";
  setDashboardMessageMode(false);
  setInboxContent(`
    <div class="inbox-feedback" data-state="disconnected">
      <h3>Connect ${escapeHtml(serviceName)} to load your inbox</h3>
      <p>Your dashboard will show live messages as soon as a mail channel is connected.</p>
      <a class="btn-save inbox-cta" href="/auth/settings">Open channel settings</a>
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
  let activeGroup = "";
  const rows = messages
    .map((message) => {
      const sender = message.sender || message.sender_email || "Unknown sender";
      const subject = message.subject || "(No subject)";
      const snippet = toPreviewText(message.snippet) || "No preview available.";
      const channel = formatChannelName(message.channel);
      const groupLabel = getInboxGroupLabel(message.received_at);
      const labels = Array.isArray(message.labels)
        ? message.labels.map(formatMessageLabel).filter(Boolean)
        : [];
      const unreadClass = message.unread ? " is-unread" : "";
      const labelMarkup = labels.length
        ? labels.slice(0, 2).map((label) => `<span class="inbox-chip">${escapeHtml(label)}</span>`).join("")
        : "";
      const groupMarkup =
        groupLabel !== activeGroup
          ? `<div class="inbox-date-divider">${escapeHtml(groupLabel)}</div>`
          : "";
      activeGroup = groupLabel;

      return `${groupMarkup}
        <article class="inbox-item${unreadClass}" data-message-id="${escapeHtml(message.id)}">
          <div class="inbox-avatar">${escapeHtml(getAvatarInitials(sender))}</div>
          <div class="inbox-message-main">
            <div class="inbox-item-head">
              <strong class="inbox-sender">${escapeHtml(sender)}</strong>
              <span class="inbox-subject">${escapeHtml(subject)}</span>
            </div>
            <p class="inbox-snippet">${escapeHtml(snippet)}</p>
          </div>
          <div class="inbox-message-side">
            <time class="inbox-time">${escapeHtml(formatInboxTime(message.received_at))}</time>
            <div class="inbox-meta">
              <span class="inbox-chip inbox-channel">${escapeHtml(channel)}</span>
              ${labelMarkup}
            </div>
            ${message.unread ? '<span class="inbox-unread-dot" aria-label="Unread"></span>' : ""}
          </div>
        </article>
      `;
    })
    .join("");

  setInboxContent(`<div class="inbox-list">${rows}</div>`);
}

function markMessageRead(messageId) {
  inboxMessagesCache = inboxMessagesCache.map((message) =>
    String(message.id) === String(messageId)
      ? { ...message, unread: false }
      : message
  );
  Object.keys(inboxMessagesCacheByChannel).forEach((channel) => {
    inboxMessagesCacheByChannel[channel] = inboxMessagesCacheByChannel[channel].map((message) =>
      String(message.id) === String(messageId)
        ? { ...message, unread: false }
        : message
    );
  });
  updateInboxUnreadBadge();
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
  const safeBody = bodyHtml
    ? `<iframe id="message-html-frame" class="message-html-frame" title="Email message body" sandbox referrerpolicy="no-referrer"></iframe>`
    : formatPlainMessageBody(bodyText) || "<p>No message body available.</p>";
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

  const frame = document.getElementById("message-html-frame");
  if (frame) {
    frame.srcdoc = buildEmailHtmlDocument(bodyHtml);
  }
}

function restoreInboxList() {
  currentMessageId = null;
  if (!mailViews.has(currentDashboardView)) {
    renderEmptyView(currentDashboardView);
    return;
  }

  const channel = channelForView(currentDashboardView);
  const cachedMessages = inboxMessagesCacheByChannel[channel] || [];
  if (cachedMessages.length) {
    inboxMessagesCache = cachedMessages;
    renderInboxMessages(cachedMessages);
    return;
  }
  loadInboxMessages();
}

async function loadMessageDetail(messageId) {
  currentMessageId = messageId;
  markMessageRead(messageId);
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
  currentDashboardView = mailViews.has(currentDashboardView)
    ? currentDashboardView
    : "sb-inbox";
  const channel = channelForView(currentDashboardView);
  renderInboxLoading();

  try {
    const response = await fetch(`/api/messages?limit=10&channel=${encodeURIComponent(channel)}`, {
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
        renderInboxNeedsConnect(channel);
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
    inboxMessagesCacheByChannel[channel] = messages;
    updateInboxUnreadBadge();

    if (!mailViews.has(currentDashboardView)) {
      return;
    }

    if (!messages.length) {
      renderInboxEmpty();
      return;
    }

    renderInboxMessages(messages);
  } catch (error) {
    renderInboxError("Network error while loading inbox.");
  }
}

function switchSidebar(itemId) {
  if (typeof switchPage === "function") {
    switchPage("dashboard");
  }

  currentDashboardView = itemId;
  setActiveSidebarItem(itemId);

  if (mailViews.has(itemId)) {
    const channel = channelForView(itemId);
    const cachedMessages = inboxMessagesCacheByChannel[channel] || [];
    if (cachedMessages.length) {
      inboxMessagesCache = cachedMessages;
      renderInboxMessages(cachedMessages);
      return;
    }

    loadInboxMessages();
    return;
  }

  renderEmptyView(itemId);
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
  setActiveSidebarItem(currentDashboardView);
  loadInboxMessages();
});
