/**
 * CSRF 토큰을 자동으로 붙이는 공용 REST 클라이언트. window.TakuAPI로 노출된다.
 * 모든 요청은 csrftoken 쿠키 값을 읽어 X-CSRFToken 헤더로 보내고
 * (Django의 기본 CSRF 헤더명과 맞춘 것이다), 세션 쿠키가 함께 가도록
 * credentials: 'same-origin'을 쓴다. 항목 업로드(upload)는 Content-Type을
 * 직접 지정하지 않는데, 그래야 브라우저가 multipart 경계값을 알아서 채운다.
 */

(function () {
  "use strict";

  // DRF가 "인증되지 않음" 403에 붙이는 detail 문구. 앱은 한국어(ko)로만
  // 서비스되므로 실제로는 한국어 문자열만 오지만 영어도 함께 대비해둔다.
  var AUTH_DETAIL_MARKERS = [
    "Authentication credentials were not provided",
    "자격 인증 데이터가 제공되지 않았습니다",
  ];

  // ── 쿠키 읽기 ──────────────────────────────────────────────────────────

  function getCookie(name) {
    var prefix = name + "=";
    for (var part of document.cookie.split(";")) {
      var trimmed = part.trim();
      if (trimmed.startsWith(prefix)) {
        return decodeURIComponent(trimmed.slice(prefix.length));
      }
    }
    return "";
  }

  // ── 내부 요청 헬퍼 ───────────────────────────────────────────────

  function buildJsonHeaders() {
    return {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    };
  }

  function buildUploadHeaders() {
    // Content-Type을 넣지 않아야 브라우저가 multipart 경계값을 직접 설정한다
    return {
      "X-CSRFToken": getCookie("csrftoken"),
    };
  }

  async function parseResponse(response) {
    var data = null;
    var contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    }
    return { ok: response.ok, status: response.status, data: data };
  }

  async function request(method, url, body) {
    var options = {
      method: method,
      credentials: "same-origin",
      headers: buildJsonHeaders(),
    };
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }
    try {
      var response = await fetch(url, options);
      // parseResponse 내부의 response.json()도 실패할 수 있어, await 없이
      // 그냥 반환하면 그 오류가 이 try/catch를 빠져나가 잡히지 않는다.
      return await parseResponse(response);
    } catch (_networkError) {
      return { ok: false, status: 0, data: null };
    }
  }

  // ── 공용 오류 헬퍼 ───────────────────────────────────────────────

  /**
   * 응답을 고정된 오류 종류 문자열로 분류한다: auth(인증 필요) / csrf /
   * validation(400) / conflict(409) / notfound(404) / server(500대) /
   * network(연결 실패) / ratelimited(429) / unknown.
   */
  function classify(result) {
    var s = result.status;
    if (s === 0) { return "network"; }
    if (s === 400) { return "validation"; }
    if (s === 403) {
      var detail = (result.data && typeof result.data.detail === "string")
        ? result.data.detail
        : "";
      for (var m = 0; m < AUTH_DETAIL_MARKERS.length; m++) {
        if (detail.indexOf(AUTH_DETAIL_MARKERS[m]) !== -1) {
          return "auth";
        }
      }
      return "csrf";
    }
    if (s === 404) { return "notfound"; }
    if (s === 409) { return "conflict"; }
    if (s === 429) { return "ratelimited"; }
    if (s >= 500) { return "server"; }
    return "unknown";
  }

  // 응답을 사람이 읽을 수 있는 한국어 오류 메시지로 바꾼다.
  function formatError(result) {
    if (result.status === 0) {
      return "네트워크 오류가 발생했습니다. 다시 시도해 주세요.";
    }
    // 429는 JSON 본문이 없을 수 있어 data 존재 여부를 확인하기 전에 먼저 처리한다.
    if (result.status === 429) {
      return "요청이 많아요. 잠시 후 다시 시도해 주세요.";
    }
    var data = result.data;
    if (!data) {
      return "알 수 없는 오류가 발생했습니다.";
    }
    // 서버가 내려주는 의미별 오류 코드
    if (data.code === "duplicate_user_event_status") {
      return "이미 추가됨";
    }
    if (data.code === "duplicate_event_interest") {
      return "이미 찜한 이벤트입니다.";
    }
    if (data.code === "photo_limit_exceeded") {
      return "사진은 기록당 최대 5장까지 첨부할 수 있습니다.";
    }
    // DRF가 필드에 속하지 않는 오류에 기본으로 담는 detail 문자열
    if (typeof data.detail === "string") {
      return data.detail;
    }
    // 필드별 오류 딕셔너리
    if (typeof data === "object") {
      var parts = [];
      Object.keys(data).forEach(function (field) {
        var val = data[field];
        var messages = Array.isArray(val) ? val : [String(val)];
        parts.push(field + ": " + messages.join(" "));
      });
      if (parts.length > 0) {
        return parts.join(" | ");
      }
    }
    return "알 수 없는 오류가 발생했습니다.";
  }

  // 현재 경로를 next로 붙인 로그인 URL로 이동한다. 모든 호출자가 URL을
  // 각자 만들지 않고 이 함수 하나를 공유한다.
  function redirectToLogin() {
    var next = encodeURIComponent(
      window.location.pathname + window.location.search
    );
    window.location.href = "/accounts/login/?next=" + next;
  }

  // 서버가 <body>에 남겨둔 로그인 상태를 읽는다. 어차피 실패할 요청을
  // 보내는 대신 미리 로그인 안내를 띄우기 위해서다.
  function isAuthenticated() {
    return document.body.dataset.authenticated === "true";
  }

  // 강제 이동이나 헷갈리는 오류 대신 로그인/회원가입을 안내하는 모달을 띄운다.
  // 이미 열려 있으면 다시 열지 않는다. 열리면 포커스가 닫기 버튼으로 가고
  // Tab은 모달 안의 컨트롤 사이에서만 순환하며, 닫으면 원래 포커스로 되돌아간다.
  function promptLogin() {
    if (document.querySelector(".auth-modal-overlay")) {
      return;
    }
    var next = encodeURIComponent(
      window.location.pathname + window.location.search
    );

    var overlay = document.createElement("div");
    overlay.className = "auth-modal-overlay";

    var modal = document.createElement("div");
    modal.className = "auth-modal";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-labelledby", "auth-modal-title");
    modal.setAttribute("aria-describedby", "auth-modal-desc");

    var close = document.createElement("button");
    close.type = "button";
    close.className = "auth-modal-close";
    close.textContent = "×";
    close.setAttribute("aria-label", "닫기");

    var title = document.createElement("h2");
    title.id = "auth-modal-title";
    title.textContent = "로그인이 필요합니다";

    var desc = document.createElement("p");
    desc.id = "auth-modal-desc";
    desc.textContent = "찜·방문 예정을 저장하려면 로그인해 주세요.";

    var actions = document.createElement("div");
    actions.className = "auth-modal-actions";

    var loginLink = document.createElement("a");
    loginLink.className = "auth-modal-primary";
    loginLink.href = "/accounts/login/?next=" + next;
    loginLink.textContent = "로그인";

    var registerLink = document.createElement("a");
    registerLink.className = "auth-modal-secondary";
    registerLink.href = "/accounts/signup/?next=" + next;
    registerLink.textContent = "회원가입";

    actions.appendChild(loginLink);
    actions.appendChild(registerLink);
    modal.appendChild(close);
    modal.appendChild(title);
    modal.appendChild(desc);
    modal.appendChild(actions);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    document.documentElement.classList.add("confirm-scroll-lock");

    var previouslyFocused = document.activeElement;
    var focusables = [close, loginLink, registerLink];

    function dismiss() {
      overlay.remove();
      document.documentElement.classList.remove("confirm-scroll-lock");
      document.removeEventListener("keydown", onKey);
      if (previouslyFocused && typeof previouslyFocused.focus === "function") {
        previouslyFocused.focus();
      }
    }
    function onKey(evt) {
      if (evt.key === "Escape") {
        dismiss();
        return;
      }
      if (evt.key === "Tab") {
        trapTab(evt);
      }
    }
    function trapTab(evt) {
      var first = focusables[0];
      var last = focusables[focusables.length - 1];
      if (evt.shiftKey) {
        if (document.activeElement === first || !overlay.contains(document.activeElement)) {
          evt.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last || !overlay.contains(document.activeElement)) {
          evt.preventDefault();
          first.focus();
        }
      }
    }
    close.addEventListener("click", dismiss);
    overlay.addEventListener("click", function (evt) {
      if (evt.target === overlay) {
        dismiss();
      }
    });
    document.addEventListener("keydown", onKey);
    close.focus();
  }

  // ── 외부 공개 API ─────────────────────────────────────────────────────────────

  window.TakuAPI = {
    getCookie: getCookie,

    get: function (url) {
      return request("GET", url, undefined);
    },

    post: function (url, body) {
      return request("POST", url, body);
    },

    patch: function (url, body) {
      return request("PATCH", url, body);
    },

    del: function (url) {
      return request("DELETE", url, undefined);
    },

    // 멀티파트 업로드(기본 POST). method에 "PATCH"를 넘기면 기존 자원의
    // 부분 수정(예: 이미지 교체)에도 쓸 수 있다.
    upload: async function (url, formData, method) {
      try {
        var response = await fetch(url, {
          method: method || "POST",
          credentials: "same-origin",
          headers: buildUploadHeaders(),
          body: formData,
        });
        // request()의 parseResponse 호출과 같은 이유로 await가 필요하다.
        return await parseResponse(response);
      } catch (_networkError) {
        return { ok: false, status: 0, data: null };
      }
    },

    classify: classify,
    formatError: formatError,
    redirectToLogin: redirectToLogin,
    isAuthenticated: isAuthenticated,
    promptLogin: promptLogin,

    // 요청이 진행 중인 동안 버튼을 비활성화하고 스피너를 붙여 이중 제출을 막는다.
    setLoading: function (button, isLoading) {
      if (!button) {
        return;
      }
      button.disabled = !!isLoading;
      if (isLoading) {
        button.classList.add("is-loading");
      } else {
        button.classList.remove("is-loading");
      }
    },

    // 제출이 성공했다는 표시(data-committed-redirect)를 버튼에 남긴 뒤 이동한다.
    // 이 표시는 DOM 속성이라 bfcache 스냅샷에도 그대로 남아, 나중에 이 페이지가
    // 복원됐을 때 "이 제출은 이미 성공했다"는 증거로 쓰인다. 표시를 남기는 순서를
    // 호출하는 쪽이 아니라 이 함수가 보장한다 — 순서를 각자 지키게 했다가 세 파일에서
    // 이미 실패한 적이 있다. 일반적인 성공 후 이동이라 방문 기록을 남기는 assign을 쓴다.
    commitAndNavigate: function (button, url) {
      if (button) {
        button.setAttribute("data-committed-redirect", url);
      }
      window.location.assign(url);
    },
  };

  // ── bfcache 복원 ───────────────────────────────────────────────────────

  // bfcache 복원(event.persisted)은 페이지를 떠날 때 버튼이 요청 중이던
  // 상태(.is-loading) 그대로 되살릴 수 있다 — 그 요청이 끝나 버튼을 다시
  // 켜줄 기회가 다시는 오지 않는다. .is-loading에만 적용해 서버가 의도적으로
  // 비활성화한 버튼(이미 승인된 드래프트 등)은 건드리지 않는다.
  // 그중 data-committed-redirect 표시가 있는 버튼은 직전 제출이 이미
  // 성공했다는 뜻이라, 다시 켜서 재제출을 허용하는 대신 그 목적지로 강제
  // 이동시킨다. 이때는 replace를 써서 뒤로가기 때마다 새 기록이 쌓이는
  // 루프를 막는다.
  window.addEventListener("pageshow", function (evt) {
    if (!evt.persisted) {
      return;
    }
    var loadingButtons = document.querySelectorAll(".is-loading");
    for (var i = 0; i < loadingButtons.length; i++) {
      var btn = loadingButtons[i];
      var committedRedirect = btn.dataset.committedRedirect;
      if (committedRedirect) {
        window.location.replace(committedRedirect);
        return;
      }
      window.TakuAPI.setLoading(btn, false);
    }
  });
})();
