/**
 * 검수 큐(list.html) 전용 단축키. J/K 행 이동, A 승인, R 반려, X 선택,
 * Enter 전체 검토 화면 이동(D6).
 *
 * 이 파일은 순수 키 처리만 한다 — "현재 행" 상태 관리, 실제 승인/반려
 * 요청, 확인 대화상자, 서버 응답 반영은 전부 draft_bulk.js가 이미 만든
 * 실제 버튼/링크를 그대로 클릭해서 재사용한다(window.TakuQueue). 그래야
 * 키보드 판정도 마우스 클릭과 완전히 같은 확인 절차·오류 표시·포커스
 * 이동을 거친다.
 *
 * ⚠️ 입력 중 무효화: document.activeElement가 input/textarea/select/
 * [contenteditable]이면 전부 no-op이다. 인스펙터에는 없지만 커맨드바
 * 검색창이 있어, 이 가드가 없으면 검색창에 "r"을 타이핑하다 드래프트가
 * 반려될 수 있다.
 */

(function () {
  "use strict";

  var EDITABLE_TAGS = ["INPUT", "TEXTAREA", "SELECT"];

  function isEditingContext() {
    var active = document.activeElement;
    if (!active) {
      return false;
    }
    if (EDITABLE_TAGS.indexOf(active.tagName) !== -1) {
      return true;
    }
    if (active.isContentEditable) {
      return true;
    }
    return false;
  }

  function handleKeydown(evt) {
    if (!window.TakuQueue || !window.TakuQueue.hasRows()) {
      return;
    }
    // 조합키(⌘/Ctrl/Alt)가 눌린 상태는 브라우저·OS 단축키와 겹칠 수 있어
    // 손대지 않는다.
    if (evt.metaKey || evt.ctrlKey || evt.altKey) {
      return;
    }
    if (isEditingContext()) {
      return;
    }

    switch (evt.key) {
      case "j":
      case "J":
        evt.preventDefault();
        window.TakuQueue.moveNext();
        break;
      case "k":
      case "K":
        evt.preventDefault();
        window.TakuQueue.movePrev();
        break;
      case "a":
      case "A": {
        var approveBtn = window.TakuQueue.getCurrentApproveButton();
        if (approveBtn && !approveBtn.disabled) {
          evt.preventDefault();
          approveBtn.click();
        }
        break;
      }
      case "r":
      case "R": {
        var rejectBtn = window.TakuQueue.getCurrentRejectButton();
        if (rejectBtn && !rejectBtn.disabled) {
          evt.preventDefault();
          rejectBtn.click();
        }
        break;
      }
      case "x":
      case "X": {
        var checkbox = window.TakuQueue.getCurrentCheckbox();
        if (checkbox) {
          evt.preventDefault();
          checkbox.click();
        }
        break;
      }
      case "Enter": {
        var link = window.TakuQueue.getCurrentFullReviewLink();
        if (link) {
          evt.preventDefault();
          window.location.href = link.href;
        }
        break;
      }
      default:
        break;
    }
  }

  document.addEventListener("keydown", handleKeydown);
})();
