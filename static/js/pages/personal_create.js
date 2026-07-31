/**
 * 비공식 장소 등록 페이지. 종류 빠른 선택 칩, 이미지 미리보기, 폼 제출을 담당한다.
 */

(function () {
  "use strict";

  var LIST_URL = "/archive/personal/";
  var MAX_BYTES = 5 * 1024 * 1024;
  var ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

  function setText(el, message) {
    if (el) { el.textContent = message; }
  }

  function handle403(result, errorEl) {
    if (window.TakuAPI.classify(result) === "auth") {
      window.TakuAPI.redirectToLogin();
    } else {
      setText(errorEl, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
    }
  }

  // 서버의 이미지 검증을 클라이언트에서도 미리 흉내내 빠른 피드백을 준다.
  function validateImageFile(file, errorEl) {
    if (ALLOWED_TYPES.indexOf(file.type) === -1) {
      setText(errorEl, "JPEG · PNG · WebP 형식만 첨부할 수 있습니다.");
      return false;
    }
    if (file.size > MAX_BYTES) {
      setText(errorEl, "이미지는 5MB 이하만 첨부할 수 있습니다.");
      return false;
    }
    return true;
  }

  // ── 종류 선택 칩 ──────────────────────────────────────────────────────
  // 칩은 항상 #personal-category 자유 입력 필드에만 값을 쓴다. 칩을
  // 클릭했든 직접 입력했든 읽는 곳은 제출 핸들러의 category 읽기 하나뿐이다.
  function bindCategoryChips() {
    var group = document.querySelector(".personal-form-category-chips");
    if (!group || group.dataset.chipsBound) { return; }
    group.dataset.chipsBound = "1";

    var form = group.closest("form");
    if (!form) { return; }
    var input = form.elements["category"];
    if (!input) { return; }
    var chips = group.querySelectorAll(".personal-form-category-chip");

    function syncFromValue() {
      var value = input.value;
      for (var i = 0; i < chips.length; i++) {
        var isMatch = chips[i].dataset.categoryLabel === value;
        chips[i].classList.toggle("is-active", isMatch);
        chips[i].setAttribute("aria-pressed", isMatch ? "true" : "false");
      }
    }

    for (var i = 0; i < chips.length; i++) {
      chips[i].addEventListener("click", function () {
        input.value = this.dataset.categoryLabel;
        syncFromValue();
      });
    }
    input.addEventListener("input", syncFromValue);

    // 입력값이 이미 채워져 있으면(검증 오류 후 재렌더링 등) 한 번 동기화한다.
    syncFromValue();
  }

  // ── 이미지 드롭존 미리보기 ──────────────────────────────────────────────

  function bindImagePreview() {
    var input = document.getElementById("personal-image");
    if (!input || input.dataset.previewBound) { return; }
    input.dataset.previewBound = "1";

    var dropzone = input.closest(".personal-form-dropzone");
    if (!dropzone) { return; }
    var placeholder = dropzone.querySelector(".personal-form-dropzone-placeholder");
    var currentUrl = null;

    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) { return; }

      var errorEl = document.getElementById("personal-create-error");
      if (!validateImageFile(file, errorEl)) { return; }
      setText(errorEl, "");

      if (currentUrl) { URL.revokeObjectURL(currentUrl); }
      currentUrl = URL.createObjectURL(file);

      var img = dropzone.querySelector("img");
      if (!img) {
        img = document.createElement("img");
        img.alt = "미리보기";
        dropzone.appendChild(img);
      }
      img.src = currentUrl;
      if (placeholder) { placeholder.hidden = true; }
    });
  }

  // ── 제출 ───────────────────────────────────────────────────────────────

  function bindCreateForm() {
    var form = document.getElementById("personal-create-form");
    if (!form) { return; }
    var errorEl = document.getElementById("personal-create-error");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      setText(errorEl, "");

      var title = form.elements["title"].value.trim();
      if (!title) {
        setText(errorEl, "이름을 입력해 주세요.");
        form.elements["title"].focus();
        return;
      }

      var imageInput = form.elements["image"];
      var imageFile = imageInput && imageInput.files && imageInput.files[0];
      if (imageFile && !validateImageFile(imageFile, errorEl)) {
        return;
      }

      var fields = {
        kind: form.elements["kind"].value,
        title: title,
        category: form.elements["category"].value.trim(),
        work_title: form.elements["work_title"].value.trim(),
        location_name: form.elements["location_name"].value.trim(),
        region: form.elements["region"].value.trim(),
        url: form.elements["url"].value.trim(),
        memo: form.elements["memo"].value.trim(),
      };

      // client_token은 서버가 발급한 숨김 필드(중복 제출 방지용)다. 값이
      // 있을 때만 보낸다 — 빈 문자열을 보내면 서버 UUIDField 검증에서
      // 400으로 거부되기 때문이다.
      var clientTokenEl = form.elements["client_token"];
      if (clientTokenEl && clientTokenEl.value) { fields.client_token = clientTokenEl.value; }

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
        window.TakuAPI.commitAndNavigate(submitBtn, LIST_URL);
        return;
      }

      window.TakuAPI.setLoading(submitBtn, false);

      if (result.status === 403) {
        handle403(result, errorEl);
        return;
      }
      if (result.status === 0) {
        setText(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }
      setText(errorEl, window.TakuAPI.formatError(result));
    });
  }

  function init() {
    bindCategoryChips();
    bindImagePreview();
    bindCreateForm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
