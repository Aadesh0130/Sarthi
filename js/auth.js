/* =========================================================
   Sārthi — Authentication UI (real backend only)
   ---------------------------------------------------------
   Wires the existing generic modal (`data-modal` / `data-modal-body`,
   already used elsewhere for the checkout confirmation -- see
   js/main.js's checkout()) to the REAL phone-OTP + JWT auth backend at
   /api/auth/* (see backend/app/api/auth.py). No new UI chrome is
   invented: this reuses the same modal shell and the same
   btn/field/segmented classes already defined in css/styles.css.

   Hard rules enforced here (per the integration spec):
   - The OTP is never generated on the client and never printed to the
     browser console. The only thing shown to the user is whatever the
     backend's own response says (an honest "check your phone" message,
     or -- only when the backend's own /api/auth/status reports
     dev_mode -- a note that no SMS provider is configured, which is a
     configuration fact, not a fabricated code).
   - A login is never faked. Every state transition here follows a real
     `ok:true` response from js/api.js (SarthiAPI.*), which itself only
     returns ok:true for a genuine 2xx backend response.
   - Errors shown to the user are the backend's own error text
     (rate limits, expiry, wrong code, invalid number, etc.), not
     generic client-invented copy.

   Depends on js/api.js (window.SarthiAPI) and the modal/theme helpers
   in js/main.js. Include this after both on every page that has the
   `[data-auth-open]` nav button and the `[data-modal]` shell (both are
   already present on every Sārthi page).
   ========================================================= */
