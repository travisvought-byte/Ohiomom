// Loads the OhioMom Wix form from a server that is not Wix, in a real browser, and checks that
// the form arrives from Wix (visitor token + form schema). Nothing is filled in or submitted.
// Run by .github/workflows/wix-forms-check.yml; it needs network access to www.wixapis.com.
const { chromium } = require("playwright");
const BASE = process.env.SITE || "http://127.0.0.1:8080";
const PAGES = [["/ohio/report.html", "#report"]];
(async () => {
  const browser = await chromium.launch();
  let failed = false;
  for (const [path, sel] of PAGES) {
    const page = await browser.newPage();
    const wix = [];
    page.on("response", (r) => { if (r.url().includes("wixapis.com")) wix.push(r.status() + " " + new URL(r.url()).pathname); });
    page.on("requestfailed", (r) => { if (r.url().includes("wix")) wix.push("FAILED " + r.url() + " " + (r.failure() || {}).errorText); });
    page.on("console", (m) => { if (m.type() === "error") console.log("  console:", m.text()); });
    await page.goto(BASE + path, { waitUntil: "load" });
    try {
      await page.waitForSelector(sel + " input, " + sel + " textarea", { timeout: 20000 });
      const labels = await page.$$eval(sel + " label", (ls) => ls.map((l) => l.textContent.trim()));
      console.log("OK", path, "form loaded from Wix; fields:", labels.join(" | "));
    } catch (e) {
      failed = true;
      console.log("FAIL", path, "form did not load:", (await page.textContent(sel)).trim().slice(0, 200));
    }
    console.log("  Wix calls:", wix.join(", ") || "none");
    await page.close();
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
