/**
 * 이벤트 목록(list.html) 행 인라인 액션: 검증 완료, 비공개, 다시 게시.
 * POST /staff/events/<id>/publish-status/ {"publish_status":"draft"|"published"},
 * POST /staff/events/<id>/verified/ {} → 둘 다 200 {"id", ..., "quality_badges":[...]}.
 */

(function () {
  "use strict";

  var CSRF_OR_SESSION_MSG =
    "403 오류: 세션이 만료되었거나 보안 토큰이 유효하지 않습니다. " +
    "페이지를 새로고침한 뒤 다시 시도해 주세요.";

  var VERIFY_CONFIRM_MESSAGE =
    "이 이벤트의 공식 정보를 다시 확인했나요? 검증 완료로 기록되며 되돌릴 수 없습니다.";

  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  /* ── 행 조회 헬퍼 ──────────────────────────────────────────────────── */

  function getRowActionButtons(row) {
    return {
      verify: row.querySelector('[data-row-action="verify"]'),
      unpublish: row.querySelector('[data-row-action="unpublish"]'),
      republish: row.querySelector('[data-row-action="republish"]'),
    };
  }

  function setRowLocked(row, locked) {
    var checkbox = row.querySelector("[data-event-select]");
    if (checkbox) {
      checkbox.disabled = locked;
    }
    var buttons = getRowActionButtons(row);
    Object.keys(buttons).forEach(function (key) {
      if (buttons[key]) {
        buttons[key].disabled = locked;
      }
    });
    // api.js의 pageshow 핸들러는 ".is-loading" 버튼만 복구해 체크박스·형제
    // 버튼의 plain disabled는 못 풀어준다 — 행 표식을 따로 남겨 아래에서 복구한다.
    row.classList.toggle("is-row-locked", locked);
  }

  function getErrorEl(row) {
    return row.querySelector("[data-row-error]");
  }

  function clearError(row) {
    var errorEl = getErrorEl(row);
    if (errorEl) {
      errorEl.textContent = "";
      errorEl.hidden = true;
    }
  }

  function showError(row, message) {
    var errorEl = getErrorEl(row);
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.hidden = false;
      errorEl.focus();
    }
  }

  function announce(message) {
    var live = document.getElementById("event-live");
    if (!live) {
      return;
    }
    // 포커스 이동과 같은 틱에 쓰면 스크린리더가 live region 갱신을 놓칠 수 있어 한 박자 늦춘다.
    window.setTimeout(function () {
      live.textContent = message;
    }, 100);
  }

  function getRowTitle(row) {
    var titleCell = row.querySelector(".events-title-cell");
    return titleCell ? titleCell.textContent : "";
  }

  /* ── 경고 배지 다시 그리기(응답 quality_badges 기준) ──────────────── */

  function redrawWarningBadges(row, qualityBadges) {
    row.querySelectorAll(".events-warn-badge").forEach(function (badge) {
      badge.remove();
    });
    var host = row.querySelector("[data-row-error-host]");
    if (!host) {
      return;
    }
    var badges = qualityBadges || [];
    var refNode = host.firstChild;
    badges.forEach(function (label) {
      var span = document.createElement("span");
      span.className = "events-warn-badge";
      span.textContent = "⚠ " + label;
      host.insertBefore(span, refNode);
    });
  }

  /* ── 결과 문단(행 제거 시에만) ────────────────────────────────────── */

  function showResult(message) {
    var resultEl = document.getElementById("event-bulk-result");
    if (!resultEl) {
      return;
    }
    // 결과 문단은 툴바 안에 있어, 체크박스가 없어 툴바가 hidden인 탭에서도 보이게 먼저 노출한다.
    var toolbar = document.getElementById("event-bulk-toolbar");
    if (toolbar && toolbar.hidden) {
      toolbar.hidden = false;
    }
    resultEl.textContent = message + " ";
    var link = document.createElement("a");
    link.href = window.location.href;
    link.textContent = "이 페이지 새로고침";
    resultEl.appendChild(link);
    resultEl.focus();
  }

  function handleRowRemoval() {
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

  function refreshBulkToolbar() {
    if (window.TakuEventBulk) {
      window.TakuEventBulk.refreshToolbar();
    }
  }

  /* ── 체크박스 셀 생성(재게시 시 서버 마크업과 동일) ──────────────── */

  function buildCheckboxCell(row, eventId, title) {
    var cell = row.querySelector("td");
    if (!cell) {
      return;
    }
    cell.textContent = "";
    var label = document.createElement("label");
    label.className = "sr-only";
    label.setAttribute("for", "event-select-" + eventId);
    label.textContent = title + " 선택";
    var input = document.createElement("input");
    input.type = "checkbox";
    input.id = "event-select-" + eventId;
    input.className = "event-select-checkbox";
    input.setAttribute("data-event-select", "");
    input.setAttribute("data-event-id", String(eventId));
    cell.appendChild(label);
    cell.appendChild(input);
  }

  function removeCheckboxCell(row) {
    var checkbox = row.querySelector("[data-event-select]");
    if (!checkbox) {
      return;
    }
    var cell = checkbox.closest("td");
    var label = cell ? cell.querySelector("label") : null;
    if (label) {
      label.remove();
    }
    checkbox.remove();
  }

  /* ── 성공 반영 ────────────────────────────────────────────────────── */

  function applyUnpublishSuccess(row, btn, data) {
    var selectedPublishStatus = row.closest("table")
      ? row.closest("table").dataset.selectedPublishStatus
      : "";
    var selectedWarning = row.closest("table")
      ? row.closest("table").dataset.selectedWarning
      : "";
    var title = getRowTitle(row);

    if (selectedPublishStatus === "published" || selectedWarning) {
      row.remove();
      showResult("1건 비공개 완료.");
      handleRowRemoval();
      announce(title + " 비공개 완료");
      return;
    }

    var badge = row.querySelector(".events-status-badge");
    if (badge) {
      badge.classList.remove("events-status-badge--published");
      badge.classList.add("events-status-badge--draft");
      badge.textContent = "비공개";
    }
    redrawWarningBadges(row, data.quality_badges);
    removeCheckboxCell(row);
    var buttons = getRowActionButtons(row);
    if (buttons.verify) {
      buttons.verify.hidden = true;
    }
    if (buttons.unpublish) {
      buttons.unpublish.hidden = true;
    }
    if (buttons.republish) {
      buttons.republish.hidden = false;
      buttons.republish.focus();
    }
    announce(title + " 비공개 완료");
  }

  function applyRepublishSuccess(row, btn, data) {
    var table = row.closest("table");
    var selectedPublishStatus = table ? table.dataset.selectedPublishStatus : "";
    var title = getRowTitle(row);

    if (selectedPublishStatus === "draft") {
      row.remove();
      showResult("1건 게시 완료.");
      handleRowRemoval();
      announce(title + " 게시 완료");
      return;
    }

    var badge = row.querySelector(".events-status-badge");
    if (badge) {
      badge.classList.remove("events-status-badge--draft");
      badge.classList.add("events-status-badge--published");
      badge.textContent = "게시";
    }
    redrawWarningBadges(row, data.quality_badges);
    buildCheckboxCell(row, data.id, title);
    var buttons = getRowActionButtons(row);
    if (buttons.republish) {
      buttons.republish.hidden = true;
    }
    if (buttons.unpublish) {
      buttons.unpublish.hidden = false;
    }
    if (buttons.verify) {
      buttons.verify.hidden = false;
      buttons.verify.textContent =
        row.dataset.verified === "1" ? "다시 검증" : "검증 완료";
    }
    if (buttons.unpublish) {
      buttons.unpublish.focus();
    }
    announce(title + " 게시 완료");
  }

  function applyVerifySuccess(row, btn, data) {
    var table = row.closest("table");
    var selectedWarning = table ? table.dataset.selectedWarning : "";
    var title = getRowTitle(row);

    if (selectedWarning === "needs_reverification") {
      row.remove();
      showResult("1건 검증 완료.");
      handleRowRemoval();
      announce(title + " 검증 완료");
      return;
    }

    row.dataset.verified = "1";
    btn.textContent = "다시 검증";
    redrawWarningBadges(row, data.quality_badges);
    btn.focus();
    announce(title + " 검증 완료");
  }

  /* ── 요청 처리 ────────────────────────────────────────────────────── */

  function endpointFor(action, eventId) {
    if (action === "verify") {
      return "/staff/events/" + eventId + "/verified/";
    }
    return "/staff/events/" + eventId + "/publish-status/";
  }

  function bodyFor(action) {
    if (action === "unpublish") {
      return { publish_status: "draft" };
    }
    if (action === "republish") {
      return { publish_status: "published" };
    }
    return {};
  }

  function handleFailure(row, btn, action, result) {
    var title = getRowTitle(row);
    if (result.status === 403) {
      showError(row, CSRF_OR_SESSION_MSG);
      announce(title + " 처리 실패");
      return;
    }
    if (result.status === 404) {
      row.remove();
      showResult("1건은 이미 삭제된 이벤트였습니다.");
      handleRowRemoval();
      announce(title + " 이미 삭제됨");
      return;
    }
    showError(row, window.TakuAPI.formatError(result));
    announce(title + " 처리 실패");
  }

  function handleSuccess(row, btn, action, data) {
    if (action === "unpublish") {
      applyUnpublishSuccess(row, btn, data);
    } else if (action === "republish") {
      applyRepublishSuccess(row, btn, data);
    } else if (action === "verify") {
      applyVerifySuccess(row, btn, data);
    }
    refreshBulkToolbar();
  }

  function performAction(row, btn, action) {
    var eventId = btn.dataset.eventId;
    clearError(row);
    setRowLocked(row, true);
    window.TakuAPI.setLoading(btn, true);

    window.TakuAPI.post(endpointFor(action, eventId), bodyFor(action)).then(function (result) {
      window.TakuAPI.setLoading(btn, false);
      setRowLocked(row, false);

      if (!result.ok) {
        handleFailure(row, btn, action, result);
        refreshBulkToolbar();
        return;
      }

      handleSuccess(row, btn, action, result.data);
    });
  }

  function handleActionClick(btn) {
    var row = btn.closest("[data-event-row]");
    if (!row) {
      return;
    }
    var action = btn.dataset.rowAction;

    if (action === "verify") {
      askConfirm(VERIFY_CONFIRM_MESSAGE).then(function (confirmed) {
        if (!confirmed) {
          return;
        }
        performAction(row, btn, action);
      });
      return;
    }

    performAction(row, btn, action);
  }

  /* ── 초기화 ────────────────────────────────────────────────────────── */

  function bindRowActionDelegation() {
    var table = document.querySelector(".events-table");
    if (!table) {
      return;
    }
    table.addEventListener("click", function (event) {
      var btn = event.target.closest("[data-row-action]");
      if (!btn) {
        return;
      }
      handleActionClick(btn);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindRowActionDelegation();
  });

  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) {
      return;
    }
    document.querySelectorAll("[data-event-row].is-row-locked").forEach(function (row) {
      setRowLocked(row, false);
    });
  });
})();
