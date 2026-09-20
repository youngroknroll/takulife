/**
 * 스태프 대시보드 "새 수집처 탐색" 패널을 폴링으로 실시간 갱신한다.
 * 서버가 처음 렌더한 마크업은 그대로 두고, 이후에는 순수 JSON 응답만
 * 받아 textContent·클래스 토큰·hidden 속성만 바꾼다(innerHTML 금지).
 */

(function () {
  "use strict";

  var SHORT_DELAY_MS = 5000;
  var LONG_DELAY_MS = 20000;
  var MAX_DELAY_MS = 60000;

  var panel = null;
  var liveUrl = null;
  var rowTemplate = null;
  var outcomeTemplate = null;

  var timerId = null;
  var currentDelay = LONG_DELAY_MS;
  var inFlight = false;
  var stopped = false;
  var lastCompareKey = null;
  var lastPhase = null;
  var lastDetail = null;

  // ── 표시용 변환 ──────────────────────────────────────────────────

  // 서버 |date:"y.m.d H:i"와 같은 결과를 ISO 문자열 슬라이스로 만든다(D12).
  function formatDateTime(iso) {
    if (!iso || iso.length < 16) {
      return "-";
    }
    return (
      iso.slice(2, 4) + "." + iso.slice(5, 7) + "." + iso.slice(8, 10) +
      " " + iso.slice(11, 13) + ":" + iso.slice(14, 16)
    );
  }

  // server_time과 last_heartbeat_at의 차이를 "N초/N분/N시간"으로 보여준다.
  function formatElapsedKorean(serverIso, heartbeatIso) {
    var serverMs = Date.parse(serverIso);
    var hbMs = Date.parse(heartbeatIso);
    if (isNaN(serverMs) || isNaN(hbMs)) {
      return "";
    }
    var diffSec = Math.max(0, Math.round((serverMs - hbMs) / 1000));
    if (diffSec < 60) {
      return diffSec + "초";
    }
    var diffMin = Math.round(diffSec / 60);
    if (diffMin < 60) {
      return diffMin + "분";
    }
    return Math.round(diffMin / 60) + "시간";
  }

  // Django truncatechars:60과 같은 절단 규칙(전체 길이 n, 말줄임표 포함).
  function truncate(str, n) {
    if (!str) {
      return "";
    }
    if (str.length <= n) {
      return str;
    }
    return str.slice(0, n - 1) + "…";
  }

  function setFieldText(root, field, value) {
    var el = root.querySelector('[data-field="' + field + '"]');
    if (el) {
      el.textContent = String(value);
    }
  }

  // ── 러너 배지·진행 행 ────────────────────────────────────────────

  function updateRunnerBadge(runner) {
    var badge = document.getElementById("dash-runner-badge");
    var badgeText = document.getElementById("dash-runner-badge-text");
    var submitBtn = document.getElementById("dash-discovery-submit");
    var hint = document.getElementById("dash-discovery-offline-hint");
    var queryInput = document.getElementById("dash-discovery-query");
    if (!badge || !badgeText || !submitBtn || !hint || !queryInput) {
      return;
    }

    // BIR-12: 오프라인으로 바뀌어 버튼이 비활성화되는 순간 포커스가
    // 거기 있었다면 검색어 입력으로 옮긴다(비활성 버튼은 포커스를 못 받는다).
    var wasFocusedOnSubmit = document.activeElement === submitBtn;

    if (runner.online) {
      badge.classList.remove("dash-status-badge--disabled");
      badge.classList.add("dash-status-badge--ok");
      badgeText.textContent = "러너 온라인";
      submitBtn.disabled = false;
      submitBtn.classList.add("dash-cta-accent");
      submitBtn.removeAttribute("aria-describedby");
      hint.hidden = true;
      queryInput.removeAttribute("aria-describedby");
    } else {
      badge.classList.remove("dash-status-badge--ok");
      badge.classList.add("dash-status-badge--disabled");
      badgeText.textContent = "러너 오프라인";
      submitBtn.disabled = true;
      submitBtn.classList.remove("dash-cta-accent");
      submitBtn.setAttribute("aria-describedby", "dash-discovery-offline-hint");
      hint.hidden = false;
      queryInput.setAttribute("aria-describedby", "dash-discovery-offline-hint");
      if (wasFocusedOnSubmit) {
        queryInput.focus();
      }
    }
  }

  function updateRunnerMeta(runner, serverTime) {
    var metaEl = document.getElementById("dash-runner-meta");
    if (!metaEl) {
      return;
    }
    if (runner.online) {
      metaEl.textContent = "heartbeat " + formatElapsedKorean(serverTime, runner.last_heartbeat_at) + " 전";
    } else if (runner.last_heartbeat_at) {
      metaEl.textContent = "마지막 heartbeat " + formatElapsedKorean(serverTime, runner.last_heartbeat_at) + " 전";
    } else {
      metaEl.textContent = "heartbeat 없음";
    }
  }

  // BIR-9~11: aria-live polite는 이 행 하나뿐이고, phase나 detail이
  // 실제로 바뀔 때만 텍스트를 대입해 같은 문구가 반복 낭독되지 않게 한다.
  function updateProgressRow(runner) {
    var row = document.getElementById("dash-discovery-progress");
    var textEl = document.getElementById("dash-discovery-progress-text");
    if (!row || !textEl) {
      return;
    }
    row.hidden = !runner.progress_visible;
    var detail = runner.detail || "";
    if (runner.phase !== lastPhase || detail !== lastDetail) {
      textEl.textContent = detail;
      textEl.setAttribute("title", detail);
      lastPhase = runner.phase;
      lastDetail = detail;
    }
  }

  // ── 실행 표 ──────────────────────────────────────────────────────

  function buildRunRow(run, expandedIds) {
    var frag = rowTemplate.content.cloneNode(true);
    var mainRow = frag.querySelector("tr[data-run-id]");
    var outcomeRow = frag.querySelector('[data-field="outcome-row"]');
    mainRow.dataset.runId = String(run.id);

    setFieldText(mainRow, "created_at", formatDateTime(run.created_at));
    var queryEl = mainRow.querySelector('[data-field="query"]');
    queryEl.textContent = run.query || "-";
    queryEl.setAttribute("title", run.query || "-");

    var statusBadge = mainRow.querySelector('[data-field="status-badge"]');
    statusBadge.className = "dash-status-badge dash-status-badge--" + run.tone;
    statusBadge.textContent = run.status_label;

    var errorEl = mainRow.querySelector('[data-field="error-summary"]');
    if (run.error_summary) {
      errorEl.hidden = false;
      errorEl.textContent = truncate(run.error_summary, 60);
    } else {
      errorEl.hidden = true;
      errorEl.textContent = "";
    }

    setFieldText(mainRow, "promoted_count", run.promoted_count);
    setFieldText(mainRow, "failed_count", run.failed_count);
    setFieldText(mainRow, "events_created", run.events_created);
    setFieldText(mainRow, "events_excluded", run.events_excluded === null || run.events_excluded === undefined ? "-" : run.events_excluded);
    setFieldText(mainRow, "events_failed", run.events_failed === null || run.events_failed === undefined ? "-" : run.events_failed);

    var toggleBtn = mainRow.querySelector('[data-field="outcome-toggle"]');
    var emptySpan = mainRow.querySelector('[data-field="outcome-empty"]');
    var outcomeRowId = "dash-outcome-" + run.id;
    outcomeRow.id = outcomeRowId;

    if (run.outcomes && run.outcomes.length > 0) {
      toggleBtn.hidden = false;
      emptySpan.hidden = true;
      toggleBtn.setAttribute("aria-controls", outcomeRowId);
      toggleBtn.setAttribute(
        "aria-label",
        formatDateTime(run.created_at) + (run.query ? " " + run.query : "") + " 실행 결과 상세"
      );
      // BIR-7: 이전에 펼쳐져 있던 실행이면 갱신 후에도 펼침 상태를 유지한다.
      var expanded = expandedIds.indexOf(String(run.id)) !== -1;
      toggleBtn.dataset.expanded = String(expanded);
      toggleBtn.setAttribute("aria-expanded", String(expanded));
      outcomeRow.hidden = !expanded;

      var list = outcomeRow.querySelector('[data-field="outcome-list"]');
      run.outcomes.forEach(function (outcome) {
        var item = outcomeTemplate.content.cloneNode(true);
        item.querySelector('[data-field="display_url"]').textContent = outcome.display_url;
        var badge = item.querySelector('[data-field="outcome-badge"]');
        badge.className = "dash-status-badge dash-status-badge--" + outcome.tone;
        badge.textContent = outcome.outcome_label;
        var reasonEl = item.querySelector('[data-field="reason_label"]');
        if (outcome.reason_label) {
          reasonEl.hidden = false;
          reasonEl.textContent = outcome.reason_label;
        } else {
          reasonEl.hidden = true;
        }
        list.appendChild(item);
      });
    } else {
      toggleBtn.hidden = true;
      emptySpan.hidden = false;
      outcomeRow.hidden = true;
    }

    return frag;
  }

  function updateRunsTable(runs) {
    var tableWrap = document.getElementById("dash-runs-table");
    var emptyEl = document.getElementById("dash-runs-empty");
    var tbody = document.getElementById("dash-runs-body");
    if (!tableWrap || !emptyEl || !tbody) {
      return;
    }

    if (!runs || runs.length === 0) {
      tableWrap.hidden = true;
      emptyEl.hidden = false;
      tbody.replaceChildren();
      return;
    }
    tableWrap.hidden = false;
    emptyEl.hidden = true;

    // BIR-6·7: 교체 전에 포커스·펼침 상태를 기억해뒀다 교체 후 되돌린다.
    var focusedRunId = null;
    var active = document.activeElement;
    if (active && tbody.contains(active) && active.classList.contains("dash-outcome-toggle")) {
      var activeRow = active.closest("tr[data-run-id]");
      if (activeRow) {
        focusedRunId = activeRow.dataset.runId;
      }
    }
    var expandedIds = [];
    tbody.querySelectorAll('.dash-outcome-toggle[aria-expanded="true"]').forEach(function (btn) {
      var tr = btn.closest("tr[data-run-id]");
      if (tr) {
        expandedIds.push(tr.dataset.runId);
      }
    });

    var fragment = document.createDocumentFragment();
    runs.forEach(function (run) {
      fragment.appendChild(buildRunRow(run, expandedIds));
    });
    tbody.replaceChildren(fragment);

    if (focusedRunId) {
      var restored = tbody.querySelector('tr[data-run-id="' + focusedRunId + '"] .dash-outcome-toggle');
      if (restored) {
        restored.focus();
      }
    }
  }

  // ── 응답 적용 ────────────────────────────────────────────────────

  function computeInterval(data) {
    // BIR-2: 러너 온라인이거나 대기·진행 중 실행이 있으면 5초, 아니면 20초.
    return data.runner.online || data.runner.active ? SHORT_DELAY_MS : LONG_DELAY_MS;
  }

  function applyPayload(data) {
    // BIR-13: server_time을 뺀 나머지가 직전과 같으면 DOM을 건드리지 않는다.
    var compareKey = JSON.stringify({ runner: data.runner, runs: data.runs });
    if (compareKey === lastCompareKey) {
      return;
    }
    lastCompareKey = compareKey;

    updateRunnerBadge(data.runner);
    updateRunnerMeta(data.runner, data.server_time);
    updateProgressRow(data.runner);
    updateRunsTable(data.runs);
  }

  function showAuthExpired() {
    var metaEl = document.getElementById("dash-runner-meta");
    if (metaEl) {
      metaEl.textContent = "세션이 만료되었습니다 — 새로고침 후 다시 로그인";
    }
  }

  // ── 폴링 루프 ────────────────────────────────────────────────────

  function stopPolling() {
    stopped = true;
    clearTimeout(timerId);
  }

  function scheduleNext(delay) {
    clearTimeout(timerId);
    if (stopped || document.hidden) {
      // BIR-1: 숨김 상태에서는 타이머를 세우지 않는다 — visibilitychange가 재개를 맡는다.
      return;
    }
    timerId = setTimeout(poll, delay);
  }

  async function poll() {
    if (stopped || document.hidden) {
      return;
    }
    if (inFlight) {
      // BIR-15: 이미 요청 중이면 새 요청을 내지 않는다.
      return;
    }
    inFlight = true;
    var result = await window.TakuAPI.get(liveUrl);
    inFlight = false;
    if (stopped) {
      return;
    }

    if (!result.ok) {
      if (window.TakuAPI.classify(result) === "auth") {
        // BIR-4: 세션 만료면 폴링을 완전히 멈춘다.
        stopPolling();
        showAuthExpired();
        return;
      }
      // BIR-3: 오류마다 간격을 배증하고 60초에서 멈춘다.
      currentDelay = Math.min(currentDelay * 2, MAX_DELAY_MS);
      scheduleNext(currentDelay);
      return;
    }

    applyPayload(result.data);
    currentDelay = computeInterval(result.data);
    scheduleNext(currentDelay);
  }

  // ── 초기화 ───────────────────────────────────────────────────────

  function handleVisibilityChange() {
    if (stopped) {
      return;
    }
    clearTimeout(timerId);
    if (!document.hidden) {
      // BIR-1: 탭이 다시 보이면 즉시 1회 재검증한다.
      poll();
    }
  }

  function handlePageShow(event) {
    if (!event.persisted || stopped) {
      return;
    }
    // BIR-5: bfcache 복원 시 화면이 낡았을 수 있어 즉시 재검증한다.
    poll();
  }

  function init() {
    panel = document.getElementById("dash-discovery-panel");
    if (!panel) {
      return;
    }
    liveUrl = panel.dataset.liveUrl;
    if (!liveUrl) {
      return;
    }
    rowTemplate = document.getElementById("dash-run-row-template");
    outcomeTemplate = document.getElementById("dash-run-outcome-template");
    if (!rowTemplate || !outcomeTemplate) {
      return;
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("pageshow", handlePageShow);
    poll();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
