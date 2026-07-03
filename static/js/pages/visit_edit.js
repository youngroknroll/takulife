/**
 * visit_edit.js — Visit-record edit page (archive_visit_edit).
 *
 * Edits one existing record:
 *   - PATCH /api/visit-records/<id>/  (visited_on, short_review)
 *   - existing photos: DELETE /api/visit-records/<id>/photos/<photoId>/  (immediate)
 *   - new photos: Instagram-style preview, uploaded on save via
 *     POST /api/visit-records/<id>/photos/  (sequential)
 *   - record delete: DELETE /api/visit-records/<id>/
 *
 * 대표(cover) = the first photo overall: first existing photo if any, else the
 * first newly-added preview. Recomputed whenever photos change.
 */

(function () {
  "use strict";

  var MAX_PHOTOS = 5;
  var MAX_BYTES = 5 * 1024 * 1024;
  var ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
  var VISITS_URL = "/archive/visits/";

  var pendingItems = []; // [{ file, url }] — new photos queued for upload

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

  function existingCount() {
    return document.querySelectorAll(
      "#existing-photo-grid .photo-preview-tile"
    ).length;
  }

  function updateTrigger() {
    var trigger = document.getElementById("visit-photos-trigger");
    if (trigger) {
      trigger.hidden = existingCount() + pendingItems.length >= MAX_PHOTOS;
    }
  }

  // ── cover badge across both grids ──────────────────────────────────────────

  function clearCovers() {
    var tiles = document.querySelectorAll(".photo-preview-tile");
    for (var i = 0; i < tiles.length; i++) {
      tiles[i].classList.remove("is-cover");
      var badge = tiles[i].querySelector(".photo-preview-cover-badge");
      if (badge) { badge.remove(); }
    }
  }

  function markCover(tile) {
    if (!tile) { return; }
    tile.classList.add("is-cover");
    var badge = document.createElement("span");
    badge.className = "photo-preview-cover-badge";
    badge.textContent = "대표";
    tile.appendChild(badge);
  }

  function refreshCover() {
    clearCovers();
    var firstExisting = document.querySelector(
      "#existing-photo-grid .photo-preview-tile"
    );
    if (firstExisting) {
      markCover(firstExisting);
      return;
    }
    var firstNew = document.querySelector("#photo-preview-grid .photo-preview-tile");
    markCover(firstNew);
  }

  // ── new-photo preview grid ─────────────────────────────────────────────────

  function renderNewGrid(grid) {
    grid.textContent = "";
    updateTrigger();
    if (pendingItems.length === 0) {
      grid.hidden = true;
      refreshCover();
      return;
    }
    grid.hidden = false;

    pendingItems.forEach(function (item, index) {
      var tile = document.createElement("div");
      tile.className = "photo-preview-tile";

      var img = document.createElement("img");
      img.src = item.url;
      img.alt = "추가 미리보기 " + (index + 1);
      tile.appendChild(img);

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "photo-preview-remove";
      remove.textContent = "×";
      remove.setAttribute("aria-label", "제거: " + item.file.name);
      remove.addEventListener("click", function () {
        removeNewAt(index, grid);
      });
      tile.appendChild(remove);

      grid.appendChild(tile);
    });
    refreshCover();
  }

  function removeNewAt(index, grid) {
    var removed = pendingItems.splice(index, 1)[0];
    if (removed) { URL.revokeObjectURL(removed.url); }
    renderNewGrid(grid);

    var buttons = grid.querySelectorAll(".photo-preview-remove");
    if (buttons.length > 0) {
      var next = buttons[Math.min(index, buttons.length - 1)];
      if (next) { next.focus(); }
    } else {
      var input = document.getElementById("visit-photos");
      if (input) { input.focus(); }
    }
  }

  function isDuplicate(file) {
    return pendingItems.some(function (item) {
      return item.file.name === file.name &&
        item.file.size === file.size &&
        item.file.lastModified === file.lastModified;
    });
  }

  function addFiles(fileList, grid, errorEl) {
    setText(errorEl, "");
    var rejected = [];

    for (var i = 0; i < fileList.length; i++) {
      var file = fileList[i];
      if (existingCount() + pendingItems.length >= MAX_PHOTOS) {
        setText(errorEl, "사진은 기존 포함 최대 " + MAX_PHOTOS + "장까지입니다.");
        break;
      }
      if (ALLOWED_TYPES.indexOf(file.type) === -1) {
        rejected.push(file.name + " (지원하지 않는 형식)");
        continue;
      }
      if (file.size > MAX_BYTES) {
        rejected.push(file.name + " (5MB 초과)");
        continue;
      }
      if (isDuplicate(file)) { continue; }
      pendingItems.push({ file: file, url: URL.createObjectURL(file) });
    }

    if (rejected.length > 0) {
      setText(errorEl, "일부 사진은 제외됐습니다: " + rejected.join(", "));
    }
    renderNewGrid(grid);
  }

  // ── existing-photo delete (immediate) ──────────────────────────────────────

  function bindExistingDeletes(recordId, errorEl) {
    var grid = document.getElementById("existing-photo-grid");
    var emptyHint = document.getElementById("existing-empty-hint");
    if (!grid) { return; }

    grid.addEventListener("click", async function (evt) {
      var btn = evt.target.closest("[data-existing-photo-id]");
      if (!btn) { return; }

      var photoId = btn.getAttribute("data-existing-photo-id");
      if (!(await askConfirm("이 사진을 삭제하시겠습니까? 되돌릴 수 없습니다."))) {
        return;
      }
      setText(errorEl, "");
      window.TakuAPI.setLoading(btn, true);

      var result = await window.TakuAPI.del(
        "/api/visit-records/" + recordId + "/photos/" + photoId + "/"
      );

      if (result.status === 204) {
        var tile = btn.closest(".photo-preview-tile");
        if (tile) { tile.remove(); }
        if (existingCount() === 0) {
          grid.hidden = true;
          if (emptyHint) { emptyHint.hidden = false; }
        }
        refreshCover();
        updateTrigger();
        return;
      }

      window.TakuAPI.setLoading(btn, false);
      if (result.status === 403) {
        handle403(result, errorEl);
      } else if (result.status === 404) {
        setText(errorEl, "사진을 찾을 수 없습니다.");
      } else if (result.status === 0) {
        setText(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
      } else {
        setText(errorEl, "사진 삭제 중 오류가 발생했습니다.");
      }
    });
  }

  // ── sequential upload of new photos ────────────────────────────────────────

  async function uploadNewPhotos(recordId, statusEl) {
    var total = pendingItems.length;
    for (var i = 0; i < pendingItems.length; i++) {
      setText(statusEl, "사진 업로드 중 (" + (i + 1) + "/" + total + ")...");
      var formData = new FormData();
      formData.append("image", pendingItems[i].file);
      var result = await window.TakuAPI.upload(
        "/api/visit-records/" + recordId + "/photos/",
        formData
      );
      if (result.status !== 201) {
        return { succeeded: i, total: total };
      }
    }
    return { succeeded: total, total: total };
  }

  // ── save (PATCH + new photos) and record delete ────────────────────────────

  function bindForm() {
    var form = document.getElementById("visit-edit-form");
    if (!form) { return; }

    var recordId = form.getAttribute("data-record-id");
    var errorEl = document.getElementById("visit-edit-error");
    var statusEl = document.getElementById("visit-edit-status");
    var grid = document.getElementById("photo-preview-grid");
    var fileInput = document.getElementById("visit-photos");
    var triggerBtn = document.getElementById("visit-photos-trigger");
    var submitBtn = form.querySelector('[type="submit"]');
    var deleteBtn = form.querySelector("[data-delete-record-id]");

    refreshCover();
    updateTrigger();
    bindExistingDeletes(recordId, errorEl);

    if (fileInput && grid) {
      fileInput.addEventListener("change", function () {
        addFiles(fileInput.files, grid, errorEl);
        fileInput.value = "";
      });
    }

    if (triggerBtn && fileInput) {
      triggerBtn.addEventListener("click", function () {
        fileInput.click();
      });
    }

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      setText(errorEl, "");
      setText(statusEl, "");

      var visitedOn = form.elements["visited_on"].value;
      var shortReview = form.elements["short_review"].value;
      if (!visitedOn) {
        setText(errorEl, "방문 날짜를 입력해 주세요.");
        return;
      }

      window.TakuAPI.setLoading(submitBtn, true);
      setText(statusEl, "저장 중...");

      var result = await window.TakuAPI.patch("/api/visit-records/" + recordId + "/", {
        visited_on: visitedOn,
        short_review: shortReview,
      });

      if (result.status !== 200) {
        window.TakuAPI.setLoading(submitBtn, false);
        setText(statusEl, "");
        if (result.status === 403) {
          handle403(result, errorEl);
        } else if (result.status === 0) {
          setText(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        } else {
          setText(errorEl, window.TakuAPI.formatError(result));
        }
        return;
      }

      if (pendingItems.length === 0) {
        window.location.assign(VISITS_URL);
        return;
      }

      var outcome = await uploadNewPhotos(recordId, statusEl);
      if (outcome.succeeded === outcome.total) {
        setText(statusEl, "저장 완료. 이동 중...");
        window.location.assign(VISITS_URL);
        return;
      }

      setText(
        statusEl,
        "변경은 저장됐고 새 사진 " + outcome.succeeded + "/" + outcome.total +
          "장이 올라갔습니다. 나머지는 다시 시도해 주세요."
      );
      window.TakuAPI.setLoading(submitBtn, false);
    });

    if (deleteBtn) {
      deleteBtn.addEventListener("click", async function () {
        var globalErrorEl = document.getElementById("visit-global-error");
        if (
          !(await askConfirm(
            "이 방문 기록을 삭제하시겠습니까? 메모와 사진도 함께 삭제되며 되돌릴 수 없습니다."
          ))
        ) {
          return;
        }
        setText(globalErrorEl, "");
        window.TakuAPI.setLoading(deleteBtn, true);

        var result = await window.TakuAPI.del("/api/visit-records/" + recordId + "/");
        if (result.status === 204) {
          window.location.assign(VISITS_URL);
          return;
        }

        window.TakuAPI.setLoading(deleteBtn, false);
        if (result.status === 403) {
          handle403(result, globalErrorEl);
        } else if (result.status === 0) {
          setText(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        } else {
          setText(globalErrorEl, "기록 삭제 중 오류가 발생했습니다.");
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindForm);
  } else {
    bindForm();
  }
})();
