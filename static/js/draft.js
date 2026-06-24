/**
 * draft.js — Admin draft management actions for TakuLog
 *
 * Binds create / edit / approve / reject controls via data attributes.
 * All API writes go through window.TakuAPI (api.js) — no CSRF duplication.
 *
 * Data attributes expected by each control:
 *
 *   Create form  (#draft-create-form)
 *     - no extra attributes; reads #draft-url and #draft-source-name inputs
 *
 *   Edit form (#draft-edit-form)
 *     - data-draft-id  — numeric draft PK
 *
 *   Approve button (#draft-approve-btn)
 *     - data-draft-id  — numeric draft PK
 *
 *   Reject button (#draft-reject-btn)
 *     - data-draft-id  — numeric draft PK
 *
 * Error containers (textContent only, no innerHTML):
 *   #draft-create-error  — shown inline on create failure
 *   #draft-edit-error    — shown inline on edit failure
 *   #draft-action-error  — shown inline on approve/reject failure
 *
 * Success:
 *   Create  → window.location.reload()
 *   Edit    → window.location.reload()
 *   Approve → show event_id link in #draft-approve-success, then reload after 1.5 s
 *   Reject  → window.location.reload()
 *
 * 403 contract:
 *   Any 403 on these staff-only pages indicates a lost session or CSRF failure.
 *   Show the error message in the relevant container and do NOT redirect to login
 *   (the user is already on an @staff_member_required page).
 */

