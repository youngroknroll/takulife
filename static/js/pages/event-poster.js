/**
 * event-poster.js — Staff poster upload/delete for takulife event detail page
 *
 * Handles:
 *   - File input change → immediate URL.createObjectURL preview (prevents
 *     wrong-file upload by showing what will be uploaded before confirming)
 *   - Upload button → TakuAPI.upload to POST /api/events/<id>/poster/ with
 *     multipart FormData; 200 → reload; 400 → inline error; 403 → inline error
 *   - Delete button → confirm dialog → TakuAPI.del to DELETE
 *     /api/events/<id>/poster/; 204 → reload
 *
 * Relies on window.TakuAPI (api.js) for all requests.
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

  // Styled confirm modal (confirm-modal.js) with a native window.confirm
  // fallback if that script didn't load — same pattern as status.js/visit.js/
  // draft.js's askConfirm.
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
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

    // Re-selecting a file (or clearing the input) after an earlier preview
    // used to leak the previous blob URL — nothing ever revoked it, unlike
    // the same pattern in visit_create.js/visit_edit.js.
    var currentObjectUrl = null;

    fileInput.addEventListener("change", function () {
      if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
        currentObjectUrl = null;
      }
      if (!fileInput.files || fileInput.files.length === 0) {
        previewImg.style.display = "none";
        previewImg.src = "";
        return;
      }
      currentObjectUrl = URL.createObjectURL(fileInput.files[0]);
      previewImg.src = currentObjectUrl;
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
        setError(errorEl, "이벤트 정보를 찾을 수 없습니다.");
        return;
      }

      var formData = new FormData();
      formData.append("image", fileInput.files[0]);

      window.TakuAPI.setLoading(uploadBtn, true);

      var result = await window.TakuAPI.upload(
        "/api/events/" + eventId + "/poster/",
        formData
      );

      if (result.status === 200) {
        // Reload-equivalent: destination is the current URL (WED §5-2
        // boundary ③ — same fidelity as the reload it replaces).
        window.TakuAPI.commitAndNavigate(uploadBtn, window.location.href);
        return;
      }

      window.TakuAPI.setLoading(uploadBtn, false);

      if (result.status === 400) {
        setError(errorEl, window.TakuAPI.formatError(result));
        return;
      }

      if (result.status === 403) {
        setError(errorEl, "접근 권한이 없습니다. 스태프 계정으로 로그인해 주세요.");
        return;
      }

      if (result.status === 404) {
        setError(errorEl, "해당 이벤트를 찾을 수 없습니다.");
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

      var confirmed = await askConfirm("포스터를 삭제하시겠습니까?");
      if (!confirmed) { return; }

      var eventId = deleteBtn.getAttribute("data-event-id");
      if (!eventId) {
        setError(errorEl, "이벤트 정보를 찾을 수 없습니다.");
        return;
      }

      window.TakuAPI.setLoading(deleteBtn, true);

      var result = await window.TakuAPI.del(
        "/api/events/" + eventId + "/poster/"
      );

      if (result.status === 204) {
        // Reload-equivalent: destination is the current URL (WED §5-2
        // boundary ③ — same fidelity as the reload it replaces).
        window.TakuAPI.commitAndNavigate(deleteBtn, window.location.href);
        return;
      }

      window.TakuAPI.setLoading(deleteBtn, false);

      if (result.status === 403) {
        setError(errorEl, "접근 권한이 없습니다. 스태프 계정으로 로그인해 주세요.");
        return;
      }

      if (result.status === 404) {
        setError(errorEl, "해당 이벤트를 찾을 수 없습니다.");
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
