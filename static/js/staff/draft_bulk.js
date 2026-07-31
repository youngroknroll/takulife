/**
 * 드래프트 큐(list.html)의 다중 선택 + 일괄 승인/반려 + 행 단위(인스펙터)
 * 승인/반려 + "현재 행" 상태 관리.
 *
 * 일괄:
 *   POST /staff/drafts/bulk-approve/ {"draft_ids":[...]} → 200
 *   POST /staff/drafts/bulk-reject/  {"draft_ids":[...]} → 200
 *   둘 다 {"succeeded": [...ids], "failed": [{"id","reason"}]}를 돌려준다.
 * 행 단위:
 *   POST /staff/drafts/<id>/approve/, /staff/drafts/<id>/reject/ (draft.js의
 *   전체 검토 화면과 같은 엔드포인트) — 여기서는 큐 인스펙터의 버튼에서 쓴다.
 *
 * 제목이 없는 드래프트(data-missing-title)는 전체선택 대상에서 빠지지만
 * 개별 선택은 그대로 가능하다.
 * 목록 변경은 서버가 succeeded/failed를 응답한 뒤에만 한다 — 낙관적 제거
 * 없음(D7, 유령 행 결함 전례).
 * 보안: 서버에서 받은 값으로 HTML을 조립하지 않는다 — textContent/className만
 * 바꿔 스크립트 삽입 위험을 없앤다.
 *
 * window.TakuQueue로 "현재 행" 이동·판정 트리거를 외부(queue_shortcuts.js)에
 * 공개한다 — 단축키는 여기 있는 실제 버튼을 클릭하는 방식으로 확인 대화상자·
 * 오류 표시·서버 응답 반영 로직을 그대로 재사용한다.
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
    var rejectBtn = document.getElementById("bulk-reject-btn");

    if (countEl) {
      countEl.textContent = selected.length + "건 선택";
    }
    if (approveBtn) {
      approveBtn.disabled = selected.length === 0;
    }
    if (rejectBtn) {
      rejectBtn.disabled = selected.length === 0;
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

  /* ── 카운트 보정 ──────────────────────────────────────────────────── */

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

  /* ── 현재 행(J/K 대상) 관리 ───────────────────────────────────────
   * 큐의 모든 행 데이터는 페이지 로드 시 서버가 이미 렌더링해 뒀다(D5) —
   * 여기서는 hidden/포커스/실시간 안내만 다룬다. */

  function getRows() {
    return Array.prototype.slice.call(
      document.querySelectorAll("[data-queue-row]")
    );
  }

  function getRowById(draftId) {
    return document.querySelector(
      '[data-queue-row][data-draft-id="' + draftId + '"]'
    );
  }

  function getPanelById(draftId) {
    return document.querySelector(
      '[data-inspector-panel][data-draft-id="' + draftId + '"]'
    );
  }

  function getCurrentId() {
    var row = document.querySelector("[data-queue-row].is-current");
    return row ? row.dataset.draftId : null;
  }

  function announce(row) {
    var live = document.getElementById("queue-inspector-live");
    if (!live) {
      return;
    }
    var titleEl = row.querySelector(".queue-title");
    var title = titleEl ? titleEl.textContent : "";
    live.textContent = "#" + row.dataset.draftId + " " + title + " 선택됨";
  }

  // 판정 결과를 "선택됨"과 구분해 알린다. 같은 문구를 재사용하면 방금 반려한
  // 사용자가 "선택됨"만 듣고 성공 여부를 알 수 없다.
  function announceOutcome(draftId, stateLabel) {
    var live = document.getElementById("queue-inspector-live");
    if (live) {
      live.textContent = "#" + draftId + " " + stateLabel;
    }
  }

  // focus가 필요한 이유: J/K로 옮긴 뒤 A/R을 누르면 바로 그 행이 대상이어야
  // 하고, 스크린리더 사용자도 어느 행이 현재인지 포커스로 알 수 있어야 한다.
  function setCurrentRow(draftId, options) {
    var opts = options || {};
    var rows = getRows();
    rows.forEach(function (row) {
      var isTarget = row.dataset.draftId === String(draftId);
      row.classList.toggle("is-current", isTarget);
      var openBtn = row.querySelector("[data-queue-row-open]");
      if (openBtn) {
        if (isTarget) {
          openBtn.setAttribute("aria-current", "true");
        } else {
          openBtn.removeAttribute("aria-current");
        }
      }
    });

    document
      .querySelectorAll("[data-inspector-panel]")
      .forEach(function (panel) {
        var isTarget = panel.dataset.draftId === String(draftId);
        panel.hidden = !isTarget;
        panel.classList.toggle("is-current", isTarget);
      });

    var emptyEl = document.getElementById("queue-inspector-empty");
    if (emptyEl) {
      emptyEl.hidden = true;
    }

    var targetRow = getRowById(draftId);
    if (targetRow) {
      if (opts.announce !== false) {
        announce(targetRow);
      }
      if (opts.focus) {
        var openBtn = targetRow.querySelector("[data-queue-row-open]");
        if (openBtn) {
          openBtn.focus();
        }
      }
    }
  }

  function showEmptyState() {
    document.querySelectorAll("[data-queue-row]").forEach(function (row) {
      row.classList.remove("is-current");
    });
    document
      .querySelectorAll("[data-inspector-panel]")
      .forEach(function (panel) {
        panel.hidden = true;
      });
    var emptyEl = document.getElementById("queue-inspector-empty");
    if (emptyEl) {
      emptyEl.hidden = false;
      // 판정 후 포커스를 body로 잃지 않고 빈 상태 문구로 보낸다(D6).
      emptyEl.focus();
    }
    var live = document.getElementById("queue-inspector-live");
    if (live) {
      live.textContent = "이 페이지의 드래프트를 모두 처리했습니다.";
    }
  }

  function moveCurrent(step) {
    var rows = getRows();
    if (rows.length === 0) {
      return;
    }
    var currentId = getCurrentId();
    var index = rows.findIndex(function (row) {
      return row.dataset.draftId === currentId;
    });
    if (index === -1) {
      index = 0;
    }
    var nextIndex = index + step;
    if (nextIndex < 0) {
      nextIndex = 0;
    }
    if (nextIndex > rows.length - 1) {
      nextIndex = rows.length - 1;
    }
    setCurrentRow(rows[nextIndex].dataset.draftId, { focus: true });
  }

  // 행이 판정으로 사라진 뒤 다음(없으면 이전) 행으로 넘어간다. 아무 행도
  // 남지 않으면 빈 상태 문구로 포커스를 보낸다 — <body>로 잃지 않는다(D6).
  function advanceAfterRemoval(removedIndex, remainingRows) {
    if (remainingRows.length === 0) {
      showEmptyState();
      return;
    }
    var nextIndex = Math.min(removedIndex, remainingRows.length - 1);
    setCurrentRow(remainingRows[nextIndex].dataset.draftId, { focus: true });
  }

  function removeDraftRow(draftId) {
    var rows = getRows();
    var index = rows.findIndex(function (row) {
      return row.dataset.draftId === String(draftId);
    });
    var wasCurrent = getCurrentId() === String(draftId);

    var row = getRowById(draftId);
    if (row) {
      row.remove();
    }
    var panel = getPanelById(draftId);
    if (panel) {
      panel.remove();
    }

    if (wasCurrent) {
      advanceAfterRemoval(index, getRows());
    }
  }

  /* ── 일괄 판정 응답을 화면에 반영 ──────────────────────── */

  // 서버가 list.html에 내려주는 라벨 맵을 읽는다(json_script). 이 스크립트는
  // 큐 화면 밖에서도 로드될 수 있으니, 블록이 없거나 파싱에 실패해도 빈
  // 객체로 조용히 물러선다 — 아래 소비부의 `|| targetLabel` 폴백이 대신한다.
  function readStatusStateLabels() {
    var el = document.getElementById("draft-status-labels");
    if (!el) {
      return {};
    }
    try {
      return JSON.parse(el.textContent) || {};
    } catch (e) {
      return {};
    }
  }

  var STATUS_STATE_LABEL = readStatusStateLabels();

  function applySucceededDraft(draftId, selectedStatus, targetStatus, targetLabel) {
    var checkbox = document.querySelector(
      '[data-draft-select][data-draft-id="' + draftId + '"]'
    );

    if (selectedStatus === "pending") {
      // 검토 대기 탭에서는 판정된 행이 더 이상 이 목록에 속하지 않는다.
      removeDraftRow(draftId);
      return;
    }

    // "전체" 탭: 행은 남기고 상태만 갱신한다. 표의 상태 배지와 인스펙터
    // 헤더의 배지가 따로 있어 둘 다 갱신하고, 더 이상 대기 상태가 아니므로
    // 승인/반려 버튼도 지운다(되돌릴 수 없는 판정이라 다시 누를 수 없어야
    // 한다).
    var stateLabel = STATUS_STATE_LABEL[targetStatus] || targetLabel;
    var chip = document.querySelector(
      '[data-queue-row][data-draft-id="' + draftId + '"] [data-draft-status-chip]'
    );
    if (chip) {
      chip.textContent = stateLabel;
      chip.className = "queue-status-chip review-status-" + targetStatus;
      chip.setAttribute("data-draft-status-chip", "");
    }
    if (checkbox) {
      checkbox.remove();
    }

    var panel = getPanelById(draftId);
    if (panel) {
      var panelChip = panel.querySelector(".queue-inspector-head .queue-status-chip");
      if (panelChip) {
        panelChip.textContent = stateLabel;
        panelChip.className = "queue-status-chip review-status-" + targetStatus;
      }
      var actionScope = panel.querySelector("[data-draft-action-scope]");
      if (actionScope) {
        actionScope.remove();
      }
      // 판정을 누른 버튼은 확인 대화상자가 닫히는 시점에 이미 사라졌거나
      // 포커스를 잃는다. 여기서 되돌려 놓지 않으면 body에 남아 키보드
      // 사용자가 위치를 잃는다(실측: 반려 후 activeElement === body).
      if (document.activeElement === document.body) {
        var panelHead = panel.querySelector(".queue-inspector-head");
        if (panelHead) {
          panelHead.setAttribute("tabindex", "-1");
          panelHead.focus();
        }
      }
    }

    // 행 이동 없이 배지 글자만 바뀌므로, 알리지 않으면 결과가 조용히 끝난다.
    announceOutcome(draftId, stateLabel);
  }

  function applyFailedDraft(item) {
    var failEl = document.querySelector(
      '[data-queue-row][data-draft-id="' + item.id + '"] [data-bulk-fail-reason]'
    );
    if (failEl) {
      failEl.textContent = item.reason;
      failEl.hidden = false;
    }
  }

  function applyBulkResult(data, selectedStatus, targetStatus, targetLabel) {
    var succeeded = (data && data.succeeded) || [];
    var failed = (data && data.failed) || [];

    succeeded.forEach(function (draftId) {
      applySucceededDraft(draftId, selectedStatus, targetStatus, targetLabel);
    });
    failed.forEach(function (item) {
      applyFailedDraft(item);
    });

    if (succeeded.length > 0) {
      adjustCount("chip-count-pending", -succeeded.length);
      if (targetStatus === "approved") {
        adjustCount("chip-count-approved", succeeded.length);
      } else {
        adjustCount("chip-count-rejected", succeeded.length);
      }
    }

    var resultEl = document.getElementById("bulk-approve-result");
    if (resultEl) {
      var total = succeeded.length + failed.length;
      resultEl.textContent =
        failed.length === 0
          ? succeeded.length + "건 모두 " + targetLabel + " 완료."
          : succeeded.length +
            "/" +
            total +
            "건 " +
            targetLabel +
            " 완료. 처리되지 않은 항목은 행에서 사유를 확인하세요.";
      resultEl.focus();
    }
  }

  /* ── 일괄 승인/반려 버튼 공용 처리 ───────────────────────────────── */

  function bindBulkJudgementButton(btnId, endpoint, confirmVerb, targetStatus, targetLabel) {
    var btn = document.getElementById(btnId);
    if (!btn) {
      return;
    }
    var resultEl = document.getElementById("bulk-approve-result");
    var errorEl = document.getElementById("bulk-approve-error");
    var table = document.querySelector(".queue-table");
    var selectedStatus = table ? table.dataset.selectedStatus : "";

    btn.addEventListener("click", function () {
      var selected = getSelectedCheckboxes();
      if (selected.length === 0) {
        return;
      }
      var draftIds = selected.map(function (cb) {
        return parseInt(cb.dataset.draftId, 10);
      });

      askConfirm(
        "선택한 " + draftIds.length + "건을 " + confirmVerb + "합니다. 진행할까요?"
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

        window.TakuAPI.post(endpoint, { draft_ids: draftIds }).then(function (result) {
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

          applyBulkResult(result.data, selectedStatus, targetStatus, targetLabel);
          updateToolbarState();
        });
      });
    });
  }

  /* ── 인스펙터의 행 단위 승인/반려(J/K/A/R가 클릭하는 실제 버튼) ──────
   * draft.js의 전체 검토 화면과 같은 엔드포인트를 쓰지만, 페이지 이동 대신
   * 큐 화면 안에서 행을 갱신한다. */

  function bindQueueRowJudgement(selector, endpointSuffix, confirmMessage, targetStatus, targetLabel) {
    document.querySelectorAll(selector).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var draftId = btn.dataset.draftId;
        var scope = btn.closest("[data-draft-action-scope]");
        var panel = btn.closest("[data-inspector-panel]");
        var errorEl = panel ? panel.querySelector('[data-role="draft-action-error"]') : null;

        askConfirm(confirmMessage).then(function (confirmed) {
          if (!confirmed) {
            return;
          }
          if (errorEl) {
            errorEl.hidden = true;
            errorEl.textContent = "";
          }
          window.TakuAPI.setLoading(btn, true);

          window.TakuAPI.post("/staff/drafts/" + draftId + "/" + endpointSuffix + "/", {}).then(
            function (result) {
              window.TakuAPI.setLoading(btn, false);
              if (!result.ok) {
                var message =
                  result.status === 403 ? CSRF_OR_SESSION_MSG : window.TakuAPI.formatError(result);
                if (errorEl) {
                  errorEl.textContent = message;
                  errorEl.hidden = false;
                  errorEl.focus();
                }
                return;
              }

              var table = document.querySelector(".queue-table");
              var selectedStatus = table ? table.dataset.selectedStatus : "";
              adjustCount("chip-count-pending", -1);
              if (targetStatus === "approved") {
                adjustCount("chip-count-approved", 1);
              } else {
                adjustCount("chip-count-rejected", 1);
              }
              // "검토 대기" 탭이면 이 행은 더 이상 그 탭에 속하지 않으니
              // 제거(+다음 행/빈 상태로 포커스 이동)한다. "전체" 탭이면
              // 상태만 갱신하고 행은 그대로 둔다 — applySucceededDraft가
              // bulk-approve/reject와 같은 이 분기를 공유한다(D7).
              void scope;
              applySucceededDraft(draftId, selectedStatus, targetStatus, targetLabel);
            }
          );
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
    bindBulkJudgementButton(
      "bulk-approve-btn",
      "/staff/drafts/bulk-approve/",
      "승인하고 게시",
      "approved",
      "승인"
    );
    bindBulkJudgementButton(
      "bulk-reject-btn",
      "/staff/drafts/bulk-reject/",
      "반려",
      "rejected",
      "반려"
    );
    updateToolbarState();
  }

  function initQueueRowJudgement() {
    bindQueueRowJudgement(
      "[data-draft-approve]",
      "approve",
      "승인하고 게시하면 공개 이벤트 목록에 노출됩니다. 진행할까요?",
      "approved",
      "승인"
    );
    bindQueueRowJudgement(
      "[data-draft-reject]",
      "reject",
      "이 드래프트를 반려할까요? 공개 목록에는 노출되지 않습니다.",
      "rejected",
      "반려"
    );
  }

  document.addEventListener("DOMContentLoaded", function () {
    initBulkToolbar();
    initQueueRowJudgement();
  });

  /* ── 외부 공개: 단축키(queue_shortcuts.js)가 쓰는 최소 API ────────── */
  window.TakuQueue = {
    hasRows: function () {
      return getRows().length > 0;
    },
    moveNext: function () {
      moveCurrent(1);
    },
    movePrev: function () {
      moveCurrent(-1);
    },
    getCurrentApproveButton: function () {
      var id = getCurrentId();
      if (!id) {
        return null;
      }
      return document.querySelector(
        '[data-inspector-panel][data-draft-id="' + id + '"] [data-draft-approve]'
      );
    },
    getCurrentRejectButton: function () {
      var id = getCurrentId();
      if (!id) {
        return null;
      }
      return document.querySelector(
        '[data-inspector-panel][data-draft-id="' + id + '"] [data-draft-reject]'
      );
    },
    getCurrentCheckbox: function () {
      var id = getCurrentId();
      if (!id) {
        return null;
      }
      return document.querySelector(
        '[data-draft-select][data-draft-id="' + id + '"]'
      );
    },
    getCurrentFullReviewLink: function () {
      var id = getCurrentId();
      if (!id) {
        return null;
      }
      return document.querySelector(
        '[data-inspector-panel][data-draft-id="' + id + '"] [data-queue-full-review]'
      );
    },
  };
})();
