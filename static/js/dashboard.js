/**

 * dashboard.js — Inbox + Sidebar + Navigation

 * Handles message list rendering, sidebar switching, caching, and toolbar state.

 */

// ── State ────────────────────────────────────────────────────────────────────

let inboxMessagesCache = [];

const inboxMessagesCacheByChannel = {};

let currentMessageId = null;

let currentDashboardView = "sb-inbox";

let miniMessageListScrollTop = 0;

if (typeof window !== "undefined") {
  window.currentEmails = window.currentEmails || [];
  window.loadedEmails = window.loadedEmails || [];
}

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
  if (
    viewId === "sb-outlook" ||
    viewId === "sb-draft" ||
    viewId === "sb-sent" ||
    viewId === "sb-archive" ||
    viewId === "sb-trash"
  )
    return "outlook";

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

// ── Unread Badge ──────────────────────────────────────────────────────────────

function updateInboxUnreadBadge() {
  const badge = document.getElementById("inbox-unread-badge");

  if (!badge) return;

  const messages = inboxMessagesCacheByChannel.all || inboxMessagesCache || [];

  const unreadCount = messages.filter((m) => m.unread).length;

  badge.textContent = String(unreadCount);

  badge.hidden = unreadCount === 0;
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

function renderInboxMessages(messages, options = {}) {
  setDashboardMessageMode(false);
  const shouldUpdateCurrent = options.updateCurrent !== false;
  if (typeof window !== "undefined" && shouldUpdateCurrent) {
    window.currentEmails = messages;
    window.loadedEmails = messages;
  }

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

  renderInboxLoading();

  try {
    const response = await fetch(
      `/api/messages?limit=25&channel=${encodeURIComponent(channel)}&folder=${encodeURIComponent(currentDashboardView)}`,

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
    if (typeof window !== "undefined") {
      window.currentEmails = messages;
      window.loadedEmails = messages;
    }

    const cacheKey = `${channel}_${currentDashboardView}`;

    inboxMessagesCacheByChannel[cacheKey] = messages;

    updateInboxUnreadBadge();

    if (!mailViews.has(currentDashboardView)) return;

    if (!messages.length) {
      renderInboxEmpty();
      return;
    }

    renderInboxMessages(messages);
  } catch {
    renderInboxError("Network error while loading inbox.");
  }
}

function restoreInboxList() {
  currentMessageId = null;
  if (typeof window !== "undefined") window.activeMessageId = "";

  if (!mailViews.has(currentDashboardView)) {
    renderEmptyView(currentDashboardView);
    return;
  }

  const channel = channelForView(currentDashboardView);

  const cacheKey = `${channel}_${currentDashboardView}`;

  const cachedMessages = inboxMessagesCacheByChannel[cacheKey] || [];

  if (cachedMessages.length) {
    inboxMessagesCache = cachedMessages;
    if (typeof window !== "undefined") {
      window.currentEmails = cachedMessages;
      window.loadedEmails = cachedMessages;
    }

    renderInboxMessages(cachedMessages);

    return;
  }

  loadInboxMessages();
}

// ── Sidebar Switching ─────────────────────────────────────────────────────────

function switchSidebar(itemId) {
  if (typeof switchPage === "function") switchPage("dashboard");

  currentDashboardView = itemId;
  if (typeof window !== "undefined") window.currentDashboardView = itemId;

  setActiveSidebarItem(itemId);

  if (mailViews.has(itemId)) {
    const channel = channelForView(itemId);

    const cacheKey = `${channel}_${itemId}`;

    const cachedMessages = inboxMessagesCacheByChannel[cacheKey] || [];

    if (cachedMessages.length) {
      inboxMessagesCache = cachedMessages;
      if (typeof window !== "undefined") {
        window.currentEmails = cachedMessages;
        window.loadedEmails = cachedMessages;
      }

      renderInboxMessages(cachedMessages);

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
  showToast("Sort applied: " + type);
  closeMenus();
}

function applyFilter(type) {
  showToast("Filter applied: " + type);
  closeMenus();
}

function closeMenus() {
  document
    .querySelectorAll(".dropdown-menu")
    .forEach((m) => (m.style.display = "none"));
}

// ── AI Command Bridge ────────────────────────────────────────────────────────

function getDashboardMessagesForAi() {
  if (typeof window === "undefined") return inboxMessagesCache || [];
  return window.loadedEmails?.length
    ? window.loadedEmails
    : window.currentEmails || inboxMessagesCache || [];
}

function renderAiFilteredMessages(messages, label) {
  if (!messages.length) {
    setDashboardMessageMode(false);
    setInboxContent(`

      <div class="inbox-feedback" data-state="empty">

        <h3>No matching messages</h3>

        <p>${escapeHtml(label || "The AI command did not match loaded mail.")}</p>

      </div>

    `);
    return;
  }

  renderInboxMessages(messages, { updateCurrent: false });
}

function aiNavigate(payload = {}) {
  const target = payload.target || payload.page || "dashboard";

  if (target === "settings") {
    if (typeof switchPage === "function") switchPage("settings");
    if (payload.tab && typeof activateSettingsTabByName === "function") {
      activateSettingsTabByName(payload.tab);
    }
    return true;
  }

  if (target === "compose") {
    if (typeof switchPage === "function") switchPage("compose");
    return true;
  }

  if (target === "gmail") {
    switchSidebar("sb-emails");
    return true;
  }

  if (target === "outlook") {
    switchSidebar("sb-outlook");
    return true;
  }

  if (typeof switchPage === "function") switchPage(target);
  return true;
}

function aiOpenMessage(payload = {}) {
  const messageId = payload.message_id || payload.id;
  if (!messageId) return false;
  if (typeof switchPage === "function") switchPage("dashboard");
  if (typeof window !== "undefined") window.activeMessageId = messageId;
  loadMessageDetail(messageId);
  return true;
}

function aiApplyFilter(payload = {}) {
  if (typeof switchPage === "function") switchPage("dashboard");

  const messages = getDashboardMessagesForAi();
  const ids = new Set((payload.message_ids || []).map((id) => String(id)));
  let filtered = ids.size
    ? messages.filter((message) => ids.has(String(message.id)))
    : messages.slice();

  if (payload.channel) {
    filtered = filtered.filter(
      (message) =>
        String(message.channel || "").toLowerCase() ===
        String(payload.channel).toLowerCase(),
    );
  }
  if (payload.unread) filtered = filtered.filter((message) => message.unread);
  if (payload.has_attachments) {
    filtered = filtered.filter(
      (message) =>
        message.has_attachments ||
        message.hasAttachments ||
        (Array.isArray(message.attachments) && message.attachments.length > 0),
    );
  }
  if (payload.sender) {
    filtered = filtered.filter((message) =>
      String(message.sender || message.sender_email || "")
        .toLowerCase()
        .includes(String(payload.sender).toLowerCase()),
    );
  }
  if (payload.subject) {
    filtered = filtered.filter((message) =>
      String(message.subject || "")
        .toLowerCase()
        .includes(String(payload.subject).toLowerCase()),
    );
  }
  if (payload.today) {
    const today = new Date().toDateString();
    filtered = filtered.filter((message) => {
      const date = new Date(message.received_at || message.date || "");
      return !Number.isNaN(date.getTime()) && date.toDateString() === today;
    });
  }

  renderAiFilteredMessages(filtered, "No loaded messages matched that filter.");
  return true;
}

function aiPrefillCompose(payload = {}) {
  aiNavigate({ target: "compose" });

  const inputs = document.querySelectorAll("#page-compose input");
  const textarea = document.querySelector("#page-compose textarea");
  const toInput = inputs[0];
  const subjectInput = inputs[1];

  if (toInput && payload.to) toInput.value = payload.to;
  if (subjectInput && payload.subject) subjectInput.value = payload.subject;
  if (textarea && payload.body) textarea.value = payload.body;
  return true;
}

function aiMarkReadLocal(payload = {}) {
  const messageId = payload.message_id || payload.id;
  if (!messageId) return false;
  markMessageRead(messageId);
  return true;
}

if (typeof window !== "undefined") {
  window.AICommandCenter = {
    applyFilter: aiApplyFilter,
    getActiveMessageId: () => currentMessageId || "",
    getActiveView: () => currentDashboardView || "sb-inbox",
    navigate: aiNavigate,
    openMessage: aiOpenMessage,
    prefillCompose: aiPrefillCompose,
    markReadLocal: aiMarkReadLocal,
  };
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

      if (messageId && messageId !== currentMessageId) {
        if (typeof window !== "undefined") window.activeMessageId = messageId;
        loadMessageDetail(messageId);
      }

      return;
    }

    // Inbox row click → load message

    const messageRow = event.target.closest(".inbox-item");

    if (messageRow) {
      const messageId = messageRow.dataset.messageId;

      if (messageId) {
        if (typeof window !== "undefined") window.activeMessageId = messageId;
        loadMessageDetail(messageId);
      }

      return;
    }

    // Prevent default on action buttons (handled elsewhere)

    const placeholderButton = event.target.closest(
      "#read-aloud-btn, #reply-btn, #forward-btn, #archive-btn, #delete-btn, .use-btn",
    );

    if (placeholderButton) event.preventDefault();
  });
}
