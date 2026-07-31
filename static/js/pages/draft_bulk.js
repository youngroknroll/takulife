/**
 * 드래프트 목록의 다중 선택 + 일괄 승인 기능.
 * POST /staff/drafts/bulk-approve/ {"draft_ids":[...]} →
 *   200 {"succeeded": [...ids], "failed": [{"id","reason"}]}
 * 제목이 없는 드래프트(data-missing-title)는 전체선택 대상에서 빠지지만
 * 개별 선택은 그대로 가능하다.
 * 보안: 서버에서 받은 값으로 HTML을 조립하지 않는다 — 화면 갱신은 모두
 * textContent나 className 교체만 사용해 스크립트 삽입 위험을 없앤다.
 */

(function () {
  "use strict";

  var CSRF_OR_SESSION_MSG =
    "403 오류: 세션이 만료되었거나 보안 토큰이 유효하지 않습니다. " +
    "페이지를 새로고침한 뒤 다시 시도해 주세요.";

  // 되돌릴 수 없는 동작이라 확인을 거친다. 공용 모달이 없으면 기본 confirm으로 대체한다.
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  /* ── 선택 상태 헬퍼 ────────────────────────────────────────────────── */

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

  /* ── 툴바 상태(개수, 버튼 비활성, 전체선택 중간 상태) ──── */

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

  /* ── 이벤트 바인딩 ─────────────────────────────────────────────────────────── */

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

  /* ── 승인 응답을 화면에 반영 ──────────────────────── */

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
      var toolbar = document.getElementById("bulk-toolbar");
      chip.textContent = (toolbar && toolbar.dataset.approvedLabel) || "approved";
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
      var total = succeeded.length + failed.length;
      resultEl.textContent =
        failed.length === 0
          ? succeeded.length + "건 모두 승인 완료."
          : succeeded.length +
            "/" +
            total +
            "건 승인 완료. 승인되지 않은 항목은 카드에서 사유를 확인하세요.";
      resultEl.focus();
    }
  }

  /* ── 승인 버튼 ───────────────────────────────────────────────────── */

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
              errorEl.focus();
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

  /* ── 초기화 ─────────────────────────────────────────────────────────── */

  function initBulkToolbar() {
    var toolbar = document.getElementById("bulk-toolbar");
    if (!toolbar) {
      return;
    }
    if (getAllCheckboxes().length === 0) {
      return; // 이 페이지에 대기 중인 드래프트가 없으면 숨긴 채로 둔다
    }

    toolbar.hidden = false;
    bindIndividualCheckboxes();
    bindSelectAllCheckbox();
    bindBulkApproveButton();
    updateToolbarState();
  }

  document.addEventListener("DOMContentLoaded", initBulkToolbar);
})();
