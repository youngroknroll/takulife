/**
 * 스태프의 드래프트 등록·수정·승인·반려 동작.
 * 원문 보기 토글은 hidden 속성만 바꿀 뿐 raw_text 내용을 직접 읽거나
 * 쓰지 않아 XSS 위험이 없다.
 * 스태프 전용 페이지의 403은 세션 만료나 보안 토큰 오류를 뜻하므로
 * 로그인 페이지로 보내지 않고 오류 메시지만 보여준다.
 */

(function () {
  "use strict";

  /* ── 헬퍼 ──────────────────────────────────────────────────────────── */

  function showError(container, message) {
    if (!container) {
      return;
    }
    container.textContent = message;
    container.hidden = false;
    container.focus();
  }

  function hideError(container) {
    if (!container) {
      return;
    }
    container.textContent = "";
    container.hidden = true;
  }

  // 공용 모달이 없으면 기본 confirm으로 대체한다.
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  /* ── 403 메시지(세션 만료/CSRF) ──────────────────────────────── */

  var CSRF_OR_SESSION_MSG =
    "403 오류: 세션이 만료되었거나 보안 토큰이 유효하지 않습니다. " +
    "페이지를 새로고침한 뒤 다시 시도해 주세요.";

  /* ── 등록 폼 ──────────────────────────────────────────────────────── */

  function bindCreateForm() {
    var form = document.getElementById("draft-create-form");
    if (!form) {
      return;
    }
    var errorEl = document.getElementById("draft-create-error");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", function (evt) {
      evt.preventDefault();
      hideError(errorEl);

      var urlInput = document.getElementById("draft-url");
      var nameInput = document.getElementById("draft-source-name");
      var sourceUrl = urlInput ? urlInput.value.trim() : "";
      var sourceName = nameInput ? nameInput.value.trim() : "";

      if (!sourceUrl) {
        showError(errorEl, "URL을 입력해 주세요.");
        return;
      }

      window.TakuAPI.setLoading(submitBtn, true);

      window.TakuAPI.post("/api/event-drafts/", {
        source_url: sourceUrl,
        source_name: sourceName,
      }).then(function (result) {
        if (result.ok) {
          // 새로고침과 같은 효과를 내도록 현재 URL로 다시 이동한다.
          // submitBtn을 일부러 진행 중 상태(.is-loading)로 남겨둔다 —
          // bfcache 복원 시 api.js가 이 표시를 찾아야 강제 이동 처리가 동작한다.
          window.TakuAPI.commitAndNavigate(submitBtn, window.location.href);
          return;
        }
        window.TakuAPI.setLoading(submitBtn, false);
        if (result.status === 403) {
          showError(errorEl, CSRF_OR_SESSION_MSG);
          return;
        }
        showError(errorEl, window.TakuAPI.formatError(result));
      });
    });
  }

  /* ── 수정 폼 ────────────────────────────────────────────────────────── */

  function bindEditForm() {
    var form = document.getElementById("draft-edit-form");
    if (!form) {
      return;
    }
    var errorEl = document.getElementById("draft-edit-error");
    var submitBtn = form.querySelector('[type="submit"]');
    var draftId = form.dataset.draftId;

    form.addEventListener("submit", function (evt) {
      evt.preventDefault();
      hideError(errorEl);

      var payload = {};

      var sourceNameEl = form.querySelector('[name="source_name"]');
      if (sourceNameEl) {
        payload.source_name = sourceNameEl.value;
      }

      var titleEl = form.querySelector('[name="extracted_title"]');
      if (titleEl) {
        payload.extracted_title = titleEl.value;
      }

      var categoryEl = form.querySelector('[name="extracted_category"]');
      if (categoryEl) {
        payload.extracted_category = categoryEl.value;
      }

      var workEl = form.querySelector('[name="extracted_work_title"]');
      if (workEl) {
        payload.extracted_work_title = workEl.value;
      }

      var locationEl = form.querySelector('[name="extracted_location_name"]');
      if (locationEl) {
        payload.extracted_location_name = locationEl.value;
      }

      var regionEl = form.querySelector('[name="extracted_region"]');
      if (regionEl) {
        payload.extracted_region = regionEl.value;
      }

      var startEl = form.querySelector('[name="extracted_start_date"]');
      if (startEl) {
        payload.extracted_start_date = startEl.value || null;
      }

      var endEl = form.querySelector('[name="extracted_end_date"]');
      if (endEl) {
        payload.extracted_end_date = endEl.value || null;
      }

      var summaryEl = form.querySelector('[name="extracted_summary"]');
      if (summaryEl) {
        payload.extracted_summary = summaryEl.value;
      }

      window.TakuAPI.setLoading(submitBtn, true);

      window.TakuAPI.patch("/api/event-drafts/" + draftId + "/", payload).then(
        function (result) {
          if (result.ok) {
            // 새로고침과 같은 효과를 내도록 현재 URL로 다시 이동한다.
            // submitBtn을 일부러 진행 중 상태(.is-loading)로 남겨둔다 —
            // bfcache 복원 시 api.js가 이 표시를 찾아야 강제 이동 처리가 동작한다.
            window.TakuAPI.commitAndNavigate(submitBtn, window.location.href);
            return;
          }
          window.TakuAPI.setLoading(submitBtn, false);
          if (result.status === 403) {
            showError(errorEl, CSRF_OR_SESSION_MSG);
            return;
          }
          showError(errorEl, window.TakuAPI.formatError(result));
        }
      );
    });
  }

  /* ── 승인 버튼 ───────────────────────────────────────────────────── */

  function bindApproveButton() {
    var btn = document.getElementById("draft-approve-btn");
    if (!btn) {
      return;
    }
    var errorEl = document.getElementById("draft-action-error");
    var successEl = document.getElementById("draft-approve-success");
    var draftId = btn.dataset.draftId;
    var rejectBtn = document.getElementById("draft-reject-btn");
    var listUrlEl = btn.closest("[data-list-url]");
    var listUrl = listUrlEl ? listUrlEl.dataset.listUrl : "/staff/drafts/";

    btn.addEventListener("click", async function () {
      var confirmed = await askConfirm(
        "승인하고 게시하면 공개 이벤트 목록에 노출됩니다. 진행할까요?"
      );
      if (!confirmed) {
        return;
      }
      hideError(errorEl);
      window.TakuAPI.setLoading(btn, true);

      window.TakuAPI.post(
        "/staff/drafts/" + draftId + "/approve/",
        {}
      ).then(function (result) {
        window.TakuAPI.setLoading(btn, false);
        if (result.ok) {
          if (successEl) {
            var eventId = result.data && result.data.event_id;
            successEl.textContent = "승인 완료. ";
            if (eventId) {
              var eventLink = document.createElement("a");
              eventLink.href = "/events/" + eventId + "/";
              eventLink.textContent = "이벤트 #" + eventId + " 보기";
              successEl.appendChild(eventLink);
              successEl.appendChild(document.createTextNode(" · "));
            }
            var listLink = document.createElement("a");
            listLink.href = listUrl;
            listLink.textContent = "목록으로 돌아가기";
            successEl.appendChild(listLink);
            successEl.hidden = false;
            // 아래에서 버튼을 비활성화하기 전에 여기로 포커스를 옮긴다 —
            // 포커스를 가진 요소가 비활성화되면 알림 없이 body로 밀려난다.
            successEl.focus();
          }
          // 성공 시 새로고침하지 않으므로, 이미 승인된 드래프트가 다시
          // 제출되지 않도록 두 검토 버튼을 모두 비활성화한다.
          btn.disabled = true;
          if (rejectBtn) {
            rejectBtn.disabled = true;
          }
          return;
        }
        if (result.status === 403) {
          showError(errorEl, CSRF_OR_SESSION_MSG);
          return;
        }
        showError(errorEl, window.TakuAPI.formatError(result));
      });
    });
  }

  /* ── 반려 버튼 ────────────────────────────────────────────────────── */

  function bindRejectButton() {
    var btn = document.getElementById("draft-reject-btn");
    if (!btn) {
      return;
    }
    var errorEl = document.getElementById("draft-action-error");
    var draftId = btn.dataset.draftId;
    var reasonEl = document.getElementById("draft-reject-reason");
    var listUrlEl = btn.closest("[data-list-url]");
    var listUrl = listUrlEl ? listUrlEl.dataset.listUrl : "/staff/drafts/";

    btn.addEventListener("click", async function () {
      var confirmed = await askConfirm(
        "이 드래프트를 반려할까요? 공개 목록에는 노출되지 않습니다."
      );
      if (!confirmed) {
        return;
      }
      hideError(errorEl);
      window.TakuAPI.setLoading(btn, true);

      var rejectionReason = reasonEl ? reasonEl.value.trim() : "";

      window.TakuAPI.post(
        "/staff/drafts/" + draftId + "/reject/",
        { rejection_reason: rejectionReason }
      ).then(function (result) {
        if (result.ok) {
          // btn을 일부러 진행 중 상태(.is-loading)로 남겨둔다 — bfcache
          // 복원 시 api.js가 이 표시를 찾아야 강제 이동 처리가 동작한다.
          window.TakuAPI.commitAndNavigate(btn, listUrl);
          return;
        }
        window.TakuAPI.setLoading(btn, false);
        if (result.status === 403) {
          showError(errorEl, CSRF_OR_SESSION_MSG);
          return;
        }
        showError(errorEl, window.TakuAPI.formatError(result));
      });
    });
  }

  /* ── 원문 보기 토글 ─────────────────────────────────────────────────── */

  function bindRawTextToggle() {
    var btn = document.getElementById("raw-text-toggle");
    if (!btn) {
      return;
    }
    var truncatedEl = document.getElementById("raw-text-truncated");
    var fullEl = document.getElementById("raw-text-full");
    if (!truncatedEl || !fullEl) {
      return;
    }

    btn.addEventListener("click", function () {
      var isExpanded = btn.getAttribute("data-expanded") === "true";
      var expand = !isExpanded;

      // hidden 속성만 바꾼다 — JS는 raw_text 내용을 건드리지 않는다.
      truncatedEl.hidden = expand;
      fullEl.hidden = !expand;

      btn.setAttribute("data-expanded", String(expand));
      btn.setAttribute("aria-expanded", String(expand));
      btn.textContent = expand ? "접기" : "전체 보기";
    });
  }

  /* ── 초기화 ─────────────────────────────────────────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    bindCreateForm();
    bindEditForm();
    bindApproveButton();
    bindRejectButton();
    bindRawTextToggle();
  });
})();
