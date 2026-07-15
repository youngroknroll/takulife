/**
 * collection.js — CollectionItem create/edit/delete (archive/collection screens)
 *
 * Handles:
 *   - Create via form#collection-create-form → POST /api/collection-items/
 *   - Edit via form#collection-edit-form → PATCH /api/collection-items/<id>/
 *   - Delete via [data-delete-item-id] → DELETE /api/collection-items/<id>/
 *
 * Client guards mirror the server for fast feedback (image 5MB/JPEG-PNG-WebP,
 * tradeable_quantity <= quantity); the server remains the source of truth
 * (visit_create.js's explicit division of labor). Both forms use a single
 * multipart-or-JSON submit (personal_entries.js's pattern) — CollectionItem's
 * image is one field on the same resource, not a separate photo sub-resource,
 * so there is no two-phase create+upload step here (unlike visit_create.js).
 */

(function () {
  "use strict";

  var MAX_BYTES = 5 * 1024 * 1024;
  var ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
  var LIST_URL = "/archive/collection/";
  // Fields rendered inside the collapsed <details> group — a server error on
  // any of these must reopen it (personal_entries.js:107-111's pattern,
  // generalized to this form's larger field set).
  var DETAIL_KEYS = [
    "work_title", "character_name", "item_type",
    "acquired_on", "acquisition_source", "visit_record", "tradeable_quantity",
  ];

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

  // Confirm before a destructive, unrecoverable action (personal_entries.js's
  // askConfirm — shared modal with a native confirm() fallback).
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  function parseIntOrDefault(raw, fallback) {
    var n = parseInt(raw, 10);
    return isNaN(n) ? fallback : n;
  }

  // Client-side mirror of events/image_validation.py's size/format checks —
  // fast feedback for the common case. The server remains authoritative for
  // cases this can't catch (format spoofing, decompression bombs); those
  // rare 400s fall through to formatError's default rendering untouched.
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

  function openDetailIfErrored(result) {
    if (!result.data || typeof result.data !== "object") { return; }
    var hasDetailError = DETAIL_KEYS.some(function (key) {
      return key in result.data;
    });
    if (!hasDetailError) { return; }
    var detailFields = document.getElementById("collection-detail-fields");
    if (detailFields) { detailFields.open = true; }
  }

  // Shared field collection for create/edit — every editable text/number/
  // checkbox field except image (handled separately by the caller) and
  // visit_record (create-only; the edit form never renders a writable
  // visit_record control, per core/views.py's FK-pair invariant).
  function collectSharedFields(form) {
    return {
      name: form.elements["name"].value.trim(),
      quantity: parseIntOrDefault(form.elements["quantity"].value, 0),
      tradeable_quantity: parseIntOrDefault(form.elements["tradeable_quantity"].value, 0),
      is_wanted: form.elements["is_wanted"].checked,
      memo: form.elements["memo"].value.trim(),
      work_title: form.elements["work_title"].value.trim(),
      character_name: form.elements["character_name"].value.trim(),
      item_type: form.elements["item_type"].value.trim(),
      acquisition_source: form.elements["acquisition_source"].value.trim(),
    };
  }

  function buildFormData(fields, imageFile) {
    var formData = new FormData();
    Object.keys(fields).forEach(function (key) {
      formData.append(key, fields[key]);
    });
    formData.append("image", imageFile);
    return formData;
  }

  // ── create ──────────────────────────────────────────────────────────────

  function bindCreateForm() {
    var form = document.getElementById("collection-create-form");
    if (!form) { return; }
    var errorEl = document.getElementById("collection-create-error");
    var statusEl = document.getElementById("collection-create-status");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      setText(errorEl, "");
      setText(statusEl, "");

      if (!form.elements["name"].value.trim()) {
        setText(errorEl, "이름을 입력해 주세요.");
        return;
      }

      var imageInput = form.elements["image"];
      var imageFile = imageInput && imageInput.files && imageInput.files[0];
      if (imageFile && !validateImageFile(imageFile, errorEl)) {
        return;
      }

      var fields = collectSharedFields(form);
      if (fields.tradeable_quantity > fields.quantity) {
        setText(errorEl, "교환 가능 수량은 보유 수량보다 클 수 없습니다.");
        return;
      }

      var acquiredOn = form.elements["acquired_on"].value;
      if (acquiredOn) { fields.acquired_on = acquiredOn; }

      // Preselected (locked) subject uses a hidden input; the selectable
      // dropdown otherwise. Both share name="visit_record" (collection_create
      // .html), so this reads either. Omit the key entirely for "연결 안 함"
      // — an empty-string FK id is invalid, not "no relation".
      var visitRecordEl = form.elements["visit_record"];
      var visitRecordVal = visitRecordEl ? visitRecordEl.value : "";
      if (visitRecordVal) { fields.visit_record = parseInt(visitRecordVal, 10); }

      // Synchronous disable happens before the first await below, so a
      // second click/Enter arriving after this line finds the button already
      // disabled — no separate in-flight flag needed (TakuAPI.setLoading
      // sets button.disabled directly).
      window.TakuAPI.setLoading(submitBtn, true);

      var result = imageFile
        ? await window.TakuAPI.upload("/api/collection-items/", buildFormData(fields, imageFile))
        : await window.TakuAPI.post("/api/collection-items/", fields);

      if (result.status === 201) {
        window.location.assign(LIST_URL);
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
      openDetailIfErrored(result);
    });
  }

  // ── edit ────────────────────────────────────────────────────────────────

  // Disables every control in the form — used only for the "item is
  // provably gone" 404 case, so no field the user edits can produce another
  // doomed submit (BIR criterion: lock the whole form, not just the button).
  //
  // Deliberately has no pageshow/bfcache recovery listener, unlike
  // status.js's .is-sibling-locked (status.js:516-530): that lock protects
  // an in-flight request interrupted by navigation — the request that would
  // have unlocked it never got the chance to run again, so it must be
  // force-cleared on restore. This lock is the opposite: it is applied only
  // *after* the 404 response already confirmed the item is gone, a settled
  // fact, not an interrupted operation. Resetting it on a bfcache restore
  // would re-enable a submit path into a row that provably does not exist —
  // recreating the exact retry loop this lock exists to prevent. Marked
  // with .is-item-gone-locked for introspection only (no bfcache handler
  // reads it), mirroring api.js's own note that a deliberately-disabled
  // control must be left untouched by any pageshow recovery.
  //
  // This guarantee holds only because the 404 branch in bindEditForm calls
  // window.TakuAPI.setLoading(submitBtn, false) *before* calling this
  // function, clearing submitBtn's .is-loading class first. If that call
  // were skipped or moved after lockForm(), submitBtn would still carry
  // .is-loading when this function runs, and api.js's own global pageshow
  // handler (api.js:380-387) — unconditional, scoped only to .is-loading —
  // would re-enable that one button on a bfcache restore while every other
  // control here stays correctly disabled (BIR post-implementation finding,
  // 2026-07-16: reachable via this page's own "목록으로 돌아가기" link +
  // browser Back). See tests/e2e/test_collection_edit_bfcache_lock_e2e.py.
  function lockForm(form) {
    var controls = form.querySelectorAll("input, select, textarea, button");
    for (var i = 0; i < controls.length; i++) {
      controls[i].disabled = true;
      controls[i].classList.add("is-item-gone-locked");
    }
  }

  // Mirrors visit_create.js's revealContinueLink: append the one remaining
  // valid action and focus it, since every other control just went disabled.
  function revealBackLink(form) {
    if (document.getElementById("collection-back-link")) { return; }
    var link = document.createElement("a");
    link.id = "collection-back-link";
    link.className = "record-cta";
    link.href = LIST_URL;
    link.textContent = "목록으로 돌아가기";
    form.appendChild(link);
    link.focus();
  }

  // Delete lives in two places sharing the same data-delete-item-id
  // convention (visit.js/visit_edit.js's exact precedent) — but unlike that
  // pair, both places load this single collection.js file, so one binder
  // must handle both instead of two page-scoped ones (which would
  // double-bind the edit page's button). Success behavior still differs by
  // context: a list card reloads in place, the edit page navigates back.
  function bindItemDeletes() {
    var deleteBtns = document.querySelectorAll("[data-delete-item-id]");
    var globalErrorEl = document.getElementById("collection-global-error");

    for (var i = 0; i < deleteBtns.length; i++) {
      (function (btn) {
        if (btn.dataset.deleteBound) { return; }
        btn.dataset.deleteBound = "1";
        var onEditPage = !!btn.closest("#collection-edit-form");

        btn.addEventListener("click", async function () {
          if (!(await askConfirm("이 굿즈를 삭제하시겠습니까? 되돌릴 수 없습니다."))) {
            return;
          }
          var itemId = btn.getAttribute("data-delete-item-id");
          setText(globalErrorEl, "");
          window.TakuAPI.setLoading(btn, true);

          var result = await window.TakuAPI.del("/api/collection-items/" + itemId + "/");

          if (result.status === 204) {
            if (onEditPage) {
              window.location.assign(LIST_URL);
            } else {
              window.location.reload();
            }
            return;
          }

          window.TakuAPI.setLoading(btn, false);

          if (result.status === 403) {
            handle403(result, globalErrorEl);
            return;
          }
          if (result.status === 404) {
            setText(globalErrorEl, "이미 삭제된 항목입니다.");
            return;
          }
          if (result.status === 0) {
            setText(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
            return;
          }
          setText(globalErrorEl, "삭제 중 오류가 발생했습니다.");
        });
      })(deleteBtns[i]);
    }
  }

  function bindEditForm() {
    var form = document.getElementById("collection-edit-form");
    if (!form) { return; }

    var itemId = form.dataset.itemId;
    var errorEl = document.getElementById("collection-edit-error");
    var statusEl = document.getElementById("collection-edit-status");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      setText(errorEl, "");
      setText(statusEl, "");

      if (!form.elements["name"].value.trim()) {
        setText(errorEl, "이름을 입력해 주세요.");
        return;
      }

      var imageInput = form.elements["image"];
      var imageFile = imageInput && imageInput.files && imageInput.files[0];
      if (imageFile && !validateImageFile(imageFile, errorEl)) {
        return;
      }

      var fields = collectSharedFields(form);
      if (fields.tradeable_quantity > fields.quantity) {
        setText(errorEl, "교환 가능 수량은 보유 수량보다 클 수 없습니다.");
        return;
      }

      var acquiredOn = form.elements["acquired_on"].value;
      if (acquiredOn) { fields.acquired_on = acquiredOn; }

      window.TakuAPI.setLoading(submitBtn, true);

      var result = imageFile
        ? await window.TakuAPI.upload(
            "/api/collection-items/" + itemId + "/",
            buildFormData(fields, imageFile),
            "PATCH"
          )
        : await window.TakuAPI.patch("/api/collection-items/" + itemId + "/", fields);

      if (result.status === 200) {
        window.location.assign(LIST_URL);
        return;
      }

      // Unconditional, same position as every sibling handler in this file
      // (bindCreateForm, bindItemDeletes) — see lockForm's docstring for why
      // the 404 branch below must never run before this line.
      window.TakuAPI.setLoading(submitBtn, false);

      // The item was provably deleted (e.g. a concurrent delete) between
      // this page's GET and this submit. Retrying is never correct — no
      // field edit can make a gone row patchable — so the form is locked
      // instead of leaving an inline error the user can keep resubmitting
      // into the same 404 (BIR pre-implementation criterion #4).
      if (result.status === 404) {
        setText(errorEl, "삭제된 항목입니다.");
        lockForm(form);
        revealBackLink(form);
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
      openDetailIfErrored(result);
    });
  }

  function init() {
    bindCreateForm();
    bindEditForm();
    bindItemDeletes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Live search (archive_search.js) swaps #archive-results on the list page
  // — the create/edit forms live outside that region and are unaffected;
  // the per-button dataset.deleteBound guard keeps this idempotent.
  document.addEventListener("archive:listswapped", bindItemDeletes);
})();
