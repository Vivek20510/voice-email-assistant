/**
 * settings.js — Language + Password + Toast + UI Utilities
 * Settings panel logic: language preference, password change, toast notifications.
 */

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(message, type = "success") {
  const toast = document.getElementById("toast");
  if (!toast) return;

  toast.innerText = message;

  if (type === "error") {
    toast.style.backgroundColor = "#dc3545";
    toast.style.color = "#fff";
  } else if (type === "warning") {
    toast.style.backgroundColor = "#ffc107";
    toast.style.color = "#000";
  } else {
    toast.style.backgroundColor = "#28a745";
    toast.style.color = "#fff";
  }

  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2500);
}

// ── Language Preference ───────────────────────────────────────────────────────
function restoreSavedLanguage() {
  const savedLang = localStorage.getItem("preferred_language");
  if (!savedLang) return;

  // Settings page select (id="language-select")
  const selectA = document.getElementById("language-select");
  if (selectA) selectA.value = savedLang;

  // Dashboard settings select (id="languageSelect")
  const selectB = document.getElementById("languageSelect");
  if (selectB) selectB.value = savedLang;
}

function saveLanguagePreference() {
  // Support both possible select IDs used in the templates
  const select =
    document.getElementById("language-select") ||
    document.getElementById("languageSelect");
  if (!select) return;

  const language = select.value;
  localStorage.setItem("preferred_language", language);

  // Optional backend persist
  fetch("/api/set-language", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  }).catch(() => {});

  showToast("✅ Language saved: " + language);
}

// ── Password Change Modal ─────────────────────────────────────────────────────
function openChangePassword() {
  const modal = document.getElementById("changePasswordModal");
  if (modal) modal.style.display = "block";
}

function closeChangePassword() {
  const modal = document.getElementById("changePasswordModal");
  if (modal) modal.style.display = "none";
}

function checkPasswordMatch() {
  const newPwd = document.getElementById("newPassword")?.value || "";
  const confirmPwd = document.getElementById("confirmPassword")?.value || "";
  const matchHint = document.getElementById("matchHint");
  if (!matchHint) return;

  matchHint.style.display =
    confirmPwd.length > 0 && newPwd !== confirmPwd ? "block" : "none";
}

function hideOldPwdError() {
  const el = document.getElementById("oldPwdHint");
  if (el) el.style.display = "none";
}

// Alias kept for backward compat
function hideOldError() {
  hideOldPwdError();
}

function submitPassword() {
  const oldPwd = document.getElementById("oldPassword")?.value.trim() || "";
  const newPwd = document.getElementById("newPassword")?.value.trim() || "";
  const confirmPwd =
    document.getElementById("confirmPassword")?.value.trim() || "";

  const passwordHint = document.getElementById("passwordHint");
  const matchHint = document.getElementById("matchHint");
  const samePwdHint = document.getElementById("samePwdHint");
  const oldPwdHint = document.getElementById("oldPwdHint");

  // Reset all hints
  [passwordHint, matchHint, samePwdHint, oldPwdHint].forEach((el) => {
    if (el) el.style.display = "none";
  });

  const pwdRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{8,}$/;
  let isValid = true;

  if (!oldPwd || !newPwd || !confirmPwd) isValid = false;

  if (!pwdRegex.test(newPwd)) {
    if (passwordHint) passwordHint.style.display = "block";
    isValid = false;
  }

  if (newPwd !== confirmPwd) {
    if (matchHint) matchHint.style.display = "block";
    isValid = false;
  }

  if (oldPwd === newPwd && newPwd.length > 0) {
    if (samePwdHint) samePwdHint.style.display = "block";
    isValid = false;
  }

  if (!isValid) return;

  fetch("/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ oldPassword: oldPwd, newPassword: newPwd }),
  })
    .then((res) => res.json().then((body) => ({ status: res.status, body })))
    .then(({ status, body }) => {
      if (oldPwdHint) oldPwdHint.style.display = "none";

      if (status !== 200) {
        if (body.error === "Incorrect old password") {
          if (oldPwdHint) oldPwdHint.style.display = "block";
        }
        if (body.error?.includes("same")) {
          if (samePwdHint) samePwdHint.style.display = "block";
        }
        return;
      }

      showToast("✅ Password updated successfully");
      ["oldPassword", "newPassword", "confirmPassword"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = "";
      });
      closeChangePassword();
    });
}

// ── Settings Tab Switcher ─────────────────────────────────────────────────────
function switchSettingsTab(clickedEl, panelId) {
  // Deactivate all nav items
  document.querySelectorAll(".settings-nav-item").forEach((item) => {
    item.classList.remove("active");
  });
  clickedEl.classList.add("active");

  // Hide all panels
  document.querySelectorAll(".settings-section").forEach((section) => {
    section.classList.remove("active");
    section.classList.add("hidden");
  });

  // Activate target panel
  const panel = document.getElementById(panelId);
  if (panel) {
    panel.classList.add("active");
    panel.classList.remove("hidden");
  }
}

function activateSettingsTabByName(tabName) {
  const map = {
    profile: "spanel-profile",
    voice: "spanel-voice",
    notifications: "spanel-notifications",
    channels: "spanel-channels",
    security: "spanel-security",
    appearance: "spanel-appearance",
    language: "spanel-language",
  };
  const panelId = map[tabName];
  if (!panelId) return;

  const navItems = document.querySelectorAll(".settings-nav-item");
  navItems.forEach((item) => {
    if (item.getAttribute("onclick")?.includes(panelId)) {
      switchSettingsTab(item, panelId);
    }
  });
}

// ── Logout Confirm ────────────────────────────────────────────────────────────
function confirmLogout() {
  if (window.confirm("Are you sure you want to sign out?")) {
    window.location.href = "/auth/logout";
  }
}
