/**
* compose.js — Compose + Send + AI Draft
* Handles message composition, sending, AI-assisted drafting, and attachments.
*/

// ── Multi-file Attachment State ───────────────────────────────────────────────
let selectedFiles = [];
let composeSendLoading = false;
let composeDraftLoading = false;
let lastAiDraftState = null;

function updateComposeCount() {
 const messageEl = document.getElementById("compose-message");
 const countEl = document.getElementById("compose-count");
 if (!messageEl || !countEl) return;
 countEl.textContent = String(messageEl.value.length);
}

function initAttachmentPreview() {
 const fileInput = document.getElementById("compose-attachment");
 const preview = document.getElementById("attachment-preview");
 if (!fileInput || !preview) return;

 fileInput.addEventListener("change", () => {
   Array.from(fileInput.files).forEach((file) => {
     selectedFiles.push(file);

     const fileDiv = document.createElement("div");
     fileDiv.className = "attachment-item";
     fileDiv.innerHTML = `
       <span>📎 ${escapeHtml(file.name)}</span>
       <button type="button" data-name="${escapeHtml(file.name)}">✕</button>
     `;

     fileDiv.querySelector("button").addEventListener("click", () => {
       selectedFiles = selectedFiles.filter((f) => f.name !== file.name);
       fileDiv.remove();
     });

     preview.appendChild(fileDiv);
   });

   // Allow same file to be re-selected
   fileInput.value = "";
 });
}

// ── Profile Card Toggle ───────────────────────────────────────────────────────
function initProfileCardToggle() {
 const toggle = document.getElementById("profileToggle");
 const card = document.getElementById("profileCard");
 if (!toggle || !card) return;

 toggle.addEventListener("click", (e) => {
   e.stopPropagation();
   card.classList.toggle("active");
 });

 document.addEventListener("click", () => card.classList.remove("active"));
}

// ── Photo Picker ──────────────────────────────────────────────────────────────
function openPhotoPicker() {
 document.getElementById("photoInput").click();
}

function loadPhoto(event) {
 const file = event.target.files[0];
 if (!file) return;
 const reader = new FileReader();
 reader.onload = (e) => {
   document.getElementById("profilePhoto").src = e.target.result;
 };
 reader.readAsDataURL(file);
}

// ── Send Message ──────────────────────────────────────────────────────────────
function setButtonLoading(button, loading, loadingLabel) {
 if (!button) return;
 if (!button.dataset.defaultLabel) button.dataset.defaultLabel = button.textContent.trim();
 button.disabled = loading;
 const label = button.querySelector("span");
 if (label) {
   label.textContent = loading ? loadingLabel : button.dataset.defaultLabel;
 } else {
   button.textContent = loading ? loadingLabel : button.dataset.defaultLabel;
 }
}

function clearComposeErrors() {
 const toEl = document.getElementById("compose-to");
 const msgEl = document.getElementById("compose-message");
 const toError = document.getElementById("to-error");
 const msgError = document.getElementById("message-error");

 if (toError) toError.textContent = "";
 if (msgError) msgError.textContent = "";
 toEl?.classList.remove("input-error");
 msgEl?.classList.remove("input-error");
}

function setComposeError(field, message) {
 const errorId = field === "to" ? "to-error" : "message-error";
 const fieldId = field === "to" ? "compose-to" : "compose-message";
 const errorEl = document.getElementById(errorId);
 const fieldEl = document.getElementById(fieldId);

 if (errorEl) errorEl.textContent = message;
 fieldEl?.classList.add("input-error");
}

async function readJsonResponse(response) {
 try {
   return await response.json();
 } catch {
   return {};
 }
}

async function sendComposeMessage() {
 if (composeSendLoading) return;

 const toEl = document.getElementById("compose-to");
 const msgEl = document.getElementById("compose-message");
 const subjectEl = document.getElementById("compose-subject");
 const channelEl = document.getElementById("compose-channel");
 const scheduleEl = document.getElementById("compose-schedule");
 const sendBtn = document.getElementById("compose-send-btn");

 clearComposeErrors();

 const channel = (channelEl?.value || "gmail").toLowerCase();
 const to = (toEl?.value || "").trim();
 const body = (msgEl?.value || "").trim();

 if (!to) {
   setComposeError("to", "Recipient is required");
   return;
 }

 if (!body) {
   setComposeError("message", "Message is required");
   return;
 }

 if (!["gmail", "outlook"].includes(channel)) {
   showToast("Sending via WhatsApp or Telegram is not supported yet", "warning");
   return;
 }

 const data = {
   channel,
   to,
   subject: subjectEl?.value || "",
   body,
   schedule: scheduleEl?.value || "now",
 };

 const endpoint = channel === "gmail" ? "/api/send" : "/auth/send-message";

 composeSendLoading = true;
 setButtonLoading(sendBtn, true, "Sending...");

 try {
   const res = await fetch(endpoint, {
     method: "POST",
     headers: { "Content-Type": "application/json" },
     body: JSON.stringify(data),
   });

   const response = await readJsonResponse(res);

   if (!res.ok) {
     const error = response.error || response.message || "Failed to send message";
     if (/recipient|to/i.test(error)) setComposeError("to", "Recipient is required");
     if (/message|body/i.test(error)) setComposeError("message", "Message is required");
     showToast(error, "error");
     return;
   }

   showToast("Message sent successfully");
   if (toEl) toEl.value = "";
   if (msgEl) msgEl.value = "";
   if (subjectEl) subjectEl.value = "";
   updateComposeCount();
 } catch (err) {
   console.error(err);
   showToast("Failed to send message", "error");
 } finally {
   composeSendLoading = false;
   setButtonLoading(sendBtn, false, "Send");
 }
}

