// Polls, the message form and the "did you find it" question. Answers go to one Wix form
// ("OhioMom: we're listening") and show up in the Wix dashboard under Forms and Submissions.
// The Wix form code is only loaded when someone actually answers.
const FORM_ID = "de82990f-3c94-455b-8e57-b6e710c25d31";
const T = { topic: "topic_om01", question: "question_om02", answer: "answer_om03", message: "message_om04", area: "area_om05", page: "page_om06", email: "email_om07" };

function area() {
  try {
    const a = JSON.parse(localStorage.getItem("om.area") || "null");
    return a ? (a.c ? a.c + " County, " : "") + a.r : "";
  } catch (e) { return ""; }
}
function remember(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* private mode */ } }
function recall(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }

export async function send(v) {
  try {
    const mod = await import("/js/wix/form-store.js");
    const store = mod.createFormStore({ formId: FORM_ID });
    const values = {};
    Object.keys(T).forEach((k) => { if (v[k]) values[T[k]] = String(v[k]).slice(0, 2000); });
    const where = area();
    if (where) values[T.area] = where;
    values[T.page] = location.pathname;
    return await new Promise((resolve) => {
      let done = false;
      const timer = setTimeout(() => { if (!done) { done = true; resolve(false); } }, 20000);
      const go = () => {
        const s = store.getState();
        if (done || s.loading || !s.form) return;
        done = true;
        store.setValues((prev) => Object.assign({}, prev, values));
        store.submit().then((o) => { clearTimeout(timer); resolve(!!o); }, () => { clearTimeout(timer); resolve(false); });
      };
      store.subscribe(go);
      store.start();
      go();
    });
  } catch (e) { return false; }
}

const SORRY = "That did not send. Please try again.";

document.querySelectorAll("[data-poll]").forEach((box) => {
  const id = box.getAttribute("data-poll"), q = box.getAttribute("data-q");
  const buttons = Array.from(box.querySelectorAll(".opts button")), note = box.querySelector(".pollnote");
  const mark = (answer) => buttons.forEach((b) => { b.disabled = true; b.setAttribute("aria-pressed", String(b.textContent === answer)); });
  const before = recall("om.poll." + id);
  if (before) { mark(before); note.textContent = "Thanks. You answered this one."; }
  buttons.forEach((b) => b.addEventListener("click", async () => {
    const answer = b.textContent;
    mark(answer); note.textContent = "Sending…";
    if (await send({ topic: "poll", question: q, answer: answer })) {
      remember("om.poll." + id, answer); note.textContent = "Thanks. That helps us decide what to build next.";
    } else {
      buttons.forEach((x) => { x.disabled = false; x.setAttribute("aria-pressed", "false"); }); note.textContent = SORRY;
    }
  }));
});

document.querySelectorAll("[data-feedback]").forEach((form) => {
  const note = form.querySelector(".pollnote"), button = form.querySelector("button");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = form.querySelector("textarea").value.trim();
    if (!message) { note.textContent = "Write a few words first."; return; }
    button.disabled = true; note.textContent = "Sending…";
    const ok = await send({ topic: "feedback", question: form.querySelector("select").value, message: message, email: form.querySelector("input").value.trim() });
    button.disabled = false;
    if (ok) { form.reset(); note.textContent = "Thank you. A person will read this."; } else { note.textContent = SORRY; }
  });
});

// "Did you find what you came for?" at the bottom of every other page.
const foot = document.querySelector("footer");
if (foot && !document.querySelector("[data-feedback]") && !document.getElementById("report")) {
  const box = document.createElement("section");
  box.className = "wrap helpful";
  box.innerHTML = '<p><span>Did you find what you came for?</span> <button type="button">Yes</button> <button type="button">Not yet</button></p>';
  foot.parentNode.insertBefore(box, foot);
  const q = "Did you find what you came for?";
  box.addEventListener("click", async (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.hasAttribute("data-more")) {
      const text = box.querySelector("input").value.trim(); if (!text) return;
      b.disabled = true;
      box.innerHTML = (await send({ topic: "page", question: "What were you looking for?", message: text })) ? "<p>Thank you. We will look for it.</p>" : "<p>" + SORRY + "</p>";
      return;
    }
    const answer = b.textContent;
    box.innerHTML = answer === "Yes" ? "<p>Good. Thanks for telling us.</p>"
      : '<p><label for="hmore">What were you looking for?</label> <input id="hmore" type="text" maxlength="300"> <button type="button" data-more>Send</button></p>';
    send({ topic: "page", question: q, answer: answer });
  });
}