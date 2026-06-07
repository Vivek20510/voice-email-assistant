/**

 * dashboard.js — Inbox + Sidebar + Navigation

 * Handles message list rendering, sidebar switching, caching, and toolbar state.

 */

// ── State ────────────────────────────────────────────────────────────────────

let inboxMessagesCache = [];

const inboxMessagesCacheByChannel = {};

let currentMessageId = null;

let currentDashboardView = "sb-inbox";

let inboxTotalCount = 0;

let miniMessageListScrollTop = 0;

let activeInboxSort = "newest";

let activeInboxFilter = "all";

const OUTLOOK_NOTIFICATION_POLL_MS = 30000;

const OUTLOOK_NOTIFICATION_SETTLE_MS = 2000;

const knownOutlookMessageIds = new Set();

let outlookNotificationMessages = [];

let outlookNotificationUnseenCount = 0;

let outlookNotificationsInitialized = false;

let outlookNotificationRefreshInFlight = false;

let outlookNotificationPollTimer = null;

// ── View Metadata ─────────────────────────────────────────────────────────────

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

const mailViews = new Set([
  "sb-inbox",

  "sb-emails",

  "sb-outlook",

  "sb-draft",

  "sb-sent",

  "sb-archive",

  "sb-trash",
]);

// ── View Helpers ──────────────────────────────────────────────────────────────

function channelForView(viewId) {
  if (viewId === "sb-outlook") return "outlook";

  if (viewId === "sb-emails") return "gmail";

  return "all";
}

function folderForView(viewId) {
  const folders = {
    "sb-draft": "draft",

    "sb-sent": "sent",

    "sb-archive": "archive",

    "sb-trash": "trash",
  };

  return folders[viewId] || "inbox";
}

function cacheKeyForView(viewId) {
  const channel = channelForView(viewId);

  const folder = folderForView(viewId);

  return folder === "inbox" ? channel : `${channel}:${folder}`;
}

// ── DOM Helpers ───────────────────────────────────────────────────────────────

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

  if (dashboardBody)
    dashboardBody.classList.toggle("message-mode", isMessageMode);

  if (toolbar) {
    toolbar.hidden = isMessageMode;
    toolbar.style.display = isMessageMode ? "none" : "";
  }

  if (aiPanel) aiPanel.hidden = isMessageMode;

  if (title)
    title.textContent = isMessageMode
      ? "Message"
      : dashboardViewTitles[currentDashboardView] || "Inbox";

  if (toolbarActions) {
    toolbarActions.hidden = isMessageMode;
    toolbarActions.style.display = isMessageMode ? "none" : "";
  }
}

function setActiveSidebarItem(itemId) {
  document.querySelectorAll(".sidebar-item").forEach((item) => {
    item.classList.toggle("active", item.id === itemId);
  });
}

function rememberMiniMessageListScroll() {
  const miniList = document.querySelector(".message-mini-list");

  if (miniList) miniMessageListScrollTop = miniList.scrollTop;
}

function restoreMiniMessageListScroll() {
  const miniList = document.querySelector(".message-mini-list");

  if (miniList) miniList.scrollTop = miniMessageListScrollTop;
}

// ── Inbox Count Badge ─────────────────────────────────────────────────────────

function updateInboxUnreadBadge(totalCount = inboxTotalCount) {
  const badge = document.getElementById("inbox-unread-badge");

  if (!badge) return;

  inboxTotalCount = Number.isFinite(Number(totalCount))
    ? Number(totalCount)
    : 0;

  badge.textContent = String(inboxTotalCount);

  badge.hidden = inboxTotalCount === 0;
}

// ── Outlook Notifications ────────────────────────────────────────────────────

function outlookMessagesFrom(messages) {
  return (Array.isArray(messages) ? messages : []).filter(
    (message) => String(message?.channel || "").toLowerCase() === "outlook",
  );
}

function updateNotificationBadge() {
  const badge = document.getElementById("notification-count");

  if (!badge) return;

  badge.textContent = String(outlookNotificationUnseenCount);

  badge.hidden = outlookNotificationUnseenCount === 0;
}