function saveComposeDraft() {
 const draft = {
   channel: document.getElementById("compose-channel")?.value || "outlook",
   to: document.getElementById("compose-to")?.value || "",
   subject: document.getElementById("compose-subject")?.value || "",
   body: document.getElementById("compose-message")?.value || "",
   schedule: document.getElementById("compose-schedule")?.value || "now",
   updatedAt: new Date().toISOString(),
 };

 localStorage.setItem("composeDraft", JSON.stringify(draft));
 showToast("Draft saved");
}

// ── AI Write / Draft ──────────────────────────────────────────────────────────
function setAiDraftActionsVisible(visible) {
 const undoBtn = document.getElementById("compose-ai-undo-btn");
 const regenerateBtn = document.getElementById("compose-ai-regenerate-btn");
 if (undoBtn) undoBtn.hidden = !visible;
 if (regenerateBtn) regenerateBtn.hidden = !visible;
}

function parseDraft(draft) {
 const subjectMatch = draft.match(/Subject:(.*)/i);
 return {
   subject: subjectMatch ? subjectMatch[1].trim() : "",
   body: draft.replace(/Subject:.*\n?/i, "").trim() || draft,
 };
}

async function requestAiDraft(prompt, tone = "professional") {
 const res = await fetch("/api/compose/draft", {
   method: "POST",
   headers: { "Content-Type": "application/json" },
   body: JSON.stringify({ prompt, tone }),
 });

 const data = await readJsonResponse(res);
 if (!res.ok) throw new Error(data.error || "AI draft generation failed");
 return data;
}

async function handleAiWrite(options = {}) {
 if (composeDraftLoading) return;

 const subjectEl = document.getElementById("compose-subject");
 const messageEl = document.getElementById("compose-message");
 const aiBtn = document.getElementById("compose-ai-write-btn");
 const regenerateBtn = document.getElementById("compose-ai-regenerate-btn");

 if (!subjectEl || !messageEl) {
   console.error("Compose fields not found");
   return;
 }

 const prompt = options.prompt || messageEl.value || subjectEl.value;
 const tone = options.tone || "professional";
 if (!prompt.trim()) {
   showToast("Please type something first", "warning");
   return;
 }

 const previousBody =
   options.previousBody !== undefined ? options.previousBody : messageEl.value;
 const previousSubject =
   options.previousSubject !== undefined ? options.previousSubject : subjectEl.value;

 composeDraftLoading = true;
 setButtonLoading(aiBtn, true, "Writing...");
 setButtonLoading(regenerateBtn, true, "Regenerating...");

 try {
   const data = await requestAiDraft(prompt, tone);
   const parsed = parseDraft(data.draft || "");

   if (parsed.subject) subjectEl.value = parsed.subject;
   messageEl.value = parsed.body;
   lastAiDraftState = {
     prompt,
     tone,
     previousBody,
     previousSubject,
   };
   updateComposeCount();
   setAiDraftActionsVisible(true);

   showToast("AI draft generated");
 } catch (err) {
   console.error(err);
   showToast(err.message || "Draft generation failed", "error");
 } finally {
   composeDraftLoading = false;
   setButtonLoading(aiBtn, false, "AI Write");
   setButtonLoading(regenerateBtn, false, "Regenerate");
 }
}

function undoAiDraft() {
 if (!lastAiDraftState || composeDraftLoading) return;

 const subjectEl = document.getElementById("compose-subject");
 const messageEl = document.getElementById("compose-message");

 if (subjectEl) subjectEl.value = lastAiDraftState.previousSubject || "";
 if (messageEl) messageEl.value = lastAiDraftState.previousBody || "";

 updateComposeCount();
 setAiDraftActionsVisible(false);
 showToast("AI draft undone");
}

function regenerateAiDraft() {
 if (!lastAiDraftState || composeDraftLoading) return;
 handleAiWrite({
   prompt: lastAiDraftState.prompt,
   tone: lastAiDraftState.tone,
   previousBody: lastAiDraftState.previousBody,
   previousSubject: lastAiDraftState.previousSubject,
 });
}

// ── AI Input Key Handler ──────────────────────────────────────────────────────
function handleAiKey(event) {
 if (event.key === "Enter") {
   event.preventDefault();
   if (typeof sendAiQuery === "function") sendAiQuery();
 }
}
