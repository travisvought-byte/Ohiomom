// Report a problem form. The fields, wording and thank-you message come from the form
// in the Wix dashboard, so they can be changed there without touching this file.
import { createFormStore, FORM_ERROR } from "/js/wix/form-store.js";

var FORM_ID = "0ea7667b-0e3e-427e-9c35-380a30005ab5";
var formEl = document.getElementById("report");
var store = createFormStore({ formId: FORM_ID });
var built = false;

function esc(v) {
  return String(v == null ? "" : v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function inputType(control) {
  return { email: "email", url: "url", phone: "tel", number: "number", date: "date" }[control] || "text";
}
function fieldHtml(f) {
  var html = '<p class="field"><label for="' + esc(f.target) + '">' + esc(f.label) + (f.required ? " *" : "") + "</label>";
  if (f.control === "textarea") {
    html += '<textarea id="' + esc(f.target) + '" name="' + esc(f.target) + '" rows="6"></textarea>';
  } else {
    html += '<input id="' + esc(f.target) + '" name="' + esc(f.target) + '" type="' + inputType(f.control) + '">';
  }
  return html + '<span class="error" role="alert" data-error="' + esc(f.target) + '"></span></p>';
}
function build(s) {
  formEl.innerHTML = s.form.fields.map(fieldHtml).join("") +
    '<p class="error" role="alert" data-error="' + FORM_ERROR + '"></p>' +
    '<p><button class="btn call" type="submit">' + esc(s.form.submitText || "Send report") + "</button></p>";
  built = true;
}
function render(s) {
  if (s.outcome) {
    formEl.innerHTML = "<p><strong>" + esc(s.outcome.message || "Thank you. Your report was sent.") + "</strong></p>";
    return;
  }
  if (!s.form) {
    formEl.innerHTML = '<p id="status">' + esc(s.errors[FORM_ERROR] || "Loading the form…") + "</p>";
    return;
  }
  if (s.closed) {
    formEl.innerHTML = "<p>" + esc(s.form.disabledMessage || "This form is not taking reports right now.") + "</p>";
    return;
  }
  if (!built) build(s);
  Array.prototype.forEach.call(formEl.querySelectorAll("[data-error]"), function (el) {
    var key = el.getAttribute("data-error"), msg = s.errors[key] || "";
    el.textContent = msg;
    var control = formEl.querySelector('[name="' + key + '"]');
    if (control) { if (msg) control.setAttribute("aria-invalid", "true"); else control.removeAttribute("aria-invalid"); }
  });
  var button = formEl.querySelector("button");
  if (button) { button.disabled = s.loading; button.setAttribute("aria-busy", s.loading ? "true" : "false"); }
}

formEl.addEventListener("input", function (e) { if (e.target.name) store.setValue(e.target.name, e.target.value); });
formEl.addEventListener("focusout", function (e) { if (e.target.name) store.validate(e.target.name); });
formEl.addEventListener("submit", function (e) { store.submit(e); });
store.subscribe(render);
render(store.getState());
store.start();