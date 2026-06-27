/**
 * visit.js — Visit record actions for TakuLog
 *
 * Handles:
 *   - Create visit record via form#visit-create-form
 *   - Upload photo via per-card file input + upload button
 *   - Delete visit record via [data-delete-record-id]
 *   - Delete photo via [data-photo-id][data-record-id] on photo-delete-btn
 *
 * Relies on window.TakuAPI (api.js) for all requests:
 *   - JSON actions: TakuAPI.post / TakuAPI.del
 *   - Multipart photo upload: TakuAPI.upload (does NOT set Content-Type)
 *   - 403 disambiguation: TakuAPI.classify → 'auth' → TakuAPI.redirectToLogin()
 *   - Error messages: TakuAPI.formatError
 *
 * All DOM writes use textContent only (no innerHTML with API data).
 */

(function () {
  "use strict";

  // ── DOM helpers ──────────────────────────────────────────────────────────

  function setError(el, message) {
    if (!el) { return; }
    el.textContent = message;
  }

  function clearError(el) {
    if (!el) { return; }
    el.textContent = "";
  }

  // ── 403 handler ──────────────────────────────────────────────────────────

  function handle403(result, errorEl) {
    var kind = window.TakuAPI.classify(result);
    if (kind === "auth") {
      window.TakuAPI.redirectToLogin();
    } else {
      setError(errorEl, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
    }
  }

  // ── multipart photo upload ───────────────────────────────────────────────

  async function uploadPhoto(recordId, file, errorEl, btn) {
    var formData = new FormData();
    formData.append("image", file);

    window.TakuAPI.setLoading(btn, true);

    var result = await window.TakuAPI.upload(
      "/api/visit-records/" + recordId + "/photos/",
      formData
    );

    if (result.status === 201) {
      window.location.reload();
      return;
    }

    window.TakuAPI.setLoading(btn, false);

    if (result.status === 403) {
      handle403(result, errorEl);
      return;
    }

    if (result.status === 0) {
      setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
      return;
    }

    if (result.status === 400) {
      setError(errorEl, window.TakuAPI.formatError(result));
      return;
    }

    if (result.status === 404) {
      setError(errorEl, "해당 방문 기록을 찾을 수 없습니다.");
      return;
    }

    setError(errorEl, "업로드 중 오류가 발생했습니다. 다시 시도해 주세요.");
  }

  // ── create visit record ──────────────────────────────────────────────────

  function bindCreateForm() {
    var form = document.getElementById("visit-create-form");
    if (!form) { return; }
    var errorEl = document.getElementById("visit-create-error");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      clearError(errorEl);

      // subject value is "event:<id>" (official) or "personal:<id>" (unofficial)
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

  // ── photo upload buttons ─────────────────────────────────────────────────

  function bindPhotoUploads() {
    var uploadBtns = document.querySelectorAll("[data-upload-record-id]");
    for (var i = 0; i < uploadBtns.length; i++) {
      (function (btn) {
        btn.addEventListener("click", function () {
          var recordId = btn.getAttribute("data-upload-record-id");
          var fileInput = document.querySelector(
            "input[type='file'][data-record-id='" + recordId + "']"
          );
          var errorEl = document.querySelector(
            "[data-photo-error='" + recordId + "']"
          );
          clearError(errorEl);

          if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            setError(errorEl, "업로드할 파일을 선택해 주세요.");
            return;
          }

          uploadPhoto(recordId, fileInput.files[0], errorEl, btn);
        });
      })(uploadBtns[i]);
    }
  }

  // ── photo delete buttons ─────────────────────────────────────────────────

  function bindPhotoDeletes() {
    var deleteBtns = document.querySelectorAll(".photo-delete-btn");
    for (var i = 0; i < deleteBtns.length; i++) {
      (function (btn) {
        btn.addEventListener("click", async function () {
          var photoId = btn.getAttribute("data-photo-id");
          var recordId = btn.getAttribute("data-record-id");
          var errorEl = document.querySelector(
            "[data-photo-error='" + recordId + "']"
          );
          clearError(errorEl);
          window.TakuAPI.setLoading(btn, true);

          var result = await window.TakuAPI.del(
            "/api/visit-records/" + recordId + "/photos/" + photoId + "/"
          );

          if (result.status === 204) {
            window.location.reload();
            return;
          }

          window.TakuAPI.setLoading(btn, false);

          if (result.status === 403) {
            handle403(result, errorEl);
            return;
          }

          if (result.status === 404) {
            setError(errorEl, "사진을 찾을 수 없습니다.");
            return;
          }

          if (result.status === 0) {
            setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
            return;
          }

          setError(errorEl, "사진 삭제 중 오류가 발생했습니다.");
        });
      })(deleteBtns[i]);
    }
  }

  // ── record delete buttons ────────────────────────────────────────────────

  function bindRecordDeletes() {
    var deleteBtns = document.querySelectorAll("[data-delete-record-id]");
    var globalErrorEl = document.getElementById("visit-global-error");

    for (var i = 0; i < deleteBtns.length; i++) {
      (function (btn) {
        btn.addEventListener("click", async function () {
          var recordId = btn.getAttribute("data-delete-record-id");
          clearError(globalErrorEl);
          window.TakuAPI.setLoading(btn, true);

          var result = await window.TakuAPI.del(
            "/api/visit-records/" + recordId + "/"
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

  // ── init ─────────────────────────────────────────────────────────────────

  function init() {
    bindCreateForm();
    bindPhotoUploads();
    bindPhotoDeletes();
    bindRecordDeletes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