function renderOutlookNotificationMenu() {
  const list = document.getElementById("notification-list");

  if (!list) return;

  if (!outlookNotificationMessages.length) {
    list.innerHTML = '<p class="notification-empty">No new Outlook emails.</p>';
    return;
  }

  list.innerHTML = outlookNotificationMessages
    .map((message) => {
      const sender = message.sender || message.sender_email || "Unknown sender";

      const subject = message.subject || "(No subject)";

      return `
        <button type="button" class="notification-item" data-message-id="${escapeHtml(message.id)}">
          <span class="notification-sender">${escapeHtml(sender)}</span>
          <span class="notification-subject">${escapeHtml(subject)}</span>
          <span class="notification-time">${escapeHtml(formatInboxTime(message.received_at))}</span>
        </button>
      `;
    })
    .join("");
}

function recordOutlookMessages(messages) {
  const outlookMessages = outlookMessagesFrom(messages);

  if (!outlookNotificationsInitialized) {
    outlookMessages.forEach((message) => {
      if (message.id) knownOutlookMessageIds.add(String(message.id));
    });

    outlookNotificationsInitialized = true;
    return [];
  }

  const newMessages = outlookMessages.filter(
    (message) => message.id && !knownOutlookMessageIds.has(String(message.id)),
  );

  outlookMessages.forEach((message) => {
    if (message.id) knownOutlookMessageIds.add(String(message.id));
  });

  if (newMessages.length) {
    const messagesById = new Map(
      outlookNotificationMessages.map((message) => [
        String(message.id),
        message,
      ]),
    );

    newMessages.forEach((message) =>
      messagesById.set(String(message.id), message),
    );

    outlookNotificationMessages = Array.from(messagesById.values());

    outlookNotificationUnseenCount += newMessages.length;

    updateNotificationBadge();
    renderOutlookNotificationMenu();
  }

  return newMessages;
}

function replaceCachedOutlookMessages(messages) {
  const outlookMessages = outlookMessagesFrom(messages);

  inboxMessagesCacheByChannel[viewCacheKey("sb-outlook")] = outlookMessages;

  const combinedCacheKey = viewCacheKey("sb-inbox");

  if (
    Object.prototype.hasOwnProperty.call(
      inboxMessagesCacheByChannel,
      combinedCacheKey,
    )
  ) {
    const nonOutlookMessages = inboxMessagesCacheByChannel[
      combinedCacheKey
    ].filter(
      (message) => String(message?.channel || "").toLowerCase() !== "outlook",
    );

    inboxMessagesCacheByChannel[combinedCacheKey] = [
      ...nonOutlookMessages,
      ...outlookMessages,
    ];
  }

  if (currentDashboardView === "sb-outlook") {
    inboxMessagesCache = outlookMessages;
  } else if (
    currentDashboardView === "sb-inbox" &&
    inboxMessagesCacheByChannel[combinedCacheKey]
  ) {
    inboxMessagesCache = inboxMessagesCacheByChannel[combinedCacheKey];
  }

  updateInboxUnreadBadge();

  if (
    currentMessageId === null &&
    ["sb-inbox", "sb-outlook"].includes(currentDashboardView)
  ) {
    renderCurrentInboxMessages();
  }
}

function acknowledgeOutlookNotifications() {
  outlookNotificationUnseenCount = 0;

  updateNotificationBadge();
}

function toggleOutlookNotifications(event) {
  if (event) event.stopPropagation();

  const button = document.getElementById("notification-toggle");

  const menu = document.getElementById("notification-menu");

  if (!button || !menu) return;

  const willOpen = menu.hidden;

  menu.hidden = !willOpen;
  button.setAttribute("aria-expanded", String(willOpen));

  if (willOpen) {
    renderOutlookNotificationMenu();
    acknowledgeOutlookNotifications();
    refreshOutlookNotifications({ manual: true });
  }
}

function closeOutlookNotifications() {
  const button = document.getElementById("notification-toggle");

  const menu = document.getElementById("notification-menu");

  if (!button || !menu) return;

  menu.hidden = true;
  button.setAttribute("aria-expanded", "false");
}

function waitForOutlookSync() {
  return new Promise((resolve) => {
    setTimeout(resolve, OUTLOOK_NOTIFICATION_SETTLE_MS);
  });
}

