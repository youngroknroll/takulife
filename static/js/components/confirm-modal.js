/**
 * 예/아니오 확인 모달. window.TakuConfirm(message)로 호출하며 예=true,
 * 아니오·ESC·바깥 클릭=false로 해결되는 Promise를 반환한다.
 * 처음 쓸 때 한 번만 만들어 재사용한다(싱글턴). 메시지는 textContent만
 * 써서 XSS 위험이 없다. 되돌릴 수 없는 동작의 확인이라 기본 포커스는
 * 더 안전한 "아니오"에 놓고, Tab은 두 버튼 사이에서만 순환한다.
 */

(function () {
  "use strict";

  // ── 싱글턴 참조 ────────────────────────────────────────────────────────

  var overlay = null;
  var dialog = null;
  var messageEl = null;
  var noBtn = null;
  var yesBtn = null;

  var currentResolve = null;
  var previousFocus = null;

  var closeTimer = null;
  var closeListener = null;

  function cancelPendingClose() {
    if (closeTimer !== null) { window.clearTimeout(closeTimer); closeTimer = null; }
    if (closeListener !== null) { overlay.removeEventListener("transitionend", closeListener); closeListener = null; }
  }

  function overlayTransitionMs() {
    var raw = window.getComputedStyle(overlay).transitionDuration || "0s";
    var max = 0;
    raw.split(",").forEach(function (part) {
      var value = parseFloat(part);
      if (isNaN(value)) { return; }
      var ms = part.indexOf("ms") !== -1 ? value : value * 1000;
      if (ms > max) { max = ms; }
    });
    return max;
  }

  // ── DOM 생성(첫 사용 시 한 번만) ──────────────────────────────────────────

  function buildDOM() {
    overlay = document.createElement("div");
    overlay.className = "confirm-overlay";
    overlay.setAttribute("hidden", "");

    dialog = document.createElement("div");
    dialog.className = "confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "confirm-message");

    messageEl = document.createElement("p");
    messageEl.className = "confirm-message";
    messageEl.id = "confirm-message";

    var actions = document.createElement("div");
    actions.className = "confirm-actions";

    noBtn = document.createElement("button");
    noBtn.type = "button";
    noBtn.className = "confirm-no";
    noBtn.textContent = "아니오";

    yesBtn = document.createElement("button");
    yesBtn.type = "button";
    yesBtn.className = "confirm-yes";
    yesBtn.textContent = "예";

    // 아니오가 왼쪽, 예가 오른쪽
    actions.appendChild(noBtn);
    actions.appendChild(yesBtn);

    dialog.appendChild(messageEl);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // ── 이벤트 바인딩 ─────────────────────────────────────────────────────

    yesBtn.addEventListener("click", function () {
      resolve(true);
    });

    noBtn.addEventListener("click", function () {
      resolve(false);
    });

    // 배경(오버레이 자체) 클릭일 때만 닫는다
    overlay.addEventListener("click", function (evt) {
      if (evt.target === overlay) {
        resolve(false);
      }
    });

    // ESC 키
    overlay.addEventListener("keydown", function (evt) {
      if (evt.key === "Escape") {
        evt.preventDefault();
        resolve(false);
      }

      // 포커스 가두기: Tab이 두 버튼 사이에서만 순환한다
      if (evt.key === "Tab") {
        var focused = document.activeElement;
        if (evt.shiftKey) {
          // Shift+Tab: 아니오에 있으면 예로 넘어간다
          if (focused === noBtn) {
            evt.preventDefault();
            yesBtn.focus();
          }
        } else {
          // Tab: 예에 있으면 아니오로 넘어간다
          if (focused === yesBtn) {
            evt.preventDefault();
            noBtn.focus();
          }
        }
      }
    });
  }

  // ── 열기 / 닫기 ──────────────────────────────────────────────────────────

  function open(message) {
    if (!overlay) {
      buildDOM();
    }

    messageEl.textContent = message;

    previousFocus = document.activeElement || document.body;

    cancelPendingClose();
    overlay.removeAttribute("hidden");
    document.documentElement.classList.add("confirm-scroll-lock");

    // 초기 상태를 먼저 한 번 그리게 해야 CSS 전환 효과가 실제로 재생된다
    requestAnimationFrame(function () {
      overlay.classList.add("is-open");
      noBtn.focus();
    });
  }

  function close() {
    // 어떤 닫힘 경로든(배경/ESC/예/아니오) 여기부터 시작해, 사라지는
    // 애니메이션을 기다리지 않고 스크롤 잠금을 바로 푼다.
    document.documentElement.classList.remove("confirm-scroll-lock");

    cancelPendingClose();
    overlay.classList.remove("is-open");

    // CSS 전환이 아예 안 일어날 수 있는 여러 경우(동작 최소화 설정,
    // 인쇄용 스타일, 백그라운드 탭의 rAF 지연 등)를 모두 대비해, 전환이
    // 끝나지 않아도 setTimeout으로 반드시 hidden을 복원한다.
    var duration = overlayTransitionMs();
    if (duration === 0) {
      overlay.setAttribute("hidden", "");
    } else {
      var finalize = function () {
        cancelPendingClose();
        overlay.setAttribute("hidden", "");
      };
      closeListener = function (evt) {
        if (evt.target === overlay) { finalize(); }
      };
      overlay.addEventListener("transitionend", closeListener);
      closeTimer = window.setTimeout(finalize, duration + 100);
    }

    if (previousFocus && typeof previousFocus.focus === "function") {
      previousFocus.focus();
    }
    previousFocus = null;
  }

  function resolve(value) {
    if (currentResolve === null) {
      return;
    }
    var fn = currentResolve;
    currentResolve = null;
    close();
    fn(value);
  }

  // ── 외부 공개 API ────────────────────────────────────────────────────────────

  function TakuConfirm(message) {
    // 이미 열려 있으면(정상적으로는 일어나지 않아야 함) 기존 것을 false로 닫고 새로 연다
    if (currentResolve !== null) {
      var oldResolve = currentResolve;
      currentResolve = null;
      oldResolve(false);
    }

    return new Promise(function (res) {
      currentResolve = res;
      open(message);
    });
  }

  window.TakuConfirm = TakuConfirm;
})();
