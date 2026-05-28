/**
* compose.js — Compose + Send + AI Draft
* Handles message composition, sending, AI-assisted drafting, and attachments.
*/

// ── Multi-file Attachment State ───────────────────────────────────────────────
let selectedFiles = [];

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
function sendComposeMessage() {
 const toEl = document.getElementById("compose-to");
 const msgEl = document.getElementById("compose-message");
 const toError = document.getElementById("to-error");
 const msgError = document.getElementById("message-error");

 // Clear previous errors
 if (toError) toError.textContent = "";
 if (msgError) msgError.textContent = "";
 toEl?.classList.remove("input-error");
 msgEl?.classList.remove("input-error");

 const data = {
   channel: document.getElementById("compose-channel")?.value,
   to: toEl?.value,
   subject: document.getElementById("compose-subject")?.value,
   body: msgEl?.value,
   schedule: document.getElementById("compose-schedule")?.value,
 };

 fetch("/auth/send-message", {
   method: "POST",
   headers: { "Content-Type": "application/json" },
   body: JSON.stringify(data),
 })
   .then(async (res) => {
     const response = await res.json();

     if (!res.ok) {
       if (response.error?.includes("Recipient")) {
         if (toError) toError.textContent = "Recipient is required";
         toEl?.classList.add("input-error");
       }
       if (response.error?.includes("message")) {
         if (msgError) msgError.textContent = "Message is required";
         msgEl?.classList.add("input-error");
       }
       return;
     }

     showToast("✅ Message sent successfully");
     if (toEl) toEl.value = "";
     if (msgEl) msgEl.value = "";
     const subjectEl = document.getElementById("compose-subject");
     if (subjectEl) subjectEl.value = "";
     updateComposeCount();
   })
   .catch((err) => {
     console.error(err);
     showToast("❌ Failed to send message", "error");
   });
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
async function handleAiWrite() {
 const subjectEl = document.getElementById("compose-subject");
 const messageEl = document.getElementById("compose-message");

 if (!subjectEl || !messageEl) {
   console.error("Compose fields not found");
   return;
 }

 const prompt = messageEl.value || subjectEl.value;
 if (!prompt.trim()) {
   showToast("Please type something first", "warning");
   return;
 }

 const originalText = messageEl.value;
 messageEl.value = "Generating AI draft...";

 try {
   const res = await fetch("/api/compose/draft", {
     method: "POST",
     headers: { "Content-Type": "application/json" },
     body: JSON.stringify({ prompt, tone: "professional" }),
   });

   const data = await res.json();
   console.log("API RESPONSE:", data);
   if (!res.ok) throw new Error(data.error || "Failed");

   const draft = data.draft || "";
   const subjectMatch = draft.match(/Subject:(.*)/i);
   if (subjectMatch) subjectEl.value = subjectMatch[1].trim();


// ✅ SAFE FIX (important)
   let cleanDraft = draft.replace(/Subject:.*\n?/i, "").trim();

   // ✅ fallback if empty
   messageEl.value = cleanDraft || draft;
   updateComposeCount();

   showToast("✅ AI draft generated");
 } catch (err) {
   console.error(err);
   messageEl.value = originalText;
   showToast("❌ Draft generation failed", "error");
 }
}

// ── AI Input Key Handler ──────────────────────────────────────────────────────
function handleAiKey(event) {
 if (event.key === "Enter") {
   event.preventDefault();
   if (typeof sendAiQuery === "function") sendAiQuery();
 }
}
