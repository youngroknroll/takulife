/**
 * personal_edit.js — /archive/personal/<id>/edit/ render-only edit page.
 *
 * Handles:
 *   - category quick-pick chips (personal_create.js's bindCategoryChips,
 *     mirrored 1:1 — same `.personal-form-category-chips` class, same
 *     single source-of-truth read from #personal-category)
 *   - image dropzone preview for a newly picked replacement file
 *   - image delete → immediate PATCH { image: null } (JSON), separate from
 *     the main form submit (BIR: never merge into the multipart PATCH —
 *     every other single-click destructive action here is immediate+
 *     confirm, so folding this into a deferred save would break that
 *     expectation)
 *   - form submit → PATCH /api/personal-entries/<id>/ (existing API, no new
 *     endpoint; multipart only when a replacement image file is attached)
 *   - entry delete → DELETE /api/personal-entries/<id>/ (same confirm copy
 *     as the list and detail screens)
 *   - 404 lock cascade: unlike personal_detail.js (which only needs to
 *     .focus() its already-alive back-link), this page's own back-link AND
 *     취소 link both point at /archive/personal/<id>/, which 404s too once
 *     the entry is gone — so both must be neutralized and a brand-new
 *     "목록으로 돌아가기" link appended instead (collection.js's
 *     revealBackLink precedent, not personal_detail.js's).
 *
 * Relies on window.TakuAPI (api.js) for requests, 403 disambiguation and
 * error formatting, and window.TakuConfirm (confirm-modal.js) for the
 * destructive-action confirm dialog. All DOM writes use textContent only.
 */

(function () {
  "use strict";

  var LIST_URL = "/archive/personal/";
  var MAX_BYTES = 5 * 1024 * 1024;
  var ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

  var goneLocked = false; // guards against double-appending the back-to-list link

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

  // Client-side mirror of the server's image guard — fast feedback for the
  // common case; the server remains authoritative (personal_create.js's
  // validateImageFile precedent).
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

  // Disables every control in the form — no field the user still edits can
  // produce another doomed submit (collection.js's lockForm precedent).
  function lockForm(form) {
    var controls = form.querySelectorAll("input, select, textarea, button");
    for (var i = 0; i < controls.length; i++) {
      controls[i].disabled = true;
      controls[i].classList.add("is-item-gone-locked");
    }
  }

  // The top back-link and 취소 link both target /archive/personal/<id>/,
  // which is gone too — this page (unlike personal_detail.js) needs a
  // brand-new surviving link, not a .focus() on an already-dead one
  // (collection.js's revealBackLink precedent).
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

  // ── category chips (personal_create.js's bindCategoryChips, mirrored) ──

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

    // One sync pass against the server-rendered prefill value.
    syncFromValue();
  }

  // ── image: replacement preview + immediate delete ──────────────────────

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
      // Synchronous disable before the first await, mirroring every other
      // destructive control on this page.
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

  // ── save ─────────────────────────────────────────────────────────────

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

      // Unconditional, before any 404 branch — see lockForm's callers for
      // why: a .is-loading button left disabled-but-not-marked would be
      // silently re-enabled by api.js's own bfcache pageshow handler.
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

  // ── entry delete ─────────────────────────────────────────────────────

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
