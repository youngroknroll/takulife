/**
 * personal_entries.js — "내 항목" (PersonalEntry) actions for takulife
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

  // Confirm before a destructive, unrecoverable action. Uses the shared modal
  // (confirm-modal.js, loaded in base.html) with a native confirm() fallback.
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
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

      var fields = {
        kind: form.elements["kind"].value,
        title: title,
        category: form.elements["category"].value.trim(),
        work_title: form.elements["work_title"].value.trim(),
        location_name: form.elements["location_name"].value.trim(),
        url: form.elements["url"].value.trim(),
        memo: form.elements["memo"].value.trim(),
      };

      // Image attached → multipart request (matches visit_create.js's use of
      // TakuAPI.upload for binary payloads). No image → keep the plain JSON
      // path unchanged.
      var imageInput = form.elements["image"];
      var imageFile = imageInput && imageInput.files && imageInput.files[0];

      window.TakuAPI.setLoading(submitBtn, true);

      var result;
      if (imageFile) {
        var formData = new FormData();
        Object.keys(fields).forEach(function (key) {
          formData.append(key, fields[key]);
        });
        formData.append("image", imageFile);
        result = await window.TakuAPI.upload("/api/personal-entries/", formData);
      } else {
        result = await window.TakuAPI.post("/api/personal-entries/", fields);
      }

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

      // 상세 정보(접힘) 그룹 안의 url 필드가 원인이면 펼쳐서 보여준다.
      if (result.data && result.data.url) {
        var detailFields = document.getElementById("entry-detail-fields");
        if (detailFields) { detailFields.open = true; }
      }
    });
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

  // ── 공식 제보 (promote a private item into the review pipeline) ──

  function bindPromote() {
    // Reveal the per-card official-URL form on demand.
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
            window.location.reload();
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
    bindCreateForm();
    bindEntryDeletes();
    bindPromote();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Live search swaps the results fragment: re-wire the new cards' delete and
  // promote controls. The create form lives outside the swap region, so it is
  // left alone; the per-element guards keep this idempotent. (Status/interest
  // buttons in the swapped cards are re-wired by status.js's own listener.)
  document.addEventListener("archive:listswapped", function () {
    bindEntryDeletes();
    bindPromote();
  });
})();
