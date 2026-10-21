/**
 * JavaScriptCatalog(/jsi18n/) 로드가 실패하거나 아직 도착하지 않았을 때
 * gettext/ngettext/interpolate가 미정의라 다른 스크립트가 ReferenceError로
 * 죽지 않도록 항등(no-op) 폴백을 먼저 정의한다. 이 스크립트 뒤에 로드되는
 * 카탈로그 스크립트가 같은 전역을 자신의 번역 함수로 덮어쓴다.
 */
(function () {
  "use strict";

  if (typeof window.gettext !== "function") {
    window.gettext = function (msgid) {
      return msgid;
    };
  }

  if (typeof window.ngettext !== "function") {
    window.ngettext = function (singular, plural, count) {
      return count === 1 ? singular : plural;
    };
  }

  if (typeof window.interpolate !== "function") {
    window.interpolate = function (fmt, obj, named) {
      if (named) {
        return fmt.replace(/%\(\w+\)s/g, function (match) {
          return String(obj[match.slice(2, -2)]);
        });
      }
      var i = 0;
      return fmt.replace(/%s/g, function () {
        return String(obj[i++]);
      });
    };
  }
})();
