/**

 * app.js — Entry Point

 * Bootstraps the entire dashboard application.

 * Depends on: dashboard.js, message.js, compose.js, ai.js, settings.js

 */

document.addEventListener("DOMContentLoaded", () => {
  // ── Dashboard boot ──────────────────────────────────────────────────────────

  if (typeof applyInitialDashboardState === "function")
    applyInitialDashboardState();

  if (typeof bindDashboardInteractions === "function")
    bindDashboardInteractions();

  if (
    typeof setActiveSidebarItem === "function" &&
    typeof currentDashboardView !== "undefined"
  ) {
    setActiveSidebarItem(currentDashboardView);
  }

  if (typeof loadInboxMessages === "function") loadInboxMessages();

  if (typeof initializeOutlookNotifications === "function")
    initializeOutlookNotifications();

  // ── Compose attachment (single file toast) ──────────────────────────────────

  const fileInput = document.getElementById("compose-attachment");

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      const file = fileInput.files[0];

      if (file) showToast("📎 Attached: " + file.name);
    });
  }

  // ── Compose field error clear ───────────────────────────────────────────────

  const toEl = document.getElementById("compose-to");

  const msgEl = document.getElementById("compose-message");

  if (toEl) {
    toEl.addEventListener("input", () => {
      toEl.classList.remove("input-error");

      const err = document.getElementById("to-error");

      if (err) err.textContent = "";
    });
  }

  if (msgEl) {
    msgEl.addEventListener("input", () => {
      msgEl.classList.remove("input-error");

      const err = document.getElementById("message-error");

      if (err) err.textContent = "";
    });
  }

  // ── Multi-file attachment preview ───────────────────────────────────────────

  if (typeof initAttachmentPreview === "function") initAttachmentPreview();

  // ── Language preference restore ─────────────────────────────────────────────

  if (typeof restoreSavedLanguage === "function") restoreSavedLanguage();

  if (typeof restoreSavedTheme === "function") restoreSavedTheme();

  // ── Profile card toggle ─────────────────────────────────────────────────────

  if (typeof initProfileCardToggle === "function") initProfileCardToggle();
});

function handleNavSearch(query) {
  const value = String(query || "")
    .trim()
    .toLowerCase();
  const rows = document.querySelectorAll(".inbox-item");

  rows.forEach((row) => {
    const text = row.textContent.toLowerCase();
    row.hidden = Boolean(value) && !text.includes(value);
  });
}

// ── Global dropdown close on outside click ──────────────────────────────────

document.addEventListener("click", (e) => {
  if (!e.target.closest(".tool-dropdown")) {
    if (typeof closeMenus === "function") closeMenus();
  }
});
