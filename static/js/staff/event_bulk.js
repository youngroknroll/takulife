/**
 * 이벤트 목록(list.html)의 다중 선택 + 일괄 비공개 설정.
 * POST /staff/events/bulk-unpublish/ {"event_ids":[...]} → 200
 *   {"succeeded":[...ids], "failed":[{"id","reason"}]}
 * 목록 변경은 서버가 succeeded/failed를 응답한 뒤에만 한다(낙관적 제거 없음,
 * draft_bulk.js와 같은 이유).
 */

(function () {
  "use strict";

  var CSRF_OR_SESSION_MSG =
    "403 오류: 세션이 만료되었거나 보안 토큰이 유효하지 않습니다. " +
    "페이지를 새로고침한 뒤 다시 시도해 주세요.";

  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  /* ── 선택 상태 헬퍼 ────────────────────────────────────────────────── */

  function getAllCheckboxes() {
    return Array.prototype.slice.call(
      document.querySelectorAll("[data-event-select]")
    );
  }

  function getSelectedCheckboxes() {
    return getAllCheckboxes().filter(function (cb) {
      return cb.checked;
    });
  }

  /* ── 툴바 상태(개수, 버튼 비활성, 전체선택 중간 상태) ──────────────── */

  function updateSelectAllState() {
    var selectAll = document.getElementById("event-select-all");
    if (!selectAll) {
      return;
    }
    var all = getAllCheckboxes();
    var selected = getSelectedCheckboxes();

    if (all.length === 0) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
      selectAll.disabled = true;
      return;
    }

    selectAll.disabled = false;
    if (selected.length === 0) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
    } else if (selected.length === all.length) {
      selectAll.checked = true;
      selectAll.indeterminate = false;
    } else {
      selectAll.checked = false;
      selectAll.indeterminate = true;
    }
  }

  function updateToolbarState() {
    var selected = getSelectedCheckboxes();
    var countEl = document.getElementById("event-bulk-selected-count");
    var btn = document.getElementById("event-bulk-unpublish-btn");

    if (countEl) {
      countEl.textContent = selected.length + "건 선택";
    }
    if (btn) {
      btn.disabled = selected.length === 0;
    }
    updateSelectAllState();
  }

  /* ── 이벤트 바인딩 ─────────────────────────────────────────────────── */

  function bindCheckboxChangeDelegation() {
    var table = document.querySelector(".events-table");
    if (!table) {
      return;
    }
    table.addEventListener("change", function (event) {
      if (event.target.matches("[data-event-select]")) {
        updateToolbarState();
      }
    });
  }

  function bindSelectAllCheckbox() {
    var selectAll = document.getElementById("event-select-all");
    if (!selectAll) {
      return;
    }
    selectAll.addEventListener("change", function () {
      var checked = selectAll.checked;
      getAllCheckboxes().forEach(function (cb) {
        cb.checked = checked;
      });
      updateToolbarState();
    });
  }

  /* ── 일괄 비공개 응답을 화면에 반영 ───────────────────────────────── */

  function getRowById(eventId) {
    return document.querySelector('[data-event-row="' + eventId + '"]');
  }

  function applySucceededEvent(eventId, table) {
    var row = getRowById(eventId);
    if (!row) {
      return false;
    }

    var selectedPublishStatus = table ? table.dataset.selectedPublishStatus : "";
    var selectedWarning = table ? table.dataset.selectedWarning : "";

    if (selectedPublishStatus === "published" || selectedWarning) {
      // 이 필터에는 더 이상 속하지 않는 결과라 행을 통째로 지운다.
      row.remove();
      return true;
    }

    // "전체" 탭 + 경고 없음: 행은 남기고 배지·체크박스만 갱신한다.
    var badge = row.querySelector(".events-status-badge");
    if (badge) {
      badge.classList.remove("events-status-badge--published");
      badge.classList.add("events-status-badge--draft");
      badge.textContent = "비공개";
    }
    row.querySelectorAll(".events-warn-badge").forEach(function (warnBadge) {
      warnBadge.remove();
    });
    // 비공개로 전환됐으니 인라인 액션 버튼도 그 상태에 맞춰 토글한다.
    var verifyBtn = row.querySelector('[data-row-action="verify"]');
    if (verifyBtn) {
      verifyBtn.hidden = true;
    }
    var unpublishBtn = row.querySelector('[data-row-action="unpublish"]');
    if (unpublishBtn) {
      unpublishBtn.hidden = true;
    }
    var republishBtn = row.querySelector('[data-row-action="republish"]');
    if (republishBtn) {
      republishBtn.hidden = false;
    }
    var checkbox = row.querySelector("[data-event-select]");
    if (checkbox) {
      var cell = checkbox.closest("td");
      var label = cell ? cell.querySelector("label") : null;
      if (label) {
        label.remove();
      }
      checkbox.remove();
    }
    return false;
  }

  function applyFailedEvent(item) {
    var row = getRowById(item.id);
    if (!row) {
      return;
    }
    var failEl = row.querySelector("[data-row-error]");
    if (failEl) {
      failEl.textContent = item.reason;
      failEl.hidden = false;
    }
  }

  function applyBulkResult(data, table) {
    var succeeded = (data && data.succeeded) || [];
    var failed = (data && data.failed) || [];
    var removedAny = false;

    succeeded.forEach(function (eventId) {
      if (applySucceededEvent(eventId, table)) {
        removedAny = true;
      }
    });
    failed.forEach(function (item) {
      applyFailedEvent(item);
    });

    var resultEl = document.getElementById("event-bulk-result");
    if (resultEl) {
      var total = succeeded.length + failed.length;
      var resultText =
        failed.length === 0
          ? succeeded.length + "건 모두 비공개 완료."
          : succeeded.length +
            "/" +
            total +
            "건 비공개 완료. 처리되지 않은 항목은 행에서 사유를 확인하세요.";
      resultEl.textContent = resultText;
      var liveEl = document.getElementById("event-live");
      if (liveEl) {
        liveEl.textContent = resultText;
      }
      if (removedAny) {
        resultEl.appendChild(document.createTextNode(" "));
        var link = document.createElement("a");
        link.href = window.location.href;
        link.textContent = "이 페이지 새로고침";
        resultEl.appendChild(link);
      }
      resultEl.focus();
    }

    if (document.querySelectorAll("[data-event-row]").length === 0) {
      var tableWrap = document.querySelector(".events-table-wrap");
      if (tableWrap) {
        tableWrap.hidden = true;
      }
      var emptyEl = document.getElementById("event-bulk-empty");
      if (emptyEl) {
        emptyEl.hidden = false;
        emptyEl.focus();
      }
    }
  }

  /* ── 일괄 비공개 버튼 처리 ────────────────────────────────────────── */

  function bindBulkUnpublishButton() {
    var btn = document.getElementById("event-bulk-unpublish-btn");
    if (!btn) {
      return;
    }
    var resultEl = document.getElementById("event-bulk-result");
    var errorEl = document.getElementById("event-bulk-error");
    var table = document.querySelector(".events-table");

    btn.addEventListener("click", function () {
      var selected = getSelectedCheckboxes();
      if (selected.length === 0) {
        return;
      }
      var eventIds = selected.map(function (cb) {
        return parseInt(cb.dataset.eventId, 10);
      });

      askConfirm(
        "선택한 " +
          eventIds.length +
          "건을 비공개로 설정합니다. 되돌리려면 각 건을 개별적으로 다시 게시해야 합니다. 진행할까요?"
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

        window.TakuAPI.post("/staff/events/bulk-unpublish/", { event_ids: eventIds }).then(
          function (result) {
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

            applyBulkResult(result.data, table);
            updateToolbarState();
          }
        );
      });
    });
  }

  /* ── 초기화 / 재계산 ──────────────────────────────────────────────── */

  // 리스너를 다시 붙이지 않고 노출 여부와 카운터만 재계산한다. 재게시로
  // 체크박스가 새로 생겼을 때 event_row_actions.js가 이 함수만 부른다.
  function refreshToolbar() {
    var toolbar = document.getElementById("event-bulk-toolbar");
    if (!toolbar) {
      return;
    }
    if (getAllCheckboxes().length > 0) {
      toolbar.hidden = false;
    }
    updateToolbarState();
  }

  function initBulkToolbar() {
    var toolbar = document.getElementById("event-bulk-toolbar");
    if (!toolbar) {
      return;
    }
    bindCheckboxChangeDelegation();
    bindSelectAllCheckbox();
    bindBulkUnpublishButton();
    refreshToolbar();
  }

  window.TakuEventBulk = { refreshToolbar: refreshToolbar };

  document.addEventListener("DOMContentLoaded", function () {
    initBulkToolbar();
  });
})();
