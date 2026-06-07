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
  if (savedLang) applySavedLanguage(savedLang);

  fetch("/api/language-preference")
    .then((response) => response.json())
    .then((data) => {
      if (!data.language) return;
      localStorage.setItem("preferred_language", data.language);
      applySavedLanguage(data.language);
    })
    .catch(() => {});
}

function applySavedLanguage(language) {
  const selectA = document.getElementById("language-select");
  if (selectA) selectA.value = language;

  const selectB = document.getElementById("languageSelect");
  if (selectB) selectB.value = language;
}

async function saveLanguagePreference() {
  // Support both possible select IDs used in the templates
  const select =
    document.getElementById("language-select") ||
    document.getElementById("languageSelect");
  if (!select) return;

  const language = select.value;

  try {
    const response = await fetch("/api/set-language", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language }),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Language could not be saved.");
    }

    localStorage.setItem("preferred_language", data.language);
    applySavedLanguage(data.language);
    showToast("Language saved: " + data.language);
  } catch (error) {
    showToast(error.message || "Language could not be saved.", "error");
  }
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

function validatePassword() {
  const newPwd = document.getElementById("newPassword")?.value || "";
  const passwordHint = document.getElementById("passwordHint");
  if (!passwordHint) return;

  const pwdRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{8,}$/;
  passwordHint.style.display =
    newPwd.length > 0 && !pwdRegex.test(newPwd) ? "block" : "none";
  checkPasswordMatch();
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

// ── Appearance ────────────────────────────────────────────────────────────────
function resolveThemeChoice(choice) {
  if (choice !== "system") return choice;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function setThemePreference(choice) {
  const theme = choice || "light";
  localStorage.setItem("voiceMailTheme", theme);
  document.documentElement.dataset.theme = resolveThemeChoice(theme);
  document.documentElement.dataset.themeChoice = theme;
}

function saveAppearanceSettings() {
  const theme = document.getElementById("appearance-theme")?.value || "light";
  setThemePreference(theme);
  showToast("Appearance saved");
}

function restoreSavedTheme() {
  const theme = localStorage.getItem("voiceMailTheme") || "light";
  const select = document.getElementById("appearance-theme");
  if (select) select.value = theme;
  setThemePreference(theme);
}

// ── Voice Phrase Modal ────────────────────────────────────────────────────────
function openVoiceModal() {
  const modal = document.getElementById("voiceModal");
  if (modal) modal.style.display = "block";
}

function closeModal() {
  const modal = document.getElementById("voiceModal");
  if (modal) modal.style.display = "none";
}

function saveVoicePin() {
  const input = document.getElementById("voiceInput");
  const phrase = input?.value.trim() || "";
  if (!phrase) {
    showToast("Enter a voice phrase", "warning");
    return;
  }

  localStorage.setItem("voicePhrase", phrase);
  if (input) input.value = "";
  closeModal();
  showToast("Voice phrase saved");
}

// ── Logout Confirm ────────────────────────────────────────────────────────────
function confirmLogout() {
  if (window.confirm("Are you sure you want to sign out?")) {
    window.location.href = "/auth/logout";
  }
}

// ── Security Questions Modal ────────────────────────────────────────────────
function openSecurityQuestionsModal() {
  const modal = document.getElementById("securityQuestionsModal");
  if (modal) modal.style.display = "block";
}

function closeSecurityQuestionsModal() {
  const modal = document.getElementById("securityQuestionsModal");
  if (modal) modal.style.display = "none";
}

async function saveSecurityQuestions() {
  const q1 = document.getElementById("security_question_1")?.value.trim() || "";
  const a1 = document.getElementById("security_answer_1")?.value.trim() || "";
  const q2 = document.getElementById("security_question_2")?.value.trim() || "";
  const a2 = document.getElementById("security_answer_2")?.value.trim() || "";

  const hint = document.getElementById("securityQuestionsHint");
  if (hint) hint.style.display = "none";

  if (!q1 || !q2 || q1 === q2 || a1.length < 3 || a2.length < 3) {
    if (hint) hint.style.display = "block";
    return;
  }

  try {
    const res = await fetch("/auth/update-security-questions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        security_question_1: q1,
        security_answer_1: a1,
        security_question_2: q2,
        security_answer_2: a2,
      }),
    });

    const body = await res.json().catch(() => ({}));

    if (!res.ok) {
      showToast(body.error || "Could not save security questions", "error");
      return;
    }

    showToast(body.message || "Security questions saved");
    closeSecurityQuestionsModal();
  } catch (err) {
    showToast("Could not save security questions", "error");
  }
}
