/**
 * 폼 오류 표시 공용 규칙. window.TakuFormFeedback으로 노출한다.
 * 입력이 잘못되면 그 입력에 aria-invalid와 오류 문장 연결(aria-describedby)을
 * 달고 포커스를 옮기며, 값이 고쳐지면 그 입력의 표시만 걷는다. 입력에 속하지
 * 않는 오류(권한·서버·네트워크·삭제 실패)는 오류 문장 자체로 포커스를 옮긴다.
 * 오류 문장은 이 파일이 만들지 않는다 — 호출부가 쓴 문장을 그대로 둔다.
 */

(function () {
  "use strict";

  var DESC_ATTR = "data-feedback-desc";
  var BOUND_ATTR = "data-feedback-bound";
  var idSeed = 0;

  function tokensOf(el) {
    var raw = el.getAttribute("aria-describedby") || "";
    return raw.split(/\s+/).filter(function (token) { return token; });
  }

  function writeTokens(el, tokens) {
    if (tokens.length) {
      el.setAttribute("aria-describedby", tokens.join(" "));
    } else {
      el.removeAttribute("aria-describedby");
    }
  }

  // 이 헬퍼가 붙인 표시만 걷는다. 원래 있던 힌트 연결은 그대로 둔다.
  function clearControl(el) {
    el.removeAttribute("aria-invalid");
    var added = el.getAttribute(DESC_ATTR);
    if (added) {
      writeTokens(el, tokensOf(el).filter(function (token) { return token !== added; }));
      el.removeAttribute(DESC_ATTR);
    }
  }

  function clear(form) {
    if (!form) { return; }
    var controls = form.querySelectorAll("[aria-invalid], [" + DESC_ATTR + "]");
    for (var i = 0; i < controls.length; i++) {
      clearControl(controls[i]);
    }
  }

  function ensureId(errorEl) {
    if (!errorEl.id) {
      idSeed += 1;
      errorEl.id = "form-feedback-error-" + idSeed;
    }
    return errorEl.id;
  }

  // 컨트롤마다 한 번만 건다. 값이 바뀌면 그 컨트롤의 표시만 해제한다.
  function bindRelease(el) {
    if (el.getAttribute(BOUND_ATTR)) { return; }
    el.setAttribute(BOUND_ATTR, "1");
    var release = function () { clearControl(el); };
    el.addEventListener("input", release);
    el.addEventListener("change", release);
  }

  // 교차 필드 오류용: 짝 컨트롤을 고쳐도 표시된 컨트롤의 표시를 푼다.
  // 짝마다 리스너는 한 번만 걸고, 풀 대상 목록만 갱신한다.
  var partnerTargets = new WeakMap();

  function bindPartnerRelease(partner, targets) {
    var known = partnerTargets.get(partner);
    if (known) {
      targets.forEach(function (el) {
        if (known.indexOf(el) === -1) { known.push(el); }
      });
      return;
    }
    var list = targets.slice();
    partnerTargets.set(partner, list);
    var release = function () { list.forEach(clearControl); };
    partner.addEventListener("input", release);
    partner.addEventListener("change", release);
  }

  function isUsable(el) {
    return !!el && el.nodeType === 1 && !el.disabled && el.type !== "hidden";
  }

  // 닫힌 <details> 안의 컨트롤은 숨겨져 있어 focus()가 조용히 실패하므로 먼저 연다.
  function openAncestorDetails(el) {
    var node = el.parentElement;
    while (node) {
      if (node.tagName === "DETAILS" && !node.open) { node.open = true; }
      node = node.parentElement;
    }
  }

  function byDocumentOrder(a, b) {
    return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  }

  // releaseWith: 값이 바뀌면 이 표시도 함께 풀 짝 컨트롤 목록(선택).
  function markInvalid(controls, errorEl, releaseWith) {
    var list = Array.prototype.slice.call(controls || []).filter(isUsable);
    if (!list.length) { return; }
    list.sort(byDocumentOrder);
    var errorId = errorEl ? ensureId(errorEl) : "";

    list.forEach(function (el) {
      el.setAttribute("aria-invalid", "true");
      if (errorId) {
        var tokens = tokensOf(el);
        if (tokens.indexOf(errorId) === -1) {
          writeTokens(el, tokens.concat(errorId));
          el.setAttribute(DESC_ATTR, errorId);
        }
      }
      bindRelease(el);
    });

    Array.prototype.slice.call(releaseWith || []).filter(isUsable).forEach(function (partner) {
      bindPartnerRelease(partner, list);
    });

    openAncestorDetails(list[0]);
    list[0].focus();
  }

  // 입력에 속하지 않는 오류: 오류 문장에 포커스를 줘 화면 안으로 가져온다.
  function focusError(errorEl) {
    if (!errorEl) { return; }
    if (!errorEl.hasAttribute("tabindex")) { errorEl.setAttribute("tabindex", "-1"); }
    errorEl.focus();
  }

  // 서버 400 본문의 키가 폼 컨트롤 name과 같으면 그 컨트롤을 모은다.
  // aliases는 키 이름이 다른 경우(예: 방문의 event → subject)를 잇는다.
  function controlsForServerErrors(form, payload, aliases) {
    var found = [];
    if (!form || !payload || typeof payload !== "object" || Array.isArray(payload)) {
      return found;
    }
    Object.keys(payload).forEach(function (key) {
      var name = (aliases && aliases[key]) || key;
      var named = form.elements[name];
      if (!named) { return; }
      var nodes = named.nodeType === 1 ? [named] : Array.prototype.slice.call(named);
      nodes.forEach(function (node) {
        if (found.indexOf(node) === -1) { found.push(node); }
      });
    });
    return found.filter(isUsable);
  }

  // 서버 오류 한 번에: 매핑되는 입력이 있으면 그 입력, 없으면 오류 문장으로 포커스한다.
  function showServerError(form, payload, errorEl, aliases) {
    var controls = controlsForServerErrors(form, payload, aliases);
    if (controls.length) {
      markInvalid(controls, errorEl);
    } else {
      focusError(errorEl);
    }
  }

  window.TakuFormFeedback = {
    clear: clear,
    markInvalid: markInvalid,
    focusError: focusError,
    controlsForServerErrors: controlsForServerErrors,
    showServerError: showServerError,
  };
})();
