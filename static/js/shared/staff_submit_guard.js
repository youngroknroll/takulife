/**
 * data-submit-guard 속성이 붙은 폼에서만 동작하는 이중 제출 방지 가드.
 * 모든 스태프 페이지에 공통 로드되므로(templates/staff/base_staff.html의
 * shell_js), 특정 폼이 항상 있다고 가정하지 않고 속성이 붙은 폼만 다룬다.
 * 전역 `form` 선택자 대신 opt-in 방식을 쓰는 이유: 나중에 다른 폼이 추가돼도
 * 이 파일을 건드리지 않는 한 조용히 가드에 걸리는 일이 없게 하기 위해서다.
 *
 * 버튼 click이 아니라 폼 submit 이벤트에 건다 — 입력창에서 Enter로 제출해도 잡힌다.
 * preventDefault는 절대 호출하지 않는다. 첫 제출은 원래 흐름대로 통과해야 하고,
 * 버튼 비활성화는 이벤트가 이미 발생한 뒤 동기적으로 일어나므로 페이지 이동이
 * 끝나기 전의 두 번째 클릭·Enter만 막힌다.
 * 클래스는 반드시 .is-loading을 쓴다 — api.js의 공용 pageshow 핸들러가 이 클래스를
 * 보고 bfcache 복원 시 버튼을 다시 활성화한다. 다른 클래스명을 쓰면 뒤로가기 후
 * 버튼이 영영 비활성 상태로 남는다.
 *
 * 저장·생성 폼은 검증 오류 시 같은 URL을 다시 렌더링해 돌아올 수 있는데,
 * 이때는 매번 새 버튼을 가진 새 문서라 bfcache 복원이 아니므로 별도 처리가 필요 없다.
 */
(function () {
  "use strict";

  var forms = document.querySelectorAll("form[data-submit-guard]");
  forms.forEach(function (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector("button[type=submit]");
      if (!button) {
        return;
      }
      button.disabled = true;
      button.classList.add("is-loading");
    });
  });
})();