(function () {
  "use strict";

  /* ── helpers ──────────────────────────────────────────────────────────── */

  function showError(container, message) {
    if (!container) {
      return;
    }
    container.textContent = message;
    container.hidden = false;
  }

  function hideError(container) {
    if (!container) {
      return;
    }
    container.textContent = "";
    container.hidden = true;
  }

  /**
   * Render a DRF error envelope (detail string or field-keyed dict) into a
   * human-readable string. Only textContent assignment is used by callers.
   */
  function formatError(data) {
    if (!data) {
      return "알 수 없는 오류가 발생했습니다.";
    }
    if (typeof data.detail === "string") {
      return data.detail;
    }
    // Field error dict: { field: ["msg", ...], ... } or { field: "msg", ... }
    var parts = [];
    Object.keys(data).forEach(function (field) {
      var messages = Array.isArray(data[field]) ? data[field] : [data[field]];
      parts.push(field + ": " + messages.join(" "));
    });
    if (parts.length) {
      return parts.join(" | ");
    }
    return JSON.stringify(data);
  }

  /* ── 403 message (lost session / CSRF) ──────────────────────────────── */

  var CSRF_OR_SESSION_MSG =
    "403 오류: 세션이 만료되었거나 보안 토큰이 유효하지 않습니다. " +
    "페이지를 새로고침한 뒤 다시 시도해 주세요.";

  /* ── create form ──────────────────────────────────────────────────────── */

  function bindCreateForm() {
    var form = document.getElementById("draft-create-form");
    if (!form) {
      return;
    }
    var errorEl = document.getElementById("draft-create-error");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", function (evt) {
      evt.preventDefault();
      hideError(errorEl);

      var urlInput = document.getElementById("draft-url");
      var nameInput = document.getElementById("draft-source-name");
      var sourceUrl = urlInput ? urlInput.value.trim() : "";
      var sourceName = nameInput ? nameInput.value.trim() : "";

      if (!sourceUrl) {
        showError(errorEl, "source_url: URL을 입력해 주세요.");
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
      }

      window.TakuAPI.post("/api/event-drafts/", {
        source_url: sourceUrl,
        source_name: sourceName,
      }).then(function (result) {
        if (submitBtn) {
          submitBtn.disabled = false;
        }
        if (result.ok) {
          window.location.reload();
          return;
        }
        if (result.status === 403) {
          showError(errorEl, CSRF_OR_SESSION_MSG);
          return;
        }
        showError(errorEl, formatError(result.data));
      });
    });
  }

  /* ── edit form ────────────────────────────────────────────────────────── */

  function bindEditForm() {
    var form = document.getElementById("draft-edit-form");
    if (!form) {
      return;
    }
    var errorEl = document.getElementById("draft-edit-error");
    var submitBtn = form.querySelector('[type="submit"]');
    var draftId = form.dataset.draftId;

    form.addEventListener("submit", function (evt) {
      evt.preventDefault();
      hideError(errorEl);

      var payload = {};

      var sourceNameEl = form.querySelector('[name="source_name"]');
      if (sourceNameEl) {
        payload.source_name = sourceNameEl.value;
      }

      var titleEl = form.querySelector('[name="extracted_title"]');
      if (titleEl) {
        payload.extracted_title = titleEl.value;
      }

      var categoryEl = form.querySelector('[name="extracted_category"]');
      if (categoryEl) {
        payload.extracted_category = categoryEl.value;
      }

      var workEl = form.querySelector('[name="extracted_work_title"]');
      if (workEl) {
        payload.extracted_work_title = workEl.value;
      }

      var locationEl = form.querySelector('[name="extracted_location_name"]');
      if (locationEl) {
        payload.extracted_location_name = locationEl.value;
      }

      var regionEl = form.querySelector('[name="extracted_region"]');
      if (regionEl) {
        payload.extracted_region = regionEl.value;
      }

      var startEl = form.querySelector('[name="extracted_start_date"]');
      if (startEl) {
        payload.extracted_start_date = startEl.value || null;
      }

      var endEl = form.querySelector('[name="extracted_end_date"]');
      if (endEl) {
        payload.extracted_end_date = endEl.value || null;
      }

      var summaryEl = form.querySelector('[name="extracted_summary"]');
      if (summaryEl) {
        payload.extracted_summary = summaryEl.value;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
      }

      window.TakuAPI.patch("/api/event-drafts/" + draftId + "/", payload).then(
        function (result) {
          if (submitBtn) {
            submitBtn.disabled = false;
          }
          if (result.ok) {
            window.location.reload();
            return;
          }
          if (result.status === 403) {
            showError(errorEl, CSRF_OR_SESSION_MSG);
            return;
          }
          showError(errorEl, formatError(result.data));
        }
      );
    });
  }

  /* ── approve button ───────────────────────────────────────────────────── */

  function bindApproveButton() {
    var btn = document.getElementById("draft-approve-btn");
    if (!btn) {
      return;
    }
    var errorEl = document.getElementById("draft-action-error");
    var successEl = document.getElementById("draft-approve-success");
    var draftId = btn.dataset.draftId;

    btn.addEventListener("click", function () {
      var confirmed = window.confirm(
        "승인하고 게시하면 공개 행사 목록에 노출됩니다. 진행할까요?"
      );
      if (!confirmed) {
        return;
      }
      hideError(errorEl);
      btn.disabled = true;

      window.TakuAPI.post(
        "/api/event-drafts/" + draftId + "/approve/",
        {}
      ).then(function (result) {
        btn.disabled = false;
        if (result.ok) {
          var eventId = result.data && result.data.event_id;
          if (successEl && eventId) {
            var link = document.createElement("a");
            link.href = "/events/" + eventId + "/";
            link.textContent = "행사 #" + eventId + " 보기";
            successEl.textContent = "승인 완료. ";
            successEl.appendChild(link);
            successEl.hidden = false;
          }
          setTimeout(function () {
            window.location.reload();
          }, 1500);
          return;
        }
        if (result.status === 403) {
          showError(errorEl, CSRF_OR_SESSION_MSG);
          return;
        }
        showError(errorEl, formatError(result.data));
      });
    });
  }

  /* ── reject button ────────────────────────────────────────────────────── */

  function bindRejectButton() {
    var btn = document.getElementById("draft-reject-btn");
    if (!btn) {
      return;
    }
    var errorEl = document.getElementById("draft-action-error");
    var draftId = btn.dataset.draftId;

    btn.addEventListener("click", function () {
      var confirmed = window.confirm(
        "이 드래프트를 반려할까요? 공개 목록에는 노출되지 않습니다."
      );
      if (!confirmed) {
        return;
      }
      hideError(errorEl);
      btn.disabled = true;

      window.TakuAPI.post(
        "/api/event-drafts/" + draftId + "/reject/",
        {}
      ).then(function (result) {
        btn.disabled = false;
        if (result.ok) {
          window.location.reload();
          return;
        }
        if (result.status === 403) {
          showError(errorEl, CSRF_OR_SESSION_MSG);
          return;
        }
        showError(errorEl, formatError(result.data));
      });
    });
  }

  /* ── init ─────────────────────────────────────────────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    bindCreateForm();
    bindEditForm();
    bindApproveButton();
    bindRejectButton();
  });
})();
