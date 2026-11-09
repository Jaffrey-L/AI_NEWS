import { expect, test } from "@playwright/test";

expect.extend({
  async toHaveCountGreaterThan(locator, expected) {
    const actual = await locator.count();
    return {
      pass: actual > expected,
      message: () => `expected count ${actual} to be greater than ${expected}`
    };
  }
});

test.beforeEach(async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".card").first()).toBeVisible();
});

test("loads readable monthly AI news cards", async ({ page }) => {
  await expect(page.locator(".top-briefing")).toBeVisible();
  await expect(page.locator(".top-card")).toHaveCount(10);
  await expect(page.locator(".top-card[data-top-link]")).toHaveCount(10);
  await expect(page.locator(".top-card[data-top-link]").first()).toHaveAttribute("href", /^https?:\/\//);
  await expect(page.locator(".top-card[data-top-link]").first()).toHaveAttribute("target", "_blank");
  await expect(page.locator(".top-card[data-top-link]").first()).toContainText("查看原文");
  await expect(page.locator("#sourceHealth")).toContainText("\u6765\u6e90\u5065\u5eb7");
  await expect(page.locator("#sourceHealth")).toContainText("\u7cbe\u9009\u515c\u5e95");
  await expect(page.locator(".card h3").first()).toBeVisible();
  await expect(page.locator(".card")).toHaveCountGreaterThan(30);
  await expect(page.locator(".reading-actions").first()).toBeVisible();
  await expect(page.locator(".brief-grid").first()).toBeVisible();
  await expect(page.locator("#qualityFilter")).toHaveValue("default");
  await expect(page.locator(".quality-review").first()).toContainText("\u8d28\u91cf\u7406\u7531");
  await expect(page.locator(".card").first()).toHaveAttribute("data-quality-score", /^[6-9]\d|100$/);
  await expect(page.locator(".key-points").first()).toBeVisible();
  await expect(page.locator(".visual").first()).toBeVisible();
  await expect(page.locator(".chip").filter({ hasText: /\u6280\u672f\u66f4\u65b0|\u91cd\u8981\u529f\u80fd\u66f4\u65b0|AI\u5e94\u7528\u65b9\u6cd5/ }).first()).toBeVisible();
  await expect(page.locator(".read-more-note").first()).toContainText("\u5982\u679c\u611f\u5174\u8da3\u8bf7\u70b9\u51fb\u67e5\u770b\u539f\u6587");
  await expect(page.locator(".original-title")).toHaveCount(0);
  await expect(page.locator("#kpiTotal")).not.toHaveText("-");
});

test("filters A-grade sources", async ({ page }) => {
  await page.selectOption("#gradeFilter", "A");
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toBeVisible();
  await expect(page.locator(".card").filter({ hasNotText: "A\u7ea7\u4fe1\u6e90" })).toHaveCount(0);
});

test("filters creator articles", async ({ page }) => {
  await page.selectOption("#categoryFilter", "\u6838\u5fc3AI\u535a\u4e3b");
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toContainText("\u6838\u5fc3AI\u535a\u4e3b");
});

test("source, date, search and reset work", async ({ page }) => {
  const initialCount = await page.locator(".card").count();
  await page.selectOption("#sourceFilter", { index: 1 });
  await expect(page.locator(".card")).toHaveCount(initialCount);
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toBeVisible();

  await page.click('[data-days="7"]');
  await expect(page.locator('[data-days="7"]')).toHaveClass(/active/);
  await expect(page.locator(".card").first()).toBeVisible();
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toBeVisible();

  await page.fill("#startDateFilter", "2099-01-01");
  await page.fill("#endDateFilter", "2099-01-02");
  await expect(page.locator(".card").first()).toBeVisible();
  await page.click("#applyBtn");
  await expect(page.locator(".empty")).toBeVisible();

  await page.click("#resetBtn");
  await page.fill("#searchInput", "OpenAI");
  await expect(page.locator(".card")).toHaveCountGreaterThan(20);
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toContainText(/OpenAI/i);

  await page.click("#resetBtn");
  await expect(page.locator("#categoryFilter")).toHaveValue("all");
  await expect(page.locator("#sourceFilter")).toHaveValue("all");
  await expect(page.locator("#readingFilter")).toHaveValue("all");
  await expect(page.locator("#qualityFilter")).toHaveValue("default");
  await expect(page.locator('[data-days="year"]')).toHaveClass(/active/);
  await expect(page.locator("#searchInput")).toHaveValue("");
  await expect(page.locator(".card")).toHaveCountGreaterThan(30);
});

test("practice category remains usable", async ({ page }) => {
  await page.selectOption("#categoryFilter", "Vibe/Prompt/Agent\u5b9e\u6218");
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toContainText("Vibe/Prompt/Agent\u5b9e\u6218");
});

test("date fields use native date picker controls", async ({ page }) => {
  await expect(page.locator("#startDateFilter")).toHaveAttribute("type", "date");
  await expect(page.locator("#endDateFilter")).toHaveAttribute("type", "date");
  await expect(page.locator('[data-target="startDateFilter"]')).toBeVisible();
  await expect(page.locator('[data-target="endDateFilter"]')).toBeVisible();
});

test("source health details and reading state persist", async ({ page }) => {
  await page.click("#sourceHealthToggle");
  await expect(page.locator("#sourceHealthPanel")).toBeVisible();
  await expect(page.locator(".source-health-row").filter({ hasText: "AI\u4e2a\u4eba\u516c\u53f8\u5927\u795e" }).first()).toBeVisible();

  const firstTitle = await page.locator(".card h3").first().innerText();
  await page.locator(".card").first().locator('[data-state="read"]').click();
  await page.locator(".card").first().locator('[data-state="favorite"]').click();
  await page.locator(".card").first().locator('[data-state="later"]').click();
  await expect(page.locator(".card").first()).toHaveClass(/is-read/);

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator(".card h3").first()).toContainText(firstTitle.slice(0, 12));
  await expect(page.locator(".card").first().locator('[data-state="read"]')).toHaveClass(/active/);

  await page.selectOption("#readingFilter", "favorite");
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toContainText(firstTitle.slice(0, 12));

  await page.selectOption("#readingFilter", "later");
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toContainText(firstTitle.slice(0, 12));
});

