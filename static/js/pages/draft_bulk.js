/**
 * draft_bulk.js — Multi-select + bulk approve for the draft list
 * (templates/core/drafts/list.html only; split out of draft.js because the
 * selection/DOM-patching logic below is a self-contained slice).
 *
 * Endpoint: POST /staff/drafts/bulk-approve/ {"draft_ids":[...]} →
 *   200 {"succeeded": [...ids], "failed": [{"id", "reason"}]}
 * (see staff/views.py::StaffDraftBulkApproveView). A 400 only happens for a
 * structurally invalid request (empty/non-integer/over-cap draft_ids), which
 * cannot occur from this UI since selection always yields a non-empty list
 * of real numeric ids capped by the page size (20).
 *
 * Markup contract (server-rendered, see list.html):
 *   #bulk-toolbar            — hidden by default; this script un-hides it
 *                              only when at least one pending checkbox
 *                              ([data-draft-select]) exists on the page.
 *   #draft-select-all        — page-level select-all checkbox.
 *   [data-draft-select]      — one per pending draft card, data-draft-id
 *                              carries the numeric pk. data-missing-title
 *                              ("true") marks drafts with no title — these
 *                              are excluded from select-all (still
 *                              individually selectable, per PO decision).
 *   #bulk-selected-count     — "N건 선택됨" live count.
 *   #bulk-approve-btn        — disabled while selection is empty.
 *   #bulk-approve-result     — single role=status/aria-live=polite region;
 *                              this is the ONLY place that announces the
 *                              routine "N/M 성공" summary (per-item failures
 *                              are static text, not additional live
 *                              announcements — avoids screen-reader spam).
 *   #bulk-approve-error      — role=alert, hidden by default. Reserved for
 *                              genuine request-level exceptions (403/lost
 *                              session, network, 5xx) that prevent any
 *                              result from coming back at all — mirrors the
 *                              existing #draft-action-error convention
 *                              (draft.js) rather than overloading the
 *                              polite status region with an interrupt.
 *   .draft-list[data-selected-status] — current status filter ("" = all,
 *                              "pending", "approved", "rejected"). Drives
 *                              whether a succeeded card is removed outright
 *                              (pending filter) or just re-chipped
 *                              (any other filter, including "all").
 *   [data-draft-status-chip] — the review-status chip inside each card;
 *                              swapped to "approved" on success.
 *   [data-bulk-fail-reason]  — empty <p> per card (no role — static visual
 *                              text only, not a live announcement; the
 *                              routine "N/M 성공" summary above is the only
 *                              thing that speaks). textContent only, never
 *                              innerHTML (server pre-renders it empty, this
 *                              script only fills plain text, and resets it
 *                              back to empty/hidden when a card that
 *                              previously failed succeeds on retry).
 *
 * Security: no HTML is ever constructed from server data — all writes are
 * textContent or className toggles against a fixed, known string set.
 */