async function refreshOutlookNotifications({ manual = false } = {}) {
  if (outlookNotificationRefreshInFlight) return false;

  outlookNotificationRefreshInFlight = true;

  try {
    const refreshResponse = await fetch("/api/outlook/refresh", {
      method: "POST",
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    let refreshPayload = {};

    try {
      refreshPayload = await refreshResponse.json();
    } catch {
      refreshPayload = {};
    }

    if (!refreshResponse.ok) {
      if (manual)
        showToast(
          refreshPayload.error || "Unable to refresh Outlook.",
          "error",
        );

      return false;
    }

    await waitForOutlookSync();

    const inboxResponse = await fetch(
      "/api/messages?limit=25&channel=outlook&folder=inbox",
      {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      },
    );

    let inboxPayload = {};

    try {
      inboxPayload = await inboxResponse.json();
    } catch {
      inboxPayload = {};
    }

    if (!inboxResponse.ok) {
      if (manual)
        showToast(
          inboxPayload.error || "Unable to load Outlook messages.",
          "error",
        );

      return false;
    }

    const messages = Array.isArray(inboxPayload.messages)
      ? inboxPayload.messages
      : Array.isArray(inboxPayload.emails)
        ? inboxPayload.emails
        : [];

    recordOutlookMessages(messages);
    replaceCachedOutlookMessages(messages);

    return true;
  } catch {
    if (manual) showToast("Network error while refreshing Outlook.", "error");

    return false;
  } finally {
    outlookNotificationRefreshInFlight = false;
  }
}

function initializeOutlookNotifications() {
  const button = document.getElementById("notification-toggle");

  if (!button) return;

  updateNotificationBadge();
  renderOutlookNotificationMenu();

  button.addEventListener("click", toggleOutlookNotifications);

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".notification-center"))
      closeOutlookNotifications();
  });

  const list = document.getElementById("notification-list");

  if (list) {
    list.addEventListener("click", (event) => {
      const item = event.target.closest(".notification-item");

      if (!item?.dataset.messageId) return;

      closeOutlookNotifications();
      loadMessageDetail(item.dataset.messageId);
    });
  }

  if (outlookNotificationPollTimer === null) {
    outlookNotificationPollTimer = setInterval(
      refreshOutlookNotifications,
      OUTLOOK_NOTIFICATION_POLL_MS,
    );
  }
}

// ── Cache Helpers ─────────────────────────────────────────────────────────────

function getCachedInboxMessages(cacheKey, channel = cacheKey) {
  if (
    Object.prototype.hasOwnProperty.call(inboxMessagesCacheByChannel, cacheKey)
  ) {
    return inboxMessagesCacheByChannel[cacheKey];
  }

  if (
    cacheKey === channel &&
    channel !== "all" &&
    Object.prototype.hasOwnProperty.call(inboxMessagesCacheByChannel, "all")
  ) {
    const messages = inboxMessagesCacheByChannel.all.filter(
      (m) => String(m.channel || "").toLowerCase() === channel,
    );

    inboxMessagesCacheByChannel[cacheKey] = messages;

    return messages;
  }

  return null;
}

function viewCacheKey(viewId = currentDashboardView) {
  const channel = channelForView(viewId);

  return `${channel}_${viewId}`;
}

function currentCachedMessages() {
  const cacheKey = viewCacheKey();

  return inboxMessagesCacheByChannel[cacheKey] || inboxMessagesCache || [];
}

function allCachedMessages() {
  const messagesById = new Map();

  Object.values(inboxMessagesCacheByChannel).forEach((messages) => {
    if (!Array.isArray(messages)) return;
    messages.forEach((message) => {
      if (!message || !message.id) return;
      messagesById.set(String(message.id), message);
    });
  });

  (inboxMessagesCache || []).forEach((message) => {
    if (!message || !message.id) return;
    messagesById.set(String(message.id), message);
  });

  return Array.from(messagesById.values());
}

function findCachedMessage(messageId) {
  const channel = channelForView(currentDashboardView);

  const cachedMessages =
    inboxMessagesCacheByChannel[channel] || inboxMessagesCache || [];

  return cachedMessages.find((m) => String(m.id) === String(messageId)) || null;
}

function markMessageRead(messageId) {
  const unread = (m) =>
    String(m.id) === String(messageId) ? { ...m, unread: false } : m;

  inboxMessagesCache = inboxMessagesCache.map(unread);

  Object.keys(inboxMessagesCacheByChannel).forEach((ch) => {
    inboxMessagesCacheByChannel[ch] =
      inboxMessagesCacheByChannel[ch].map(unread);
  });

  updateInboxUnreadBadge();
}