(function () {
  "use strict";

  if (!window.SarthiAPI) return; // js/api.js failed to load -- fail soft, no auth UI rather than a broken one

  var API = window.SarthiAPI;
  var LS_USER = "sarthi.authUser"; // cached profile only, never the token itself (that lives in js/api.js's own storage)

  var state = {
    user: null,
    authStatus: null, // { phone_auth_available, google_auth_configured, dev_mode, sms_provider_configured }
    phone: "",
    resendAt: 0,
  };

  function cacheUser(user) {
    state.user = user || null;
    try {
      if (user) localStorage.setItem(LS_USER, JSON.stringify(user));
      else localStorage.removeItem(LS_USER);
    } catch (e) { /* private browsing -- session still works, just re-fetches on reload */ }
  }
  function loadCachedUser() {
    try {
      var raw = localStorage.getItem(LS_USER);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  /* ---------- nav button ---------- */
  function personIcon() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/></svg>';
  }

  function updateAuthButtons() {
    var buttons = document.querySelectorAll("[data-auth-open]");
    buttons.forEach(function (btn) {
      if (state.user) {
        var initial = (state.user.full_name || state.user.phone_number || "?").trim().charAt(0).toUpperCase();
        btn.innerHTML = '<span class="auth-avatar" aria-hidden="true">' + (initial || "🙂") + "</span>";
        btn.setAttribute("aria-label", "Your account");
        btn.classList.add("is-authed");
      } else {
        btn.innerHTML = personIcon();
        btn.setAttribute("aria-label", "Sign in");
        btn.classList.remove("is-authed");
      }
    });
  }

  /* ---------- modal helpers (reuses the shared [data-modal] shell) ---------- */
  function getModal() { return document.querySelector("[data-modal]"); }

  function renderModal(html) {
    var modal = getModal();
    if (!modal) return null;
    modal.querySelector("[data-modal-body]").innerHTML = html;
    modal.classList.add("is-open");
    return modal;
  }
  function closeModal() {
    var modal = getModal();
    if (modal) modal.classList.remove("is-open");
  }

  function statusBlock(msg, kind) {
    if (!msg) return "";
    var cls = kind === "error" ? "auth-status auth-status--error" : "auth-status";
    return '<p class="' + cls + '">' + msg + "</p>";
  }

  /* ---------- step: phone entry ---------- */
  function showPhoneStep(opts) {
    opts = opts || {};
    var devNote = state.authStatus && state.authStatus.dev_mode
      ? '<p class="muted" style="font-size:.78rem;margin-top:10px">No SMS provider is configured on this backend yet (dev mode) — verification codes are printed to the backend server console instead of being texted.</p>'
      : "";
    renderModal(
      '<div class="auth-modal">' +
      '<div class="big">🔐</div>' +
      "<h3>Sign in to Sārthi</h3>" +
      '<p class="muted" style="margin-bottom:16px">We’ll text you a one-time 6-digit code — no password needed.</p>' +
      statusBlock(opts.error, "error") +
      '<div class="field">' +
      '<label for="auth-phone">Phone number</label>' +
      '<input id="auth-phone" type="tel" inputmode="tel" placeholder="9876543210 or +919876543210" autocomplete="tel" value="' + (opts.phone || "") + '" />' +
      "</div>" +
      '<button type="button" class="btn btn--primary btn--block" data-auth-send>Send code</button>' +
      devNote +
      "</div>"
    );
    var modal = getModal();
    var input = modal.querySelector("#auth-phone");
    var sendBtn = modal.querySelector("[data-auth-send]");
    input.focus();
    function submit() {
      var phone = (input.value || "").trim();
      if (!phone) { showPhoneStep({ phone: phone, error: "Enter a phone number." }); return; }
      sendBtn.disabled = true;
      sendBtn.textContent = "Sending…";
      API.requestOtp(phone).then(function (res) {
        if (res.ok) {
          state.phone = phone;
          state.resendAt = Date.now() + (res.data.resend_cooldown || 60) * 1000;
          showOtpStep({ expiresIn: res.data.expires_in });
        } else {
          showPhoneStep({ phone: phone, error: res.error || "Couldn't send a code — please try again." });
        }
      });
    }
    sendBtn.addEventListener("click", submit);
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") submit(); });
  }

  /* ---------- step: OTP verification ---------- */
  function showOtpStep(opts) {
    opts = opts || {};
    renderModal(
      '<div class="auth-modal">' +
      '<div class="big">✉️</div>' +
      "<h3>Enter your code</h3>" +
      '<p class="muted" style="margin-bottom:16px">We sent a 6-digit code to <b>' + state.phone + "</b>. " +
      '<a href="#" data-auth-change-number>Change number</a></p>' +
      statusBlock(opts.error, "error") +
      '<div class="field">' +
      '<label for="auth-otp">6-digit code</label>' +
      '<input id="auth-otp" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="6" autocomplete="one-time-code" placeholder="••••••" style="letter-spacing:.4em;text-align:center;font-size:1.3rem" />' +
      "</div>" +
      '<button type="button" class="btn btn--primary btn--block" data-auth-verify>Verify &amp; sign in</button>' +
      '<button type="button" class="btn btn--ghost btn--block" data-auth-resend style="margin-top:10px">Resend code</button>' +
      "</div>"
    );
    var modal = getModal();
    var input = modal.querySelector("#auth-otp");
    var verifyBtn = modal.querySelector("[data-auth-verify]");
    var resendBtn = modal.querySelector("[data-auth-resend]");
    var changeLink = modal.querySelector("[data-auth-change-number]");
    input.focus();

    function tickResendLabel() {
      var remaining = Math.ceil((state.resendAt - Date.now()) / 1000);
      if (remaining > 0) {
        resendBtn.disabled = true;
        resendBtn.textContent = "Resend code (" + remaining + "s)";
      } else {
        resendBtn.disabled = false;
        resendBtn.textContent = "Resend code";
        clearInterval(timer);
      }
    }
    var timer = setInterval(tickResendLabel, 1000);
    tickResendLabel();

    function verify() {
      var otp = (input.value || "").trim();
      if (otp.length !== 6) { showOtpStep({ error: "Enter the 6-digit code." }); return; }
      verifyBtn.disabled = true;
      verifyBtn.textContent = "Verifying…";
      API.verifyOtp(state.phone, otp).then(function (res) {
        clearInterval(timer);
        if (res.ok) {
          cacheUser(res.data.user);
          updateAuthButtons();
          window.Sarthi && window.Sarthi.toast && window.Sarthi.toast("Signed in", "🎉");
          if (!res.data.user.onboarding_completed) {
            showOnboardingStep();
          } else {
            closeModal();
          }
        } else {
          showOtpStep({ error: res.error || "That code didn't work — please try again." });
        }
      });
    }
    verifyBtn.addEventListener("click", verify);
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") verify(); });

    resendBtn.addEventListener("click", function () {
      if (resendBtn.disabled) return;
      resendBtn.disabled = true;
      API.resendOtp(state.phone).then(function (res) {
        if (res.ok) {
          state.resendAt = Date.now() + (res.data.resend_cooldown || 60) * 1000;
          timer = setInterval(tickResendLabel, 1000);
          tickResendLabel();
          window.Sarthi && window.Sarthi.toast && window.Sarthi.toast("Code resent", "✉️");
        } else {
          showOtpStep({ error: res.error || "Couldn't resend a code right now." });
        }
      });
    });

    changeLink.addEventListener("click", function (e) {
      e.preventDefault();
      clearInterval(timer);
      showPhoneStep({ phone: state.phone });
    });
  }

  /* ---------- step: light onboarding (first login only) ---------- */
  function showOnboardingStep(opts) {
    opts = opts || {};
    renderModal(
      '<div class="auth-modal">' +
      '<div class="big">👋</div>' +
      "<h3>Welcome to Sārthi</h3>" +
      '<p class="muted" style="margin-bottom:16px">Just your name so we can personalise your trips — everything else is optional.</p>' +
      statusBlock(opts.error, "error") +
      '<div class="field">' +
      '<label for="auth-name">Your name</label>' +
      '<input id="auth-name" type="text" placeholder="e.g. Aadesh Karuna" autocomplete="name" />' +
      "</div>" +
      '<div class="field">' +
      '<label for="auth-city">Home city <span class="muted" style="font-weight:400">(optional)</span></label>' +
      '<input id="auth-city" type="text" placeholder="e.g. Pune" autocomplete="address-level2" />' +
      "</div>" +
      '<button type="button" class="btn btn--primary btn--block" data-auth-save>Continue</button>' +
      '<button type="button" class="btn btn--ghost btn--block" data-auth-skip style="margin-top:10px">Skip for now</button>' +
      "</div>"
    );
    var modal = getModal();
    var nameInput = modal.querySelector("#auth-name");
    var cityInput = modal.querySelector("#auth-city");
    var saveBtn = modal.querySelector("[data-auth-save]");
    var skipBtn = modal.querySelector("[data-auth-skip]");
    nameInput.focus();

    saveBtn.addEventListener("click", function () {
      var name = (nameInput.value || "").trim();
      if (!name) { showOnboardingStep({ error: "Enter your name to continue, or skip for now." }); return; }
      saveBtn.disabled = true;
      saveBtn.textContent = "Saving…";
      API.completeOnboarding({
        full_name: name,
        home_city: (cityInput.value || "").trim() || null,
      }).then(function (res) {
        if (res.ok) {
          cacheUser(res.data);
          updateAuthButtons();
          closeModal();
        } else {
          showOnboardingStep({ error: res.error || "Couldn't save your profile — you can finish this later from your account." });
        }
      });
    });
    skipBtn.addEventListener("click", closeModal);
  }

  /* ---------- step: signed-in account view ---------- */
  function showAccountStep() {
    var user = state.user || {};
    var label = user.full_name || user.phone_number || "your account";
    renderModal(
      '<div class="auth-modal">' +
      '<div class="big">' + (user.full_name ? user.full_name.trim().charAt(0).toUpperCase() : "🙂") + "</div>" +
      "<h3>" + label + "</h3>" +
      (user.phone_number ? '<p class="muted">' + user.phone_number + "</p>" : "") +
      (user.home_city ? '<p class="muted">📍 ' + user.home_city + "</p>" : "") +
      '<button type="button" class="btn btn--outline btn--block" data-auth-signout style="margin-top:18px">Sign out</button>' +
      "</div>"
    );
    getModal().querySelector("[data-auth-signout]").addEventListener("click", function () {
      API.logout().then(function () {
        cacheUser(null);
        updateAuthButtons();
        closeModal();
        window.Sarthi && window.Sarthi.toast && window.Sarthi.toast("Signed out", "👋");
      });
    });
  }

  /* ---------- open handler ---------- */
  function openAuthModal() {
    if (state.user) { showAccountStep(); return; }
    if (state.authStatus && state.authStatus.phone_auth_available === false) {
      renderModal(
        '<div class="auth-modal">' +
        '<div class="big">🚧</div>' +
        "<h3>Sign-in isn’t available yet</h3>" +
        '<p class="muted">The backend hasn’t got phone sign-in switched on right now. Please try again later.</p>' +
        "</div>"
      );
      return;
    }
    showPhoneStep();
  }

  function init() {
    // Show a cached profile immediately (fast, no flash of "signed out"),
    // then verify it against the real backend -- a stale/expired token
    // must fall back to signed-out, never keep showing a fake signed-in state.
    var cached = loadCachedUser();
    if (cached && API.isLoggedIn()) { state.user = cached; updateAuthButtons(); }

    document.querySelectorAll("[data-auth-open]").forEach(function (btn) {
      btn.addEventListener("click", openAuthModal);
    });

    API.authStatus().then(function (res) {
      if (res.ok) state.authStatus = res.data;
    });

    if (API.isLoggedIn()) {
      API.me().then(function (res) {
        if (res.ok) {
          cacheUser(res.data);
        } else {
          // Token rejected/expired -- do not keep showing a signed-in button for a session that isn't real.
          cacheUser(null);
        }
        updateAuthButtons();
      });
    } else {
      updateAuthButtons();
    }
  }

  document.addEventListener("DOMContentLoaded", init);

  window.SarthiAuth = {
    isLoggedIn: function () { return !!state.user; },
    getUser: function () { return state.user; },
    open: openAuthModal,
  };
})();
