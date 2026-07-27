/**
 * visit_detail.js — Visit-record detail page (archive_visit_detail).
 *
 * Only responsibility: record delete.
 *   DELETE /api/visit-records/<id>/
 *
 * Mirrors visit_edit.js's deleteBtn handler (askConfirm/handle403 helpers
 * included) — see visit_edit.js:35-49,365-393.
 */

(function () {
  "use strict";

  var VISITS_URL = "/archive/visits/";

  function setText(el, message) {
    if (el) { el.textContent = message; }
  }

  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  function handle403(result, errorEl) {
    var kind = window.TakuAPI.classify(result);
    if (kind === "auth") {
      window.TakuAPI.redirectToLogin();
    } else {
      setText(errorEl, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
    }
  }

  function bindDelete() {
    var deleteBtn = document.querySelector("[data-delete-record-id]");
    if (!deleteBtn) { return; }

    var recordId = deleteBtn.getAttribute("data-delete-record-id");
    var globalErrorEl = document.getElementById("visit-global-error");

    deleteBtn.addEventListener("click", async function () {
      if (
        !(await askConfirm(
          "이 방문 기록을 삭제하시겠습니까? 메모와 사진도 함께 삭제되며 되돌릴 수 없습니다."
        ))
      ) {
        return;
      }
      setText(globalErrorEl, "");
      window.TakuAPI.setLoading(deleteBtn, true);

      var result = await window.TakuAPI.del("/api/visit-records/" + recordId + "/");
      if (result.status === 204) {
        window.TakuAPI.commitAndNavigate(deleteBtn, VISITS_URL);
        return;
      }

      window.TakuAPI.setLoading(deleteBtn, false);
      if (result.status === 403) {
        handle403(result, globalErrorEl);
      } else if (result.status === 0) {
        setText(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
      } else {
        setText(globalErrorEl, "기록 삭제 중 오류가 발생했습니다.");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindDelete);
  } else {
    bindDelete();
  }
})();
