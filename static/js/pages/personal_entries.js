/**
 * "직접 등록" 목록 페이지의 동작. 항목 삭제와 공식 검토 제보 처리를 담당한다.
 * 등록(작성)은 별도 페이지(personal_create.js)가 맡아 이 파일은 다루지 않는다.
 * 화면 갱신은 항상 textContent만 사용한다.
 */

(function () {
  "use strict";

  function setError(el, message) {
    if (!el) { return; }
    el.textContent = message;
  }

  function clearError(el) {
    if (!el) { return; }
    el.textContent = "";
  }

  function handle403(result, errorEl) {
    if (window.TakuAPI.classify(result) === "auth") {
      window.TakuAPI.redirectToLogin();
    } else {
      setError(errorEl, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
    }
  }

  // 되돌릴 수 없는 동작이라 확인을 거친다. 공용 모달이 없으면 기본 confirm으로 대체한다.
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  function bindEntryDeletes() {
    var deleteBtns = document.querySelectorAll("[data-delete-entry-id]");
    var globalErrorEl = document.getElementById("entry-global-error");

    for (var i = 0; i < deleteBtns.length; i++) {
      (function (btn) {
        if (btn.dataset.deleteBound) { return; }
        btn.dataset.deleteBound = "1";
        btn.addEventListener("click", async function () {
          var entryId = btn.getAttribute("data-delete-entry-id");
          if (
            !(await askConfirm(
              "이 항목을 삭제하시겠습니까? 연결된 찜·상태·방문 기록도 함께 삭제됩니다."
            ))
          ) {
            return;
          }
          clearError(globalErrorEl);
          window.TakuAPI.setLoading(btn, true);

          var result = await window.TakuAPI.del(
            "/api/personal-entries/" + entryId + "/"
          );

          if (result.status === 204) {
            // 새로고침과 같은 효과를 내도록 현재 URL로 다시 이동한다.
            window.TakuAPI.commitAndNavigate(btn, window.location.href);
            return;
          }

          window.TakuAPI.setLoading(btn, false);

          if (result.status === 403) {
            handle403(result, globalErrorEl);
            return;
          }

          if (result.status === 404) {
            setError(globalErrorEl, "항목을 찾을 수 없습니다.");
            return;
          }

          if (result.status === 0) {
            setError(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
            return;
          }

          setError(globalErrorEl, "삭제 중 오류가 발생했습니다.");
        });
      })(deleteBtns[i]);
    }
  }

  // ── 공식 제보 ──

  function bindPromote() {
    // 버튼을 누르면 카드별 공식 URL 입력 폼을 펼친다.
    var toggles = document.querySelectorAll("[data-promote-toggle]");
    for (var t = 0; t < toggles.length; t++) {
      (function (btn) {
        if (btn.dataset.promoteBound) { return; }
        btn.dataset.promoteBound = "1";
        btn.addEventListener("click", function () {
          var id = btn.getAttribute("data-promote-toggle");
          var form = document.querySelector('[data-promote-form="' + id + '"]');
          if (!form) { return; }
          var nowHidden = !form.hidden;
          form.hidden = nowHidden;
          btn.setAttribute("data-expanded", String(!nowHidden));
          btn.setAttribute("aria-expanded", String(!nowHidden));
          if (!nowHidden) {
            var input = form.querySelector('input[name="official_url"]');
            if (input) { input.focus(); }
          }
        });
      })(toggles[t]);
    }

    var forms = document.querySelectorAll("[data-promote-form]");
    for (var f = 0; f < forms.length; f++) {
      (function (form) {
        if (form.dataset.promoteFormBound) { return; }
        form.dataset.promoteFormBound = "1";
        var id = form.getAttribute("data-promote-form");
        var errorEl = document.querySelector('[data-promote-error="' + id + '"]');
        var submitBtn = form.querySelector('[type="submit"]');

        form.addEventListener("submit", async function (evt) {
          evt.preventDefault();
          clearError(errorEl);

          var officialUrl = form.elements["official_url"].value.trim();
          if (!officialUrl) {
            setError(errorEl, "공식 URL을 입력해 주세요.");
            return;
          }

          window.TakuAPI.setLoading(submitBtn, true);

          var result = await window.TakuAPI.post(
            "/api/personal-entries/" + id + "/promote/",
            { official_url: officialUrl }
          );

          if (result.status === 201) {
            // 새로고침과 같은 효과를 내도록 현재 URL로 다시 이동한다.
            window.TakuAPI.commitAndNavigate(submitBtn, window.location.href);
            return;
          }

          window.TakuAPI.setLoading(submitBtn, false);

          if (result.status === 403) {
            handle403(result, errorEl);
            return;
          }

          if (result.status === 409) {
            setError(errorEl, "이미 공식 제보된 항목입니다.");
            return;
          }

          if (result.status === 0) {
            setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
            return;
          }

          setError(errorEl, window.TakuAPI.formatError(result));
        });
      })(forms[f]);
    }
  }

  function init() {
    bindEntryDeletes();
    bindPromote();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // 실시간 검색이 결과 목록을 통째로 교체하므로 새 카드의 삭제·제보 컨트롤을
  // 다시 연결한다. 요소별 가드가 있어 중복 연결돼도 문제없다.
  document.addEventListener("archive:listswapped", function () {
    bindEntryDeletes();
    bindPromote();
  });
})();
