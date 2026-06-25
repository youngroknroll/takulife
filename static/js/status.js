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

  var STATUS_LABELS = {
    interested: "관심",
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
    var label = STATUS_LABELS[statusSlug] || statusSlug;
    button.textContent = label;
    button.classList.add("active");
    button.setAttribute("aria-pressed", "true");
  }

  function setButtonDefault(button) {
    var slug = button.dataset.status;
    var label = STATUS_LABELS[slug] || slug;
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
    var eventId = button.dataset.eventId;
    var statusSlug = button.dataset.status;
    var statusId = button.dataset.statusId;
    var action = button.dataset.statusAction;

    if (!eventId || !statusSlug) {
      return;
    }

    var isActive = button.classList.contains("active");

    setButtonLoading(button, true);

    // Discovery buttons (empty action) toggle: an active button cancels its own
    // registration (DELETE), an inactive one registers (POST). Archive controls
    // (action="change") switch the existing status in place via PATCH.
    var result;
    var isCancel = false;

    if (action === "change" && statusId) {
      result = await window.TakuAPI.patch(
        "/api/user-event-statuses/" + statusId + "/",
        { status: statusSlug }
      );
    } else if (statusId && (isActive || action === "unset")) {
      isCancel = true;
      result = await window.TakuAPI.del("/api/user-event-statuses/" + statusId + "/");
    } else {
      result = await window.TakuAPI.post("/api/user-event-statuses/", {
        event: parseInt(eventId, 10),
        status: statusSlug,
      });
    }

    setButtonLoading(button, false);

    var kind = window.TakuAPI.classify(result);

    if (kind === "auth") {
      window.TakuAPI.redirectToLogin();
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

    if (result.status === 204 || (isCancel && result.ok)) {
      delete button.dataset.statusId;
      button.dataset.statusAction = "";
      setButtonDefault(button);
      return;
    }

    if (result.ok) {
      var responseData = result.data || {};
      if (responseData.id) {
        // Keep the empty action so the next click on this (now active) button
        // toggles the registration off instead of re-PATCHing the same status.
        button.dataset.statusId = String(responseData.id);
      }
      setButtonActive(button, statusSlug);
      return;
    }
  }

  function initStatusButtons() {
    var buttons = document.querySelectorAll("button[data-status-action]");
    buttons.forEach(function (button) {
      var statusSlug = button.dataset.status;
      if (button.dataset.statusId) {
        setButtonActive(button, statusSlug);
      } else {
        button.setAttribute("aria-pressed", "false");
      }
      button.addEventListener("click", handleClick);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initStatusButtons);
  } else {
    initStatusButtons();
  }
})();
