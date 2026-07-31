/**
 * 이벤트 상세 페이지의 스태프용 포스터 업로드·삭제.
 * 파일 선택 즉시 미리보기를 보여줘 잘못된 파일을 올리는 실수를 막는다.
 * 화면 갱신은 항상 textContent만 사용해 API 응답으로 HTML을 만들지 않는다.
 */

(function () {
  "use strict";

  // ── DOM 헬퍼 ─────────────────────────────────────────────────────────

  function setError(el, message) {
    if (!el) { return; }
    el.textContent = message;
  }

  function clearError(el) {
    if (!el) { return; }
    el.textContent = "";
  }

  // 공용 모달이 로드되지 않았으면 기본 confirm으로 대체한다.
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  // ── 파일 선택 트리거(숨긴 input + "+" 버튼) ─────────

  function bindTrigger(triggerBtn, fileInput) {
    if (!triggerBtn || !fileInput) { return; }

    triggerBtn.addEventListener("click", function () {
      fileInput.click();
    });
  }

  // ── 미리보기 ──────────────────────────────────────────────────────────────

  function bindFilePreview(fileInput, previewImg) {
    if (!fileInput || !previewImg) { return; }

    // 이전 미리보기의 blob URL을 해제하지 않으면 다시 선택할 때마다 메모리가 샌다.
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

  // ── 업로드 ────────────────────────────────────────────────────────────────

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
        // 새로고침과 같은 효과를 내도록 현재 URL로 다시 이동한다.
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

  // ── 삭제 ────────────────────────────────────────────────────────────────

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
        // 새로고침과 같은 효과를 내도록 현재 URL로 다시 이동한다.
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

  // ── 초기화 ──────────────────────────────────────────────────────────────────

  function init() {
    var fileInput = document.getElementById("poster-file-input");
    var triggerBtn = document.getElementById("poster-file-trigger");
    var previewImg = document.getElementById("poster-preview");
    var uploadBtn = document.getElementById("poster-upload-btn");
    var deleteBtn = document.getElementById("poster-delete-btn");
    var errorEl = document.getElementById("poster-error");

    if (!fileInput && !uploadBtn && !deleteBtn) {
      // 스태프용 블록이 없으면(비스태프 사용자 또는 다른 페이지) 아무 것도 하지 않는다
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
