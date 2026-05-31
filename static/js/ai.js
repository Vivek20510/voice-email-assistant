 /**
* ai.js — AI Summary + Suggested Replies + Read Aloud
* All AI-powered features: summarize, generate reply suggestions, text-to-speech.
* Depends on: dashboard.js (state), message.js (DOM IDs)
*/

// ── Summary ───────────────────────────────────────────────────────────────────
async function generateSummary() {
 const summaryEl = document.getElementById("summary-text");
 const btn = document.getElementById("summarize-btn");
 if (!summaryEl || !currentMessageId) return;
 if (btn?.disabled) return;

 const message = findCachedMessage(currentMessageId);
 if (!message) {
   summaryEl.textContent = "Unable to summarize this message.";
   return;
 }

 const textToSummarize = message.body_text || toPreviewText(message.snippet) || "";
 if (!textToSummarize || textToSummarize.length < 30) {
   summaryEl.textContent = "Message is too short to summarize.";
   return;
 }

 // Loading state
 if (btn) { btn.disabled = true; btn.textContent = "Generating..."; }
 summaryEl.textContent = "Generating AI summary…";

 try {
   const response = await fetch("/ai/summary", {
     method: "POST",
     headers: { "Content-Type": "application/json" },
     body: JSON.stringify({ text: textToSummarize }),
   });

   const data = await response.json();
   if (!response.ok) {
     summaryEl.textContent = data.error || "Failed to generate summary.";
     return;
   }

   summaryEl.textContent = data.summary || "No summary returned.";
 } catch {
   summaryEl.textContent = "Network error while generating summary.";
 } finally {
   if (btn) { btn.disabled = false; btn.textContent = "✨ Summarize"; }
 }
}

// ── Generate Replies ──────────────────────────────────────────────────────────

/**
* Called from message.js after the message view is rendered.
* Binds the "Generate Replies" button for the given message object.
*/
function bindGenerateRepliesButton(message) {
 const generateBtn = document.getElementById("generate-replies-btn");
 if (!generateBtn) return;

 generateBtn.addEventListener("click", () => {
   const wrap = document.getElementById("suggestions-generate-wrap");
   if (wrap) {
     wrap.innerHTML = `
       <span style="color:#888; font-style:italic; font-size:13px;">
         Generating AI replies...
       </span>`;
   }

   const rawBody = message.body_text || message.snippet || "";
   const emailBody = extractOriginalEmail(rawBody);

   if (!emailBody.trim()) {
     if (wrap) wrap.innerHTML = `<span style="color:#888;">No email content.</span>`;
     return;
   }

   fetch("/nlp/suggest", {
     method: "POST",
     headers: { "Content-Type": "application/json" },
     body: JSON.stringify({ text: emailBody }),
   })
     .then((res) => {
       if (!res.ok) throw new Error("AI error");
       return res.json();
     })
     .then((data) => {
       const list = document.getElementById("suggestions-list");
       const replies = Object.entries(data.suggestions || {});

       list.innerHTML = replies
         .map(
           ([tone, suggestion]) => `
             <div class="suggestion-item message-detail-suggestion-item">
               <div style="font-size:12px; color:#888;">${escapeHtml(tone)}</div>
               <span class="message-detail-suggestion-text">${escapeHtml(suggestion)}</span>
               <button type="button" class="use-btn message-detail-use-btn">Use</button>
             </div>`
         )
         .join("");

       list.querySelectorAll(".use-btn").forEach((btn) => {
         btn.addEventListener("click", () => {
           const text =
             btn.closest(".suggestion-item")
               ?.querySelector(".message-detail-suggestion-text")
               ?.textContent || "";

           const composeBody =
             document.getElementById("compose-message") ||
             document.getElementById("compose-body") ||
             document.getElementById("message");
           if (composeBody) composeBody.value = text;
           if (typeof switchPage === "function") switchPage("compose");
         });
       });
     })
     .catch(() => {
       const list = document.getElementById("suggestions-list");
       if (list) list.innerHTML = `<span style="color:#888;">Failed to generate replies.</span>`;
     });
 });
}

// ── Read Aloud (TTS) ──────────────────────────────────────────────────────────
async function handleReadAloud() {
 const btn = document.getElementById("read-aloud-btn");
 if (!btn || !currentMessageId) return;
 if (btn.disabled) return;

 const message = findCachedMessage(currentMessageId);
 if (!message) return;

 // Pick text: prefer visible summary, fall back to body
 let text = "";
 const summaryText = document.getElementById("summary-text")?.textContent;
 if (
   summaryText &&
   summaryText.length > 15 &&
   !summaryText.includes("Click") &&
   !summaryText.includes("Translating")
 ) {
   text = summaryText;
 } else {
   text = message.body_text || message.snippet || "";
 }

 if (!text.trim()) {
   showToast("No text available", "warning");
   return;
 }

 const language = localStorage.getItem("preferred_language") || "English";

 btn.disabled = true;
 btn.textContent = "🔊 Playing...";

 try {
   const res = await fetch("/read-aloud", {
     method: "POST",
     headers: { "Content-Type": "application/json" },
     body: JSON.stringify({ text, language }),
   });

   const data = await res.json();
   if (!res.ok || !data.audio_url) throw new Error(data.error || "TTS failed");

   console.log("🔊 Audio URL:", data.audio_url);

   // Stop any previous audio
   if (window.currentAudio) {
     window.currentAudio.pause();
     window.currentAudio = null;
   }

   const audioUrl = data.audio_url + "?t=" + Date.now();
   const audio = new Audio();
   audio.src = audioUrl;
   audio.preload = "auto";
   window.currentAudio = audio;

   audio.addEventListener("canplaythrough", () => {
     console.log("✅ Audio ready");
     audio.play()
       .then(() => console.log("▶ Playing"))
       .catch((err) => {
         console.error("❌ Playback blocked:", err);
         showToast("Click again to play 🔊", "warning");
         btn.disabled = false;
         btn.textContent = "▶ Read aloud";
       });
   });

   // Fallback for browsers that may skip canplaythrough
   audio.addEventListener("loadeddata", () => {
     console.log("✅ Audio loaded");
     audio.play().catch(() => console.warn("Autoplay blocked"));
   });

   audio.onended = () => {
     console.log("✅ Audio finished");
     btn.disabled = false;
     btn.textContent = "▶ Read aloud";
   };

   audio.onerror = (e) => {
     console.error("❌ Audio error", e);
     showToast("Audio playback error", "error");
     btn.disabled = false;
     btn.textContent = "▶ Read aloud";
   };

   audio.load();
 } catch (err) {
   console.error(err);
   showToast("❌ Audio failed", "error");
   btn.disabled = false;
   btn.textContent = "▶ Read aloud";
 }
} 
