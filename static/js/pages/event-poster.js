/**
 * event-poster.js — Staff poster upload/delete for oshilife event detail page
 *
 * Handles:
 *   - File input change → immediate URL.createObjectURL preview (prevents
 *     wrong-file upload by showing what will be uploaded before confirming)
 *   - Upload button → OshiAPI.upload to POST /api/events/<id>/poster/ with
 *     multipart FormData; 200 → reload; 400 → inline error; 403 → inline error
 *   - Delete button → confirm dialog → OshiAPI.del to DELETE
 *     /api/events/<id>/poster/; 204 → reload
 *
 * Relies on window.OshiAPI (api.js) for all requests.
 * All DOM writes use textContent only (no innerHTML with API data).
 */

(function () {
  "use strict";

  // ── DOM helpers ─────────────────────────────────────────────────────────

  function setError(el, message) {
    if (!el) { return; }
    el.textContent = message;
  }

  function clearError(el) {
    if (!el) { return; }
    el.textContent = "";
  }

  // ── file-select trigger (visually-hidden input + "+" tile button) ─────────

  function bindTrigger(triggerBtn, fileInput) {
    if (!triggerBtn || !fileInput) { return; }

    triggerBtn.addEventListener("click", function () {
      fileInput.click();
    });
  }

  // ── preview ──────────────────────────────────────────────────────────────

  function bindFilePreview(fileInput, previewImg) {
    if (!fileInput || !previewImg) { return; }

    fileInput.addEventListener("change", function () {
      if (!fileInput.files || fileInput.files.length === 0) {
        previewImg.style.display = "none";
        previewImg.src = "";
        return;
      }
      var objectUrl = URL.createObjectURL(fileInput.files[0]);
      previewImg.src = objectUrl;
      previewImg.style.display = "block";
    });
  }

  // ── upload ────────────────────────────────────────────────────────────────

  function bindUpload(uploadBtn, fileInput, errorEl) {
    if (!uploadBtn || !fileInput) { return; }

    uploadBtn.addEventListener("click", async function () {
      clearError(errorEl);

      if (!fileInput.files || fileInput.files.length === 0) {
        setError(errorEl, "업로드할 파일을 선택해 주세요.");
        return;
      }

      var eventId = uploadBtn.getAttribute("data-event-id");
      if (!eventId) {
        setError(errorEl, "행사 정보를 찾을 수 없습니다.");
        return;
      }

      var formData = new FormData();
      formData.append("image", fileInput.files[0]);

      window.OshiAPI.setLoading(uploadBtn, true);

      var result = await window.OshiAPI.upload(
        "/api/events/" + eventId + "/poster/",
        formData
      );

      if (result.status === 200) {
        window.location.reload();
        return;
      }

      window.OshiAPI.setLoading(uploadBtn, false);

      if (result.status === 400) {
        setError(errorEl, window.OshiAPI.formatError(result));
        return;
      }

      if (result.status === 403) {
        setError(errorEl, "접근 권한이 없습니다. 스태프 계정으로 로그인해 주세요.");
        return;
      }

      if (result.status === 404) {
        setError(errorEl, "해당 행사를 찾을 수 없습니다.");
        return;
      }

      if (result.status === 0) {
        setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }

      setError(errorEl, "업로드 중 오류가 발생했습니다. 다시 시도해 주세요.");
    });
  }

  // ── delete ────────────────────────────────────────────────────────────────

  function bindDelete(deleteBtn, errorEl) {
    if (!deleteBtn) { return; }

    deleteBtn.addEventListener("click", async function () {
      clearError(errorEl);

      var confirmed = window.confirm("포스터를 삭제하시겠습니까?");
      if (!confirmed) { return; }

      var eventId = deleteBtn.getAttribute("data-event-id");
      if (!eventId) {
        setError(errorEl, "행사 정보를 찾을 수 없습니다.");
        return;
      }

      window.OshiAPI.setLoading(deleteBtn, true);

      var result = await window.OshiAPI.del(
        "/api/events/" + eventId + "/poster/"
      );

      if (result.status === 204) {
        window.location.reload();
        return;
      }

      window.OshiAPI.setLoading(deleteBtn, false);

      if (result.status === 403) {
        setError(errorEl, "접근 권한이 없습니다. 스태프 계정으로 로그인해 주세요.");
        return;
      }

      if (result.status === 404) {
        setError(errorEl, "해당 행사를 찾을 수 없습니다.");
        return;
      }

      if (result.status === 0) {
        setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }

      setError(errorEl, "포스터 삭제 중 오류가 발생했습니다. 다시 시도해 주세요.");
    });
  }

  // ── init ──────────────────────────────────────────────────────────────────

  function init() {
    var fileInput = document.getElementById("poster-file-input");
    var triggerBtn = document.getElementById("poster-file-trigger");
    var previewImg = document.getElementById("poster-preview");
    var uploadBtn = document.getElementById("poster-upload-btn");
    var deleteBtn = document.getElementById("poster-delete-btn");
    var errorEl = document.getElementById("poster-error");

    if (!fileInput && !uploadBtn && !deleteBtn) {
      // Staff block not present (non-staff user or not event detail page)
      return;
    }

    bindTrigger(triggerBtn, fileInput);
    bindFilePreview(fileInput, previewImg);
    bindUpload(uploadBtn, fileInput, errorEl);
    bindDelete(deleteBtn, errorEl);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
