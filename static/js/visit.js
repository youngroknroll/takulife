/**
 * visit.js — Visit record actions for TakuLog
 *
 * Handles:
 *   - Create visit record via form#visit-create-form
 *   - Upload photo via per-card file input + upload button
 *   - Delete visit record via [data-delete-record-id]
 *   - Delete photo via [data-photo-id][data-record-id] on photo-delete-btn
 *
 * Relies on window.TakuAPI (api.js) for JSON POST/DELETE with CSRF.
 * Photo upload uses a local multipart fetch (FormData) because api.js sends
 * Content-Type: application/json — multipart must NOT set Content-Type manually.
 *
 * All DOM writes use textContent only (no innerHTML with API data).
 * 403 disambiguation: "Authentication credentials" in detail → login redirect;
 * any other 403 → inline CSRF message, no redirect loop.
 */

(function () {
  "use strict";

  var LOGIN_URL = "/accounts/login/";

  // ── helpers ─────────────────────────────────────────────────────────────

  function currentPath() {
    return window.location.pathname + window.location.search;
  }

  function redirectToLogin() {
    window.location.assign(LOGIN_URL + "?next=" + encodeURIComponent(currentPath()));
  }

  function csrfToken() {
    // Reuse TakuAPI's getCookie when available; fall back to inline read.
    if (window.TakuAPI && typeof window.TakuAPI.getCookie === "function") {
      return window.TakuAPI.getCookie("csrftoken");
    }
    var prefix = "csrftoken=";
    for (var part of document.cookie.split(";")) {
      var trimmed = part.trim();
      if (trimmed.startsWith(prefix)) {
        return decodeURIComponent(trimmed.slice(prefix.length));
      }
    }
    return "";
  }

  function isAuthError(data) {
    return (
      data &&
      typeof data.detail === "string" &&
      data.detail.indexOf("Authentication credentials") !== -1
    );
  }

  function handle403(data, errorEl) {
    if (isAuthError(data)) {
      redirectToLogin();
    } else {
      setError(errorEl, "보안 토큰 오류입니다. 새로고침 후 다시 시도해 주세요.");
    }
  }

  function setError(el, message) {
    if (!el) { return; }
    el.textContent = message;
  }

  function clearError(el) {
    if (!el) { return; }
    el.textContent = "";
  }

  function formatFieldErrors(data) {
    if (!data || typeof data !== "object") { return "알 수 없는 오류가 발생했습니다."; }
    var parts = [];
    for (var key in data) {
      if (!Object.prototype.hasOwnProperty.call(data, key)) { continue; }
      var val = data[key];
      var msg = Array.isArray(val) ? val.join(" ") : String(val);
      if (key === "detail") {
        parts.unshift(msg);
      } else {
        parts.push(key + ": " + msg);
      }
    }
    return parts.length > 0 ? parts.join(" | ") : "요청을 처리할 수 없습니다.";
  }

  // ── multipart photo upload (cannot use api.js — must not set Content-Type) ──

  async function uploadPhoto(recordId, file, errorEl) {
    var formData = new FormData();
    formData.append("image", file);
    var response;
    try {
      response = await fetch("/api/visit-records/" + recordId + "/photos/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": csrfToken(),
        },
        body: formData,
      });
    } catch (_networkErr) {
      setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
      return;
    }

    if (response.status === 201) {
      window.location.reload();
      return;
    }

    var data = null;
    var contentType = response.headers.get("content-type") || "";
    if (contentType.indexOf("application/json") !== -1) {
      data = await response.json();
    }

    if (response.status === 403) {
      handle403(data, errorEl);
      return;
    }

    if (response.status === 400) {
      if (data && data.code === "photo_limit_exceeded") {
        setError(errorEl, "사진은 기록당 최대 10장까지 첨부할 수 있습니다.");
      } else {
        setError(errorEl, formatFieldErrors(data));
      }
      return;
    }

    if (response.status === 404) {
      setError(errorEl, "해당 방문 기록을 찾을 수 없습니다.");
      return;
    }

    setError(errorEl, "업로드 중 오류가 발생했습니다. 다시 시도해 주세요.");
  }

  // ── create visit record ──────────────────────────────────────────────────

  function bindCreateForm() {
    var form = document.getElementById("visit-create-form");
    if (!form) { return; }
    var errorEl = document.getElementById("visit-create-error");

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      clearError(errorEl);

      var eventId = parseInt(form.elements["event"].value, 10);
      var visitedOn = form.elements["visited_on"].value;
      var shortReview = form.elements["short_review"].value;

      if (!eventId || !visitedOn) {
        setError(errorEl, "행사와 방문 날짜를 모두 입력해 주세요.");
        return;
      }

      var result = await window.TakuAPI.post("/api/visit-records/", {
        event: eventId,
        visited_on: visitedOn,
        short_review: shortReview,
      });

      if (result.status === 201) {
        window.location.reload();
        return;
      }

      if (result.status === 403) {
        handle403(result.data, errorEl);
        return;
      }

      if (result.status === 0) {
        setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
        return;
      }

      setError(errorEl, formatFieldErrors(result.data));
    });
  }

  // ── photo upload buttons ─────────────────────────────────────────────────

  function bindPhotoUploads() {
    var uploadBtns = document.querySelectorAll("[data-upload-record-id]");
    for (var i = 0; i < uploadBtns.length; i++) {
      (function (btn) {
        btn.addEventListener("click", function () {
          var recordId = btn.getAttribute("data-upload-record-id");
          var fileInput = document.querySelector(
            "input[type='file'][data-record-id='" + recordId + "']"
          );
          var errorEl = document.querySelector(
            "[data-photo-error='" + recordId + "']"
          );
          clearError(errorEl);

          if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            setError(errorEl, "업로드할 파일을 선택해 주세요.");
            return;
          }

          uploadPhoto(recordId, fileInput.files[0], errorEl);
        });
      })(uploadBtns[i]);
    }
  }

  // ── photo delete buttons ─────────────────────────────────────────────────

  function bindPhotoDeletes() {
    var deleteBtns = document.querySelectorAll(".photo-delete-btn");
    for (var i = 0; i < deleteBtns.length; i++) {
      (function (btn) {
        btn.addEventListener("click", async function () {
          var photoId = btn.getAttribute("data-photo-id");
          var recordId = btn.getAttribute("data-record-id");
          var errorEl = document.querySelector(
            "[data-photo-error='" + recordId + "']"
          );
          clearError(errorEl);

          var result = await window.TakuAPI.del(
            "/api/visit-records/" + recordId + "/photos/" + photoId + "/"
          );

          if (result.status === 204) {
            window.location.reload();
            return;
          }

          if (result.status === 403) {
            handle403(result.data, errorEl);
            return;
          }

          if (result.status === 404) {
            setError(errorEl, "사진을 찾을 수 없습니다.");
            return;
          }

          if (result.status === 0) {
            setError(errorEl, "네트워크 오류가 발생했습니다. 다시 시도해 주세요.");
            return;
          }

          setError(errorEl, "사진 삭제 중 오류가 발생했습니다.");
        });
      })(deleteBtns[i]);
    }
  }

  // ── record delete buttons ────────────────────────────────────────────────

  function bindRecordDeletes() {
    var deleteBtns = document.querySelectorAll("[data-delete-record-id]");
    var globalErrorEl = document.getElementById("visit-global-error");

    for (var i = 0; i < deleteBtns.length; i++) {
      (function (btn) {
        btn.addEventListener("click", async function () {
          var recordId = btn.getAttribute("data-delete-record-id");
          clearError(globalErrorEl);

          var result = await window.TakuAPI.del(
            "/api/visit-records/" + recordId + "/"
          );

          if (result.status === 204) {
            window.location.reload();
            return;
          }

          if (result.status === 403) {
            handle403(result.data, globalErrorEl);
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
    bindPhotoUploads();
    bindPhotoDeletes();
    bindRecordDeletes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
