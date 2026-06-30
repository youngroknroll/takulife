/**
 * status.js — wire status buttons for TakuLog
 *
 * Targets any <button data-status-action> with:
 *   data-event-id   — Event PK (always required)
 *   data-status     — status slug: interested | planned | visited | missed
 *   data-status-id  — UserEventStatus PK (present when status already exists)
 *
 * Behaviour (discovery buttons, empty data-status-action — toggle):
 *   - inactive button (no registration) → POST /api/user-event-statuses/ {event, status}
 *   - active button (its own status set) → DELETE /<id>/  (re-click cancels)
 * Behaviour (archive controls, data-status-action="change"):
 *   - PATCH /<id>/ {status} to switch the existing status in place
 *   - data-status-action="unset" (legacy) → DELETE /<id>/
 *
 * 403 handling (via TakuAPI.classify):
 *   - kind 'auth' → TakuAPI.redirectToLogin()
 *   - kind 'csrf' → show non-destructive inline CSRF message; do NOT redirect
 *
 * 409 handling:
 *   - code === "duplicate_user_event_status"
 *     → reconcile button to "이미 추가됨" without scary error
 *
 * XSS: all DOM text uses textContent / dataset / classList. Never innerHTML
 * with API strings.
 *
 * Depends on window.TakuAPI (api.js must load first).
 */

