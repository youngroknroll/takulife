/**
 * personal_entries.js — "내 항목" (PersonalEntry) actions for TakuLog
 *
 * Handles:
 *   - Create personal entry via form#entry-create-form
 *   - Delete personal entry via [data-delete-entry-id]
 *
 * Relies on window.TakuAPI (api.js) for requests, 403 disambiguation and error
 * formatting. All DOM writes use textContent only.
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

  function bindCreateForm() {
    var form = document.getElementById("entry-create-form");
    if (!form) { return; }
    var errorEl = document.getElementById("entry-create-error");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      clearError(errorEl);

      var title = form.elements["title"].value.trim();
      if (!title) {
        setError(errorEl, "이름을 입력해 주세요.");
        return;
      }

      var payload = {
        kind: form.elements["kind"].value,
        title: title,
        category: form.elements["category"].value.trim(),
        work_title: form.elements["work_title"].value.trim(),
        location_name: form.elements["location_name"].value.trim(),
        url: form.elements["url"].value.trim(),
        memo: form.elements["memo"].value.trim(),
      };

      window.TakuAPI.setLoading(submitBtn, true);

      var result = await window.TakuAPI.post("/api/personal-entries/", payload);

      if (result.status === 201) {
        window.location.reload();
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

  function bindEntryDeletes() {
    var deleteBtns = document.querySelectorAll("[data-delete-entry-id]");
    var globalErrorEl = document.getElementById("entry-global-error");

    for (var i = 0; i < deleteBtns.length; i++) {
      (function (btn) {
        btn.addEventListener("click", async function () {
          var entryId = btn.getAttribute("data-delete-entry-id");
          clearError(globalErrorEl);
          window.TakuAPI.setLoading(btn, true);

          var result = await window.TakuAPI.del(
            "/api/personal-entries/" + entryId + "/"
          );

          if (result.status === 204) {
            window.location.reload();
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

  function init() {
    bindCreateForm();
    bindEntryDeletes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