test("exports reusable daily digest", async ({ page }) => {
  await expect(page.locator(".digest-export")).toBeVisible();
  await expect(page.locator("#copyBriefBtn")).toBeVisible();
  await expect(page.locator("#copyBriefBtn")).toContainText("复制今日简报");
  await expect(page.locator("#digestQualityChips")).toContainText("Top 情报");
  await expect(page.locator("#digestReadablePreview")).toContainText("最值得看 3 条");
  await expect(page.locator("#digestReadablePreview .digest-story")).toHaveCount(3);
  await expect(page.locator("#digestReadablePreview .digest-story").first()).toHaveAttribute("href", /^https?:\/\//);
  await expect(page.locator("#digestReadablePreview .digest-method-link").first()).toHaveAttribute("href", /^https?:\/\//);
  await expect(page.locator("#digestWechatPreview")).toContainText("AI Daily Radar 日报");
  await expect(page.locator("#digestWechatPreview .digest-channel-link")).toHaveCount(3);
  await expect(page.locator("#digestWechatPreview .digest-channel-link").first()).toHaveAttribute("href", /^https?:\/\//);
  await expect(page.locator(".digest-source")).not.toHaveAttribute("open", "");
  await expect(page.locator("#digestPreview")).toHaveValue(/AI Daily Radar 日报/);
  await expect(page.locator("#digestPreview")).toHaveValue(/今日必看 Top \d+/);
  await expect(page.locator("#digestPreview")).toHaveValue(/7 天趋势雷达/);
  await expect(page.locator("#digestPreview")).toHaveValue(/方法论与实战/);
  await expect(page.locator("#digestPreview")).toHaveValue(/来源健康/);
  await expect(page.locator("#serverDigestLink")).toHaveAttribute("href", /\.\/data\/digests\/latest\.md/);
  await expect(page.locator("#digestArchiveMeta")).toContainText("服务器已生成归档");

  await page.evaluate(() => {
    window.__copiedText = "";
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (text) => { window.__copiedText = text; } }
    });
  });
  await page.click("#copyBriefBtn");
  await expect(page.locator("#digestStatus")).toContainText("今日简报 已复制");
  expect(await page.evaluate(() => window.__copiedText.includes("AI Daily Radar 今日简报"))).toBe(true);

  await page.click("#copyMarkdownBtn");
  await expect(page.locator("#digestStatus")).toContainText("Markdown 已复制");
  expect(await page.evaluate(() => /## 今日必看 Top \d+/.test(window.__copiedText))).toBe(true);

  await page.click("#copyWechatBtn");
  await expect(page.locator("#digestStatus")).toContainText("微信/飞书版日报 已复制");
  expect(await page.evaluate(() => window.__copiedText.includes("如果感兴趣请点击查看原文章"))).toBe(true);

  const download = page.waitForEvent("download");
  await page.click("#downloadDigestBtn");
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/ai-daily-radar-\d{4}-\d{2}-\d{2}\.md/);
});

test("quality filter switches default, top candidates, all and archive", async ({ page }) => {
  await expect(page.locator("#qualityFilter")).toHaveValue("default");
  await expect(page.locator(".card").first()).toHaveAttribute("data-quality-tier", /default|top/);

  await page.selectOption("#qualityFilter", "top");
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toHaveAttribute("data-quality-tier", "top");
  const topScores = await page.locator(".card").evaluateAll((cards) => cards.map((card) => Number(card.dataset.qualityScore)));
  expect(topScores.length).toBeGreaterThan(0);
  expect(topScores.every((score) => score >= 80)).toBe(true);

  await page.selectOption("#qualityFilter", "archive");
  await page.click("#applyBtn");
  const archiveCount = await page.locator(".card:not(.empty)").count();
  if (archiveCount > 0) {
    await expect(page.locator(".card").first()).toHaveAttribute("data-quality-tier", "archive");
    await expect(page.locator(".quality-review").first()).toContainText("\u5f52\u6863");
  } else {
    await expect(page.locator(".empty")).toBeVisible();
  }

  await page.selectOption("#qualityFilter", "all");
  await page.click("#applyBtn");
  await expect(page.locator(".card").first()).toBeVisible();
});

test("shows seven day trend radar", async ({ page }) => {
  await expect(page.locator(".trend-radar")).toBeVisible();
  await expect(page.locator("#trendMeta")).toContainText("共");
  await expect(page.locator("#companyTrends .trend-row").first()).toBeVisible();
  await expect(page.locator("#modelTrends .trend-row").first()).toBeVisible();
  await expect(page.locator("#topicTrends .trend-row").first()).toBeVisible();
});

test("desktop layout keeps filters left of stream", async ({ page }) => {
  const filterBox = await page.locator(".filters").boundingBox();
  const streamBox = await page.locator(".stream").boundingBox();
  expect(filterBox).not.toBeNull();
  expect(streamBox).not.toBeNull();
  expect(filterBox.x).toBeLessThan(streamBox.x);
});
