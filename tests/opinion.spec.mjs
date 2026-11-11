import { expect, test } from "@playwright/test";

const week = {
  week: "2026-W45", weekStart: "2026-11-02", weekEnd: "2026-11-08",
  path: "./data/weekly/2026-W45.json", title: "AI 可以提出自己的判断"
};
const earlier = {
  week: "2026-W44", weekStart: "2026-10-26", weekEnd: "2026-11-01",
  path: "./data/weekly/2026-W44.json", title: "上一周的解读"
};
const article = {
  ...week, subtitle: "这篇文章由模型撰写，但每个论点仍能回到原始资料。",
  generatedAt: "2026-11-09T12:00:00Z", model: "deepseek-flash",
  sources: [
    { id: "S1", title: "First original", sourceName: "Source One", publishedAt: "2026-11-08", url: "https://example.com/one" },
    { id: "S2", title: "Second original", sourceName: "Source Two", publishedAt: "2026-11-06", url: "https://example.com/two" }
  ],
  sections: [
    { heading: "观点", paragraphs: [{ text: "把每周解读放在首页，同时保留证据。", citations: [{ sourceId: "S1", evidence: "Original source evidence" }] }] },
    { heading: "实践", paragraphs: [{ text: "读者可以展开论据并打开原文。", citations: [{ sourceId: "S2", evidence: "Another original excerpt" }] }] }
  ]
};

async function mockArchive(page, weeks = [week, earlier]) {
  await page.route("**/data/weekly/index.json", (route) => route.fulfill({ json: { weeks } }));
  await page.route("**/data/weekly/2026-W45.json", (route) => route.fulfill({ json: article }));
}

test("weekly interpretation leads and every argument links to its original", async ({ page }) => {
  await mockArchive(page);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#opinionArticle h3")).toHaveText(article.title);
  await expect(page.locator("#opinionMeta")).toContainText("2026-11-02 至 2026-11-08");
  await expect(page.locator("#opinionArticle .opinion-citations a")).toHaveCount(2);
  await expect(page.locator("#opinionArticle .opinion-sources a")).toHaveCount(2);
  await expect(page.locator("#opinionArticle .opinion-citations a").first()).toHaveAttribute("href", "https://example.com/one");
  await page.locator("#opinionArticle details").first().locator("summary").click({ position: { x: 5, y: 5 } });
  await expect(page.locator("#opinionArticle blockquote").first()).toContainText("Original source evidence");
  await expect(page.locator(".source-intro, .overview, .trend-radar, .top-briefing, .digest-export, .layout, .sources")).toHaveCount(0);
});

test("loads only the weekly article and its cited originals", async ({ page }) => {
  const fetched = [];
  page.on("request", (request) => fetched.push(request.url()));
  await mockArchive(page, [week]);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#opinionArticle h3")).toHaveText(article.title);
  await expect(page.locator("#opinionArticle .opinion-citations a")).toHaveCount(2);
  expect(fetched.some((url) => url.endsWith("/data/news.json") || url.endsWith("/sources.json"))).toBe(false);
});

test("week archive keeps the last article if another week fails", async ({ page }) => {
  await mockArchive(page);
  await page.route("**/data/weekly/2026-W44.json", (route) => route.fulfill({ status: 404, body: "" }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.locator("#weekSelect").selectOption("2026-W44");
  await expect(page.locator("#opinionMeta")).toContainText("暂时无法读取");
  await expect(page.locator("#opinionArticle h3")).toHaveText(article.title);
});

test("selecting an earlier week changes the interpretation and URL", async ({ page }) => {
  await mockArchive(page);
  await page.route("**/data/weekly/2026-W44.json", (route) => route.fulfill({
    json: { ...article, ...earlier }
  }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.locator("#weekSelect").selectOption("2026-W44");
  await expect(page.locator("#opinionArticle h3")).toHaveText(earlier.title);
  await expect(page).toHaveURL(/week=2026-W44/);
});

test("treats article text as text, not executable markup", async ({ page }) => {
  const untrusted = structuredClone(article);
  untrusted.sections[0].paragraphs[0].text = "<img src=x onerror=alert(1)>";
  await mockArchive(page, [week]);
  await page.route("**/data/weekly/2026-W45.json", (route) => route.fulfill({ json: untrusted }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#opinionArticle img")).toHaveCount(0);
  await expect(page.locator("#opinionArticle p").filter({ hasText: "<img" })).toBeVisible();
});

test("real weekly article fits a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#opinionArticle h3")).not.toBeEmpty();
  await expect(page.locator("#opinionMeta")).toContainText("AI 自动撰写");
  await expect(page.locator("#opinionArticle .opinion-citations a").first()).toHaveAttribute("href", /^https:\/\//);
  const box = await page.locator(".opinion").boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(375);
});
