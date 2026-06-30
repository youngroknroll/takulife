/**
 * visit.js — Visit record actions for TakuLog
 *
 * Handles:
 *   - Delete visit record via [data-delete-record-id]
 *   - Navigate per-card photo carousels ([data-carousel], loop)
 *
 * Category filter chips are now server-side anchor links (GET ?filter=...).
 * Client-side chip filtering has been removed.
 *
 * Photo add/delete lives on the edit page (visit_edit.js); cards are view-only.
 *
 * Relies on window.TakuAPI (api.js) for all requests:
 *   - JSON actions: TakuAPI.post / TakuAPI.del
 *   - Multipart photo upload: TakuAPI.upload (does NOT set Content-Type)
 *   - 403 disambiguation: TakuAPI.classify → 'auth' → TakuAPI.redirectToLogin()
 *   - Error messages: TakuAPI.formatError
 *
 * All DOM writes use textContent only (no innerHTML with API data).
 */

(function () {
  "use strict";

  // ── DOM helpers ──────────────────────────────────────────────────────────

  function setError(el, message) {
    if (!el) { return; }
    el.textContent = message;
  }

  function clearError(el) {
    if (!el) { return; }
    el.textContent = "";
  }

  // ── 403 handler ──────────────────────────────────────────────────────────

  function handle403(result, errorEl) {
    var kind = window.TakuAPI.classify(result);
    if (kind === "auth") {
      window.TakuAPI.redirectToLogin();
    } else {
      setError(errorEl, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
    }
  }

  // Confirm before a destructive, unrecoverable action. Uses the shared modal
  // (confirm-modal.js, loaded in base.html) with a native confirm() fallback.
  function askConfirm(message) {
    if (typeof window.TakuConfirm === "function") {
      return window.TakuConfirm(message);
    }
    return Promise.resolve(window.confirm(message));
  }

  // ── create visit record ──────────────────────────────────────────────────

  function bindCreateForm() {
    var form = document.getElementById("visit-create-form");
    if (!form) { return; }
    var errorEl = document.getElementById("visit-create-error");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      clearError(errorEl);

      // subject value is "event:<id>" (official) or "personal:<id>" (unofficial)
      var subjectValue = form.elements["subject"].value;
      var visitedOn = form.elements["visited_on"].value;
      var shortReview = form.elements["short_review"].value;

      if (!subjectValue || !visitedOn) {
        setError(errorEl, "대상과 방문 날짜를 모두 입력해 주세요.");
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

      window.TakuAPI.setLoading(submitBtn, true);

      var result = await window.TakuAPI.post("/api/visit-records/", payload);

      if (result.status === 201) {
        window.location.reload();
        return;
      }

      window.TakuAPI.setLoading(submitBtn, false);

      if (result.status === 403) {
        handle403(result, errorEl);
        return;
      }

      if (result.status === 0) {
        setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }

      setError(errorEl, window.TakuAPI.formatError(result));
    });
  }

  // ── per-card photo carousel (view-only, loops) ───────────────────────────

  function bindPhotoCarousels() {
    var carousels = document.querySelectorAll("[data-carousel]");
    for (var i = 0; i < carousels.length; i++) {
      (function (carousel) {
        if (carousel.dataset.carouselBound) { return; }
        carousel.dataset.carouselBound = "1";
        var track = carousel.querySelector(".photo-track");
        var slides = carousel.querySelectorAll(".photo-slide");
        var prev = carousel.querySelector(".carousel-prev");
        var next = carousel.querySelector(".carousel-next");
        var indexEl = carousel.querySelector(".carousel-index");
        if (!track || slides.length < 2 || !prev || !next) { return; }

        var count = slides.length;
        var index = 0;

        function render() {
          track.style.transform = "translateX(-" + (index * 100) + "%)";
          if (indexEl) { indexEl.textContent = String(index + 1); }
        }

        prev.addEventListener("click", function () {
          index = (index - 1 + count) % count;
          render();
        });
        next.addEventListener("click", function () {
          index = (index + 1) % count;
          render();
        });
      })(carousels[i]);
    }
  }

  // ── record delete buttons ────────────────────────────────────────────────

  function bindRecordDeletes() {
    var deleteBtns = document.querySelectorAll("[data-delete-record-id]");
    var globalErrorEl = document.getElementById("visit-global-error");

    for (var i = 0; i < deleteBtns.length; i++) {
      (function (btn) {
        if (btn.dataset.deleteBound) { return; }
        btn.dataset.deleteBound = "1";
        btn.addEventListener("click", async function () {
          var recordId = btn.getAttribute("data-delete-record-id");
          if (
            !(await askConfirm(
              "이 방문 기록을 삭제하시겠습니까? 메모와 사진도 함께 삭제되며 되돌릴 수 없습니다."
            ))
          ) {
            return;
          }
          clearError(globalErrorEl);
          window.TakuAPI.setLoading(btn, true);

          var result = await window.TakuAPI.del(
            "/api/visit-records/" + recordId + "/"
          );

          if (result.status === 204) {
            window.location.reload();
            return;
          }

          window.TakuAPI.setLoading(btn, false);

          if (result.status === 403) {
            handle403(result, globalErrorEl);
            return;
          }

          if (result.status === 404) {
            setError(globalErrorEl, "기록을 찾을 수 없습니다.");
            return;
          }

          if (result.status === 0) {
            setError(globalErrorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
            return;
          }

          setError(globalErrorEl, "기록 삭제 중 오류가 발생했습니다.");
        });
      })(deleteBtns[i]);
    }
  }

  // ── init ─────────────────────────────────────────────────────────────────

  function init() {
    bindCreateForm();
    bindPhotoCarousels();
    bindRecordDeletes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Live search swaps the results fragment: re-wire the new cards' photo
  // carousels and delete buttons. The create form lives outside the swap
  // region, so it is left alone; the per-element guards keep this idempotent.
  document.addEventListener("archive:listswapped", function () {
    bindPhotoCarousels();
    bindRecordDeletes();
  });
})();
