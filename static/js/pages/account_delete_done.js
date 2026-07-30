/**
 * account_delete_done.js — /accounts/delete/done/ only.
 *
 * IC8: the deletion-request POST calls logout() before redirecting here, so
 * this page only ever renders for a session that has just been logged out.
 * A back/forward-cache restore (event.persisted) can bring this exact page
 * back from memory without a fresh request — harmless on its own (the view
 * itself is @never_cache, so a *fresh* load never shows stale state), but
 * if the user then navigates further back into a bfcache'd *pre-deletion*
 * page, that earlier snapshot can still read as "logged in" (its DOM was
 * captured before logout()). Forcing a reload right here, the one page this
 * flow guarantees the user lands on right after logout(), is the cheapest
 * point to break that chain: a reload re-requests every bfcache'd page the
 * user later returns to only after it, off a fresh (logged-out) session.
 *
 * Same event contract as api.js/theme.js's own pageshow handlers (this file
 * doesn't reuse them — they solve unrelated problems: api.js re-arms
 * frozen submit buttons, theme.js has no pageshow listener at all).
 */
(function () {
  "use strict";

  window.addEventListener("pageshow", function (evt) {
    if (evt.persisted) {
      window.location.reload();
    }
  });
})();
