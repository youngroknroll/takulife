/**
 * 방문 기록 목록 화면의 동작: 기록 삭제.
 * 사진 추가·삭제는 수정 페이지(visit_edit.js)가 맡고 이 카드들은 보기 전용이다.
 * 화면 갱신은 항상 textContent만 사용해 API 응답으로 HTML을 만들지 않는다.
 */

(function () {
  "use strict";

  // ── DOM 헬퍼 ──────────────────────────────────────────────────────────

  function setError(el, message) {
    if (!el) { return; }
    el.textContent = message;
  }

  function clearError(el) {
    if (!el) { return; }
    el.textContent = "";
  }

  // ── 403 처리 ──────────────────────────────────────────────────────────

  function handle403(result, errorEl) {
    var kind = window.TakuAPI.classify(result);
    if (kind === "auth") {
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

  // ── 방문 기록 등록 ──────────────────────────────────────────────────────

  function bindCreateForm() {
    var form = document.getElementById("visit-create-form");
    if (!form) { return; }
    var errorEl = document.getElementById("visit-create-error");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      clearError(errorEl);

      // subject 값은 "event:<id>"(공식) 또는 "personal:<id>"(비공식)
      var subjectValue = form.elements["subject"].value;
      var visitedOn = form.elements["visited_on"].value;
      var shortReview = form.elements["short_review"].value;

      if (!subjectValue || !visitedOn) {
        setError(errorEl, "대상과 방문 날짜를 모두 입력해 주세요.");
        return;
      }

      var sep = subjectValue.indexOf(":");
      var subjectType = subjectValue.slice(0, sep);
      var subjectId = parseInt(subjectValue.slice(sep + 1), 10);

      var payload = { visited_on: visitedOn, short_review: shortReview };
      if (subjectType === "personal") {
        payload.personal_entry = subjectId;
      } else {
        payload.event = subjectId;
      }

      window.TakuAPI.setLoading(submitBtn, true);

      var result = await window.TakuAPI.post("/api/visit-records/", payload);

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

      if (result.status === 0) {
        setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }

      setError(errorEl, window.TakuAPI.formatError(result));
    });
  }

  // ── 기록 삭제 버튼 ────────────────────────────────────────────────

  function bindRecordDeletes() {
    var deleteBtns = document.querySelectorAll("[data-delete-record-id]");
    var globalErrorEl = document.getElementById("visit-global-error");

    for (var i = 0; i < deleteBtns.length; i++) {
      (function (btn) {
        if (btn.dataset.deleteBound) { return; }
        btn.dataset.deleteBound = "1";
        btn.addEventListener("click", async function () {
          var recordId = btn.getAttribute("data-delete-record-id");
          if (
            !(await askConfirm(
              "이 방문 기록을 삭제하시겠습니까? 메모와 사진도 함께 삭제되며 되돌릴 수 없습니다."
            ))
          ) {
            return;
          }
          clearError(globalErrorEl);
          window.TakuAPI.setLoading(btn, true);

          var result = await window.TakuAPI.del(
            "/api/visit-records/" + recordId + "/"
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
            setError(globalErrorEl, "기록을 찾을 수 없습니다.");
            return;
          }

          if (result.status === 0) {
            setError(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
            return;
          }

          setError(globalErrorEl, "기록 삭제 중 오류가 발생했습니다.");
        });
      })(deleteBtns[i]);
    }
  }

  // ── 초기화 ─────────────────────────────────────────────────────────────────

  function init() {
    bindCreateForm();
    bindRecordDeletes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // 새 카드의 삭제 버튼을 다시 연결한다.
  document.addEventListener("archive:listswapped", function () {
    bindRecordDeletes();
  });
})();
