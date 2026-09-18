/**
 * 프론트 오류를 서버 오류 묶음 API로 보고한다(트랙 36 S4). head 인라인
 * 부트스트랩(base.html/base_staff.html)이 큐에 쌓아둔 항목을 먼저 처리하고,
 * 이후 발생하는 오류는 이 스크립트가 직접 addEventListener로 받는다.
 * 사용자 영향은 0이어야 한다 — DOM·토스트·콘솔 출력 없음, 실패는 조용히 삼킨다.
 */
(function () {
  "use strict";

  var ENDPOINT = "/api/client-errors/";
  var MAX_PER_PAGE = 5;
  var MAX_MESSAGE_LEN = 300;
  var EXTENSION_SCHEMES = { "chrome-extension": true, "moz-extension": true, "safari-extension": true };

  var reportedCount = 0;
  var seenFingerprints = {};

  function toInt(value) {
    return typeof value === "number" && isFinite(value) ? Math.trunc(value) : 0;
  }

  function isSameOriginUrl(rawUrl) {
    try {
      return new URL(rawUrl, window.location.href).origin === window.location.origin;
    } catch (e) {
      return false;
    }
  }

  function processEntry(entry) {
    if (reportedCount >= MAX_PER_PAGE) {
      return;
    }
    var isRejection = "reason" in entry;
    var message = isRejection ? String(entry.reason) : entry.message || "";
    if (!isRejection && (message === "Script error." || message === "Script error")) {
      return;
    }
    var name = entry.name || "";
    var scriptPath;
    var line = 0;
    var col = 0;
    if (isRejection) {
      // 서버 계약상 script가 필수라, 출처를 알 수 없는 프로미스 거부는
      // 자리표시자 문자열로 채운다(rejection은 line·col 정보가 없다).
      scriptPath = "(promise)";
    } else {
      var filename = entry.filename || "";
      var scheme = filename.split(":")[0];
      if (!filename || EXTENSION_SCHEMES[scheme] || !isSameOriginUrl(filename)) {
        return;
      }
      scriptPath = new URL(filename, window.location.href).pathname;
      line = toInt(entry.lineno);
      col = toInt(entry.colno);
    }
    var fingerprint = name + "|" + scriptPath + "|" + line + "|" + message.slice(0, 100);
    if (seenFingerprints[fingerprint]) {
      return;
    }
    seenFingerprints[fingerprint] = true;
    // 무시한 이벤트(확장·교차 출처·중복)는 상한을 쓰지 않게 여기서 센다 —
    // 전송 전에 올려 두어 sendReport가 던져도 재시도 루프가 생기지 않는다.
    reportedCount += 1;
    sendReport({ message: message.slice(0, MAX_MESSAGE_LEN), script: scriptPath, line: line, col: col, name: name || undefined });
  }

  function sendReport(payload) {
    if (!navigator.sendBeacon) {
      return;
    }
    navigator.sendBeacon(ENDPOINT, new Blob([JSON.stringify(payload)], { type: "application/json" }));
  }

  function drainBootstrapQueue() {
    var queued = window.__takuErrorQueue;
    if (Array.isArray(queued)) {
      for (var i = 0; i < queued.length; i++) {
        // 항목 하나가 던져도 나머지 드레인·싱크 교체·리스너 등록이 멈추지 않게 한다.
        try {
          processEntry(queued[i]);
        } catch (err) {
          // 보고 실패는 조용히 삼킨다.
        }
      }
    }
    // 부트스트랩 리스너는 계속 살아 있어 이후에도 push를 시도한다. 큐를 push
    // 무시 싱크로 바꿔 그 push가 조용히 버려지게 하고, 이 시점부터는 아래
    // 자체 리스너만 오류를 처리해 같은 이벤트가 두 번 보고되지 않게 한다.
    window.__takuErrorQueue = { push: function () {} };
  }

  function bindListeners() {
    window.addEventListener("error", function (e) {
      try {
        processEntry({ message: e.message, filename: e.filename, lineno: e.lineno, colno: e.colno, name: e.error && e.error.name });
      } catch (err) {
        // 보고 실패가 페이지 동작에 번지지 않게 조용히 삼킨다.
      }
    });
    window.addEventListener("unhandledrejection", function (e) {
      try {
        processEntry({ reason: e.reason, name: e.reason && e.reason.name });
      } catch (err) {
        // 보고 실패가 페이지 동작에 번지지 않게 조용히 삼킨다.
      }
    });
  }

  // bfcache로 페이지가 되살아나도 이 스크립트는 다시 실행되지 않으므로
  // reportedCount·seenFingerprints는 같은 페이지뷰 동안 그대로 유지된다.
  try {
    drainBootstrapQueue();
    bindListeners();
  } catch (e) {
    // 초기화 자체가 실패해도 페이지 동작에는 영향이 없어야 한다.
  }
})();
