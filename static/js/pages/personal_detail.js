/**
 * personal_detail.js — PersonalEntry (비공식 장소) read-only detail page
 * (archive_personal_detail).
 *
 * Responsibilities:
 *   - Entry delete: DELETE /api/personal-entries/<id>/
 *   - 공식 제보 토글/제출: POST /api/personal-entries/<id>/promote/
 *     (personal_entries.js와 동일 로직 — 이 페이지엔 인스턴스가 1개뿐이라
 *     루프 없이 단일 바인딩으로 이식)
 *
 * 찜/상태 버튼은 base.html이 전역 로드하는 status.js가 자동으로 바인딩한다
 * (personal_entries.html의 목록 카드와 동일한 data-* 계약) — 이 파일은
 * 건드리지 않는다.
 *
 * 404 잠금 캐스케이드(BIR 핵심 계약): 삭제 요청이 "이미 삭제됨"을 확인하면
 * 찜·상태·제보·방문기록 CTA(인플로우 + 모바일 고정 바)·수정 링크까지
 * 5종 이상을 함께 잠근다 — 형제(collection_detail.js)는 수정 링크 1개만
 * 잠갔지만, 이 페이지는 핵심 루프 CTA(방문 기록 남기기)까지 살아있으면
 * 이미 사라진 항목에 두 번째 막다른 골목을 만든다. 상단 "← 직접 등록
 * 목록으로" 링크는 이미 살아있는 정적 링크이므로 새로 만들지 않고
 * `.focus()`만 이동한다.
 */

