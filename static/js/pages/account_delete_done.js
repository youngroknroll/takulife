/**
 * 탈퇴 요청 처리는 로그아웃 후 이 페이지로 이동한다. 뒤로가기로 bfcache에
 * 저장된 탈퇴 이전 화면을 다시 열면 로그인 상태로 보일 수 있어, 이 페이지에
 * bfcache로 복원됐을 때(event.persisted) 강제로 새로고침해 그 뒤에 여는
 * 모든 캐시 페이지가 로그아웃된 최신 상태로 다시 요청되게 한다.
 */
(function () {
  "use strict";

  window.addEventListener("pageshow", function (evt) {
    if (evt.persisted) {
      window.location.reload();
    }
  });
})();