(function () {
  "use strict";

  function removeRowIfOptedIn(button) {
    if (!button.hasAttribute("data-remove-on-cancel")) { return; }
    var row = button.closest("article");
    if (!row) { return; }
    var mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mql.matches) {
      row.remove();
      return;
    }
    row.style.transition = "opacity .15s";
    row.style.opacity = "0";
    row.addEventListener("transitionend", function () { row.remove(); }, { once: true });
  }

  // Graceful fallback to native confirm if confirm-modal.js didn't load.
  // The message is overridable per button via data-confirm-message (e.g. a
  // "삭제" button confirms with "삭제하시겠습니까?" instead of the cancel default).
  function askCancel(message) {
    var msg = message || "취소하시겠습니까?";
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(msg);
    }
    return Promise.resolve(window.confirm(msg));
  }

  var STATUS_LABELS = {
    interested: "찜",
    planned: "방문 예정",
    visited: "방문 완료",
    missed: "놓침",
  };

  function showCsrfError(button) {
    var container = button.closest("[data-status-error-container]") || button.parentElement;
    var existing = container.querySelector(".status-csrf-error");
    if (existing) {
      return;
    }
    var msg = document.createElement("p");
    msg.className = "status-csrf-error";
    msg.setAttribute("role", "alert");
    msg.textContent = "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.";
    msg.style.cssText = "color:#b91c1c;font-size:0.82rem;margin:4px 0 0;";
    container.appendChild(msg);
  }

  function setButtonActive(button, statusSlug) {
    // A button may supply its own kind-aware label (e.g. goods → 구매 예정);
    // fall back to the generic status vocabulary otherwise.
    var label = button.dataset.labelActive || STATUS_LABELS[statusSlug] || statusSlug;
    button.textContent = label;
    button.classList.add("active");
    button.setAttribute("aria-pressed", "true");
  }

  function setButtonDefault(button) {
    var slug = button.dataset.status;
    var label = button.dataset.label || STATUS_LABELS[slug] || slug;
    button.textContent = label;
    button.classList.remove("active");
    button.setAttribute("aria-pressed", "false");
  }

  function setButtonAlreadyAdded(button) {
    button.textContent = "이미 추가됨";
    button.classList.add("active");
    button.setAttribute("aria-pressed", "true");
    button.disabled = true;
  }

  function setButtonLoading(button, loading) {
    // Delegate to the shared helper so the button also shows the .is-loading
    // spinner (disabled + aria-busy) while the request is in flight.
    window.TakuAPI.setLoading(button, loading);
  }

  async function handleClick(event) {
    var button = event.currentTarget;
    // Subject = an official event (data-event-id) OR an unofficial personal
    // entry (data-personal-entry-id). Only needed when registering a new status;
    // change/cancel operate on the existing UserEventStatus by data-status-id.
    var eventId = button.dataset.eventId;
    var personalEntryId = button.dataset.personalEntryId;
    var statusSlug = button.dataset.status;
    var statusId = button.dataset.statusId;
    var action = button.dataset.statusAction;

    if (!statusSlug) {
      return;
    }

    // Visitors who aren't logged in can't save a status — prompt them to log in
    // or sign up instead of firing a request that just 403s.
    if (!window.TakuAPI.isAuthenticated()) {
      window.TakuAPI.promptLogin();
      return;
    }

    var isActive = button.classList.contains("active");

    // On a discovery card 관심/방문 예정 sit in the same row but an event holds
    // only one status. Find the sibling button that currently owns the
    // registration so this click can switch the status over instead of
    // conflicting. (Archive "change" controls never switch siblings.)
    var activeSibling = null;
    if (action !== "change") {
      var container = button.closest("[data-status-error-container]");
      if (container) {
        var siblings = container.querySelectorAll("button[data-status-action]");
        for (var i = 0; i < siblings.length; i++) {
          if (siblings[i] !== button && siblings[i].dataset.statusId) {
            activeSibling = siblings[i];
            break;
          }
        }
      }
    }

    var willCancel = action !== "change" && statusId && (isActive || action === "unset");
    if (willCancel && !(await askCancel(button.dataset.confirmMessage))) {
      return;
    }

    setButtonLoading(button, true);

    // Discovery semantics (empty action):
    //   active button         → DELETE  (cancel its own registration)
    //   inactive, sibling set → PATCH   (switch the event to this status)
    //   inactive, none set    → POST    (register)
    // Archive controls (action="change") switch the status in place via PATCH.
    var result;
    var mode;

    if (action === "change" && statusId) {
      mode = "change";
      result = await window.TakuAPI.patch(
        "/api/user-event-statuses/" + statusId + "/",
        { status: statusSlug }
      );
    } else if (statusId && (isActive || action === "unset")) {
      mode = "cancel";
      result = await window.TakuAPI.del("/api/user-event-statuses/" + statusId + "/");
    } else if (activeSibling) {
      mode = "switch";
      result = await window.TakuAPI.patch(
        "/api/user-event-statuses/" + activeSibling.dataset.statusId + "/",
        { status: statusSlug }
      );
    } else {
      mode = "register";
      var payload = { status: statusSlug };
      if (personalEntryId) {
        payload.personal_entry = parseInt(personalEntryId, 10);
      } else if (eventId) {
        payload.event = parseInt(eventId, 10);
      } else {
        // No subject to register against — nothing to do.
        setButtonLoading(button, false);
        return;
      }
      result = await window.TakuAPI.post("/api/user-event-statuses/", payload);
    }

    setButtonLoading(button, false);

    var kind = window.TakuAPI.classify(result);

    if (kind === "auth") {
      // session expired mid-page — prompt re-login rather than silently redirect
      window.TakuAPI.promptLogin();
      return;
    }

    if (kind === "csrf" || kind === "network") {
      showCsrfError(button);
      return;
    }

    if (kind === "conflict") {
      var code = result.data && result.data.code;
      if (code === "duplicate_user_event_status") {
        setButtonAlreadyAdded(button);
      }
      return;
    }

    // Controls that opt into a reload (archive change buttons, the 비공식-page
    // 예정 toggle) let the server re-derive the row badge, available actions,
    // kind-aware labels and summary counts instead of patching the DOM piecemeal.
    if ((result.ok || result.status === 204) && button.hasAttribute("data-reload-on-success")) {
      window.location.reload();
      return;
    }

    if (mode === "cancel" && (result.status === 204 || result.ok)) {
      delete button.dataset.statusId;
      setButtonDefault(button);
      removeRowIfOptedIn(button);
      return;
    }

    if (result.ok) {
      var responseData = result.data || {};
      // A switch moves the single registration from the sibling to this button.
      var fallbackId;
      if (mode === "switch" && activeSibling) {
        fallbackId = activeSibling.dataset.statusId;
        delete activeSibling.dataset.statusId;
        setButtonDefault(activeSibling);
      }
      // Keep the empty action so the next click on this (now active) button
      // toggles the registration off instead of re-PATCHing the same status.
      var newId = responseData.id ? String(responseData.id) : fallbackId;
      if (newId) {
        button.dataset.statusId = newId;
      }
      setButtonActive(button, statusSlug);
      return;
    }
  }

  // ── interest toggle (♡/♥) — fully independent from the funnel ──

  function setInterestActive(button, interestId) {
    button.dataset.interestId = String(interestId);
    button.classList.add("active");
    button.setAttribute("aria-pressed", "true");
    var glyph = button.querySelector("[data-interest-glyph]");
    if (glyph) {
      glyph.textContent = "♥";
    }
  }

  function setInterestDefault(button) {
    delete button.dataset.interestId;
    button.classList.remove("active");
    button.setAttribute("aria-pressed", "false");
    var glyph = button.querySelector("[data-interest-glyph]");
    if (glyph) {
      glyph.textContent = "♡";
    }
  }

  async function handleInterestClick(event) {
    var button = event.currentTarget;
    // Subject = official event OR unofficial personal entry. Needed only to
    // register a new interest; un-favouriting uses the existing data-interest-id.
    var eventId = button.dataset.eventId;
    var personalEntryId = button.dataset.personalEntryId;
    var interestId = button.dataset.interestId;

    if (!eventId && !personalEntryId && !interestId) {
      return;
    }

    if (!window.TakuAPI.isAuthenticated()) {
      window.TakuAPI.promptLogin();
      return;
    }

    if (interestId && !(await askCancel(button.dataset.confirmMessage))) {
      return;
    }

    window.TakuAPI.setLoading(button, true);

    var result;
    if (interestId) {
      result = await window.TakuAPI.del("/api/event-interests/" + interestId + "/");
    } else {
      var payload = {};
      if (personalEntryId) {
        payload.personal_entry = parseInt(personalEntryId, 10);
      } else {
        payload.event = parseInt(eventId, 10);
      }
      result = await window.TakuAPI.post("/api/event-interests/", payload);
    }

    window.TakuAPI.setLoading(button, false);

    var kind = window.TakuAPI.classify(result);

    if (kind === "auth") {
      window.TakuAPI.promptLogin();
      return;
    }

    if (kind === "csrf" || kind === "network") {
      showCsrfError(button);
      return;
    }

    if (kind === "conflict") {
      var code = result.data && result.data.code;
      if (code === "duplicate_event_interest") {
        // Already interested — reconcile to active state using the id if present
        var existingId = result.data && result.data.id;
        if (existingId) {
          setInterestActive(button, existingId);
        } else {
          button.classList.add("active");
          button.setAttribute("aria-pressed", "true");
        }
      }
      return;
    }

    if (interestId && (result.status === 204 || result.ok)) {
      setInterestDefault(button);
      removeRowIfOptedIn(button);
      return;
    }

    if (result.ok) {
      var responseData = result.data || {};
      if (responseData.id) {
        setInterestActive(button, responseData.id);
      }
      return;
    }
  }

  // Idempotent: a button is wired at most once (data-status-bound guard), so
  // re-running after a live-search swap binds only the freshly inserted buttons
  // and never double-binds the ones already present.
  function initStatusButtons() {
    var buttons = document.querySelectorAll("button[data-status-action]");
    buttons.forEach(function (button) {
      if (button.dataset.statusBound) return;
      button.dataset.statusBound = "1";
      // Only discovery toggle buttons (empty action) reflect their own
      // registration as an active label. Archive controls with an explicit
      // action (change / unset) keep their authored label and state.
      if (!button.dataset.statusAction) {
        if (button.dataset.statusId) {
          setButtonActive(button, button.dataset.status);
        } else {
          button.setAttribute("aria-pressed", "false");
        }
      }
      button.addEventListener("click", handleClick);
    });

    var interestButtons = document.querySelectorAll("button[data-interest-toggle]");
    interestButtons.forEach(function (button) {
      if (button.dataset.interestBound) return;
      button.dataset.interestBound = "1";
      button.addEventListener("click", handleInterestClick);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initStatusButtons);
  } else {
    initStatusButtons();
  }

  // Re-scan after archive live search replaces the results fragment: the new
  // status/interest buttons need wiring (direct binding, not delegation). The
  // guard above keeps this safe to call repeatedly.
  document.addEventListener("archive:listswapped", initStatusButtons);
})();
