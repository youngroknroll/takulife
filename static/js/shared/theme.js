/**
 * 다크/라이트 테마 결정과 전환. 우선순위는 localStorage 저장값 →
 * 시스템 설정(prefers-color-scheme) → 라이트 순이다.
 * base.html의 인라인 스니펫이 첫 페인트 전에 같은 로직의 읽기 전용 버전을
 * 먼저 실행해 깜빡임을 막고, 이 파일은 저장·전환 API·시스템 설정 변경 감지까지
 * 맡는 완전판이라 다시 적용해도 결과가 같으면 아무 영향이 없다.
 * localStorage는 이 저장소에서 처음 쓰는 API라, 프라이빗 브라우징 등에서
 * 접근이 예외를 던질 수 있어 모든 호출을 try/catch로 감싼다.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "takulife-theme";
  var mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

  function readStoredTheme() {
    try {
      var value = window.localStorage.getItem(STORAGE_KEY);
      return value === "light" || value === "dark" ? value : null;
    } catch (e) {
      return null;
    }
  }

  function writeStoredTheme(theme) {
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
      // 저장이 막혀도 이번 페이지에는 테마가 적용된다. 새로고침 뒤에만 유지되지 않는다.
    }
  }

  function resolveTheme() {
    var stored = readStoredTheme();
    if (stored) {
      return stored;
    }
    return mediaQuery.matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
  }

  function toggle() {
    var current = document.documentElement.getAttribute("data-theme");
    var next = current === "dark" ? "light" : "dark";
    writeStoredTheme(next);
    applyTheme(next);
  }

  // 방문자가 아직 명시적으로 테마를 고르지 않은 동안에만 시스템 설정 변경을 계속 따라간다.
  mediaQuery.addEventListener("change", function () {
    if (!readStoredTheme()) {
      applyTheme(mediaQuery.matches ? "dark" : "light");
    }
  });

  applyTheme(resolveTheme());

  function bindToggleButtons() {
    var buttons = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", toggle);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindToggleButtons);
  } else {
    bindToggleButtons();
  }

  // bfcache 복원은 떠날 때의 테마를 그대로 얼려서 가져오므로, 그사이 다른 탭에서
  // 테마가 바뀌었다면 여기서 다시 적용해 최신 상태로 맞춘다.
  window.addEventListener("pageshow", function (evt) {
    if (!evt.persisted) {
      return;
    }
    applyTheme(resolveTheme());
  });

  window.TakuTheme = {
    toggle: toggle,
  };
})();
