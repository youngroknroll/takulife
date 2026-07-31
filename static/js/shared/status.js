/**
 * 상태 버튼(찜/방문 예정/방문 완료/놓침)과 찜(관심) 토글 처리.
 * 탐색 화면의 버튼은 클릭할 때마다 등록/해제를 토글하고, 보관함 화면의
 * "변경" 버튼은 기존 상태를 그대로 다른 값으로 바꾼다.
 * 중복 등록(409)은 오류로 보여주지 않고 "이미 추가됨"으로 자연스럽게 맞춘다.
 * 화면 갱신은 항상 textContent/dataset/classList만 사용해 API 응답으로
 * HTML을 만들지 않는다. window.TakuAPI(api.js)가 먼저 로드돼 있어야 한다.
 */

(function () {
  "use strict";

  function removeRowIfOptedIn(button) {
    if (!button.hasAttribute("data-remove-on-cancel")) { return; }
    var row = button.closest("article");
    if (!row) { return; }
    var mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mql.matches) {
      row.remove();
      return;
    }
    row.style.transition = "opacity .15s";
    row.style.opacity = "0";
    var remove = function () { row.remove(); };
    row.addEventListener("transitionend", remove, { once: true });
    window.setTimeout(remove, 250);
  }

  // 공용 모달이 없으면 기본 confirm으로 대체한다. 메시지는 버튼별
  // data-confirm-message로 바꿀 수 있다.
  function askCancel(message) {
    var msg = message || "취소하시겠습니까?";
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(msg);
    }
    return Promise.resolve(window.confirm(msg));
  }

  var STATUS_LABELS = {
    interested: "찜",
    planned: "방문 예정",
    visited: "방문 완료",
    missed: "놓침",
  };

  // §6.4 성공 피드백 문구 — 정적 테이블, missed는 의도적으로 없음(토스트 없음).
  // 발화는 버튼의 data-toast opt-in이 있을 때만(아래 각 성공 분기 참고).
  var STATUS_TOAST_MESSAGES = {
    interested: "찜 목록에 저장했어요",
    planned: "나의 일정에 추가했어요",
    visited: "방문 완료로 변경했어요. 기록을 남길 수 있어요",
  };

  function showToast(message) {
    if (message && window.TakuToast) {
      window.TakuToast.show(message);
    }
  }

  function showInlineError(button, message) {
    var container = button.closest("[data-status-error-container]") || button.parentElement;
    var existing = container.querySelector(".status-inline-error");
    if (existing) {
      existing.textContent = message;
      existing.tabIndex = -1;
      existing.focus();
      return;
    }
    var msg = document.createElement("p");
    msg.className = "status-inline-error inline-error";
    msg.textContent = message;
    msg.tabIndex = -1;
    container.appendChild(msg);
    msg.focus();
  }

  // 새로 시도할 때마다 먼저 호출해, 이전 실패 메시지가 이번엔 성공한
  // 컨트롤 옆에 그대로 남아 있지 않게 한다.
  function clearInlineError(button) {
    var container = button.closest("[data-status-error-container]") || button.parentElement;
    var existing = container.querySelector(".status-inline-error");
    if (existing) {
      existing.remove();
    }
  }

  function setButtonActive(button, statusSlug) {
    // 버튼이 자기만의 표시 문구를 갖고 있으면 그것을 쓰고, 없으면 공통 어휘로 대체한다.
    var label = button.dataset.labelActive || STATUS_LABELS[statusSlug] || statusSlug;
    button.textContent = label;
    button.classList.add("active");
  }

  function setButtonDefault(button) {
    var slug = button.dataset.status;
    var label = button.dataset.label || STATUS_LABELS[slug] || slug;
    button.textContent = label;
    button.classList.remove("active");
  }

  function setButtonAlreadyAdded(button) {
    button.textContent = "이미 추가됨";
    button.classList.add("active");
    button.disabled = true;
  }

  function setButtonLoading(button, loading) {
    // 공용 헬퍼에 위임해 요청 중에는 버튼도 스피너와 함께 비활성화된다.
    window.TakuAPI.setLoading(button, loading);
  }

  async function handleClick(event) {
    var button = event.currentTarget;
    // 대상은 공식 이벤트 또는 비공식 직접 등록 항목 중 하나다. 새로 등록할
    // 때만 필요하고, 변경·취소는 기존 data-status-id로 처리한다.
    var eventId = button.dataset.eventId;
    var personalEntryId = button.dataset.personalEntryId;
    var statusSlug = button.dataset.status;
    var statusId = button.dataset.statusId;
    var action = button.dataset.statusAction;

    if (!statusSlug) {
      return;
    }

    // 로그인하지 않은 방문자는 상태를 저장할 수 없으니, 실패할 요청을
    // 보내는 대신 로그인·회원가입을 안내한다.
    if (!window.TakuAPI.isAuthenticated()) {
      window.TakuAPI.promptLogin();
      return;
    }

    var isActive = button.classList.contains("active");

    // 아래의 동시 클릭 잠금 처리와 공유하는 컨테이너
    var container = button.closest("[data-status-error-container]");

    // 탐색 카드에서는 관심/방문 예정 버튼이 한 줄에 있지만 이벤트는 상태를
    // 하나만 가질 수 있다. 현재 등록을 갖고 있는 형제 버튼을 찾아, 충돌 대신
    // 상태를 그쪽으로 옮기게 한다. (보관함 "변경" 버튼은 형제를 바꾸지 않는다.)
    var activeSibling = null;
    if (action !== "change" && container) {
      var siblings = container.querySelectorAll("button[data-status-action]");
      for (var i = 0; i < siblings.length; i++) {
        if (siblings[i] !== button && siblings[i].dataset.statusId) {
          activeSibling = siblings[i];
          break;
        }
      }
    }

    var willCancel = action !== "change" && statusId && (isActive || action === "unset");
    if (willCancel && !(await askCancel(button.dataset.confirmMessage))) {
      return;
    }

    setButtonLoading(button, true);
    clearInlineError(button);

    // 요청이 끝나기 전 같은 컨테이너의 다른 상태 버튼을 잠가, 연속 클릭이
    // 서로 경합해 하나가 조용히 409로 버려지는 일을 막는다.
    var lockedSiblings = [];
    var focusedSibling = null;
    if (container) {
      var statusButtons = container.querySelectorAll(".status-btn");
      for (var s = 0; s < statusButtons.length; s++) {
        if (statusButtons[s] !== button && !statusButtons[s].disabled) {
          if (document.activeElement === statusButtons[s]) { focusedSibling = statusButtons[s]; }
          statusButtons[s].disabled = true;
          // 서버가 렌더링 시점부터 비활성화한 게 아니라 이 잠금 때문이라는
          // 표시. api.js의 bfcache 복원 처리는 .is-loading만 풀어주므로
          // 이 잠금은 아래에서 별도로 풀어준다.
          statusButtons[s].classList.add("is-sibling-locked");
          lockedSiblings.push(statusButtons[s]);
        }
      }
    }

    function unlockSiblings() {
      lockedSiblings.forEach(function (sibling) {
        sibling.disabled = false;
        sibling.classList.remove("is-sibling-locked");
      });
      // 포커스가 있던 형제 버튼을 비활성화하면 포커스가 body로 밀려난다.
      // 다시 클릭 가능해졌으니 포커스를 되돌린다.
      if (focusedSibling && focusedSibling.isConnected && document.activeElement === document.body) {
        focusedSibling.focus();
      }
    }

    // 잠금은 이미 위에서 걸었으니, 아래 어떤 경로로 빠져나가든(예외 포함)
    // finally 하나로 형제 버튼이 영원히 잠긴 채 남지 않도록 한다.
    try {
      var result;
      var mode;

      if (action === "change" && statusId) {
        mode = "change";
        result = await window.TakuAPI.patch(
          "/api/user-event-statuses/" + statusId + "/",
          { status: statusSlug }
        );
      } else if (statusId && (isActive || action === "unset")) {
        mode = "cancel";
        result = await window.TakuAPI.del("/api/user-event-statuses/" + statusId + "/");
      } else if (activeSibling) {
        mode = "switch";
        result = await window.TakuAPI.patch(
          "/api/user-event-statuses/" + activeSibling.dataset.statusId + "/",
          { status: statusSlug }
        );
      } else {
        mode = "register";
        var payload = { status: statusSlug };
        if (personalEntryId) {
          payload.personal_entry = parseInt(personalEntryId, 10);
        } else if (eventId) {
          payload.event = parseInt(eventId, 10);
        } else {
          // 등록할 대상이 없으면 할 일이 없다.
          setButtonLoading(button, false);
          return;
        }
        result = await window.TakuAPI.post("/api/user-event-statuses/", payload);
      }

      setButtonLoading(button, false);

      var kind = window.TakuAPI.classify(result);

      if (kind === "auth") {
        // 페이지를 보던 중 세션이 만료됐을 수 있으니 조용히 리다이렉트하지 않고 재로그인을 안내한다
        window.TakuAPI.promptLogin();
        return;
      }

      if (kind === "network") {
        showInlineError(button, window.TakuAPI.formatError(result));
        return;
      }

      if (kind === "csrf") {
        showInlineError(button, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
        return;
      }

      if (kind === "conflict") {
        var code = result.data && result.data.code;
        if (code === "duplicate_user_event_status") {
          setButtonAlreadyAdded(button);
        }
        return;
      }

      // 새로고침을 택한 컨트롤은 서버가 뱃지·가능한 동작·요약 수치를
      // 처음부터 다시 계산하게 하는 편이 DOM을 조각조각 고치는 것보다 안전하다.
      if ((result.ok || result.status === 204) && button.hasAttribute("data-reload-on-success")) {
        if (button.hasAttribute("data-toast") && STATUS_TOAST_MESSAGES[statusSlug]) {
          // 새로고침이 현재 문서를 지우므로 메시지는 sessionStorage를 거쳐
          // toast.js가 읽는다. 저장이 막혀도 상태 변경 자체는 이미 서버에
          // 반영됐으니 새로고침은 반드시 진행한다.
          try {
            window.sessionStorage.setItem("taku:toast", STATUS_TOAST_MESSAGES[statusSlug]);
          } catch (e) {
            // 저장이 막혔으면 토스트 없이 진행한다.
          }
        }
        window.location.reload();
        return;
      }

      if (mode === "cancel" && (result.status === 204 || result.ok)) {
        delete button.dataset.statusId;
        setButtonDefault(button);
        removeRowIfOptedIn(button);
        return;
      }

      if (result.ok) {
        var responseData = result.data || {};
        // 전환은 등록 하나를 형제 버튼에서 이 버튼으로 옮기는 것이다.
        var fallbackId;
        if (mode === "switch" && activeSibling) {
          fallbackId = activeSibling.dataset.statusId;
          delete activeSibling.dataset.statusId;
          setButtonDefault(activeSibling);
        }
        // action을 비워둬야 이제 활성화된 이 버튼을 다시 클릭했을 때
        // 같은 상태를 재전송하지 않고 등록을 해제하게 된다.
        var newId = responseData.id ? String(responseData.id) : fallbackId;
        if (newId) {
          button.dataset.statusId = newId;
        }
        setButtonActive(button, statusSlug);
        return;
      }

      // 위 어디에도 해당하지 않으면(validation/notfound/server/unknown) 조용히
      // 실패하지 않고 오류를 보여준다. 페이지별 리스너(예: personal_detail.js의
      // 404 잠금)가 반응할 수 있도록 결과도 함께 브로드캐스트한다.
      // 순서 중요: showInlineError가 먼저 포커스를 잡아야, 뒤이은 dispatch의
      // 리스너가 그 오류 요소를 지우고 백링크로 포커스를 옮길 수 있다.
      showInlineError(button, window.TakuAPI.formatError(result));
      document.dispatchEvent(
        new CustomEvent("status:request-failed", { detail: { result: result } })
      );
    } finally {
      unlockSiblings();
    }
  }

  // ── 찜(♡/♥) 토글 — 상태 흐름과 완전히 독립적이다 ──

  function setInterestActive(button, interestId) {
    button.dataset.interestId = String(interestId);
    button.classList.add("active");
    button.setAttribute("aria-pressed", "true");
    var glyph = button.querySelector("[data-interest-glyph]");
    if (glyph) {
      glyph.textContent = "♥";
    }
  }

  function setInterestDefault(button) {
    delete button.dataset.interestId;
    button.classList.remove("active");
    button.setAttribute("aria-pressed", "false");
    var glyph = button.querySelector("[data-interest-glyph]");
    if (glyph) {
      glyph.textContent = "♡";
    }
  }

  async function handleInterestClick(event) {
    var button = event.currentTarget;
    // 대상은 공식 이벤트 또는 비공식 직접 등록 항목이다. 새로 찜할 때만
    // 필요하고, 찜 해제는 기존 data-interest-id로 처리한다.
    var eventId = button.dataset.eventId;
    var personalEntryId = button.dataset.personalEntryId;
    var interestId = button.dataset.interestId;

    if (!eventId && !personalEntryId && !interestId) {
      return;
    }

    if (!window.TakuAPI.isAuthenticated()) {
      window.TakuAPI.promptLogin();
      return;
    }

    if (interestId && !(await askCancel(button.dataset.confirmMessage))) {
      return;
    }

    window.TakuAPI.setLoading(button, true);
    clearInlineError(button);

    var result;
    if (interestId) {
      result = await window.TakuAPI.del("/api/event-interests/" + interestId + "/");
    } else {
      var payload = {};
      if (personalEntryId) {
        payload.personal_entry = parseInt(personalEntryId, 10);
      } else {
        payload.event = parseInt(eventId, 10);
      }
      result = await window.TakuAPI.post("/api/event-interests/", payload);
    }

    window.TakuAPI.setLoading(button, false);

    var kind = window.TakuAPI.classify(result);

    if (kind === "auth") {
      window.TakuAPI.promptLogin();
      return;
    }

    if (kind === "network") {
      showInlineError(button, window.TakuAPI.formatError(result));
      return;
    }

    if (kind === "csrf") {
      showInlineError(button, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
      return;
    }

    if (kind === "conflict") {
      var code = result.data && result.data.code;
      if (code === "duplicate_event_interest") {
        // 이미 찜한 상태 — id가 있으면 그것으로 활성 상태를 맞춘다
        var existingId = result.data && result.data.id;
        if (existingId) {
          setInterestActive(button, existingId);
        } else {
          button.classList.add("active");
          button.setAttribute("aria-pressed", "true");
          var glyph = button.querySelector("[data-interest-glyph]");
          if (glyph) {
            glyph.textContent = "♥";
          }
        }
      }
      return;
    }

    // 찜 목록 행은 실시간 검색이 교체하는 영역 안에 있어, 새로고침 없이
    // 취소를 처리하면 검색 교체와 겹칠 때 이미 삭제된 행이 다시 그려지는
    // 유령 행 문제가 생길 수 있다. 그래서 서버가 다시 계산하도록 새로고침한다.
    if ((result.ok || result.status === 204) && button.hasAttribute("data-reload-on-success")) {
      window.location.reload();
      return;
    }

    if (interestId && (result.status === 204 || result.ok)) {
      setInterestDefault(button);
      removeRowIfOptedIn(button);
      return;
    }

    if (result.ok) {
      var responseData = result.data || {};
      if (responseData.id) {
        setInterestActive(button, responseData.id);
        if (button.hasAttribute("data-toast")) {
          showToast(STATUS_TOAST_MESSAGES.interested);
        }
      }
      return;
    }

    // 위 어디에도 해당하지 않으면(validation/notfound/server/unknown) 조용히
    // 실패하지 않고 오류를 보여준다. 페이지별 리스너(예: personal_detail.js의
    // 404 잠금)가 반응할 수 있도록 결과도 함께 브로드캐스트한다.
    // 순서 중요: showInlineError가 먼저 포커스를 잡아야, 뒤이은 dispatch의
    // 리스너가 그 오류 요소를 지우고 백링크로 포커스를 옮길 수 있다.
    showInlineError(button, window.TakuAPI.formatError(result));
    document.dispatchEvent(
      new CustomEvent("status:request-failed", { detail: { result: result } })
    );
  }

  // 버튼마다 한 번만 연결한다(data-status-bound 가드). 실시간 검색으로
  // 목록이 교체된 뒤 다시 호출해도 새로 들어온 버튼만 연결된다.
  function initStatusButtons() {
    var buttons = document.querySelectorAll("button[data-status-action]");
    buttons.forEach(function (button) {
      if (button.dataset.statusBound) return;
      button.dataset.statusBound = "1";
      // 탐색 토글 버튼(action 없음)만 자신의 등록 상태를 활성 라벨로 반영한다.
      // 명시적 action(change/unset)이 있는 보관함 컨트롤은 원래 라벨을 유지한다.
      if (!button.dataset.statusAction) {
        if (button.dataset.statusId) {
          setButtonActive(button, button.dataset.status);
        }
      }
      button.addEventListener("click", handleClick);
    });

    var interestButtons = document.querySelectorAll("button[data-interest-toggle]");
    interestButtons.forEach(function (button) {
      if (button.dataset.interestBound) return;
      button.dataset.interestBound = "1";
      button.addEventListener("click", handleInterestClick);
    });
  }

  // 현재 상태 옆 선택지 목록을 펼치고 접는다. hidden 속성만 토글해 버튼이
  // DOM에 그대로 남아 있어야, 펼쳐진 뒤에도 handleClick의 형제 탐색이 정상 동작한다.
  function initStatusToggle() {
    var toggles = document.querySelectorAll("[data-status-toggle]");
    toggles.forEach(function (button) {
      if (button.dataset.statusToggleBound) return;
      button.dataset.statusToggleBound = "1";
      button.addEventListener("click", function () {
        var target = document.getElementById(button.getAttribute("data-controls"));
        if (!target) return;
        var willShow = target.hasAttribute("hidden");
        target.toggleAttribute("hidden", !willShow);
        button.setAttribute("data-expanded", String(willShow));
        button.setAttribute("aria-expanded", String(willShow));
      });
    });
  }

  function initPage() {
    initStatusButtons();
    initStatusToggle();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage);
  } else {
    initPage();
  }

  // 실시간 검색이 결과 목록을 교체한 뒤 새 상태/찜 버튼을 다시 연결한다.
  // 위의 가드 덕분에 반복 호출해도 안전하다.
  document.addEventListener("archive:listswapped", initStatusButtons);

  // 요청이 진행 중일 때 페이지를 떠나면 unlockSiblings가 실행될 기회를
  // 잃는다. bfcache 복원 시 .is-sibling-locked로 잠긴 버튼을 여기서 직접 풀어준다.
  window.addEventListener("pageshow", function (evt) {
    if (!evt.persisted) {
      return;
    }
    document.querySelectorAll(".is-sibling-locked").forEach(function (button) {
      button.disabled = false;
      button.classList.remove("is-sibling-locked");
    });
  });
})();
