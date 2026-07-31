/**
 * 방문 기록 작성 페이지. 사진을 먼저 미리보기로 골라두고(첫 장이 대표),
 * 기록을 먼저 POST로 만든 뒤 사진을 한 장씩 순서대로 업로드한다.
 * 모두 성공하면 목록으로 이동하고, 일부만 실패하면 기록과 성공한 사진은
 * 그대로 저장된 채 사용자가 목록에서 나머지를 마저 추가할 수 있게 안내한다.
 * 형식·용량 검사는 서버와 동일하게 클라이언트에서도 미리 해 빠른 피드백을 준다.
 */

(function () {
  "use strict";

  var MAX_PHOTOS = 5;
  var MAX_BYTES = 5 * 1024 * 1024;
  var ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
  var VISITS_URL = "/archive/visits/";

  // pendingItems: 업로드 대기열의 단일 진실 공급원 [{ file, url }]
  var pendingItems = [];
  // uploadAll이 요청을 보내는 동안 true. 업로드 중에 그리드가 다시
  // 그려져도 삭제 버튼이 비활성화 상태로 태어나게 한다 — 그렇지 않으면
  // 진행 중인 인덱스보다 앞의 항목을 삭제했을 때 배열이 밀려, 재시도
  // 없이 뒤에 남은 항목을 조용히 건너뛸 수 있다.
  var uploadLocked = false;

  // ── DOM 헬퍼 ────────────────────────────────────────────────────────────

  function setText(el, message) {
    if (el) { el.textContent = message; }
  }

  function handle403(result, errorEl) {
    var kind = window.TakuAPI.classify(result);
    if (kind === "auth") {
      window.TakuAPI.redirectToLogin();
    } else {
      setText(errorEl, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
    }
  }

  // ── 미리보기 그리드 ───────────────────────────────────────────────────────────

  function updateTrigger() {
    var trigger = document.getElementById("visit-photos-trigger");
    if (trigger) { trigger.hidden = pendingItems.length >= MAX_PHOTOS; }
  }

  function renderGrid(grid) {
    // 기존 타일만 지우고 URL은 해제하지 않는다(pendingItems에 그대로 남아 있다).
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
      remove.disabled = uploadLocked;
      remove.addEventListener("click", function () {
        removeAt(index, grid);
      });
      tile.appendChild(remove);

      grid.appendChild(tile);
    });
  }

  // 업로드 중 pendingItems를 바꿀 수 있는 모든 컨트롤(추가 버튼, 파일
  // 입력, 삭제 버튼)을 한꺼번에 잠그거나 푼다.
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

  function removeAt(index, grid) {
    var removed = pendingItems.splice(index, 1)[0];
    if (removed) { URL.revokeObjectURL(removed.url); }
    renderGrid(grid);

    // 포커스가 body로 떨어지지 않도록 근처의 다른 컨트롤로 옮긴다.
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

  // ── 사진 순차 업로드 ────────────────────────────────────────────────

  async function uploadOne(recordId, file) {
    var formData = new FormData();
    formData.append("image", file);
    return window.TakuAPI.upload(
      "/api/visit-records/" + recordId + "/photos/",
      formData
    );
  }

  async function uploadAll(recordId, statusEl, grid) {
    var total = pendingItems.length;
    var succeeded = 0;

    setUploadLock(true, grid);
    for (var i = 0; i < pendingItems.length; i++) {
      setText(statusEl, "사진 업로드 중 (" + (i + 1) + "/" + total + ")...");
      var result = await uploadOne(recordId, pendingItems[i].file);
      if (result.status === 201) {
        succeeded += 1;
      } else {
        setUploadLock(false, grid);
        return { succeeded: succeeded, total: total, failedAt: i };
      }
    }
    setUploadLock(false, grid);
    return { succeeded: succeeded, total: total, failedAt: -1 };
  }

  // ── 등록 + 전체 흐름 조율 ───────────────────────────────────────────────────────

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
        // 값을 비워둬야 같은 파일을 다시 선택해도 change 이벤트가 또 발생한다.
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
      // client_token은 서버가 발급한 숨김 필드(중복 제출 방지용)다. 값이
      // 있을 때만 보낸다 — 빈 문자열을 보내면 서버 UUIDField 검증에서
      // 400으로 거부되기 때문이다.
      var clientTokenEl = form.elements["client_token"];
      if (clientTokenEl && clientTokenEl.value) { payload.client_token = clientTokenEl.value; }

      // 사진별 client_token은 두지 않는다 — 이 페이지는 사진 업로드가
      // 실패해도 같은 폼으로 돌아가 재시도하는 경로가 없어 보호할 대상이 없다.

      window.TakuAPI.setLoading(submitBtn, true);
      setText(statusEl, "기록 저장 중...");

      var result = await window.TakuAPI.post("/api/visit-records/", payload);

      if (result.status !== 201) {
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

      // 기록이 이미 만들어졌으니 다시 제출하면 중복이 생긴다. 버튼은 잠근 채로 둔다.
      var recordId = result.data && result.data.id;

      if (pendingItems.length === 0 || !recordId) {
        window.TakuAPI.commitAndNavigate(submitBtn, VISITS_URL);
        return;
      }

      var outcome = await uploadAll(recordId, statusEl, grid);

      if (outcome.failedAt === -1) {
        setText(statusEl, "저장 완료. 이동 중...");
        window.TakuAPI.commitAndNavigate(submitBtn, VISITS_URL);
        return;
      }

      // 부분 성공: 기록과 성공한 사진은 저장됐다. 조용히 이동시키지 않고
      // 결과를 보여준 뒤 사용자가 직접 계속하게 한다.
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
