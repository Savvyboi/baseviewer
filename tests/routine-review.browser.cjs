/* Synthetic routine review QA. Generates local fixtures; never reads user reviews.
 * Run: node tests/routine-review.browser.cjs [OUTPUT_ROOT]
 * Optional env: ROUTINE_QA_PYTHON (default python), PLAYWRIGHT_MODULE,
 * ROUTINE_QA_BROWSER_CHANNEL (e.g. chrome; default Playwright Chromium).
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const {spawnSync} = require("node:child_process");
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const project = path.resolve(__dirname, "..");
const root = process.argv[2] ? path.resolve(process.argv[2]) : fs.mkdtempSync(path.join(os.tmpdir(), "routine-review-qa-"));
fs.mkdirSync(root, {recursive: true});
const python = process.env.ROUTINE_QA_PYTHON || "python";
const prepared = spawnSync(python, [path.join(__dirname, "test_routine_review.py"), root], {
  cwd: project, encoding: "utf8", env: {...process.env, PYTHONPATH: path.join(project, "src")}
});
assert.equal(prepared.status, 0, prepared.stderr || prepared.stdout);
const types = {".html": "text/html", ".js": "application/javascript", ".json": "application/json", ".png": "image/png"};
const server = http.createServer((req, res) => {
  const file = path.resolve(root, "." + new URL(req.url, "http://localhost").pathname);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404).end(); return;
  }
  res.setHeader("Content-Type", types[path.extname(file)] || "application/octet-stream");
  fs.createReadStream(file).pipe(res);
});
let browser;
(async () => {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({
    headless: true,
    ...(process.env.ROUTINE_QA_BROWSER_CHANNEL ? {channel: process.env.ROUTINE_QA_BROWSER_CHANNEL} : {})
  });
  const errors = [], nonGet = [], external = [];
  const freshContext = async options => {
    const context = await browser.newContext(options);
    await context.route("**/*", route => {
      const request = route.request();
      if (request.method() !== "GET") nonGet.push(request.method());
      if (!request.url().startsWith(base + "/")) {
        external.push(request.url()); return route.abort();
      }
      return route.continue();
    });
    context.on("page", page => page.on("pageerror", error => errors.push(error.message)));
    return context;
  };
  const screenshot = async (page, name) => {
    const dimensions = await page.evaluate(async () => {
      const images = [...document.images];
      images.forEach(image => { image.loading = "eager"; });
      await Promise.all(images.map(image => image.decode()));
      return images.map(image => [image.naturalWidth, image.naturalHeight]);
    });
    assert(dimensions.length > 0 && dimensions.every(([width, height]) => width > 0 && height > 0));
    await page.screenshot({path: path.join(root, name), fullPage: true});
  };
  const download = async page => {
    const pending = page.waitForEvent("download");
    await page.locator("#export-reviews").click();
    const stream = await (await pending).createReadStream();
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  };
  const restore = async (page, payload) => {
    await page.locator("#review-import-file").setInputFiles({
      name: "synthetic-routine-qa.json", mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(payload))
    });
    await page.waitForFunction(() => /restored/.test(document.getElementById("review-import-status").textContent));
  };
  const context = await freshContext({viewport: {width: 1280, height: 900}});
  const page = await context.newPage();
  await page.goto(base + "/routine/report/index.html");
  await page.locator("#review-queue").waitFor({state: "visible"});
  assert.equal(await page.locator(".review-tools").count(), 2);
  assert.equal(await page.locator('[data-case-id=""]').count(), 2);
  assert.equal(await page.locator('a[href="validation-case.json"]').count(), 0);
  assert.match(await page.locator("#review-progress").innerText(), /0 of 3.*2 unreviewed.*1 awaiting previews/);
  assert.match(await page.locator("#review-queue").innerText(), /Routine monitoring/);
  await page.locator("#next-unreviewed").focus(); await page.keyboard.press("Enter");
  assert.equal(await page.evaluate(() => document.activeElement.className), "review-decision");
  const tool = page.locator(".review-tools").first();
  await tool.locator(".review-decision").selectOption("unclear");
  await tool.locator(".review-note").fill("SYNTHETIC routine QA only");
  const exported = await download(page);
  assert.equal(exported.schema_version, 1);
  assert.equal(exported.reviews.length, 2);
  const fields = ["mode", "case_id", "site_id", "analysis_key", "comparison_id", "record_generated_at", "acquisition_date", "sensor"];
  for (const entry of exported.reviews) {
    assert(fields.every(field => typeof entry[field] === "string"));
    assert.equal(entry.case_id, "");
  }
  for (let i = 0; i < await tool.locator("[data-view]").count(); i++) {
    const button = tool.locator("[data-view]").nth(i);
    const src = await button.getAttribute("data-src");
    await button.click();
    assert.equal(await tool.locator(".review-stage img").getAttribute("src"), src);
  }
  assert.equal(await tool.locator('[data-rendering="Shared optical range"]').count(), 3);
  assert.deepEqual((await download(page)).reviews, exported.reviews);
  await page.reload();
  await page.locator("#review-queue").waitFor({state: "visible"});
  assert.deepEqual((await download(page)).reviews, exported.reviews);
  await screenshot(page, "routine-desktop.png");
  const mobileContext = await freshContext({viewport: {width: 390, height: 844}});
  const mobile = await mobileContext.newPage();
  await mobile.goto(base + "/routine/report/index.html");
  await restore(mobile, exported);
  assert.match(await mobile.locator("#review-import-status").innerText(), /1 restored.*1 unchanged.*0 did not match/);
  assert.deepEqual((await download(mobile)).reviews, exported.reviews);
  await mobile.locator("#only-unreviewed").check();
  assert.equal(await mobile.locator("[data-review-target]:visible").count(), 2);
  assert(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await screenshot(mobile, "routine-mobile.png");
  await mobile.goto(base + "/refreshed/report/index.html");
  await restore(mobile, exported);
  assert.match(await mobile.locator("#review-import-status").innerText(), /0 restored.*2 did not match/);
  assert((await download(mobile)).reviews.every(entry => entry.case_id === "" && entry.decision === "unreviewed" && entry.note === ""));
  await mobile.goto(base + "/failed/report/index.html");
  assert.equal(await mobile.locator(".review-tools").count(), 2);
  assert.equal(await mobile.locator("[data-rendering]").count(), 0);
  assert.match(await mobile.locator("body").innerText(), /Synthetic shared preview failure/);
  await mobile.goto(base + "/default/report/index.html");
  assert.equal(await mobile.locator(".review-tools").count(), 0);
  assert.equal(await mobile.locator("#review-queue").count(), 0);
  const nojsContext = await freshContext({javaScriptEnabled: false, viewport: {width: 390, height: 844}});
  const nojs = await nojsContext.newPage();
  await nojs.goto(base + "/routine/report/index.html");
  assert.equal(await nojs.getByText("Open original PNG", {exact: true}).count(), 7);
  assert.match(await nojs.locator("body").innerText(), /Enable JavaScript/);
  await nojs.locator(".table-wrap details summary").click();
  assert.match(await nojs.locator("body").innerText(), /Synthetic cloud.mask coverage gap/);
  await screenshot(nojs, "routine-nojs.png");
  assert.deepEqual(errors, []);
  assert.deepEqual(nonGet, []);
  assert.deepEqual(external, []);
  fs.writeFileSync(path.join(root, "routine-browser-qa.json"), JSON.stringify({synthetic_only: true, passed: true, checks: ["routine-empty-case-identity", "negative-and-incomplete-queue", "fixed-and-shared-switch-same-identity", "exact-export-restore", "stale-timestamp-rejected", "mobile", "no-JavaScript-original-links", "shared-failure", "default-opt-out", "no-external-request"]}, null, 2));
  console.log("Synthetic routine review browser QA passed: " + root);
})().catch(error => {console.error(error); process.exitCode = 1;}).finally(async () => {
  if (browser) await browser.close();
  server.close();
});