(function () {
  "use strict";

  var CSRF_OR_SESSION_MSG =
    "403 오류: 세션이 만료되었거나 보안 토큰이 유효하지 않습니다. " +
    "페이지를 새로고침한 뒤 다시 시도해 주세요.";

  // Confirm before a destructive, unrecoverable action. Uses the shared modal
  // (confirm-modal.js, loaded in base.html) with a native confirm() fallback
  // — same pattern as visit.js / personal_entries.js.
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  /* ── selection helpers ────────────────────────────────────────────────── */

  function getAllCheckboxes() {
    return Array.prototype.slice.call(
      document.querySelectorAll("[data-draft-select]")
    );
  }

  function getEligibleCheckboxes() {
    return getAllCheckboxes().filter(function (cb) {
      return cb.dataset.missingTitle !== "true";
    });
  }

  function getSelectedCheckboxes() {
    return getAllCheckboxes().filter(function (cb) {
      return cb.checked;
    });
  }

  /* ── toolbar state (count, button disabled, select-all indeterminate) ──── */

  function updateSelectAllState() {
    var selectAll = document.getElementById("draft-select-all");
    if (!selectAll) {
      return;
    }
    var eligible = getEligibleCheckboxes();
    var selectedEligible = eligible.filter(function (cb) {
      return cb.checked;
    });

    if (eligible.length === 0) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
      selectAll.disabled = true;
      return;
    }

    selectAll.disabled = false;
    if (selectedEligible.length === 0) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
    } else if (selectedEligible.length === eligible.length) {
      selectAll.checked = true;
      selectAll.indeterminate = false;
    } else {
      selectAll.checked = false;
      selectAll.indeterminate = true;
    }
  }

  function updateToolbarState() {
    var selected = getSelectedCheckboxes();
    var countEl = document.getElementById("bulk-selected-count");
    var approveBtn = document.getElementById("bulk-approve-btn");

    if (countEl) {
      countEl.textContent = selected.length + "건 선택됨";
    }
    if (approveBtn) {
      approveBtn.disabled = selected.length === 0;
    }
    updateSelectAllState();
  }

  /* ── bindings ─────────────────────────────────────────────────────────── */

  function bindIndividualCheckboxes() {
    getAllCheckboxes().forEach(function (cb) {
      cb.addEventListener("change", updateToolbarState);
    });
  }

  function bindSelectAllCheckbox() {
    var selectAll = document.getElementById("draft-select-all");
    if (!selectAll) {
      return;
    }
    selectAll.addEventListener("change", function () {
      var checked = selectAll.checked;
      getEligibleCheckboxes().forEach(function (cb) {
        cb.checked = checked;
      });
      updateToolbarState();
    });
  }

  /* ── applying the bulk-approve response to the DOM ──────────────────────── */

  function adjustCount(id, delta) {
    var el = document.getElementById(id);
    if (!el) {
      return;
    }
    var current = parseInt(el.textContent, 10);
    if (isNaN(current)) {
      return;
    }
    el.textContent = String(Math.max(0, current + delta));
  }

  function applySucceededDraft(draftId, selectedStatus) {
    var checkbox = document.querySelector(
      '[data-draft-select][data-draft-id="' + draftId + '"]'
    );
    if (!checkbox) {
      return;
    }
    var card = checkbox.closest(".draft-card");

    if (selectedStatus === "pending") {
      if (card) {
        card.remove();
      }
      return;
    }

    var chip = card ? card.querySelector("[data-draft-status-chip]") : null;
    if (chip) {
      chip.textContent = "approved";
      chip.className = "draft-chip approved review-status-approved";
      chip.setAttribute("data-draft-status-chip", "");
    }
    var failEl = card ? card.querySelector("[data-bulk-fail-reason]") : null;
    if (failEl) {
      failEl.textContent = "";
      failEl.hidden = true;
    }
    var label = checkbox.closest(".draft-select");
    if (label) {
      label.remove();
    }
  }

  function applyFailedDraft(item) {
    var checkbox = document.querySelector(
      '[data-draft-select][data-draft-id="' + item.id + '"]'
    );
    if (!checkbox) {
      return;
    }
    var card = checkbox.closest(".draft-card");
    var failEl = card ? card.querySelector("[data-bulk-fail-reason]") : null;
    if (failEl) {
      failEl.textContent = item.reason;
      failEl.hidden = false;
    }
  }

  function applyBulkApproveResult(data, selectedStatus) {
    var succeeded = (data && data.succeeded) || [];
    var failed = (data && data.failed) || [];

    succeeded.forEach(function (draftId) {
      applySucceededDraft(draftId, selectedStatus);
    });
    failed.forEach(function (item) {
      applyFailedDraft(item);
    });

    if (succeeded.length > 0) {
      adjustCount("stat-pending", -succeeded.length);
      adjustCount("stat-approved", succeeded.length);
      adjustCount("chip-count-pending", -succeeded.length);
      adjustCount("chip-count-approved", succeeded.length);
    }

    var resultEl = document.getElementById("bulk-approve-result");
    if (resultEl) {
      resultEl.textContent =
        succeeded.length + "/" + (succeeded.length + failed.length) + " 성공";
    }
  }

  /* ── approve button ───────────────────────────────────────────────────── */

  function bindBulkApproveButton() {
    var btn = document.getElementById("bulk-approve-btn");
    if (!btn) {
      return;
    }
    var resultEl = document.getElementById("bulk-approve-result");
    var errorEl = document.getElementById("bulk-approve-error");
    var draftList = document.querySelector(".draft-list");
    var selectedStatus = draftList ? draftList.dataset.selectedStatus : "";

    btn.addEventListener("click", function () {
      var selected = getSelectedCheckboxes();
      if (selected.length === 0) {
        return;
      }
      var draftIds = selected.map(function (cb) {
        return parseInt(cb.dataset.draftId, 10);
      });

      askConfirm(
        "선택한 " + draftIds.length + "건을 승인하고 게시합니다. 진행할까요?"
      ).then(function (confirmed) {
        if (!confirmed) {
          return;
        }
        if (resultEl) {
          resultEl.textContent = "";
        }
        if (errorEl) {
          errorEl.textContent = "";
          errorEl.hidden = true;
        }
        window.TakuAPI.setLoading(btn, true);

        window.TakuAPI.post("/staff/drafts/bulk-approve/", {
          draft_ids: draftIds,
        }).then(function (result) {
          window.TakuAPI.setLoading(btn, false);

          if (!result.ok) {
            if (errorEl) {
              errorEl.textContent =
                result.status === 403
                  ? CSRF_OR_SESSION_MSG
                  : window.TakuAPI.formatError(result);
              errorEl.hidden = false;
            }
            updateToolbarState();
            return;
          }

          applyBulkApproveResult(result.data, selectedStatus);
          updateToolbarState();
        });
      });
    });
  }

  /* ── init ─────────────────────────────────────────────────────────────── */

  function initBulkToolbar() {
    var toolbar = document.getElementById("bulk-toolbar");
    if (!toolbar) {
      return;
    }
    if (getAllCheckboxes().length === 0) {
      return; // no pending drafts on this page — stays hidden
    }

    toolbar.hidden = false;
    bindIndividualCheckboxes();
    bindSelectAllCheckbox();
    bindBulkApproveButton();
    updateToolbarState();
  }

  document.addEventListener("DOMContentLoaded", initBulkToolbar);
})();
