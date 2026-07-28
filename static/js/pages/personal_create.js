/**
 * personal_create.js — /archive/personal/new/ write page
 *
 * Handles:
 *   - category quick-pick chips → #personal-category free-input (goods
 *     create's bindTypeChips pattern, mirrored 1:1 for this page's own
 *     `.personal-form-category-chip` class)
 *   - image dropzone preview (blob URL, revoked on replacement)
 *   - form submit → POST /api/personal-entries/ (existing API, no new
 *     endpoint), 201 → navigate to /archive/personal/
 *
 * Relies on window.TakuAPI (api.js) for requests, 403 disambiguation and error
 * formatting. All DOM writes use textContent only.
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

  // Client-side mirror of the server's image guard — fast feedback for the
  // common case; the server remains authoritative (collection.js's
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

  // ── category chips ──────────────────────────────────────────────────────
  // Chips only ever write to the #personal-category free-input — never a
  // separate hidden field — so the single form.elements["category"] read in
  // the submit handler below stays the one source of truth whether the user
  // clicked a chip or typed a custom value. Mirrors collection.js's
  // bindTypeChips (goods-create-editorial-track), with its own class name so
  // this page's chips never collide with the list page's (nonexistent here)
  // filter chips or the goods form's item-type chips.
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

    // One sync pass against whatever the input already holds (a server
    // re-render after a validation error would repopulate this).
    syncFromValue();
  }

  // ── image dropzone preview ──────────────────────────────────────────────

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

  // ── submit ───────────────────────────────────────────────────────────────

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

      // client_token: SSR-issued uuid4 hidden input (personal_create.html,
      // DAR §5-1) for create-side idempotency replay. Existence guard
      // mirrors visit_create.js's precedent — this page has no edit-form
      // twin, but the guard keeps the payload safe if the hidden input is
      // ever removed from the template. Also require a non-empty value: an
      // empty string would still pass an existence-only guard and serialize
      // as client_token: "", which the serializer's UUIDField rejects with
      // 400 — turning a missing/stale template context into a hard create
      // failure instead of a silent fallback. Empty value → send no token
      // (degrades to pre-token behavior, avoids the 400).
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
