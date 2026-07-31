/**
 * 굿즈(CollectionItem) 등록·수정·삭제 화면.
 * 이미지 용량·형식, 교환 가능 수량 등은 클라이언트에서도 미리 검사해 빠른
 * 피드백을 주지만 서버 검증이 최종 기준이다. 이미지가 같은 자원의 필드 하나라
 * visit_create.js와 달리 등록+업로드 2단계가 아닌 한 번의 제출로 끝난다.
 */

(function () {
  "use strict";

  var MAX_BYTES = 5 * 1024 * 1024;
  var ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
  var LIST_URL = "/collection/";
  // 접혀 있는 <details> 그룹 안의 필드들 — 이 중 하나라도 서버 오류가
  // 나면 그룹을 다시 펼쳐야 사용자가 오류를 볼 수 있다.
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

  // 되돌릴 수 없는 동작이라 확인을 거친다. 공용 모달이 없으면 기본 confirm으로 대체한다.
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

  // 서버 검증(events/image_validation.py)을 클라이언트에서도 미리 흉내내
  // 흔한 경우는 빠르게 알려준다. 위조된 형식 등 여기서 못 잡는 경우는
  // 서버가 400으로 걸러낸다.
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

  // 등록·수정 화면이 공통으로 쓰는 필드 수집. 이미지, visit_record(등록
  // 화면에만 있음), client_token은 따로 처리한다.
  function collectSharedFields(form) {
    var fields = {
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
    // client_token은 등록 화면에만 있는 숨김 필드(서버가 발급한 uuid4,
    // 중복 제출 방지용)라 이 존재 확인이 수정 화면 PATCH에서 자연히 빠지게
    // 한다. 값이 빈 문자열이면 보내지 않는다 — 빈 값을 보내면 서버가
    // UUIDField 검증에서 400으로 거부하기 때문이다.
    var clientTokenEl = form.elements["client_token"];
    if (clientTokenEl && clientTokenEl.value) { fields.client_token = clientTokenEl.value; }
    return fields;
  }

  function buildFormData(fields, imageFile) {
    var formData = new FormData();
    Object.keys(fields).forEach(function (key) {
      formData.append(key, fields[key]);
    });
    formData.append("image", imageFile);
    return formData;
  }

  // ── 종류 칩(item_type 빠른 선택, 등록+수정) ───────────────────────────

  // 칩은 항상 item_type 텍스트 입력에만 값을 쓴다. 칩을 클릭했든 직접
  // 입력했든 읽는 곳은 collectSharedFields 하나뿐이다.
  function bindTypeChips() {
    var groups = document.querySelectorAll(".collection-form-type-chips");
    for (var i = 0; i < groups.length; i++) {
      (function (group) {
        if (group.dataset.chipsBound) { return; }
        group.dataset.chipsBound = "1";

        var form = group.closest("form");
        if (!form) { return; }
        var input = form.elements["item_type"];
        if (!input) { return; }
        var chips = group.querySelectorAll(".collection-form-type-chip");

        function syncFromValue() {
          var value = input.value;
          for (var j = 0; j < chips.length; j++) {
            var isMatch = chips[j].dataset.typeLabel === value;
            chips[j].classList.toggle("is-active", isMatch);
            chips[j].setAttribute("aria-pressed", isMatch ? "true" : "false");
          }
        }

        for (var k = 0; k < chips.length; k++) {
          chips[k].addEventListener("click", function () {
            input.value = this.dataset.typeLabel;
            syncFromValue();
          });
        }
        input.addEventListener("input", syncFromValue);

        // 입력값이 이미 채워져 있는 경우(수정 화면 초기값, 검증 오류 후
        // 재렌더링)에도 한 번 동기화한다.
        syncFromValue();
      })(groups[i]);
    }
  }

  // ── 이미지 미리보기(등록+수정 드롭존) ─────────────────────────────

  // 마지막으로 만든 object URL을 기억해뒀다가, 파일을 다시 선택하면
  // 이전 것을 해제해 메모리가 새지 않게 한다.
  function bindImagePreview() {
    var input = document.getElementById("collection-image");
    if (!input || input.dataset.previewBound) { return; }
    input.dataset.previewBound = "1";

    var dropzone = input.closest(".collection-form-dropzone");
    if (!dropzone) { return; }
    var placeholder = dropzone.querySelector(".collection-form-dropzone-placeholder");
    var currentUrl = null;

    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) { return; }

      // 제출 핸들러와 같은 검사기를 재사용한다 — 유효하지 않은 파일은
      // 미리보기 없이 제출 시 같은 오류 메시지로 이어진다.
      var errorEl = document.getElementById(
        input.form && input.form.id === "collection-edit-form"
          ? "collection-edit-error"
          : "collection-create-error"
      );
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

  // ── 등록 ──────────────────────────────────────────────────────────────

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

      // 미리 정해진 대상은 숨김 입력, 그 외에는 선택 드롭다운을 쓰지만
      // 둘 다 name="visit_record"를 공유해 이 코드가 양쪽 다 읽는다.
      // "연결 안 함"이면 키 자체를 보내지 않는다 — 빈 문자열은 FK로 유효하지 않다.
      var visitRecordEl = form.elements["visit_record"];
      var visitRecordVal = visitRecordEl ? visitRecordEl.value : "";
      if (visitRecordVal) { fields.visit_record = parseInt(visitRecordVal, 10); }

      // 첫 await 전에 동기적으로 버튼을 비활성화해, 이후 다시 클릭·Enter해도
      // 이미 막힌 상태를 보게 한다.
      window.TakuAPI.setLoading(submitBtn, true);

      var result = imageFile
        ? await window.TakuAPI.upload("/api/collection-items/", buildFormData(fields, imageFile))
        : await window.TakuAPI.post("/api/collection-items/", fields);

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
      openDetailIfErrored(result);
    });
  }

  // ── 수정 ────────────────────────────────────────────────────────────────

  // 항목이 이미 삭제된 것으로 확인된 404 상황에서만 쓴다 — 폼의 모든
  // 컨트롤을 잠가, 어떤 필드를 고쳐도 또 다른 실패한 제출로 이어지지 않게 한다.
  //
  // status.js의 .is-sibling-locked와 달리 bfcache 복원 시 되돌리는 처리를
  // 일부러 두지 않는다. 그 잠금은 요청이 중간에 끊겨서 거는 것이라 복원 시
  // 강제로 풀어야 하지만, 이 잠금은 404로 삭제가 이미 확정된 뒤에만 걸리는
  // 것이라 복원돼도 다시 걸어야 할 확정된 사실은 그대로다. 복원 시 풀어버리면
  // 존재하지 않는 항목에 다시 제출할 길을 열어주는 셈이라 오히려 이 잠금이
  // 막으려는 재시도 루프를 재현한다.
  //
  // 이 보장은 bindEditForm의 404 분기가 이 함수를 부르기 *전에*
  // window.TakuAPI.setLoading(submitBtn, false)로 .is-loading을 먼저 지워야만
  // 성립한다. 그 호출이 없거나 순서가 바뀌면 제출 버튼에 .is-loading이 남아,
  // api.js의 전역 bfcache 복원 처리가 그 버튼만 다시 켜버리고 나머지
  // 컨트롤은 잠긴 채로 남는 불일치가 생긴다(실제로 발견된 사례).
  function lockForm(form) {
    var controls = form.querySelectorAll("input, select, textarea, button");
    for (var i = 0; i < controls.length; i++) {
      controls[i].disabled = true;
      controls[i].classList.add("is-item-gone-locked");
    }
  }

  // 나머지 컨트롤이 모두 비활성화됐으니 유일하게 남은 유효한 동작(목록으로
  // 돌아가기)을 추가하고 포커스를 옮긴다.
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

  // 삭제 버튼은 목록 카드와 수정 화면 둘 다에 있지만 같은 collection.js
  // 하나가 두 곳 모두에 로드되므로, 페이지별로 나누지 않고 한 바인더가
  // 둘 다 처리한다. 성공 후 동작은 다르다 — 목록 카드는 그 자리에서
  // 새로고침, 수정 화면은 목록으로 돌아간다.
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
              window.TakuAPI.commitAndNavigate(btn, LIST_URL);
            } else {
              // 목록 카드 삭제는 새로고침과 같은 효과를 내도록 현재 URL(쿼리
              // 문자열 포함)로 다시 이동한다.
              window.TakuAPI.commitAndNavigate(btn, window.location.href);
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
        window.TakuAPI.commitAndNavigate(submitBtn, "/collection/" + itemId + "/");
        return;
      }

      // 아래 404 분기가 실행되기 전에 반드시 .is-loading을 먼저 지운다
      // (lockForm 위 설명 참고).
      window.TakuAPI.setLoading(submitBtn, false);

      // 이 페이지를 불러온 뒤 다른 곳에서 이미 삭제된 것이 확인된 경우다.
      // 어떤 필드를 고쳐도 존재하지 않는 항목은 수정할 수 없으니, 오류
      // 메시지만 보여주고 계속 재시도하게 두는 대신 폼 전체를 잠근다.
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
    bindTypeChips();
    bindImagePreview();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // 실시간 검색이 목록 페이지의 #archive-results만 교체하고 등록·수정
  // 폼은 그 밖에 있어 영향받지 않는다. 요소별 가드 덕분에 혹시 여기서
  // 다시 호출돼도 중복 연결되지 않는다.
  document.addEventListener("archive:listswapped", function () {
    bindItemDeletes();
    bindTypeChips();
    bindImagePreview();
  });
})();
