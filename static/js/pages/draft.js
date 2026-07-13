/**
 * draft.js — Admin draft management actions for takulife
 *
 * Binds create / edit / approve / reject controls via data attributes.
 * All API writes go through window.TakuAPI (api.js) — no CSRF duplication.
 * Error formatting uses TakuAPI.formatError (no local formatError copy).
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
 *     - reads data-list-url off its closest [data-list-url] ancestor (the
 *       action-stack container, server-rendered with the ?status= the
 *       operator arrived with) for the post-success "목록으로 돌아가기" link
 *
 *   Reject button (#draft-reject-btn)
 *     - data-draft-id  — numeric draft PK
 *     - reads #draft-reject-reason's value (optional) as rejection_reason
 *     - reads data-list-url the same way as the approve button, to navigate
 *       back to the list on success (see [data-list-url] above)
 *
 *   Raw text toggle (#raw-text-toggle)
 *     - server double-renders #raw-text-truncated (visible) and
 *       #raw-text-full (hidden) — this button only flips native `hidden`
 *       on each and syncs data-expanded/label text. It never reads or
 *       writes raw_text itself (no innerHTML, no textContent assignment
 *       of user content) — the XSS surface stays at 0.
 *
 * Error containers (textContent only, no innerHTML):
 *   #draft-create-error  — shown inline on create failure
 *   #draft-edit-error    — shown inline on edit failure
 *   #draft-action-error  — shown inline on approve/reject failure
 *
 * Success:
 *   Create  → window.location.reload()
 *   Edit    → window.location.reload()
 *   Approve → show event_id link + "목록으로 돌아가기" link in
 *             #draft-approve-success (stays visible, no reload); both
 *             review buttons are disabled to block resubmission
 *   Reject  → navigate to data-list-url (see above) — no reload
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

  // Styled confirm modal (confirm-modal.js) with a native window.confirm
  // fallback if that script didn't load — same pattern as status.js/visit.js/
  // visit_edit.js/personal_entries.js/draft_bulk.js's askCancel.
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
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
        showError(errorEl, "URL을 입력해 주세요.");
        return;
      }

      window.TakuAPI.setLoading(submitBtn, true);

      window.TakuAPI.post("/api/event-drafts/", {
        source_url: sourceUrl,
        source_name: sourceName,
      }).then(function (result) {
        window.TakuAPI.setLoading(submitBtn, false);
        if (result.ok) {
          window.location.reload();
          return;
        }
        if (result.status === 403) {
          showError(errorEl, CSRF_OR_SESSION_MSG);
          return;
        }
        showError(errorEl, window.TakuAPI.formatError(result));
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

      window.TakuAPI.setLoading(submitBtn, true);

      window.TakuAPI.patch("/api/event-drafts/" + draftId + "/", payload).then(
        function (result) {
          window.TakuAPI.setLoading(submitBtn, false);
          if (result.ok) {
            window.location.reload();
            return;
          }
          if (result.status === 403) {
            showError(errorEl, CSRF_OR_SESSION_MSG);
            return;
          }
          showError(errorEl, window.TakuAPI.formatError(result));
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
    var rejectBtn = document.getElementById("draft-reject-btn");
    var listUrlEl = btn.closest("[data-list-url]");
    var listUrl = listUrlEl ? listUrlEl.dataset.listUrl : "/staff/drafts/";

    btn.addEventListener("click", async function () {
      var confirmed = await askConfirm(
        "승인하고 게시하면 공개 행사 목록에 노출됩니다. 진행할까요?"
      );
      if (!confirmed) {
        return;
      }
      hideError(errorEl);
      window.TakuAPI.setLoading(btn, true);

      window.TakuAPI.post(
        "/staff/drafts/" + draftId + "/approve/",
        {}
      ).then(function (result) {
        window.TakuAPI.setLoading(btn, false);
        if (result.ok) {
          if (successEl) {
            var eventId = result.data && result.data.event_id;
            successEl.textContent = "승인 완료. ";
            if (eventId) {
              var eventLink = document.createElement("a");
              eventLink.href = "/events/" + eventId + "/";
              eventLink.textContent = "행사 #" + eventId + " 보기";
              successEl.appendChild(eventLink);
              successEl.appendChild(document.createTextNode(" · "));
            }
            var listLink = document.createElement("a");
            listLink.href = listUrl;
            listLink.textContent = "목록으로 돌아가기";
            successEl.appendChild(listLink);
            successEl.hidden = false;
            // Move focus here before disabling btn below — a disabled
            // element that holds focus drops it to <body> with no
            // announcement (tabindex=-1 keeps this <p> out of Tab order).
            successEl.focus();
          }
          // No reload on success (see success panel above) — disable both
          // review buttons so an already-approved draft can't be resubmitted.
          btn.disabled = true;
          if (rejectBtn) {
            rejectBtn.disabled = true;
          }
          return;
        }
        if (result.status === 403) {
          showError(errorEl, CSRF_OR_SESSION_MSG);
          return;
        }
        showError(errorEl, window.TakuAPI.formatError(result));
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
    var reasonEl = document.getElementById("draft-reject-reason");
    var listUrlEl = btn.closest("[data-list-url]");
    var listUrl = listUrlEl ? listUrlEl.dataset.listUrl : "/staff/drafts/";

    btn.addEventListener("click", async function () {
      var confirmed = await askConfirm(
        "이 드래프트를 반려할까요? 공개 목록에는 노출되지 않습니다."
      );
      if (!confirmed) {
        return;
      }
      hideError(errorEl);
      window.TakuAPI.setLoading(btn, true);

      var rejectionReason = reasonEl ? reasonEl.value.trim() : "";

      window.TakuAPI.post(
        "/staff/drafts/" + draftId + "/reject/",
        { rejection_reason: rejectionReason }
      ).then(function (result) {
        window.TakuAPI.setLoading(btn, false);
        if (result.ok) {
          window.location.assign(listUrl);
          return;
        }
        if (result.status === 403) {
          showError(errorEl, CSRF_OR_SESSION_MSG);
          return;
        }
        showError(errorEl, window.TakuAPI.formatError(result));
      });
    });
  }

  /* ── raw text toggle ─────────────────────────────────────────────────── */

  function bindRawTextToggle() {
    var btn = document.getElementById("raw-text-toggle");
    if (!btn) {
      return;
    }
    var truncatedEl = document.getElementById("raw-text-truncated");
    var fullEl = document.getElementById("raw-text-full");
    if (!truncatedEl || !fullEl) {
      return;
    }

    btn.addEventListener("click", function () {
      var isExpanded = btn.getAttribute("data-expanded") === "true";
      var expand = !isExpanded;

      // Native `hidden` swap only — JS never touches raw_text content.
      truncatedEl.hidden = expand;
      fullEl.hidden = !expand;

      btn.setAttribute("data-expanded", String(expand));
      btn.textContent = expand ? "접기" : "전체 보기";
    });
  }

  /* ── init ─────────────────────────────────────────────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    bindCreateForm();
    bindEditForm();
    bindApproveButton();
    bindRejectButton();
    bindRawTextToggle();
  });
})();
