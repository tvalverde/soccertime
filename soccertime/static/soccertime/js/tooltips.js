/* Activates Bootstrap tooltips on the elements that ask for one.

   Moved out of a <script> block in base.html for the Content-Security-Policy. It runs on
   DOMContentLoaded because the tag now carries `defer`, so `bootstrap` is loaded but the
   markup it reads may not have been parsed when the file is evaluated. */

document.addEventListener('DOMContentLoaded', function () {
  const triggers = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  Array.prototype.slice.call(triggers).map(function (el) {
    return new bootstrap.Tooltip(el);
  });
});
