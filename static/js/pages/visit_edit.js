/**
 * 방문 기록 수정 페이지. 날짜·후기 저장, 기존 사진의 즉시 삭제, 새 사진의
 * 미리보기+저장 시 순차 업로드, 기록 삭제를 담당한다.
 * 대표 사진은 항상 첫 번째 사진이다 — 기존 사진이 있으면 그중 첫 장,
 * 없으면 새로 추가한 미리보기 중 첫 장. 사진이 바뀔 때마다 다시 계산한다.
 */

(function () {
  "use strict";

  var MAX_PHOTOS = 5;
  var MAX_BYTES = 5 * 1024 * 1024;
  var ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
  var VISITS_URL = "/archive/visits/";

  var pendingItems = []; // [{ file, url }] — 업로드 대기 중인 새 사진
  // uploadNewPhotos가 요청을 보내는 동안 true. 이 값을 renderNewGrid가
  // 읽어, 업로드 중 다시 그려진 삭제 버튼도 비활성화 상태로 태어나게 한다
  // — 그렇지 않으면 진행 중이 아닌 항목이 잘못 삭제될 수 있다.
  var uploadLocked = false;

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

  // ── 두 그리드에 걸친 대표 배지 ──────────────────────────────────────────

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

  // ── 새 사진 미리보기 그리드 ─────────────────────────────────────────────────

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
      remove.disabled = uploadLocked;
      remove.addEventListener("click", function () {
        removeNewAt(index, grid);
      });
      tile.appendChild(remove);

      grid.appendChild(tile);
    });
    refreshCover();
  }

  // 업로드 중 pendingItems를 바꿀 수 있는 모든 컨트롤을 한꺼번에 잠그거나 푼다.
  function setUploadLock(locked, grid) {
    uploadLocked = locked;
    var trigger = document.getElementById("visit-photos-trigger");
    var input = document.getElementById("visit-photos");
    if (trigger) { trigger.disabled = locked; }
    if (input) { input.disabled = locked; }
    if (grid) {
      var buttons = grid.querySelectorAll(".photo-preview-remove");
      for (var i = 0; i < buttons.length; i++) {
        buttons[i].disabled = locked;
      }
    }
  }

  function discardPending(index, grid) {
    var removed = pendingItems.splice(index, 1)[0];
    if (removed) { URL.revokeObjectURL(removed.url); }
    renderNewGrid(grid);
  }

  function removeNewAt(index, grid) {
    discardPending(index, grid);

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
      var item = { file: file, url: URL.createObjectURL(file) };
      // 재시도 시에도 같은 토큰을 다시 보내도록 파일 선택 시점에 한 번만
      // 발급한다 — 응답 유실 후 재전송돼도 서버가 같은 요청으로 인식해
      // 사진이 중복 생성되지 않는다. 지원하지 않는 브라우저는 그냥
      // 토큰 없이 기존 방식대로 동작한다.
      if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        item.clientToken = crypto.randomUUID();
      }
      pendingItems.push(item);
    }

    if (rejected.length > 0) {
      setText(errorEl, "일부 사진은 제외됐습니다: " + rejected.join(", "));
    }
    renderNewGrid(grid);
  }

  // ── 기존 사진 즉시 삭제 ──────────────────────────────────────────

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

  // ── 새 사진 순차 업로드 ────────────────────────────────────────

  async function uploadNewPhotos(recordId, statusEl, grid) {
    var total = pendingItems.length;
    var succeeded = 0;
    setUploadLock(true, grid);
    while (pendingItems.length > 0) {
      setText(statusEl, "사진 업로드 중 (" + (succeeded + 1) + "/" + total + ")...");
      var formData = new FormData();
      formData.append("image", pendingItems[0].file);
      // 값이 없으면 아예 보내지 않는다 — 빈 문자열은 서버 UUIDField
      // 검증에서 요청 전체를 400으로 실패시킨다.
      if (pendingItems[0].clientToken) {
        formData.append("client_token", pendingItems[0].clientToken);
      }
      var result = await window.TakuAPI.upload(
        "/api/visit-records/" + recordId + "/photos/",
        formData
      );
      if (result.status !== 201) {
        setUploadLock(false, grid); // 재시도할 수 있도록 그리드를 다시 편집 가능하게 한다
        return { succeeded: succeeded, total: total };
      }
      // 업로드된 항목은 지워, 재시도할 때 이미 성공한 것부터 이어서
      // 다시 보내지 않게 한다.
      discardPending(0, grid);
      succeeded++;
    }
    setUploadLock(false, grid);
    return { succeeded: succeeded, total: total };
  }

  // ── 저장(PATCH + 새 사진) 및 기록 삭제 ────────────────────────────

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
        window.TakuAPI.commitAndNavigate(submitBtn, VISITS_URL);
        return;
      }

      var outcome = await uploadNewPhotos(recordId, statusEl, grid);
      if (outcome.succeeded === outcome.total) {
        setText(statusEl, "저장 완료. 이동 중...");
        window.TakuAPI.commitAndNavigate(submitBtn, VISITS_URL);
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
          window.TakuAPI.commitAndNavigate(deleteBtn, VISITS_URL);
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
