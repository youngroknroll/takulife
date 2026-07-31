/**
 * 굿즈 상세 페이지(archive_collection_detail). 항목 삭제만 담당한다.
 * 삭제 성공(204) 후 404가 오면 이미 삭제된 것이므로, 화면에 남아 있는
 * 수정 링크를 눌러도 또 다른 404로 이어지지 않도록 함께 잠근다.
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

  // 항목이 이미 삭제됐다는 확정된 사실이라 .is-loading 클래스는 쓰지 않는다.
  // 그 클래스는 api.js가 bfcache 복원 시 자동으로 되돌리므로 여기서는 맞지 않다.
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
      // 첫 await 전에 동기적으로 버튼을 비활성화해, 요청이 진행되는 동안
      // 다시 클릭해도 이미 막힌 상태를 보게 한다.
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
