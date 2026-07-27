/**
 * collection_detail.js — CollectionItem read-only detail page
 * (archive_collection_detail).
 *
 * Only responsibility: item delete.
 *   DELETE /api/collection-items/<id>/
 *
 * Branch set mirrors collection.js's bindItemDeletes() (BIR requirement —
 * this page must not diverge from the list/edit pages' delete semantics),
 * with one addition: on a 404 ("already gone") this page also locks the
 * 수정 link, because unlike the list card (which just reloads the same
 * list) or the edit page (whose only remaining affordance is its own
 * submit), this page still shows a live-looking 수정 link that would lead
 * straight into collection_edit.html's own 404 dead end. Locking it here
 * avoids that second dead end.
 */

(function () {
  "use strict";

  var LIST_URL = "/collection/";

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
    var kind = window.TakuAPI.classify(result);
    if (kind === "auth") {
      window.TakuAPI.redirectToLogin();
    } else {
      setText(errorEl, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
    }
  }

  // Locks the 수정 link once the delete request has proven the item is
  // gone (404) — a settled fact, not an interrupted in-flight request, so
  // this deliberately does NOT use the .is-loading class (api.js's own
  // global pageshow handler re-enables anything still carrying .is-loading
  // on a bfcache restore; collection.js's lockForm()/.is-item-gone-locked
  // is the same distinction ported here for a single link instead of a
  // whole form).
  function lockEditLink(editLink) {
    if (!editLink) { return; }
    editLink.removeAttribute("href");
    editLink.setAttribute("aria-disabled", "true");
    editLink.classList.add("is-item-gone-locked");
    editLink.addEventListener("click", function (evt) {
      evt.preventDefault();
    });
  }

  function bindDelete() {
    var deleteBtn = document.querySelector("[data-delete-item-id]");
    if (!deleteBtn) { return; }

    var itemId = deleteBtn.getAttribute("data-delete-item-id");
    var globalErrorEl = document.getElementById("collection-global-error");
    var editLink = document.querySelector(".collection-detail-edit-btn");

    deleteBtn.addEventListener("click", async function () {
      if (!(await askConfirm("이 굿즈를 삭제하시겠습니까? 되돌릴 수 없습니다."))) {
        return;
      }
      setText(globalErrorEl, "");
      // Synchronous disable before the first await — a second click
      // arriving while the request is in flight finds the button already
      // disabled (TakuAPI.setLoading sets button.disabled directly).
      window.TakuAPI.setLoading(deleteBtn, true);

      var result = await window.TakuAPI.del("/api/collection-items/" + itemId + "/");
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
        setText(globalErrorEl, "이미 삭제된 항목입니다.");
        deleteBtn.disabled = true;
        deleteBtn.classList.add("is-item-gone-locked");
        lockEditLink(editLink);
        return;
      }
      if (result.status === 0) {
        setText(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }
      setText(globalErrorEl, "굿즈 삭제 중 오류가 발생했습니다.");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindDelete);
  } else {
    bindDelete();
  }
})();
