/**
 * "검증 완료"/"다시 검증" 버튼의 이중 제출 방지 가드.
 * 일반 POST-redirect 폼이라 preventDefault나 TakuAPI.setLoading을 쓰지 않고,
 * 이벤트가 발생한 뒤 버튼만 동기적으로 비활성화해 원래 제출 흐름을 방해하지 않는다.
 * 같은 페이지의 다른 폼(공개 전환, 삭제)은 의도적으로 건드리지 않는다.
 */
(function () {
  "use strict";

  var form = document.getElementById("staff-event-verify-form");
  if (!form) {
    return;
  }

  form.addEventListener("submit", function () {
    var button = form.querySelector("button[type=submit]");
    if (!button) {
      return;
    }
    button.disabled = true;
    button.classList.add("is-loading");
  });
})();
