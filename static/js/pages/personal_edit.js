/**
 * 비공식 장소 수정 페이지. 종류 빠른 선택 칩, 이미지 교체 미리보기·즉시
 * 삭제, 폼 저장(PATCH), 항목 삭제를 담당한다.
 * 이미지 삭제는 확인 후 바로 반영되는 다른 삭제 동작들과 통일하기 위해
 * 본 폼 제출과 분리해 즉시 PATCH { image: null }로 처리한다.
 * 삭제로 항목이 사라지면(404) 이 페이지의 뒤로가기·취소 링크도 같은
 * 항목을 가리켜 함께 404가 나므로, 그 링크들을 무효화하고 새 "목록으로
 * 돌아가기" 링크를 추가한다(personal_detail.js처럼 기존 링크에 포커스만
 * 옮기는 방식은 여기선 쓸 수 없다).
 */

(function () {
  "use strict";

  var LIST_URL = "/archive/personal/";
  var MAX_BYTES = 5 * 1024 * 1024;
  var ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

  var goneLocked = false; // 목록 링크가 중복 추가되지 않도록 막는 가드

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

  // ── 404 잠금 캐스케이드 ──────────────────────────────────────────────

  function lockLink(link) {
    if (!link) { return; }
    link.removeAttribute("href");
    link.setAttribute("aria-disabled", "true");
    link.classList.add("is-item-gone-locked");
    link.addEventListener("click", function (evt) { evt.preventDefault(); });
  }

  // 폼의 모든 컨트롤을 비활성화해, 어떤 필드를 고쳐도 실패할 제출로 이어지지 않게 한다.
  function lockForm(form) {
    var controls = form.querySelectorAll("input, select, textarea, button");
    for (var i = 0; i < controls.length; i++) {
      controls[i].disabled = true;
      controls[i].classList.add("is-item-gone-locked");
    }
  }

  // 상단 뒤로가기·취소 링크도 같은 사라진 항목을 가리키므로, 살아 있는
  // 링크에 포커스만 옮기는 대신 새 링크를 만들어야 한다.
  function revealBackLink(form) {
    if (document.getElementById("personal-edit-back-to-list")) { return; }
    var link = document.createElement("a");
    link.id = "personal-edit-back-to-list";
    link.className = "record-cta";
    link.href = LIST_URL;
    link.textContent = "목록으로 돌아가기";
    form.appendChild(link);
    link.focus();
  }

  function lockPageForGoneEntry(form) {
    if (goneLocked) { return; }
    goneLocked = true;
    setText(document.getElementById("personal-edit-global-error"), "이미 삭제된 항목입니다.");
    lockLink(document.querySelector(".personal-form-back-link"));
    lockLink(document.querySelector(".personal-form-cancel"));
    lockForm(form);
    revealBackLink(form);
  }

  // ── 종류 선택 칩(personal_create.js와 동일 로직) ──

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

    // 서버가 미리 채워둔 값에 맞춰 한 번 동기화한다.
    syncFromValue();
  }

  // ── 이미지: 교체 미리보기 + 즉시 삭제 ──────────────────────

  function bindImage(form, entryId) {
    var input = document.getElementById("personal-image");
    var dropzone = input && input.closest(".personal-form-dropzone");
    var errorEl = document.getElementById("personal-edit-error");
    var removeBtn = document.querySelector("[data-remove-image]");
    var currentUrl = null;

    if (input && dropzone) {
      input.addEventListener("change", function () {
        var file = input.files && input.files[0];
        if (!file) { return; }
        if (!validateImageFile(file, errorEl)) {
          input.value = "";
          return;
        }
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
        var placeholder = dropzone.querySelector(".personal-form-dropzone-placeholder");
        if (placeholder) { placeholder.hidden = true; }
      });
    }

    if (!removeBtn) { return; }

    removeBtn.addEventListener("click", async function () {
      if (!(await askConfirm("이 사진을 삭제하시겠습니까? 되돌릴 수 없습니다."))) {
        return;
      }
      var globalErrorEl = document.getElementById("personal-edit-global-error");
      setText(globalErrorEl, "");
      // 이 페이지의 다른 삭제 동작과 마찬가지로 첫 await 전에 동기적으로 비활성화한다.
      window.TakuAPI.setLoading(removeBtn, true);

      var result = await window.TakuAPI.patch("/api/personal-entries/" + entryId + "/", { image: null });

      if (result.status === 200) {
        if (currentUrl) { URL.revokeObjectURL(currentUrl); currentUrl = null; }
        if (input) { input.value = ""; }
        var img = dropzone && dropzone.querySelector("img");
        if (img) { img.remove(); }
        var placeholder = dropzone && dropzone.querySelector(".personal-form-dropzone-placeholder");
        if (dropzone && !placeholder) {
          placeholder = document.createElement("span");
          placeholder.className = "personal-form-dropzone-placeholder";
          placeholder.textContent = "사진을 선택하세요";
          dropzone.appendChild(placeholder);
        } else if (placeholder) {
          placeholder.hidden = false;
        }
        removeBtn.remove();
        return;
      }

      window.TakuAPI.setLoading(removeBtn, false);

      if (result.status === 403) {
        handle403(result, globalErrorEl);
        return;
      }
      if (result.status === 404) {
        lockPageForGoneEntry(form);
        return;
      }
      if (result.status === 0) {
        setText(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }
      setText(globalErrorEl, "사진 삭제 중 오류가 발생했습니다.");
    });
  }

  // ── 저장 ─────────────────────────────────────────────────────────────

  function bindForm() {
    var form = document.getElementById("personal-edit-form");
    if (!form) { return; }

    var entryId = form.dataset.entryId;
    var errorEl = document.getElementById("personal-edit-error");
    var submitBtn = form.querySelector('[type="submit"]');

    bindImage(form, entryId);

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

      // PATCH 계약: 서버 렌더 값으로 채워진 필드를 그대로 전부 보낸다 —
      // dirty 추적 없음. 지운 선택 필드는 trim()이 빈 문자열을 만들어
      // 그대로 전송된다(no-op이 아니라 명시적 초기화).
      var fields = {
        title: title,
        category: form.elements["category"].value.trim(),
        work_title: form.elements["work_title"].value.trim(),
        location_name: form.elements["location_name"].value.trim(),
        region: form.elements["region"].value.trim(),
        url: form.elements["url"].value.trim(),
        memo: form.elements["memo"].value.trim(),
      };

      window.TakuAPI.setLoading(submitBtn, true);

      var result;
      if (imageFile) {
        var formData = new FormData();
        Object.keys(fields).forEach(function (key) {
          formData.append(key, fields[key]);
        });
        formData.append("image", imageFile);
        result = await window.TakuAPI.upload(
          "/api/personal-entries/" + entryId + "/",
          formData,
          "PATCH"
        );
      } else {
        result = await window.TakuAPI.patch("/api/personal-entries/" + entryId + "/", fields);
      }

      if (result.status === 200) {
        // collection_edit.js의 선례를 따른다 — 상세 화면이 있는 형제 수정
        // 화면(굿즈 수정)은 목록이 아니라 방금 편집한 항목의 상세로
        // 돌아간다. 이 페이지의 상단 back-link 문구("← 장소 상세로")도
        // 같은 목적지를 가리켜 일관된다.
        window.TakuAPI.commitAndNavigate(submitBtn, "/archive/personal/" + entryId + "/");
        return;
      }

      // 404 분기보다 먼저 무조건 실행한다 — .is-loading이 남은 채면
      // bfcache 복원 시 api.js가 그 버튼만 조용히 다시 켜버린다.
      window.TakuAPI.setLoading(submitBtn, false);

      if (result.status === 404) {
        lockPageForGoneEntry(form);
        return;
      }
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

    bindDelete(form, entryId);
  }

  // ── 항목 삭제 ─────────────────────────────────────────────────────

  function bindDelete(form, entryId) {
    var deleteBtn = document.querySelector("[data-delete-entry-id]");
    if (!deleteBtn) { return; }
    var globalErrorEl = document.getElementById("personal-edit-global-error");

    deleteBtn.addEventListener("click", async function () {
      if (
        !(await askConfirm(
          "이 항목을 삭제하시겠습니까? 연결된 찜·상태·방문 기록도 함께 삭제됩니다."
        ))
      ) {
        return;
      }
      setText(globalErrorEl, "");
      window.TakuAPI.setLoading(deleteBtn, true);

      var result = await window.TakuAPI.del("/api/personal-entries/" + entryId + "/");
      if (result.status === 204) {
        window.TakuAPI.commitAndNavigate(deleteBtn, LIST_URL);
        return;
      }

      window.TakuAPI.setLoading(deleteBtn, false);

      if (result.status === 403) {
        handle403(result, globalErrorEl);
        return;
      }
      if (result.status === 404) {
        lockPageForGoneEntry(form);
        return;
      }
      if (result.status === 0) {
        setText(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }
      setText(globalErrorEl, "삭제 중 오류가 발생했습니다.");
    });
  }

  function init() {
    bindCategoryChips();
    bindForm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
