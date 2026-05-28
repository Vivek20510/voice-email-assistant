
/**
* message.js — Message View
* Handles single-message rendering, mini sidebar, iframe, and back navigation.
* Depends on: dashboard.js (state + helpers), ai.js (generateSummary, handleReadAloud)
*/

// ── Iframe Helpers ────────────────────────────────────────────────────────────
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

function resizeMessageFrame(frame) {
 if (!frame) return;
 try {
   const doc = frame.contentDocument || frame.contentWindow?.document;
   const root = doc?.documentElement;
   const body = doc?.body;
   const contentHeight = Math.max(
     root?.scrollHeight || 0,
     root?.offsetHeight || 0,
     body?.scrollHeight || 0,
     body?.offsetHeight || 0
   );
   if (contentHeight > 0) frame.style.height = `${Math.max(contentHeight + 24, 420)}px`;
 } catch {
   frame.style.height = "70vh";
 }
}

// ── Formatting ────────────────────────────────────────────────────────────────
function formatTimestamp(value) {
 if (!value) return "Unknown time";
 const parsed = new Date(value);
 if (Number.isNaN(parsed.getTime())) return value;
 return parsed.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function formatPlainMessageBody(bodyText) {
 const text = String(bodyText || "").trim();
 if (!text) return "";
 return text
   .split(/\n{2,}/)
   .map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`)
   .join("");
}

function extractOriginalEmail(text) {
 if (!text) return "";
 let cleaned = String(text);
 const splitMarkers = [
   /^From:.*$/im,
   /^Sent:.*$/im,
   /^To:.*$/im,
   /^Subject:.*$/im,
   /^On .* wrote:$/im,
   /^---+$/m,
 ];
 for (const marker of splitMarkers) cleaned = cleaned.split(marker)[0];
 return cleaned.trim();
}

// ── Mini Sidebar ──────────────────────────────────────────────────────────────
function getMessageNavigationItems(activeMessage) {
 const channel = channelForView(currentDashboardView);
 const cachedMessages = inboxMessagesCacheByChannel[channel] || inboxMessagesCache || [];
 const items = cachedMessages.slice(0, 25);
 const hasActive = items.some((i) => String(i.id) === String(activeMessage.id));
 return hasActive ? items : [activeMessage, ...items].slice(0, 25);
}

function renderMessageMiniSidebar(activeMessage) {
 const messages = getMessageNavigationItems(activeMessage);

 const rows = messages.map((item) => {
   const sender = item.sender || item.sender_email || "Unknown sender";
   const subject = item.subject || "(No subject)";
   const snippet = item.snippet || item.body_text || "No preview available.";
   const isActive = String(item.id) === String(activeMessage.id);
   const unreadClass = item.unread ? " is-unread" : "";

   return `
     <button type="button"
       class="message-mini-item${isActive ? " active" : ""}${unreadClass}"
       data-message-id="${escapeHtml(item.id)}"
     >
       <span class="message-mini-avatar">${escapeHtml(getAvatarInitials(sender))}</span>
       <span class="message-mini-copy">
         <span class="message-mini-row">
           <strong>${escapeHtml(sender)}</strong>
           <time>${escapeHtml(formatInboxTime(item.received_at))}</time>
         </span>
         <span class="message-mini-subject">${escapeHtml(subject)}</span>
         <span class="message-mini-snippet">${escapeHtml(toPreviewText(snippet))}</span>
       </span>
     </button>`;
 }).join("");

 return `
   <aside class="message-mini-sidebar">
     <div class="message-mini-header">
       <span>Messages</span>
       <span class="message-mini-count">${messages.length}</span>
     </div>
     <div class="message-mini-list">${rows}</div>
   </aside>`;
}

function scrollActiveMiniMessageIntoViewIfNeeded() {
 const activeItem = document.querySelector(".message-mini-item.active");
 const miniList = document.querySelector(".message-mini-list");
 if (!activeItem || !miniList) return;

 const itemRect = activeItem.getBoundingClientRect();
 const listRect = miniList.getBoundingClientRect();
 if (itemRect.top < listRect.top || itemRect.bottom > listRect.bottom) {
   activeItem.scrollIntoView({ behavior: "auto", block: "nearest" });
 }
}

// ── Loading / Error States ────────────────────────────────────────────────────
function renderMessageLoading(activeMessage = null) {
 setDashboardMessageMode(true);
 const miniSidebar = activeMessage ? renderMessageMiniSidebar(activeMessage) : "";

 setInboxContent(`
   <section class="message-view-page message-view-page-inline">
     <div class="message-view-wrap message-view-wrap-inline">
       <div class="message-detail-topbar message-detail-topbar-inline">
         <button type="button" class="back-btn message-detail-back" onclick="restoreInboxList()">← Back</button>
       </div>
       <div class="message-detail-layout message-detail-layout-inline">
         ${miniSidebar}
         <div class="message-detail-shell message-detail-shell-inline">
           <div class="message-detail-status" data-state="loading">
             <div class="message-loading-spinner" aria-hidden="true"></div>
             <h3>Loading message...</h3>
             <p>Fetching the selected email details.</p>
           </div>
         </div>
       </div>
     </div>
   </section>
 `);
 restoreMiniMessageListScroll();
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

// ── Full Message View ─────────────────────────────────────────────────────────
function renderMessageView(message) {
 setDashboardMessageMode(true);
 rememberMiniMessageListScroll();

 const sender = message.sender || message.sender_email || "Unknown sender";
 const subject = message.subject || "(No subject)";
 const bodyHtml = message.body_html || "";
 const bodyText = message.body_text || "";

 const safeBody = bodyHtml
   ? `<iframe id="message-html-frame" class="message-html-frame" title="Email message body" sandbox="allow-same-origin" referrerpolicy="no-referrer"></iframe>`
   : formatPlainMessageBody(bodyText) || "<p>No message body available.</p>";

 const suggestionMarkup = `
   <div id="suggestions-generate-wrap" style="text-align:center; padding: 12px 0;">
     <button type="button" id="generate-replies-btn" class="action-btn primary" style="padding: 8px 20px; font-size: 14px;">
       ✦ Generate Replies
     </button>
   </div>`;

 setInboxContent(`
   <section class="message-view-page message-view-page-inline" data-message-id="${escapeHtml(message.id)}">
     <div class="message-view-wrap message-view-wrap-inline">
       <div class="message-detail-topbar message-detail-topbar-inline">
         <button type="button" class="back-btn message-detail-back" onclick="restoreInboxList()">← Back</button>
       </div>

       <div class="message-detail-layout message-detail-layout-inline">
         ${renderMessageMiniSidebar(message)}

         <div class="message-detail-shell message-detail-shell-inline">
           <div class="summary-card message-detail-summary-card">
             <div>
               <div class="summary-badge message-detail-summary-badge">✦ AI Summary</div>
               <h3 class="message-detail-summary-sender">${escapeHtml(sender)}</h3>
               <div id="summary-text" class="summary-text message-detail-summary-text">
                 Click "Summarize" to generate AI summary.
               </div>
             </div>
             <button id="read-aloud-btn" type="button" class="read-aloud-btn message-detail-ghost-btn">▶ Read aloud</button>
             <button id="summarize-btn" type="button" class="message-detail-ghost-btn">✨ Summarize</button>
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
               <div class="suggestions-title message-detail-suggestions-title">
                 <span class="message-detail-star">✦</span> AI-Suggested Replies
               </div>
               <div class="ai-badge message-detail-ai-badge">AI</div>
             </div>
             <div id="suggestions-list" class="message-detail-suggestions-list">
               ${suggestionMarkup}
             </div>
           </div>
         </div>
       </div>
     </div>
   </section>
 `);

 restoreMiniMessageListScroll();

 // ── iframe init ──
 const frame = document.getElementById("message-html-frame");
 if (frame) {
   frame.addEventListener("load", () => resizeMessageFrame(frame), { once: true });
   frame.srcdoc = buildEmailHtmlDocument(bodyHtml);
   setTimeout(() => resizeMessageFrame(frame), 300);
   setTimeout(() => resizeMessageFrame(frame), 1000);
 }

 // ── Scroll mini list ──
 setTimeout(() => scrollActiveMiniMessageIntoViewIfNeeded(), 50);

 // ── Wire AI buttons (defined in ai.js) ──
 setTimeout(() => {
   const summarizeBtn = document.getElementById("summarize-btn");
   if (summarizeBtn) summarizeBtn.addEventListener("click", () => generateSummary());

   const readBtn = document.getElementById("read-aloud-btn");
   if (readBtn) readBtn.onclick = handleReadAloud;

   bindGenerateRepliesButton(message);
 }, 0);
}

// ── Fetch & Load ──────────────────────────────────────────────────────────────
async function loadMessageDetail(messageId) {
 rememberMiniMessageListScroll();
 currentMessageId = messageId;
 markMessageRead(messageId);
 renderMessageLoading(findCachedMessage(messageId));

 try {
   const response = await fetch(
     `/api/messages/${encodeURIComponent(messageId)}`,
     { headers: { Accept: "application/json" }, credentials: "same-origin" }
   );

   let payload = {};
   try { payload = await response.json(); } catch { payload = {}; }

   if (!response.ok) {
     renderMessageError(payload.error || "Unable to load this message.");
     return;
   }
   renderMessageView(payload);
 } catch {
   renderMessageError("Network error while loading this message.");
 }
}