function markAllRead() {
  const messages = currentCachedMessages();

  if (!messages.length) {
    showToast("No loaded messages to mark read", "warning");
    return;
  }

  const markRead = (message) => ({
    ...message,
    unread: false,
    labels: Array.isArray(message.labels)
      ? message.labels.filter((label) => label !== "UNREAD")
      : message.labels,
  });

  inboxMessagesCache = inboxMessagesCache.map(markRead);

  Object.keys(inboxMessagesCacheByChannel).forEach((key) => {
    inboxMessagesCacheByChannel[key] =
      inboxMessagesCacheByChannel[key].map(markRead);
  });

  updateInboxUnreadBadge();
  renderCurrentInboxMessages();
  showToast("All loaded messages marked as read");
}

// ── Formatting Helpers ────────────────────────────────────────────────────────

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")

    .replaceAll("<", "&lt;")

    .replaceAll(">", "&gt;")

    .replaceAll('"', "&quot;")

    .replaceAll("'", "&#39;");
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

  if (!value || hiddenLabels.has(value)) return "";

  if (friendlyLabels[value]) return friendlyLabels[value];

  return value

    .replace(/^Label_/, "")

    .replace(/^CATEGORY_/, "")

    .replaceAll("_", " ")

    .toLowerCase()

    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatInboxTime(value) {
  if (!value) return "";

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) return value;

  const now = new Date();

  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );

  const startOfYesterday = new Date(startOfToday);

  startOfYesterday.setDate(startOfToday.getDate() - 1);

  if (parsed >= startOfToday)
    return parsed.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

  if (parsed >= startOfYesterday) return "Yesterday";

  return parsed.toLocaleDateString([], { month: "short", day: "numeric" });
}

function parseMessageDate(value) {
  if (!value) return 0;

  const parsed = new Date(value);

  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
}

function isTodayMessage(message) {
  const timestamp = parseMessageDate(message?.received_at || message?.date);

  if (!timestamp) return false;

  const parsed = new Date(timestamp);

  const now = new Date();

  return (
    parsed.getFullYear() === now.getFullYear() &&
    parsed.getMonth() === now.getMonth() &&
    parsed.getDate() === now.getDate()
  );
}

function isStarredMessage(message) {
  if (message?.starred || message?.is_starred) return true;

  const labels = Array.isArray(message?.labels) ? message.labels : [];

  return labels.some((label) => String(label).toUpperCase() === "STARRED");
}

function sortedMessages(messages, sortType = activeInboxSort) {
  const nextMessages = [...messages];

  if (sortType === "oldest") {
    return nextMessages.sort(
      (a, b) =>
        parseMessageDate(a.received_at || a.date) -
        parseMessageDate(b.received_at || b.date),
    );
  }

  if (sortType === "sender") {
    return nextMessages.sort((a, b) => {
      const senderA = String(a.sender || a.sender_email || "").toLowerCase();
      const senderB = String(b.sender || b.sender_email || "").toLowerCase();

      return senderA.localeCompare(senderB);
    });
  }

  return nextMessages.sort(
    (a, b) =>
      parseMessageDate(b.received_at || b.date) -
      parseMessageDate(a.received_at || a.date),
  );
}

function filteredMessages(messages, filterType = activeInboxFilter) {
  if (filterType === "unread")
    return messages.filter((message) => message.unread);

  if (filterType === "starred") return messages.filter(isStarredMessage);

  if (filterType === "today") return messages.filter(isTodayMessage);

  return messages;
}

function renderFilteredInboxEmpty(filterType) {
  const labels = {
    unread: "unread messages",
    starred: "starred messages",
    today: "messages from today",
  };

  setDashboardMessageMode(false);

  setInboxContent(`

    <div class="inbox-feedback" data-state="empty">

      <h3>No ${escapeHtml(labels[filterType] || "messages")}</h3>

      <p>The current loaded message list has no matches for this filter.</p>

    </div>

  `);
}

function renderCurrentInboxMessages() {
  const baseMessages = currentCachedMessages();

  if (!baseMessages.length) {
    renderInboxEmpty();
    return;
  }

  const messages = sortedMessages(filteredMessages(baseMessages));

  if (!messages.length) {
    renderFilteredInboxEmpty(activeInboxFilter);
    return;
  }

  renderInboxMessages(messages);
}

function getInboxGroupLabel(value) {
  if (!value) return "Earlier";

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) return "Earlier";

  const now = new Date();

  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );

  const startOfYesterday = new Date(startOfToday);

  startOfYesterday.setDate(startOfToday.getDate() - 1);

  if (parsed >= startOfToday) return "Today";

  if (parsed >= startOfYesterday) return "Yesterday";

  return parsed.toLocaleDateString([], { month: "long", day: "numeric" });
}

