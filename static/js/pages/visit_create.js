/**
 * visit_create.js — Dedicated visit-record write page (archive_visit_create).
 *
 * Flow (Option A — no backend change, reuses existing APIs):
 *   1. Select photos → client-side preview grid (URL.createObjectURL),
 *      remove-before-submit, first photo = 대표 (cover).
 *   2. Submit → POST /api/visit-records/ (JSON) → read new record id.
 *   3. Sequentially upload each queued photo to
 *      POST /api/visit-records/<id>/photos/ (multipart).
 *   4. All photos OK → redirect to /archive/visits/. Partial failure leaves
 *      the saved record + successful photos; user finishes per-card on the list.
 *
 * Client guards mirror the server (JPEG/PNG/WebP, 5MB each, max 10) for fast
 * feedback; the server remains the source of truth.
 */

(function () {
  "use strict";

  var MAX_PHOTOS = 5;
  var MAX_BYTES = 5 * 1024 * 1024;
  var ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
  var VISITS_URL = "/archive/visits/";

  // pendingItems: [{ file, url }] — single source of truth for the queue.
  var pendingItems = [];

  // ── DOM helpers ────────────────────────────────────────────────────────────

  function setText(el, message) {
    if (el) { el.textContent = message; }
  }

  function handle403(result, errorEl) {
    var kind = window.OshiAPI.classify(result);
    if (kind === "auth") {
      window.OshiAPI.redirectToLogin();
    } else {
      setText(errorEl, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
    }
  }

  // ── preview grid ───────────────────────────────────────────────────────────

  function updateTrigger() {
    var trigger = document.getElementById("visit-photos-trigger");
    if (trigger) { trigger.hidden = pendingItems.length >= MAX_PHOTOS; }
  }

  function renderGrid(grid) {
    // Clear existing tiles and revoke nothing here (urls persist in pendingItems).
    grid.textContent = "";
    updateTrigger();

    if (pendingItems.length === 0) {
      grid.hidden = true;
      return;
    }
    grid.hidden = false;

    pendingItems.forEach(function (item, index) {
      var tile = document.createElement("div");
      tile.className = "photo-preview-tile" + (index === 0 ? " is-cover" : "");

      var img = document.createElement("img");
      img.src = item.url;
      img.alt = "미리보기 " + (index + 1);
      tile.appendChild(img);

      if (index === 0) {
        var badge = document.createElement("span");
        badge.className = "photo-preview-cover-badge";
        badge.textContent = "대표";
        tile.appendChild(badge);
      }

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "photo-preview-remove";
      remove.textContent = "×";
      remove.setAttribute("aria-label", "제거: " + item.file.name);
      remove.addEventListener("click", function () {
        removeAt(index, grid);
      });
      tile.appendChild(remove);

      grid.appendChild(tile);
    });
  }

  function removeAt(index, grid) {
    var removed = pendingItems.splice(index, 1)[0];
    if (removed) { URL.revokeObjectURL(removed.url); }
    renderGrid(grid);

    // Move focus to a sensible neighbor rather than letting it fall to <body>.
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

      if (pendingItems.length >= MAX_PHOTOS) {
        setText(errorEl, "사진은 최대 " + MAX_PHOTOS + "장까지 첨부할 수 있습니다.");
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
      if (isDuplicate(file)) {
        continue;
      }
      pendingItems.push({ file: file, url: URL.createObjectURL(file) });
    }

    if (rejected.length > 0) {
      setText(errorEl, "일부 사진은 제외됐습니다: " + rejected.join(", "));
    }
    renderGrid(grid);
  }

  // ── sequential photo upload ────────────────────────────────────────────────

  async function uploadOne(recordId, file) {
    var formData = new FormData();
    formData.append("image", file);
    return window.OshiAPI.upload(
      "/api/visit-records/" + recordId + "/photos/",
      formData
    );
  }

  async function uploadAll(recordId, statusEl) {
    var total = pendingItems.length;
    var succeeded = 0;

    for (var i = 0; i < pendingItems.length; i++) {
      setText(statusEl, "사진 업로드 중 (" + (i + 1) + "/" + total + ")...");
      var result = await uploadOne(recordId, pendingItems[i].file);
      if (result.status === 201) {
        succeeded += 1;
      } else {
        return { succeeded: succeeded, total: total, failedAt: i };
      }
    }
    return { succeeded: succeeded, total: total, failedAt: -1 };
  }

  // ── create + orchestrate ───────────────────────────────────────────────────

  function bindForm() {
    var form = document.getElementById("visit-create-form");
    if (!form) { return; }

    var errorEl = document.getElementById("visit-create-error");
    var statusEl = document.getElementById("visit-create-status");
    var grid = document.getElementById("photo-preview-grid");
    var fileInput = document.getElementById("visit-photos");
    var triggerBtn = document.getElementById("visit-photos-trigger");
    var submitBtn = form.querySelector('[type="submit"]');

    if (fileInput && grid) {
      fileInput.addEventListener("change", function () {
        addFiles(fileInput.files, grid, errorEl);
        // Reset so re-selecting the same file (or adding more) fires change again.
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

      var subjectValue = form.elements["subject"].value;
      var visitedOn = form.elements["visited_on"].value;
      var shortReview = form.elements["short_review"].value;

      if (!subjectValue || !visitedOn) {
        setText(errorEl, "대상과 방문 날짜를 모두 입력해 주세요.");
        return;
      }

      var sep = subjectValue.indexOf(":");
      var subjectType = subjectValue.slice(0, sep);
      var subjectId = parseInt(subjectValue.slice(sep + 1), 10);

      var payload = { visited_on: visitedOn, short_review: shortReview };
      if (subjectType === "personal") {
        payload.personal_entry = subjectId;
      } else {
        payload.event = subjectId;
      }

      window.OshiAPI.setLoading(submitBtn, true);
      setText(statusEl, "기록 저장 중...");

      var result = await window.OshiAPI.post("/api/visit-records/", payload);

      if (result.status !== 201) {
        window.OshiAPI.setLoading(submitBtn, false);
        setText(statusEl, "");
        if (result.status === 403) {
          handle403(result, errorEl);
        } else if (result.status === 0) {
          setText(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        } else {
          setText(errorEl, window.OshiAPI.formatError(result));
        }
        return;
      }

      // Record created — never resubmit (would duplicate). Keep button locked.
      var recordId = result.data && result.data.id;

      if (pendingItems.length === 0 || !recordId) {
        window.location.assign(VISITS_URL);
        return;
      }

      var outcome = await uploadAll(recordId, statusEl);

      if (outcome.failedAt === -1) {
        setText(statusEl, "저장 완료. 이동 중...");
        window.location.assign(VISITS_URL);
        return;
      }

      // Partial success: record + successful photos are saved. Don't redirect
      // silently — let the user read the result, then continue on the list.
      setText(
        statusEl,
        "기록은 저장됐고 사진 " + outcome.succeeded + "/" + outcome.total +
          "장 업로드됐습니다. 나머지는 방문 기록 목록에서 카드별로 추가할 수 있습니다."
      );
      setText(errorEl, "");
      revealContinueLink(form);
    });
  }

  function revealContinueLink(form) {
    if (document.getElementById("visit-continue-link")) { return; }
    var link = document.createElement("a");
    link.id = "visit-continue-link";
    link.className = "record-cta";
    link.href = VISITS_URL;
    link.textContent = "방문 기록 목록으로 이동";
    form.appendChild(link);
    link.focus();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindForm);
  } else {
    bindForm();
  }
})();