(function () {
  "use strict";

  var LIST_URL = "/archive/personal/";

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

  // ── 404 잠금 캐스케이드 ──────────────────────────────────────────────

  // A settled fact (the item is gone), not an interrupted in-flight request
  // — deliberately not .is-loading, matching collection_detail.js's
  // lockEditLink precedent (api.js's global pageshow handler only restores
  // .is-loading, which this lock must survive across a bfcache round trip).
  function lockLink(link) {
    if (!link) { return; }
    link.removeAttribute("href");
    link.setAttribute("aria-disabled", "true");
    link.classList.add("is-item-gone-locked");
    link.addEventListener("click", function (evt) {
      evt.preventDefault();
    });
  }

  function lockButton(button) {
    if (!button) { return; }
    button.disabled = true;
    button.classList.add("is-item-gone-locked");
  }

  function lockPageForGoneEntry() {
    // 문구를 이 함수가 단독 소유한다 — 세 호출처(삭제/제보 404, 찜·상태
    // 실패) 중 어디로 들어와도 같은 문구가 같은 자리(전역 배너)에 뜬다.
    // 제보 분기는 과거 폼 내부 오류 요소에 썼지만, 이 함수가 그 폼을
    // hidden 처리하므로 문구도 함께 사라졌었다.
    setText(
      document.getElementById("personal-detail-global-error"),
      "이미 삭제된 항목입니다."
    );
    lockButton(document.querySelector("[data-interest-toggle]"));
    lockButton(document.querySelector("[data-status-action]"));
    lockButton(document.querySelector("[data-promote-toggle]"));
    lockButton(document.querySelector("[data-delete-entry-id]"));
    // The expanded 제보 form (if open) has nothing left to submit to.
    var promoteForm = document.querySelector("[data-promote-form]");
    if (promoteForm) { promoteForm.hidden = true; }
    lockLink(document.querySelector(".personal-detail-visit-cta"));
    lockLink(document.querySelector(".personal-detail-cta-bar a"));
    lockLink(document.querySelector(".personal-detail-edit-link"));

    var backLink = document.querySelector(".personal-detail-back-link");
    if (backLink) { backLink.focus(); }
  }

  // ── 찜·상태 실패 → 잠금 캐스케이드 트리거 ────────────────────────────
  // status.js는 공유 모듈이라 "이 항목이 사라졌는지"를 모른다 — 그래서
  // 원시 result를 이벤트로만 흘려보내고, 판단은 이 페이지가 한다.
  // 판단 규칙: 404(notfound)이거나, 400이면서 응답 바디에 personal_entry
  // 필드 오류가 있는 경우(PrimaryKeyRelatedField가 없는 pk를 검증 실패로
  // 처리해 404 대신 400을 낸다). 한국어 오류 문구는 i18n/DRF 메시지 변경에
  // 깨지므로 필드 이름으로만 판단한다.
  function isGoneEntryFailure(result) {
    if (!result) { return false; }
    if (result.status === 404) { return true; }
    return (
      result.status === 400 &&
      result.data &&
      Object.prototype.hasOwnProperty.call(result.data, "personal_entry")
    );
  }

  function bindStatusFailureCascade() {
    document.addEventListener("status:request-failed", function (evt) {
      var result = evt.detail && evt.detail.result;
      if (!isGoneEntryFailure(result)) { return; }
      // 공유 모듈이 이미 붙인 인라인 오류는 DRF 원문(pk 유효성 메시지)이라
      // 사용자에게 혼란스럽다 — 제거하고 전역 배너로 대체한다.
      document.querySelectorAll(".status-inline-error").forEach(function (el) {
        el.remove();
      });
      // 문구는 lockPageForGoneEntry()가 전역 배너에 쓴다.
      lockPageForGoneEntry();
    });
  }

  // ── 삭제 ─────────────────────────────────────────────────────────────

  function bindDelete() {
    var deleteBtn = document.querySelector("[data-delete-entry-id]");
    if (!deleteBtn) { return; }

    var entryId = deleteBtn.getAttribute("data-delete-entry-id");
    var globalErrorEl = document.getElementById("personal-detail-global-error");

    deleteBtn.addEventListener("click", async function () {
      if (
        !(await askConfirm(
          "이 항목을 삭제하시겠습니까? 연결된 찜·상태·방문 기록도 함께 삭제됩니다."
        ))
      ) {
        return;
      }
      setText(globalErrorEl, "");
      // Synchronous disable before the first await — a second click arriving
      // while the request is in flight finds the button already disabled.
      window.TakuAPI.setLoading(deleteBtn, true);

      var result = await window.TakuAPI.del("/api/personal-entries/" + entryId + "/");
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
        // 문구는 lockPageForGoneEntry()가 전역 배너에 쓴다.
        lockPageForGoneEntry();
        return;
      }
      if (result.status === 0) {
        setText(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }
      setText(globalErrorEl, "삭제 중 오류가 발생했습니다.");
    });
  }

  // ── 공식 제보 (personal_entries.js와 동일 로직, 단일 인스턴스) ────────

  function bindPromote() {
    var toggle = document.querySelector("[data-promote-toggle]");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var id = toggle.getAttribute("data-promote-toggle");
        var form = document.querySelector('[data-promote-form="' + id + '"]');
        if (!form) { return; }
        var nowHidden = !form.hidden;
        form.hidden = nowHidden;
        toggle.setAttribute("data-expanded", String(!nowHidden));
        toggle.setAttribute("aria-expanded", String(!nowHidden));
        if (!nowHidden) {
          var input = form.querySelector('input[name="official_url"]');
          if (input) { input.focus(); }
        }
      });
    }

    var form = document.querySelector("[data-promote-form]");
    if (!form) { return; }
    var id = form.getAttribute("data-promote-form");
    var errorEl = document.querySelector('[data-promote-error="' + id + '"]');
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      setText(errorEl, "");

      var urlInput = form.elements["official_url"];
      var officialUrl = urlInput.value.trim();
      if (!officialUrl) {
        setText(errorEl, "공식 URL을 입력해 주세요.");
        urlInput.focus();
        return;
      }

      window.TakuAPI.setLoading(submitBtn, true);

      var result = await window.TakuAPI.post(
        "/api/personal-entries/" + id + "/promote/",
        { official_url: officialUrl }
      );

      if (result.status === 201) {
        // 제보 성공 → 목록이 아니라 같은 상세 URL로 리로드(서버가 배지 상태를
        // 다시 그린다).
        window.TakuAPI.commitAndNavigate(submitBtn, window.location.href);
        return;
      }

      window.TakuAPI.setLoading(submitBtn, false);

      if (result.status === 403) {
        handle403(result, errorEl);
        return;
      }
      if (result.status === 404) {
        // 폼 내부 오류 요소가 아니라 lockPageForGoneEntry()가 전역
        // 배너에 문구를 쓴다 — 이 폼 자체가 곧 hidden 처리되기 때문.
        lockPageForGoneEntry();
        return;
      }
      if (result.status === 409) {
        setText(errorEl, "이미 공식 제보된 항목입니다.");
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
    bindDelete();
    bindPromote();
    bindStatusFailureCascade();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
