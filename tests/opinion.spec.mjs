import { expect, test } from "@playwright/test";

const article = {
  title: "AI 可以提出自己的判断",
  subtitle: "这篇文章由模型撰写，但每个论点仍能回到原始资料。",
  editionDate: "2026-11-09",
  windowDays: 3,
  sources: [
    { id: "S1", sourceName: "Source One", publishedAt: "2026-11-09", url: "https://example.com/one" },
    { id: "S2", sourceName: "Source Two", publishedAt: "2026-11-08", url: "https://example.com/two" }
  ],
  sections: [
    { heading: "观点", paragraphs: [{ text: "把文章放在首页，同时保留证据。", citations: [{ sourceId: "S1", evidence: "Original source evidence" }] }] },
    { heading: "实践", paragraphs: [{ text: "读者可以展开论据并打开原文。", citations: [{ sourceId: "S2", evidence: "Another original excerpt" }] }] }
  ]
};

test("shows AI article before news and links each argument to evidence", async ({ page }) => {
  await page.route("**/data/opinion/latest.json", (route) => route.fulfill({ json: article }));
  await page.route("**/data/opinion/status.json", (route) => route.fulfill({ json: { state: "published" } }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#opinionArticle h3")).toHaveText(article.title);
  await expect(page.locator("#opinionMeta")).toContainText("AI 自动撰写");
  await expect(page.locator("#opinionArticle a")).toHaveCount(2);
  await expect(page.locator("#opinionArticle a").first()).toHaveAttribute("href", "https://example.com/one");
  await page.locator("#opinionArticle details").first().locator("summary").click({ position: { x: 5, y: 5 } });
  await expect(page.locator("#opinionArticle blockquote").first()).toContainText("Original source evidence");
  expect(await page.locator(".opinion").evaluate((element) => element.compareDocumentPosition(document.querySelector(".overview")) & Node.DOCUMENT_POSITION_FOLLOWING)).toBeTruthy();
});

test("keeps last edition visible when automatic update fails", async ({ page }) => {
  await page.route("**/data/opinion/latest.json", (route) => route.fulfill({ json: article }));
  await page.route("**/data/opinion/status.json", (route) => route.fulfill({ json: { state: "failed" } }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#opinionMeta")).toContainText("本轮更新失败，显示上期文章");
  await expect(page.locator("#opinionArticle h3")).toHaveText(article.title);
});

test("treats article text as text, not executable markup", async ({ page }) => {
  const untrusted = structuredClone(article);
  untrusted.sections[0].paragraphs[0].text = "<img src=x onerror=alert(1)>";
  await page.route("**/data/opinion/latest.json", (route) => route.fulfill({ json: untrusted }));
  await page.route("**/data/opinion/status.json", (route) => route.fulfill({ json: { state: "published" } }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#opinionArticle img")).toHaveCount(0);
  await expect(page.locator("#opinionArticle p").filter({ hasText: "<img" })).toBeVisible();
});

test("shows the seeded article and keeps its reading column inside a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#opinionArticle h3")).toContainText("人的工作要从产出转向判断");
  await expect(page.locator("#opinionMeta")).toContainText("AI 示例首刊");
  await expect(page.locator("#opinionArticle a").first()).toHaveAttribute("href", /^https:\/\//);
  const box = await page.locator(".opinion").boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(375);
});