function formatChannelName(channel) {
  const value = String(channel || "gmail")
    .trim()
    .toLowerCase();

  if (value === "gmail") return "Gmail";

  if (value === "outlook") return "Outlook";

  return value.charAt(0).toUpperCase() + value.slice(1);
}

function getAvatarInitials(name) {
  const parts = String(name || "")
    .split(" ")
    .map((p) => p.trim())
    .filter(Boolean);

  if (!parts.length) return "NA";

  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();

  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

// ── Render States ─────────────────────────────────────────────────────────────

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

      <p>${escapeHtml(title)} messages will appear here when this feature is developed.</p>

    </div>

  `);
}

function renderInboxNeedsConnect(channel = "all") {
  const serviceName =
    channel === "outlook"
      ? "Outlook"
      : channel === "gmail"
        ? "Gmail"
        : "Gmail or Outlook";

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

// ── Inbox List Render ─────────────────────────────────────────────────────────

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
        ? labels
            .slice(0, 2)
            .map((l) => `<span class="inbox-chip">${escapeHtml(l)}</span>`)
            .join("")
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

      </article>`;
    })
    .join("");

  setInboxContent(`<div class="inbox-list">${rows}</div>`);
}

// ── Fetch Inbox ───────────────────────────────────────────────────────────────

async function loadInboxMessages() {
  currentDashboardView = mailViews.has(currentDashboardView)
    ? currentDashboardView
    : "sb-inbox";

  const channel = channelForView(currentDashboardView);

  const folder = folderForView(currentDashboardView);

  renderInboxLoading();

  try {
    const response = await fetch(
      `/api/messages?limit=25&channel=${encodeURIComponent(channel)}&folder=${encodeURIComponent(folder)}`,

      { headers: { Accept: "application/json" }, credentials: "same-origin" },
    );

    let payload = {};

    try {
      payload = await response.json();
    } catch {
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

    const cacheKey = viewCacheKey();

    inboxMessagesCacheByChannel[cacheKey] = messages;

    recordOutlookMessages(messages);

    if (currentDashboardView === "sb-inbox") {
      updateInboxUnreadBadge(
        payload.total_count ?? payload.count ?? messages.length,
      );
    }

    if (!mailViews.has(currentDashboardView)) return;

    if (!messages.length) {
      renderInboxEmpty();
      return;
    }

    renderCurrentInboxMessages();
  } catch {
    renderInboxError("Network error while loading inbox.");
  }
}

function restoreInboxList() {
  currentMessageId = null;

  if (!mailViews.has(currentDashboardView)) {
    renderEmptyView(currentDashboardView);
    return;
  }

  const channel = channelForView(currentDashboardView);

  const cacheKey = viewCacheKey();

  const cachedMessages = inboxMessagesCacheByChannel[cacheKey] || [];

  if (cachedMessages.length) {
    inboxMessagesCache = cachedMessages;

    renderCurrentInboxMessages();

    return;
  }

  loadInboxMessages();
}

// ── Sidebar Switching ─────────────────────────────────────────────────────────

function switchSidebar(itemId) {
  if (typeof switchPage === "function") switchPage("dashboard");

  currentDashboardView = itemId;

  setActiveSidebarItem(itemId);

  if (mailViews.has(itemId)) {
    const channel = channelForView(itemId);

    const cacheKey = viewCacheKey(itemId);

    const cachedMessages = inboxMessagesCacheByChannel[cacheKey] || [];

    if (cachedMessages.length) {
      inboxMessagesCache = cachedMessages;

      renderCurrentInboxMessages();

      return;
    }

    loadInboxMessages();

    return;
  }

  renderEmptyView(itemId);
}

// ── Toolbar Dropdowns ─────────────────────────────────────────────────────────

function toggleMenu(menuId) {
  document.querySelectorAll(".dropdown-menu").forEach((menu) => {
    if (menu.id !== menuId) menu.style.display = "none";
  });

  const menu = document.getElementById(menuId);

  menu.style.display = menu.style.display === "block" ? "none" : "block";
}

function applySort(type) {
  activeInboxSort = ["newest", "oldest", "sender"].includes(type)
    ? type
    : "newest";

  renderCurrentInboxMessages();
  showToast("Sort applied: " + activeInboxSort);
  closeMenus();
}

function applyFilter(type) {
  activeInboxFilter = ["unread", "starred", "today", "all"].includes(type)
    ? type
    : "all";

  renderCurrentInboxMessages();
  showToast("Filter applied: " + activeInboxFilter);
  closeMenus();
}

function applyFilterPayload(payload = {}) {
  if (payload.unread) activeInboxFilter = "unread";
  else if (payload.today) activeInboxFilter = "today";
  else activeInboxFilter = "all";

  if (payload.channel === "gmail") {
    switchSidebar("sb-emails");
    return;
  }

  if (payload.channel === "outlook") {
    switchSidebar("sb-outlook");
    return;
  }

  renderCurrentInboxMessages();
  showToast("Filter applied: " + activeInboxFilter);
  closeMenus();
}

function closeMenus() {
  document
    .querySelectorAll(".dropdown-menu")
    .forEach((m) => (m.style.display = "none"));
}

// ── Initial State ─────────────────────────────────────────────────────────────

function applyInitialDashboardState() {
  const stateEl = document.getElementById("dashboard-state");

  if (!stateEl) return;

  const initialPage = stateEl.dataset.initialPage || "dashboard";

  const initialTab = stateEl.dataset.initialTab || "profile";

  if (typeof switchPage === "function" && initialPage !== "dashboard")
    switchPage(initialPage);

  if (
    initialPage === "settings" &&
    typeof activateSettingsTabByName === "function"
  ) {
    activateSettingsTabByName(initialTab);
  }
}

// ── Click Delegation ──────────────────────────────────────────────────────────

function bindDashboardInteractions() {
  const inboxContent = document.getElementById("inbox-content");

  if (!inboxContent) return;

  inboxContent.addEventListener("click", (event) => {
    // Mini sidebar navigation

    const miniMessage = event.target.closest(".message-mini-item");

    if (miniMessage) {
      event.preventDefault();

      const messageId = miniMessage.dataset.messageId;

      if (messageId && messageId !== currentMessageId)
        loadMessageDetail(messageId);

      return;
    }

    // Inbox row click → load message

    const messageRow = event.target.closest(".inbox-item");

    if (messageRow) {
      const messageId = messageRow.dataset.messageId;

      if (messageId) loadMessageDetail(messageId);

      return;
    }

    // Prevent default on action buttons (handled elsewhere)

    const placeholderButton = event.target.closest(
      "#read-aloud-btn, #reply-btn, #forward-btn, #archive-btn, #delete-btn, .use-btn",
    );

    if (placeholderButton) event.preventDefault();
  });
}

if (typeof window !== "undefined") {
  window.OutlookNotifications = {
    acknowledge: acknowledgeOutlookNotifications,
    initialize: initializeOutlookNotifications,
    record: recordOutlookMessages,
    refresh: refreshOutlookNotifications,
    replaceCache: replaceCachedOutlookMessages,
    toggle: toggleOutlookNotifications,
  };

  window.AICommandCenter = {
    getActiveView: () => currentDashboardView,
    getActiveMessageId: () => currentMessageId || "",
    navigate: ({ target, tab } = {}) => {
      if (!target || typeof switchPage !== "function") return false;
      switchPage(target);
      if (
        target === "settings" &&
        tab &&
        typeof activateSettingsTabByName === "function"
      ) {
        activateSettingsTabByName(tab);
      }
      return true;
    },
    prefillCompose: (payload = {}) => {
      if (typeof switchPage === "function") switchPage("compose");
      const fieldMap = {
        channel: "compose-channel",
        to: "compose-to",
        recipient: "compose-to",
        subject: "compose-subject",
        body: "compose-message",
        message: "compose-message",
      };

      Object.entries(fieldMap).forEach(([key, id]) => {
        if (payload[key] === undefined) return;
        const field = document.getElementById(id);
        if (field) field.value = payload[key];
      });

      if (typeof updateComposeCount === "function") updateComposeCount();
      return true;
    },
    openMessage: ({ message_id: messageId, id } = {}) => {
      const targetId = messageId || id;
      if (!targetId) return false;
      loadMessageDetail(targetId);
      return true;
    },
    applyFilter: (payload = {}) => {
      const { view, filter } = payload;
      if (view && mailViews.has(view)) {
        switchSidebar(view);
        return true;
      }
      if (filter && typeof filter === "string") applyFilter(filter);
      else applyFilterPayload(payload);
      return true;
    },
    markReadLocal: ({ message_id: messageId, id } = {}) => {
      const targetId = messageId || id;
      if (!targetId) return false;
      markMessageRead(targetId);
      return true;
    },
  };
}
