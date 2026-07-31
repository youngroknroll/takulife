/**
 * 성공 알림을 잠깐 보여주는 토스트. window.TakuToast.show(message)로 호출한다.
 * textContent만 사용해 XSS 위험이 없고, 약 3.5초 뒤 자동으로 사라진다.
 * 페이지를 새로고침한 뒤에도 메시지를 이어 보여줘야 하는 화면(status.js의
 * data-reload-on-success)은 새로고침 전 sessionStorage에 메시지를 저장해두고,
 * 이 파일이 로드 시 그 값을 읽어 지운 뒤 보여준다.
 * 동작 최소화 설정에서는 CSS로 전환 효과만 생략하고 자동 소멸 타이머는 그대로 돈다.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "taku:toast";
  var DISMISS_MS = 3500;

  var toastEl = null;
  var hideTimer = null;

  function build() {
    toastEl = document.createElement("div");
    toastEl.className = "taku-toast";
    toastEl.setAttribute("role", "status");
    document.body.appendChild(toastEl);
  }

  function show(message) {
    if (hideTimer) {
      window.clearTimeout(hideTimer);
      hideTimer = null;
    }

    // 같은 메시지를 다시 보여줄 때도 스크린리더가 변화를 감지하도록 일단 비운다.
    toastEl.textContent = "";
    toastEl.classList.remove("is-visible");

    // 숨김 상태를 먼저 한 번 그리게 해야 CSS 전환 효과가 실제로 재생된다.
    requestAnimationFrame(function () {
      toastEl.textContent = message;
      toastEl.classList.add("is-visible");
    });

    hideTimer = window.setTimeout(function () {
      toastEl.classList.remove("is-visible");
      hideTimer = null;
    }, DISMISS_MS);
  }

  window.TakuToast = { show: show };

  function initReloadBridge() {
    var pending;
    try {
      pending = window.sessionStorage.getItem(STORAGE_KEY);
      if (!pending) {
        return;
      }
      // 보여주기 전에 지워야 토스트가 떠 있는 중이나 다음 방문에서 같은 메시지가 다시 뜨지 않는다.
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      // 스토리지를 쓸 수 없으면 조용히 건너뛴다.
      return;
    }
    show(pending);
  }

  build();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReloadBridge);
  } else {
    initReloadBridge();
  }
})();
