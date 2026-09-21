/* =========================================================
   Sarthi — AI Travel Assistant widget (floating chat bubble).
   Talks to POST /api/ai/chat. If no AI provider key is set on
   the backend, the endpoint honestly reports "not configured"
   and this widget shows that state instead of pretending the
   assistant is live (spec section 40).

   Session management:
   - Conversation survives navigating between pages (Explore,
     Planner, Home) via sessionStorage, so asking a follow-up
     after clicking through to another page doesn't lose context.
     It's cleared when the browser tab closes, or via "Clear chat".
   - Only one request is ever in flight at a time (input disabled
     while waiting) so replies can't arrive out of order and get
     appended to the wrong place in the conversation.
   - Only the most recent messages are actually sent to the AI
     provider on each turn (full history is still shown/kept
     locally) so a long-running conversation can't silently blow
     past the provider's context window.
   ========================================================= */
(function () {
  "use strict";
  if (!window.SarthiAPI) return;

  var HISTORY_KEY = "sarthi.aiHistory";
  var MAX_TURNS_SENT = 20; // most recent messages actually sent to the AI provider each call

  var history = loadHistory();
  var checkedConfig = false;
  var isConfigured = null;
  var sending = false;

  function loadHistory() {
    try {
      var raw = sessionStorage.getItem(HISTORY_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveHistory() {
    try { sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch (e) { /* private mode etc -- fine, just in-memory for this page view */ }
  }

  function el(html) {
    var d = document.createElement("div");
    d.innerHTML = html.trim();
    return d.firstChild;
  }

  function build() {
    var bubble = el(
      '<button class="ai-fab" type="button" aria-label="Open Sarthi AI Assistant">' +
        '<span class="ai-fab__icon">✨</span>' +
      "</button>"
    );
    var panel = el(
      '<div class="ai-panel" hidden>' +
        '<div class="ai-panel__head">' +
          '<div><b>✨ Sarthi AI Assistant</b><span class="ai-panel__status" data-ai-status>checking…</span></div>' +
          '<div class="ai-panel__head-actions">' +
            '<button class="icon-btn" data-ai-clear aria-label="Clear conversation" title="Clear conversation">' +
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6h12z"/></svg>' +
            "</button>" +
            '<button class="icon-btn" data-ai-close aria-label="Close">' +
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>' +
            "</button>" +
          "</div>" +
        "</div>" +
        '<div class="ai-panel__body" data-ai-body></div>' +
        '<form class="ai-panel__foot" data-ai-form>' +
          '<input type="text" placeholder="Ask about a trip…" data-ai-input autocomplete="off" maxlength="1000" />' +
          '<button type="submit" class="btn btn--primary btn--sm" data-ai-send>Send</button>' +
        "</form>" +
      "</div>"
    );
    document.body.appendChild(bubble);
    document.body.appendChild(panel);

    var body = panel.querySelector("[data-ai-body]");
    var statusEl = panel.querySelector("[data-ai-status]");
    var form = panel.querySelector("[data-ai-form]");
    var input = panel.querySelector("[data-ai-input]");
    var sendBtn = panel.querySelector("[data-ai-send]");

    // Restore whatever was already said earlier in this browser tab, so navigating between
    // pages (or accidentally closing the panel) doesn't wipe out the conversation.
    history.forEach(function (m) {
      renderMessage(m.role === "user" ? "user" : "assistant", m.content);
    });

    bubble.addEventListener("click", function () {
      panel.hidden = !panel.hidden;
      if (!panel.hidden) checkConfig();
    });
    panel.querySelector("[data-ai-close]").addEventListener("click", function () { panel.hidden = true; });
    panel.querySelector("[data-ai-clear]").addEventListener("click", function () {
      if (sending) return; // don't clear out from under an in-flight request
      history = [];
      saveHistory();
      body.innerHTML = "";
      renderMessage(
        "assistant",
        isConfigured
          ? "Conversation cleared. Ask me things like “Plan a one-day trip to Amritsar” or “What should I visit if it rains?”"
          : "Conversation cleared."
      );
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (sending) return; // one request in flight at a time -- prevents out-of-order replies
      var text = input.value.trim();
      if (!text) return;
      input.value = "";
      send(text);
    });

    function setSending(state) {
      sending = state;
      input.disabled = state;
      sendBtn.disabled = state;
    }

    function renderMessage(kind, text, extraClass) {
      var cls = "ai-msg ai-msg--" + kind + (extraClass ? " " + extraClass : "");
      var node = el('<div class="' + cls + '"></div>');
      node.textContent = text; // textContent, not innerHTML -- never interpret model/user text as markup
      body.appendChild(node);
      body.scrollTop = body.scrollHeight;
      return node;
    }

    function addSystemMessage(text, extraClass) { return renderMessage("assistant", text, extraClass); }
    function addUserMessage(text) { return renderMessage("user", text); }

    function addTyping() {
      var t = el('<div class="ai-msg ai-msg--assistant ai-msg--typing" data-ai-typing>Thinking…</div>');
      body.appendChild(t);
      body.scrollTop = body.scrollHeight;
      return t;
    }

    function checkConfig() {
      if (checkedConfig) return;
      checkedConfig = true;
      window.SarthiAPI.health().then(function (res) {
        if (!res.ok) {
          isConfigured = false;
          statusEl.textContent = "backend unreachable";
          if (history.length === 0) {
            addSystemMessage(
              "I can't reach the Sarthi backend right now. Make sure it's running (see README) — Explore and Planner may still work from cache."
            );
          }
          return;
        }
        isConfigured = !!res.data.ai_configured;
        statusEl.textContent = isConfigured ? "online" + (res.data.ai_provider ? " · " + res.data.ai_provider : "") : "not configured";
        if (history.length > 0) return; // already mid-conversation from an earlier page -- don't re-greet
        if (!isConfigured) {
          addSystemMessage(
            "The AI Assistant isn't configured yet — set an AI provider key (OPENAI_API_KEY or GEMINI_API_KEY) in backend/.env to enable natural-language chat. " +
            "Explore and Trip Planner still work fully on real map, weather, places and routing data without it."
          );
        } else {
          addSystemMessage("Hi! Ask me things like “Plan a one-day trip to Amritsar” or “What should I visit if it rains?”");
        }
      });
    }

    function send(text) {
      addUserMessage(text);
      history.push({ role: "user", content: text });
      saveHistory();
      if (isConfigured === false) {
        addSystemMessage("AI chat is disabled until an AI provider key is set on the backend (see above).");
        return;
      }
      var typing = addTyping();
      setSending(true);
      // Keep the full conversation for display/persistence, but only actually send the
      // most recent turns to the provider -- an unbounded history would eventually exceed
      // the model's context window and start failing on long sessions.
      var payload = history.length > MAX_TURNS_SENT ? history.slice(history.length - MAX_TURNS_SENT) : history;
      window.SarthiAPI.aiChat(payload).then(function (res) {
        typing.remove();
        setSending(false);
        if (!res.ok) {
          addSystemMessage("Sorry, the assistant request failed: " + res.error, "ai-msg--error");
          return;
        }
        if (!res.data.configured) {
          isConfigured = false;
          addSystemMessage(res.data.message || "AI Assistant not configured.");
          return;
        }
        if (res.data.message && !res.data.reply) {
          // configured, but this turn genuinely failed (provider outage, rate limit, etc.)
          addSystemMessage(res.data.message, "ai-msg--error");
          return;
        }
        var reply = res.data.reply || "(no reply)";
        history.push({ role: "assistant", content: reply });
        saveHistory();
        addSystemMessage(reply);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();
