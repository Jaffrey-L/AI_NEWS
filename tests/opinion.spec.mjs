import { expect, test } from "@playwright/test";

test("weekly reading keeps its three answers and original links", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#v-week .answers .ans")).toHaveCount(3);
  await expect(page.locator("#v-week .hero h1")).not.toBeEmpty();
  await expect(page.locator("#v-week .schip")).not.toHaveCount(0);
  await expect(page.locator("#v-week .srclist li")).not.toHaveCount(0);
  await page.locator("#wkpick").selectOption("2026-W44");
  await expect(page).toHaveURL(/week=2026-W44/);
  await expect(page.locator("#v-week .hero h1")).not.toBeEmpty();
  expect(errors).toEqual([]);
});

test("Amazon shows only this week's dated originals in three distinct groups", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.locator('.tab[data-v="amazon"]').click();
  await expect(page.locator("#v-amazon .answers .ans")).toHaveCount(3);
  await expect(page.locator("#v-amazon .hero")).toContainText("W46 · 11.09–11.15（进行中）");
  await expect(page.locator("#wkpick")).toBeHidden();
  const cards = page.locator("#v-amazon .answers .ans");
  await expect(cards.nth(0)).toContainText("本周没有已核实的对应文章");
  await expect(cards.nth(1)).toContainText("AI 解读");
  await expect(cards.nth(1).locator('ol li').first()).toContainText("服务商授权升级");
  await expect(cards.nth(1)).toContainText("深圳APEC管控");
  await expect(cards.nth(1)).toContainText("IOSS改革");
  await expect(page.locator("#v-amazon .answers")).not.toContainText("Amazon Bedrock");
  await expect(page.locator("#v-amazon .answers")).not.toContainText("SAMPLE HOUSE");
  await expect(page.locator("#v-amazon")).not.toContainText("-AMZ123跨境导航");
  const groups = await page.locator("#v-amazon .answers .ans").evaluateAll((cards) =>
    cards.map((card) => [...card.querySelectorAll("li a")].map((a) => a.href))
  );
  expect(groups.every((group) => group.length <= 3)).toBe(true);
  const all = groups.flat();
  expect(all.length).toBeGreaterThan(0);
  expect(new Set(all).size).toBe(all.length);
  for (const url of all) expect(url).toMatch(/^https:\/\//);
  await expect(page.locator("#v-amazon .amazon-article")).not.toHaveCount(0);
  await expect(page.locator("#v-amazon")).not.toContainText("公众号");
});

test("older Amazon articles remain in the source archive", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.locator('.tab[data-v="sources"]').click();
  await expect(page.locator(".amazon-archive-link")).toHaveCount(42);
  await expect(page.locator("#v-sources")).toContainText("最近 2026.10.15");
  await expect(page.locator("#v-sources")).toContainText("最近 2026.06.23");
  await expect(page.locator("#v-sources")).toContainText("雨果网");
  await expect(page.locator("#v-sources")).toContainText("AWS 机器学习博客");
  await expect(page.locator("#v-sources")).not.toContainText("公众号");
});

test("all views fit a phone viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  for (const view of ["week", "amazon", "sources", "journey"]) {
    await page.locator(`.tab[data-v="${view}"]`).click();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${view} overflows`).toBeLessThanOrEqual(1);
  }
});
