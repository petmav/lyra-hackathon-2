import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

const screenshotsDir = path.resolve(__dirname, "../../../screenshots/e2e");

const coreRoutes = [
  "/",
  "/workflows",
  "/workflow-runs",
  "/hooks",
  "/hooks/validate",
  "/corpora",
  "/evidence",
  "/inventory",
  "/obligations",
  "/sandbox"
] as const;

test.describe("Praetor platform business flows", () => {
  test("core pages render without document/API 404s and produce visual evidence", async ({ page }, testInfo) => {
    for (const route of coreRoutes) {
      await visitClean(page, route);
      await expect(page.locator("body")).toContainText(/Praetor|Workflow|Evidence|Hooks|Inventory|Obligation|Sandbox|Corpora/i);
      await screenshot(page, testInfo, `route-${slug(route)}`);
    }
  });

  test("dashboard links point at currently available production/demo records", async ({ page, request }, testInfo) => {
    await visitClean(page, "/");
    await expect(page.getByRole("link", { name: /View (live run|runs)/i })).toBeVisible();

    const links = await internalLinks(page);
    const importantLinks = links.filter((href) =>
      href.startsWith("/workflow-runs/") ||
      href.startsWith("/findings/") ||
      href.startsWith("/proposed-changes/") ||
      href.startsWith("/assets/")
    );

    expect(importantLinks.length).toBeGreaterThan(0);
    await expectLinksOk(request, importantLinks);
    await screenshot(page, testInfo, "dashboard-current-record-links");
  });

  test("business flow: instantiate workflow, inspect governed agent run, and open step detail", async ({ page }, testInfo) => {
    await visitClean(page, "/workflows");
    const templateHref = await page.locator('a[href^="/workflows/"]').first().getAttribute("href");
    expect(templateHref).toBeTruthy();
    await visitClean(page, templateHref!);
    await expect(page.getByRole("button", { name: /instantiate run/i })).toBeVisible();
    await page.getByRole("button", { name: /instantiate run/i }).click();
    await expect(page).toHaveURL(/\/workflow-runs\/[^/]+$/);
    await expect(page.locator("body")).toContainText(/Compliance|Steps|Findings|Proposed changes/i);
    await screenshot(page, testInfo, "flow-workflow-run");

    const stepTarget = page.locator("text=/scan|agent|pull/i").first();
    if (await stepTarget.count()) {
      await stepTarget.click({ force: true });
      await expect(page.locator("body")).toContainText(/Runtime trace|Inputs|Outputs|sandbox|agent/i);
      await screenshot(page, testInfo, "flow-workflow-step-detail");
    }
  });

  test("business flow: review finding and proposed remediation path", async ({ page }, testInfo) => {
    await visitClean(page, "/");
    const findingLink = page.locator('a[href^="/findings/"]').first();
    test.skip((await findingLink.count()) === 0, "No finding links are available in this data set.");

    const findingHref = await findingLink.getAttribute("href");
    expect(findingHref).toBeTruthy();
    await visitClean(page, findingHref!);
    await expect(page).toHaveURL(/\/findings\/[^/]+$/);
    await expect(page.locator("body")).toContainText(/Finding|Case file|confidence|citation/i);
    await screenshot(page, testInfo, "flow-finding-review");

    const proposalLink = page.locator('a[href^="/proposed-changes/"]').first();
    if (await proposalLink.count()) {
      const proposalHref = await proposalLink.getAttribute("href");
      expect(proposalHref).toBeTruthy();
      await visitClean(page, proposalHref!);
      await expect(page).toHaveURL(/\/proposed-changes\/[^/]+$/);
      await expect(page.locator("body")).toContainText(/Apply|Diff|sandbox|approval/i);
      await screenshot(page, testInfo, "flow-proposed-change-review");
    }
  });

  test("business flow: inspect integrations, JSON stack validation, and provider streaming readiness", async ({ page }, testInfo) => {
    await visitClean(page, "/hooks");
    await expect(page.locator("body")).toContainText(/Boundary crossings|Configured hooks|Recent calls/i);
    await screenshot(page, testInfo, "flow-hooks-directory");

    await page.getByRole("link", { name: /Validate manifest/i }).click();
    await expect(page).toHaveURL(/\/hooks\/validate$/);
    await expect(page.locator("body")).toContainText(/JSON input|OpenAPI to JSON Stack|Provider stream probe/i);
    await screenshot(page, testInfo, "flow-hooks-validate");
  });

  test("business flow: generate audit packet and inspect evidence ledger", async ({ page }, testInfo) => {
    await visitClean(page, "/evidence");
    await expect(page.locator("body")).toContainText(/Generate Audit Packet|Evidence ledger/i);
    await screenshot(page, testInfo, "flow-evidence-before-generate");

    await page.getByRole("button", { name: /generate packet/i }).click();
    await expect(page.locator("body")).toContainText(/Recent packets|Evidence ledger/i);
    await screenshot(page, testInfo, "flow-evidence-after-generate");
  });

  test("demo pitch flow: end-to-end story pages are readable and screenshot-backed", async ({ page }, testInfo) => {
    const story = [
      { route: "/", assertion: /Today's|filing|governed assets/i },
      { route: "/workflows", assertion: /Run AI agents|Choose a workflow|Recent runs/i },
      { route: "/hooks", assertion: /Boundary crossings|MCP|JSON Hook Stack|Configured hooks/i },
      { route: "/evidence", assertion: /tangible|audit packet|Evidence ledger/i }
    ];

    for (const beat of story) {
      await visitClean(page, beat.route);
      await expect(page.locator("body")).toContainText(beat.assertion);
      await screenshot(page, testInfo, `pitch-${slug(beat.route)}`);
    }

    await visitClean(page, "/");
    const runHref = await page.getByRole("link", { name: /View (live run|runs)/i }).getAttribute("href");
    expect(runHref).toBeTruthy();
    await visitClean(page, runHref!);
    await expect(page.locator("body")).toContainText(/Workflow|run|Steps|Ledger/i);
    await screenshot(page, testInfo, "pitch-live-run");
  });
});

async function visitClean(page: Page, route: string): Promise<void> {
  const failures: string[] = [];
  const onPageError = (error: Error) => failures.push(`pageerror: ${error.message}`);
  const onConsole = (message: { type(): string; text(): string }) => {
    if (message.type() === "error") failures.push(`console: ${message.text()}`);
  };
  const onResponse = (response: { url(): string; status(): number; request(): { resourceType(): string } }) => {
    const resourceType = response.request().resourceType();
    if (!["document", "fetch", "xhr"].includes(resourceType)) return;
    if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`);
  };

  page.on("pageerror", onPageError);
  page.on("console", onConsole);
  page.on("response", onResponse);
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await expect(page.locator("body")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/This page could not be found|Application error|404 .*not on file/i);
  page.off("pageerror", onPageError);
  page.off("console", onConsole);
  page.off("response", onResponse);

  expect(failures, `Unexpected browser failures on ${route}`).toEqual([]);
}

async function internalLinks(page: Page): Promise<string[]> {
  return Array.from(new Set(await page.locator("a[href]").evaluateAll((anchors) =>
    anchors
      .map((anchor) => anchor.getAttribute("href") ?? "")
      .filter((href) => href.startsWith("/") && !href.startsWith("//"))
      .map((href) => href.split("#")[0])
      .filter(Boolean)
  )));
}

async function expectLinksOk(request: APIRequestContext, hrefs: string[]): Promise<void> {
  for (const href of hrefs) {
    const response = await request.get(href);
    expect(response.status(), `${href} should not 404/500`).toBeLessThan(400);
  }
}

async function screenshot(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  await fs.mkdir(screenshotsDir, { recursive: true });
  await page.screenshot({
    path: path.join(screenshotsDir, `${testInfo.project.name}-${name}.png`),
    fullPage: true
  });
}

function slug(route: string): string {
  return route === "/" ? "dashboard" : route.replace(/^\//, "").replace(/[^a-z0-9]+/gi, "-").replace(/-$/, "");
}
