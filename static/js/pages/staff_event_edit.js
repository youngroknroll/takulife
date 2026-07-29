/**
 * staff_event_edit.js — double-submit guard for the "검증 완료"/"다시 검증"
 * button on the staff event edit page (templates/staff/events/edit.html).
 *
 * This is a classic POST-redirect form (not a fetch/JSON endpoint), so this
 * intentionally does NOT call preventDefault() or TakuAPI.setLoading — the
 * native submit must proceed unmodified. The submit handler only disables the
 * button synchronously (after the submit event has already fired) and adds
 * .is-loading so the shared spinner (static/css/objects/interaction.css)
 * shows while the page navigates away. Sibling forms (toggle-publish,
 * delete) are untouched by design.
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
