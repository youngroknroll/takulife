/**
 * staff_submit_guard.js — double-submit guard for staff POST-redirect forms
 * that opt in via data-submit-guard. Loaded once for every staff console
 * page (templates/staff/base_staff.html "shell_js" block, not a per-page
 * extra_js), so this must never assume a particular form exists on the
 * current page — it only ever touches forms carrying the attribute.
 *
 * Deliberately opt-in per form (not a blanket `form` selector): the staff
 * shell has no logout/search form today, but a global selector would have
 * swallowed one silently the moment a page added one. Explicit opt-in
 * keeps that impossible without touching this file.
 *
 * Same technical contract as staff_event_edit.js's #staff-event-verify-form
 * guard, generalized to every opted-in form:
 *   - binds to the form's submit event, never the button's click, so an
 *     Enter-key submit from a text field is caught too
 *   - never calls preventDefault() — these are native POST-redirect forms;
 *     the FIRST submit must go through unmodified. Disabling the button
 *     happens synchronously inside the submit handler, after the event has
 *     already fired, so only a SECOND activation (another click/Enter)
 *     before the navigation lands is blocked
 *   - adds .is-loading (not a bespoke class) so api.js's shared pageshow
 *     handler re-enables the button on a bfcache restore. A different
 *     class name here would strand the button disabled forever after Back.
 *
 * The save (edit.html) and create (create.html) forms can re-render the
 * same URL with field errors instead of redirecting, but that response is
 * a freshly rendered document with its own fresh button — not a bfcache
 * restore — so no extra handling is needed for that path.
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
