/**
 * status.js — wire status buttons for TakuLog
 *
 * Targets any <button data-status-action> with:
 *   data-event-id   — Event PK (always required)
 *   data-status     — status slug: interested | planned | visited | missed
 *   data-status-id  — UserEventStatus PK (present when status already exists)
 *
 * Behaviour:
 *   - data-status-id absent → POST /api/user-event-statuses/ {event, status}
 *   - data-status-id present, data-status-action="change" → PATCH /<id>/ {status}
 *   - data-status-id present, data-status-action="unset"  → DELETE /<id>/
 *
 * 403 handling (per security contract):
 *   - detail contains "Authentication credentials were not provided"
 *     → redirect to /accounts/login/?next=<current path>  (treat as logged-out)
 *   - any other 403 (CSRF failure etc.)
 *     → show non-destructive inline message; do NOT retry or redirect
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

  var AUTH_DETAIL_MARKER = "Authentication credentials were not provided";

  function redirectToLogin() {
    var next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = "/accounts/login/?next=" + next;
  }

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
    button.disabled = loading;
    if (loading) {
      button.setAttribute("aria-busy", "true");
    } else {
      button.removeAttribute("aria-busy");
    }
  }

  function handle403(result, button) {
    var detail = (result.data && result.data.detail) ? result.data.detail : "";
    if (detail.indexOf(AUTH_DETAIL_MARKER) !== -1) {
      redirectToLogin();
    } else {
      showCsrfError(button);
    }
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

    setButtonLoading(button, true);

    var result;

    if (statusId && action === "unset") {
      result = await window.TakuAPI.del("/api/user-event-statuses/" + statusId + "/");
    } else if (statusId && action === "change") {
      result = await window.TakuAPI.patch(
        "/api/user-event-statuses/" + statusId + "/",
        { status: statusSlug }
      );
    } else {
      result = await window.TakuAPI.post("/api/user-event-statuses/", {
        event: parseInt(eventId, 10),
        status: statusSlug,
      });
    }

    setButtonLoading(button, false);

    if (result.status === 403) {
      handle403(result, button);
      return;
    }

    if (result.status === 409) {
      var code = result.data && result.data.code;
      if (code === "duplicate_user_event_status") {
        setButtonAlreadyAdded(button);
      }
      return;
    }

    if (result.status === 204 || (result.ok && action === "unset")) {
      delete button.dataset.statusId;
      button.dataset.statusAction = "";
      setButtonDefault(button);
      return;
    }

    if (result.ok) {
      var responseData = result.data || {};
      if (responseData.id) {
        button.dataset.statusId = String(responseData.id);
        button.dataset.statusAction = "change";
      }
      setButtonActive(button, statusSlug);
      return;
    }

    if (result.status === 0) {
      showCsrfError(button);
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
