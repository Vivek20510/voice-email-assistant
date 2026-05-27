/**

 * app.js — Entry Point

 * Bootstraps the entire dashboard application.

 * Depends on: dashboard.js, message.js, compose.js, ai.js, settings.js

 */

document.addEventListener("DOMContentLoaded", () => {
  // ── Dashboard boot ──────────────────────────────────────────────────────────

  applyInitialDashboardState();

  bindDashboardInteractions();

  setActiveSidebarItem(currentDashboardView);

  loadInboxMessages();

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

  initAttachmentPreview();

  // ── Language preference restore ─────────────────────────────────────────────

  restoreSavedLanguage();

  // ── Profile card toggle ─────────────────────────────────────────────────────

  initProfileCardToggle();
});

// ── Global dropdown close on outside click ──────────────────────────────────

document.addEventListener("click", (e) => {
  if (!e.target.closest(".tool-dropdown")) {
    closeMenus();
  }
});
