const DATA_ENDPOINT = "./data/news.json";
const SOURCES_ENDPOINT = "./sources.json";

const TEXT = {
  all: "\u5168\u90e8",
  coreCompany: "\u6838\u5fc3AI\u516c\u53f8\u65b0\u95fb",
  creator: "\u6838\u5fc3AI\u535a\u4e3b",
  solo: "AI\u4e2a\u4eba\u516c\u53f8\u5927\u795e",
  practice: "Vibe/Prompt/Agent\u5b9e\u6218",
  countPrefix: "\u5171",
  countSuffix: "\u6761",
  gradeSuffix: "\u7ea7\u4fe1\u6e90",
  importance: "\u91cd\u8981\u5ea6",
  tags: "\u6807\u7b7e",
  source: "\u6765\u6e90",
  readingScore: "\u53ef\u8bfb\u6027",
  qualityScore: "\u8d28\u91cf\u5206",
  qualityReason: "\u8d28\u91cf\u7406\u7531",
  qualityPenalty: "\u6263\u5206\u539f\u56e0",
  keyPoints: "\u8981\u70b9",
  readMoreNote: "\u5982\u679c\u611f\u5174\u8da3\u8bf7\u70b9\u51fb\u67e5\u770b\u539f\u6587"
};

const fallbackNews = [
  {
    title: "OpenAI launches DeployCo to help businesses build around intelligence",
    summary: "\u6765\u81ea OpenAI \u7684\u6700\u65b0\u52a8\u6001\uff0c\u5efa\u8bae\u6253\u5f00\u539f\u6587\u6838\u9a8c\u7ec6\u8282\u3002",
    date: "2026-05-11",
    sourceName: "OpenAI",
    sourceUrl: "https://openai.com/news/",
    sourceGrade: "A",
    category: TEXT.coreCompany,
    tags: ["OpenAI", "official"],
    importance: 5
  }
];

const categories = [TEXT.all, TEXT.coreCompany, TEXT.creator, TEXT.solo, TEXT.practice];
const TAG_LABELS = {
  official: "\u5b98\u65b9\u52a8\u6001",
  enterprise: "\u4f01\u4e1a\u5e94\u7528",
  creator: "\u535a\u4e3b\u89c2\u70b9",
  practice: "\u5b9e\u6218\u65b9\u6cd5",
  agent: "\u667a\u80fd\u4f53",
  agents: "\u667a\u80fd\u4f53",
  coding: "\u7f16\u7a0b",
  prompt: "\u63d0\u793a\u8bcd",
  workflow: "\u5de5\u4f5c\u6d41",
  research: "\u7814\u7a76",
  model: "\u6a21\u578b",
  search: "\u641c\u7d22",
  video: "\u89c6\u9891",
  newsletter: "\u901a\u8baf",
  "open-source": "\u5f00\u6e90",
  vibecoding: "Vibe Coding"
};

const categoryFilter = document.getElementById("categoryFilter");
const gradeFilter = document.getElementById("gradeFilter");
const sourceFilter = document.getElementById("sourceFilter");
const readingFilter = document.getElementById("readingFilter");
const qualityFilter = document.getElementById("qualityFilter");
const startDateFilter = document.getElementById("startDateFilter");
const endDateFilter = document.getElementById("endDateFilter");
const presetButtons = Array.from(document.querySelectorAll(".preset-btn"));
const sortFilter = document.getElementById("sortFilter");
const searchInput = document.getElementById("searchInput");
const applyBtn = document.getElementById("applyBtn");
const resetBtn = document.getElementById("resetBtn");
const newsList = document.getElementById("newsList");
const topStoriesEl = document.getElementById("topStories");
const sourceHealthEl = document.getElementById("sourceHealth");
const sourceHealthToggle = document.getElementById("sourceHealthToggle");
const sourceHealthPanel = document.getElementById("sourceHealthPanel");
const digestPreview = document.getElementById("digestPreview");
const digestMeta = document.getElementById("digestMeta");
const digestArchiveMeta = document.getElementById("digestArchiveMeta");
const digestQualityChips = document.getElementById("digestQualityChips");
const digestReadablePreview = document.getElementById("digestReadablePreview");
const digestWechatPreview = document.getElementById("digestWechatPreview");
const digestStatus = document.getElementById("digestStatus");
const serverDigestLink = document.getElementById("serverDigestLink");
const copyBriefBtn = document.getElementById("copyBriefBtn");
const copyMarkdownBtn = document.getElementById("copyMarkdownBtn");
const copyWechatBtn = document.getElementById("copyWechatBtn");
const downloadDigestBtn = document.getElementById("downloadDigestBtn");
const trendMeta = document.getElementById("trendMeta");
const companyTrends = document.getElementById("companyTrends");
const modelTrends = document.getElementById("modelTrends");
const topicTrends = document.getElementById("topicTrends");
const resultCount = document.getElementById("resultCount");
const READING_STATE_KEY = "ai-daily-radar-reading-state-v1";
let appliedFilters = null;
let activeNewsItems = [];
let allNewsItems = [];
let readingState = loadReadingState();
let digestCache = { markdown: "", wechat: "", brief: "", filename: "ai-daily-radar.md" };

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;"
  })[char]);
}

function loadReadingState() {
  try {
    return JSON.parse(localStorage.getItem(READING_STATE_KEY) || "{}");
  } catch (_) {
    return {};
  }
}

function saveReadingState() {
  localStorage.setItem(READING_STATE_KEY, JSON.stringify(readingState));
}

function itemKey(item) {
  return encodeURIComponent(item.eventId || item.sourceUrl || item.title || "");
}

function getItemState(item) {
  return readingState[itemKey(item)] || {};
}

function toggleItemState(item, field) {
  const key = itemKey(item);
  const state = { ...(readingState[key] || {}) };
  state[field] = !state[field];
  readingState[key] = state;
  saveReadingState();
}

function plainText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function firstSentence(value, fallback = "") {
  const text = plainText(value || fallback);
  return text.split(/(?<=[.!?\u3002\uff01\uff1f])\s+/)[0]?.slice(0, 180) || text.slice(0, 180);
}

function formatDigestDate(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return new Date().toISOString().slice(0, 10);
  return date.toISOString().slice(0, 10);
}

function markdownLink(title, url) {
  return url ? `[${title}](${url})` : title;
}

function topNames(rows, limit = 3) {
  return (rows || []).slice(0, limit).map((row) => `${row.name} ${row.count}`).join(" / ") || "暂无明显集中趋势";
}

function uniqueValues(values, limit = 3) {
  const seen = new Set();
  const result = [];
  values.forEach((value) => {
    const text = plainText(value);
    if (!text || seen.has(text)) return;
    seen.add(text);
    result.push(text);
  });
  return result.slice(0, limit);
}

function buildDigest(payload, newsItems) {
  const items = newsItems || [];
  const top = (payload.topStories?.length ? payload.topStories : items.slice(0, 10)).slice(0, 10);
  const methods = items.filter((item) => item.qualityScore >= 80 && (item.qualityType === "application_method" || item.category === TEXT.practice)).slice(0, 5);
  const official = items.filter((item) => item.sourceGrade === "A").slice(0, 5);
  const health = payload.sourceHealth || {};
  const trends = payload.trends || {};
  const date = formatDigestDate(payload.updatedAt);
  const trendLines = [
    "## 7 天趋势雷达",
    `- 公司热度：${(trends.companies || []).slice(0, 5).map((row) => `${row.name} ${row.count}`).join(" / ") || "暂无明显集中趋势"}`,
    `- 模型热度：${(trends.models || []).slice(0, 5).map((row) => `${row.name} ${row.count}`).join(" / ") || "暂无明显集中趋势"}`,
    `- 主题热度：${(trends.topics || []).slice(0, 5).map((row) => `${row.name} ${row.count}`).join(" / ") || "暂无明显集中趋势"}`,
    "",
  ];
  const lines = [
    `# AI Daily Radar 日报 - ${date}`,
    "",
    `> 今日默认展示 ${items.length} 条高质量情报，Top ${top.length} 已精选。来源健康：${health.ok || 0}/${health.total || 0} 正常，${health.empty || 0} 暂无高价值内容，${health.curated || 0} 精选兜底，${health.failed || 0} 失败。`,
    "",
    `## 今日必看 Top ${top.length}`,
    ...top.flatMap((item, index) => {
      const brief = item.intelligenceBrief || {};
      return [
        "",
        `${index + 1}. ${markdownLink(item.titleZh || item.title, item.sourceUrl)}`,
        `   - 推荐理由：${plainText(brief.recommendationReason || item.summaryZh || item.summary)}`,
        `   - 启发：${plainText(brief.takeaway || firstSentence(item.summaryZh || item.summary))}`,
        `   - 来源：${item.sourceName} / ${item.date} / ${item.qualityLabelZh || ""}`,
      ];
    }),
    "",
    ...trendLines,
    "## 方法论与实战",
    ...methods.map((item, index) => `${index + 1}. ${markdownLink(item.titleZh || item.title, item.sourceUrl)} - ${firstSentence(item.intelligenceBrief?.takeaway || item.summaryZh || item.summary)}`),
    "",
    "## A级/一手来源观察",
    ...official.map((item, index) => `${index + 1}. ${markdownLink(item.titleZh || item.title, item.sourceUrl)} - ${item.sourceName}`),
    "",
    "## 阅读建议",
    "- 先读 Top 10，快速判断今天最值得跟进的模型、产品和方法论变化。",
    "- 对企业应用相关内容，重点看 API、Agent 工作流、成本结构和落地路径。",
    "- 如果感兴趣请点击查看原文章，做决策前建议核验完整语境。",
  ];
  const wechat = [
    `AI Daily Radar 日报｜${date}`,
    "",
    `今天默认展示 ${items.length} 条高质量 AI 情报，精选 Top ${top.length}。`,
    "",
    "今日最值得看：",
    ...top.slice(0, 6).map((item, index) => `${index + 1}. ${item.titleZh || item.title}\n   ${firstSentence(item.intelligenceBrief?.recommendationReason || item.summaryZh || item.summary)}\n   原文：${item.sourceUrl}`),
    "",
    "实战方法提醒：",
    ...methods.slice(0, 3).map((item) => `- ${item.titleZh || item.title}：${firstSentence(item.intelligenceBrief?.takeaway || item.summaryZh || item.summary)}`),
    "",
    "如果感兴趣请点击查看原文章。"
  ].join("\n");
  const brief = [
    `AI Daily Radar 今日简报｜${date}`,
    `一句话总览：今天默认展示 ${items.length} 条高质量 AI 情报，Top ${top.length} 已精选；7 天趋势样本 ${trends.itemCount || 0} 条。`,
    `趋势信号：${topNames(trends.topics)}。`,
    "",
    "最值得看：",
    ...top.slice(0, 5).map((item, index) => `${index + 1}. ${item.titleZh || item.title}｜${item.sourceName}｜${item.sourceUrl}`),
    "",
    "来源健康：",
    `${health.ok || 0}/${health.total || 0} 正常，${health.empty || 0} 暂无高价值内容，${health.failed || 0} 失败。`,
    "",
    "如果感兴趣请点击查看原文章。"
  ].join("\n");
  return {
    markdown: lines.join("\n"),
    wechat,
    brief,
    filename: `ai-daily-radar-${date}.md`,
  };
}

function renderDigestExport(payload, newsItems) {
  if (!digestPreview) return;
  digestCache = buildDigest(payload, newsItems);
  digestPreview.value = digestCache.markdown;
  const top = (payload.topStories?.length ? payload.topStories : newsItems.slice(0, 10)).slice(0, 10);
  const methods = newsItems.filter((item) => item.qualityScore >= 80 && (item.qualityType === "application_method" || item.category === TEXT.practice)).slice(0, 3);
  const trends = payload.trends || {};
  const health = payload.sourceHealth || {};
  if (digestMeta) {
    digestMeta.textContent = `已生成 ${newsItems.length} 条情报的简报包，默认展示阅读版和微信/飞书预览，Markdown 源码已收起。`;
  }
  if (digestQualityChips) {
    const failed = health.failed || 0;
    digestQualityChips.innerHTML = [
      `${top.length} 条 Top 情报`,
      `${trends.itemCount || 0} 条趋势样本`,
      `${health.ok || 0}/${health.total || 0} 来源正常`,
      `${(payload.archiveItems || []).length} 条归档`,
      `${failed} 个失败源`,
    ].map((label, index) => `<span class="${index === 3 && failed ? "warning" : ""}">${escapeHtml(label)}</span>`).join("");
  }
  if (digestReadablePreview) {
    const leadSources = uniqueValues(top.map((item) => item.sourceName)).join("、") || "Top 10 情报";
    digestReadablePreview.innerHTML = `
      <p class="digest-lede">今天最值得快速扫一遍的是：${escapeHtml(leadSources)}。先看趋势，再挑原文深读。</p>
      <div class="digest-mini-section">
        <h3>最值得看 3 条</h3>
        ${top.slice(0, 3).map((item, index) => `
          <a class="digest-story" href="${escapeHtml(item.sourceUrl || "#")}" target="_blank" rel="noreferrer noopener">
            <strong>${index + 1}. ${escapeHtml(item.titleZh || item.title)}</strong>
            <span>${escapeHtml(item.sourceName)} · ${escapeHtml(item.date)} · ${escapeHtml(item.qualityLabelZh || "")}</span>
            <em>${escapeHtml(item.intelligenceBrief?.recommendationReason || firstSentence(item.summaryZh || item.summary))}</em>
          </a>
        `).join("")}
      </div>
      <div class="digest-signal-row">
        <span>主题：${escapeHtml(topNames(trends.topics))}</span>
        <span>模型：${escapeHtml(topNames(trends.models))}</span>
        <span>公司：${escapeHtml(topNames(trends.companies))}</span>
      </div>
      <div class="digest-mini-section">
        <h3>方法论 / 实战</h3>
        ${methods.map(renderDigestMethodLink).join("") || "<p>今天暂无特别集中的方法论条目。</p>"}
      </div>
    `;
  }
  if (digestWechatPreview) {
    digestWechatPreview.innerHTML = `
      <h3>AI Daily Radar 日报</h3>
      <p>今天默认展示 ${escapeHtml(newsItems.length)} 条高质量 AI 情报，精选 Top ${escapeHtml(top.length)}。适合直接发到微信群、飞书群或个人知识库。</p>
      <ol>
        ${top.slice(0, 3).map(renderWechatPreviewItem).join("")}
      </ol>
      <p class="channel-note">复制版会包含重点情报、方法提醒和原文链接。</p>
    `;
  }
  if (payload.digestArchive && serverDigestLink) {
    const path = payload.digestArchive.latestPath || payload.digestArchive.path;
    serverDigestLink.href = `./${path}`;
    serverDigestLink.textContent = `打开服务器归档 ${payload.digestArchive.date || ""}`.trim();
  }
  if (digestArchiveMeta && payload.digestArchive) {
    digestArchiveMeta.textContent = `服务器已生成归档：${payload.digestArchive.path}，包含 ${payload.digestArchive.topStoryCount || 0} 条 Top 情报。`;
  }
}

function renderTrendList(container, rows) {
  if (!container) return;
  const values = Array.isArray(rows) ? rows.slice(0, 8) : [];
  if (!values.length) {
    container.innerHTML = `<p class="trend-empty">暂无明显集中趋势</p>`;
    return;
  }
  const max = Math.max(...values.map((row) => row.count || 0), 1);
  container.innerHTML = values.map((row) => {
    const width = Math.max(8, Math.round(((row.count || 0) / max) * 100));
    return `
      <div class="trend-row">
        <span>${escapeHtml(row.name)}</span>
        <strong>${escapeHtml(row.count || 0)}</strong>
        <i style="--bar-width:${width}%"></i>
      </div>
    `;
  }).join("");
}

function renderTrends(trends) {
  if (!trends) return;
  if (trendMeta) {
    trendMeta.textContent = `${trends.startDate || ""} 至 ${trends.endDate || ""}，共 ${trends.itemCount || 0} 条近期高价值情报。`;
  }
  renderTrendList(companyTrends, trends.companies);
  renderTrendList(modelTrends, trends.models);
  renderTrendList(topicTrends, trends.topics);
}

function renderDigestMethodLink(item) {
  return `
    <a class="digest-method-link" href="${escapeHtml(item.sourceUrl || "#")}" target="_blank" rel="noreferrer noopener">
      <strong>${escapeHtml(item.titleZh || item.title)}</strong>
      <span>${escapeHtml(firstSentence(item.intelligenceBrief?.takeaway || item.summaryZh || item.summary))}</span>
      <em>查看关联原文</em>
    </a>
  `;
}

function renderWechatPreviewItem(item) {
  return `
    <li>
      <a class="digest-channel-link" href="${escapeHtml(item.sourceUrl || "#")}" target="_blank" rel="noreferrer noopener">
        <strong>${escapeHtml(item.titleZh || item.title)}</strong>
        <span>${escapeHtml(firstSentence(item.intelligenceBrief?.takeaway || item.summaryZh || item.summary))}</span>
        <small>查看原文：${escapeHtml(item.sourceUrl || "")}</small>
      </a>
    </li>
  `;
}

async function copyText(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    if (digestStatus) digestStatus.textContent = `${label} 已复制`;
  } catch (_) {
    digestPreview?.select();
    document.execCommand("copy");
    if (digestStatus) digestStatus.textContent = `${label} 已复制`;
  }
}

function downloadText(text, filename) {
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  if (digestStatus) digestStatus.textContent = "Markdown 文件已生成";
}

function initCategoryOptions() {
  categoryFilter.innerHTML = "";
  categories.forEach((cat) => {
    const option = document.createElement("option");
    option.value = cat === TEXT.all ? "all" : cat;
    option.textContent = cat;
    categoryFilter.appendChild(option);
  });
}

function initSourceOptions(newsItems) {
  const sources = Array.from(new Set(newsItems.map((item) => item.sourceName).filter(Boolean))).sort();
  sourceFilter.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = TEXT.all;
  sourceFilter.appendChild(allOption);
  sources.forEach((source) => {
    const option = document.createElement("option");
    option.value = source;
    option.textContent = source;
    sourceFilter.appendChild(option);
  });
}

function setActivePreset(value) {
  presetButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.days === value);
  });
}

function initDateRange(newsItems, days = 30) {
  const dates = newsItems.map((item) => item.date).filter(Boolean).sort();
  if (!dates.length) return;
  const latest = dates[dates.length - 1];
  if (days === "year") {
    startDateFilter.value = `${latest.slice(0, 4)}-01-01`;
    endDateFilter.value = latest;
    setActivePreset("year");
    return;
  }
  if (days === "all") {
    startDateFilter.value = "";
    endDateFilter.value = "";
    setActivePreset("all");
    return;
  }
  const start = new Date(`${latest}T00:00:00`);
  start.setDate(start.getDate() - Number(days));
  startDateFilter.value = start.toISOString().slice(0, 10);
  endDateFilter.value = latest;
  setActivePreset(String(days));
}

function readFilterControls() {
  let startDate = startDateFilter.value || "";
  let endDate = endDateFilter.value || "";
  if (startDate && endDate && startDate > endDate) {
    [startDate, endDate] = [endDate, startDate];
    startDateFilter.value = startDate;
    endDateFilter.value = endDate;
  }
  return {
    category: categoryFilter.value,
    grade: gradeFilter.value,
    source: sourceFilter.value,
    reading: readingFilter.value,
    quality: qualityFilter?.value || "default",
    startDate,
    endDate,
    search: searchInput.value.trim().toLowerCase(),
    sort: sortFilter.value
  };
}

function applyCurrentFilters(newsItems) {
  appliedFilters = readFilterControls();
  renderNews(getFilteredNews(newsItems));
}

function renderNews(items) {
  newsList.innerHTML = "";
  activeNewsItems = items;
  resultCount.textContent = `${TEXT.countPrefix} ${items.length} ${TEXT.countSuffix}`;

  if (!items.length) {
    newsList.innerHTML = `<article class="card empty">${TEXT.countPrefix} 0 ${TEXT.countSuffix}</article>`;
    return;
  }

  items.forEach((item) => {
    const state = getItemState(item);
    const tags = Array.isArray(item.tags) ? item.tags : [];
    const tagLabels = tags.map((tag) => TAG_LABELS[String(tag).toLowerCase()] || tag);
    const safeUrl = String(item.sourceUrl || "#");
    const qualityReview = item.qualityReview || {};
    const card = document.createElement("article");
    card.className = `card${state.read ? " is-read" : ""}`;
    card.dataset.itemKey = itemKey(item);
    card.dataset.qualityScore = String(item.qualityScore || 0);
    card.dataset.qualityTier = qualityReview.tier || "";
    card.innerHTML = `
      <div class="meta">
        <span class="chip">${escapeHtml(item.category)}</span>
        <span class="chip grade-${escapeHtml(item.sourceGrade)}">${escapeHtml(item.sourceGrade)}${TEXT.gradeSuffix}</span>
        <span class="chip">${TEXT.importance} ${escapeHtml(item.importance || 0)}</span>
        <span class="chip">${TEXT.readingScore} ${escapeHtml(item.readingScore || 0)}</span>
        <span class="chip quality-${escapeHtml(item.qualityType || "general")}">${escapeHtml(item.qualityLabelZh || "\u4e00\u822c\u52a8\u6001")}</span>
        <span class="chip">${TEXT.qualityScore} ${escapeHtml(item.qualityScore || 0)}</span>
        <span>${escapeHtml(item.date)}</span>
      </div>
      <div class="card-body">
        ${renderVisual(item)}
        <div class="card-copy">
          <h3>${escapeHtml(item.titleZh || item.title)}</h3>
          <p>${escapeHtml(item.summaryZh || item.summary)}</p>
          ${renderReadingActions(item, state)}
          ${renderQualityReview(item)}
          ${renderIntelligenceBrief(item.intelligenceBrief)}
          ${renderKeyPoints(item.keyPointsZh || item.keyPoints)}
          <p class="tagline">${TEXT.tags}: ${escapeHtml(tagLabels.join(" / "))}</p>
          ${renderRelatedSources(item)}
          <p class="read-more-note">${TEXT.readMoreNote}</p>
          <a href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer noopener">${TEXT.source}: ${escapeHtml(item.sourceName)}</a>
        </div>
      </div>
    `;
    newsList.appendChild(card);
  });
}

function renderReadingActions(item, state) {
  const key = itemKey(item);
  return `
    <div class="reading-actions" aria-label="阅读状态">
      <button class="state-btn ${state.read ? "active" : ""}" type="button" data-key="${key}" data-state="read">${state.read ? "已读" : "标为已读"}</button>
      <button class="state-btn ${state.favorite ? "active" : ""}" type="button" data-key="${key}" data-state="favorite">${state.favorite ? "已收藏" : "收藏"}</button>
      <button class="state-btn ${state.later ? "active" : ""}" type="button" data-key="${key}" data-state="later">${state.later ? "稍后读中" : "稍后读"}</button>
    </div>
  `;
}

function renderQualityReview(item) {
  const review = item.qualityReview || {};
  const reasons = Array.isArray(review.reasons) ? review.reasons.slice(0, 3) : [];
  const penalties = Array.isArray(review.penalties) ? review.penalties.slice(0, 2) : [];
  if (!reasons.length && !penalties.length) return "";
  const tierLabel = review.isTopEligible
    ? "Top \u5019\u9009"
    : review.isDefaultVisible
      ? "\u9ad8\u8d28\u91cf\u9ed8\u8ba4"
      : "\u5f52\u6863\u4f4e\u4f18\u5148\u7ea7";
  return `
    <section class="quality-review" aria-label="${TEXT.qualityReason}">
      <div class="quality-review-head">
        <strong>${TEXT.qualityReason}</strong>
        <span>${escapeHtml(tierLabel)} · ${TEXT.qualityScore} ${escapeHtml(review.score ?? item.qualityScore ?? 0)}</span>
      </div>
      ${reasons.length ? `<ul class="quality-reasons">${reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>` : ""}
      ${penalties.length ? `<p class="quality-penalties">${TEXT.qualityPenalty}: ${escapeHtml(penalties.join(" / "))}</p>` : ""}
    </section>
  `;
}

function renderTopStories(stories) {
  if (!topStoriesEl) return;
  const top = (stories || []).slice(0, 10);
  if (!top.length) {
    topStoriesEl.innerHTML = `<article class="top-card empty">${TEXT.countPrefix} 0 ${TEXT.countSuffix}</article>`;
    return;
  }
  topStoriesEl.innerHTML = top.map((item, index) => {
    const brief = item.intelligenceBrief || {};
    const safeUrl = String(item.sourceUrl || "#");
    return `
      <a class="top-card" href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer noopener" data-top-link="true">
        <span class="rank">#${escapeHtml(item.topRank || index + 1)}</span>
        <div>
          <h3>${escapeHtml(item.titleZh || item.title)}</h3>
          <p>${escapeHtml(brief.recommendationReason || item.summaryZh || item.summary)}</p>
          <small>${escapeHtml(item.sourceName)} · ${escapeHtml(item.date)} · ${escapeHtml(item.qualityLabelZh || "")}</small>
        </div>
          <span class="top-card-cta">查看原文</span>
      </a>
    `;
  }).join("");
}

function renderSourceHealth(health) {
  if (!sourceHealthEl || !health) return;
  sourceHealthEl.textContent = `来源健康：${health.ok || 0}/${health.total || 0} 正常，${health.empty || 0} 暂无高价值内容，${health.curated || 0} 精选兜底，${health.failed || 0} 失败`;
}

function renderSourceHealthDetails(details) {
  if (!sourceHealthPanel) return;
  const rows = (details || []).slice().sort((a, b) => String(a.statusLabelZh).localeCompare(String(b.statusLabelZh)) || String(a.name).localeCompare(String(b.name)));
  sourceHealthPanel.innerHTML = `
    <div class="source-health-grid">
      ${rows.map((row) => `
        <article class="source-health-row status-${escapeHtml(row.statusLabelZh || "")}">
          <strong>${escapeHtml(row.name)}</strong>
          <span>${escapeHtml(row.category || "扩展查询")}</span>
          <em>${escapeHtml(row.statusLabelZh || row.status)}</em>
          <small>RSS ${escapeHtml(row.rssItems || 0)} / News ${escapeHtml(row.googleItems || 0)} / 精选 ${escapeHtml(row.curatedItems || 0)}</small>
        </article>
      `).join("")}
    </div>
  `;
}

function renderIntelligenceBrief(brief) {
  if (!brief) return "";
  const rows = [
    ["发生了什么", brief.whatHappened],
    ["为什么重要", brief.whyItMatters],
    ["启发", brief.takeaway],
    ["适合谁看", brief.audience]
  ].filter(([, value]) => value);
  if (!rows.length) return "";
  return `<dl class="brief-grid">${rows.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>`;
}

function renderRelatedSources(item) {
  const related = Array.isArray(item.relatedSources) ? item.relatedSources : [];
  if (!item.aggregatedEvent || related.length <= 1) return "";
  const shown = related.slice(0, 4).map((source) => escapeHtml(source.sourceName || source.publisher || "source")).join(" / ");
  return `<p class="related-sources">已合并 ${related.length} 个相关来源：${shown}</p>`;
}

function renderVisual(item) {
  if (item.imageUrl) {
    return `<a class="visual" href="${escapeHtml(item.sourceUrl)}" target="_blank" rel="noreferrer noopener"><img src="${escapeHtml(item.imageUrl)}" alt=""></a>`;
  }
  const initials = String(item.sourceName || "AI").slice(0, 2).toUpperCase();
  return `<a class="visual visual-fallback" href="${escapeHtml(item.sourceUrl || "#")}" target="_blank" rel="noreferrer noopener">${escapeHtml(initials)}</a>`;
}

function renderKeyPoints(points) {
  if (!Array.isArray(points) || !points.length) return "";
  return `<ul class="key-points">${points.slice(0, 3).map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>`;
}

function inSelectedTimeRange(dateValue, filters) {
  const date = String(dateValue || "").slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  if (filters.startDate && date < filters.startDate) return false;
  if (filters.endDate && date > filters.endDate) return false;
  return true;
}

function getQualityScopedItems(defaultItems, filters) {
  const pool = allNewsItems.length ? allNewsItems : defaultItems;
  if (filters.quality === "all") return pool;
  if (filters.quality === "archive") {
    return pool.filter((item) => !item.qualityReview?.isDefaultVisible);
  }
  if (filters.quality === "top") {
    return pool.filter((item) => item.qualityReview?.isTopEligible || item.qualityScore >= 80);
  }
  return defaultItems;
}

function getFilteredNews(newsItems) {
  const filters = appliedFilters || readFilterControls();
  const scopedItems = getQualityScopedItems(newsItems, filters);

  const filtered = scopedItems.filter((item) => {
    const categoryMatch = filters.category === "all" || item.category === filters.category;
    const gradeMatch = filters.grade === "all" || item.sourceGrade === filters.grade;
    const sourceMatch = filters.source === "all" || item.sourceName === filters.source;
    const state = getItemState(item);
    const readingMatch =
      filters.reading === "all"
      || (filters.reading === "unread" && !state.read)
      || (filters.reading === "read" && state.read)
      || (filters.reading === "favorite" && state.favorite)
      || (filters.reading === "later" && state.later);
    const timeMatch = inSelectedTimeRange(item.date, filters);
    const tags = Array.isArray(item.tags) ? item.tags.join(" ") : "";
    const keyPointsZh = Array.isArray(item.keyPointsZh) ? item.keyPointsZh.join(" ") : "";
    const brief = item.intelligenceBrief || {};
    const briefText = [brief.whatHappened, brief.whyItMatters, brief.takeaway, brief.audience, brief.recommendationReason].filter(Boolean).join(" ");
    const related = Array.isArray(item.relatedSources) ? item.relatedSources.map((source) => `${source.sourceName || ""} ${source.publisher || ""}`).join(" ") : "";
    const textBlob = `${item.title} ${item.titleZh || ""} ${item.summaryZh || ""} ${item.sourceName} ${tags} ${keyPointsZh} ${briefText} ${related}`.toLowerCase();
    const searchMatch = !filters.search || textBlob.includes(filters.search);
    return categoryMatch && gradeMatch && sourceMatch && readingMatch && timeMatch && searchMatch;
  });

  if (filters.sort === "importance") {
    filtered.sort((a, b) => (b.importance || 0) - (a.importance || 0));
  } else {
    filtered.sort((a, b) => String(b.date).localeCompare(String(a.date)));
  }
  return filtered;
}

function updateKpis(newsItems) {
  const total = newsItems.length;
  const enterprise = newsItems.filter((i) => (i.tags || []).some((t) => String(t).toLowerCase().includes("enterprise"))).length;
  const aGrade = newsItems.filter((i) => i.sourceGrade === "A").length;
  const practice = newsItems.filter((i) => i.category === TEXT.practice).length;

  document.getElementById("kpiTotal").textContent = String(total);
  document.getElementById("kpiEnterprise").textContent = String(enterprise);
  document.getElementById("kpiAGrade").textContent = total ? `${Math.round((aGrade / total) * 100)}%` : "0%";
  document.getElementById("kpiPractice").textContent = String(practice);
}

function bindEvents(newsItems) {
  const markManualDate = () => setActivePreset("");
  [startDateFilter, endDateFilter].forEach((el) => el.addEventListener("input", () => {
    markManualDate();
  }));
  presetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      initDateRange(newsItems, button.dataset.days);
    });
  });
  document.querySelectorAll(".date-picker-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.target);
      if (input && typeof input.showPicker === "function") {
        input.showPicker();
      } else if (input) {
        input.focus();
      }
    });
  });
  applyBtn.addEventListener("click", () => applyCurrentFilters(newsItems));
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") applyCurrentFilters(newsItems);
  });
  resetBtn.addEventListener("click", () => {
    categoryFilter.value = "all";
    gradeFilter.value = "all";
    sourceFilter.value = "all";
    readingFilter.value = "all";
    if (qualityFilter) qualityFilter.value = "default";
    initDateRange(newsItems, "year");
    sortFilter.value = "latest";
    searchInput.value = "";
    applyCurrentFilters(newsItems);
  });
  newsList.addEventListener("click", (event) => {
    const button = event.target.closest(".state-btn");
    if (!button) return;
    const item = activeNewsItems.find((candidate) => itemKey(candidate) === button.dataset.key);
    if (!item) return;
    toggleItemState(item, button.dataset.state);
    renderNews(getFilteredNews(newsItems));
  });
  copyBriefBtn?.addEventListener("click", () => copyText(digestCache.brief, "今日简报"));
  copyMarkdownBtn?.addEventListener("click", () => copyText(digestCache.markdown, "Markdown"));
  copyWechatBtn?.addEventListener("click", () => copyText(digestCache.wechat, "微信/飞书版日报"));
  downloadDigestBtn?.addEventListener("click", () => downloadText(digestCache.markdown, digestCache.filename));
}

async function renderSourcePools() {
  try {
    const response = await fetch(SOURCES_ENDPOINT, { cache: "no-store" });
    const sourceData = await response.json();
    const fill = (id, list) => {
      const ul = document.getElementById(id);
      ul.innerHTML = "";
      (list || []).forEach((name) => {
        const li = document.createElement("li");
        li.textContent = name;
        ul.appendChild(li);
      });
    };
    fill("companySources", sourceData.companies);
    fill("creatorSources", sourceData.creators);
    fill("soloSources", sourceData.soloBuilders);
  } catch (_) {
    // Source lists are helpful context, but the news feed remains usable without them.
  }
}

async function loadNewsData() {
  try {
    const response = await fetch(DATA_ENDPOINT, { cache: "no-store" });
    if (!response.ok) throw new Error("load news failed");
    const data = await response.json();
    return {
      items: Array.isArray(data.items) && data.items.length ? data.items : fallbackNews,
      archiveItems: Array.isArray(data.archiveItems) ? data.archiveItems : [],
      allItemsCount: data.allItemsCount || data.items?.length || 0,
      qualityPolicy: data.qualityPolicy || null,
      topStories: Array.isArray(data.topStories) ? data.topStories : [],
      sourceHealth: data.sourceHealth || null,
      sourceHealthDetails: Array.isArray(data.sourceHealthDetails) ? data.sourceHealthDetails : [],
      trends: data.trends || null,
      digestArchive: data.digestArchive || null,
      updatedAt: data.updatedAt || ""
    };
  } catch (_) {
    return { items: fallbackNews, archiveItems: [], allItemsCount: fallbackNews.length, qualityPolicy: null, topStories: fallbackNews, sourceHealth: null, sourceHealthDetails: [], trends: null, digestArchive: null, updatedAt: "" };
  }
}

async function init() {
  const payload = await loadNewsData();
  const newsItems = payload.items;
  allNewsItems = [...newsItems, ...(payload.archiveItems || [])];
  initCategoryOptions();
  initSourceOptions(allNewsItems);
  initDateRange(allNewsItems, "year");
  updateKpis(newsItems);
  bindEvents(newsItems);
  appliedFilters = readFilterControls();
  renderTopStories(payload.topStories.length ? payload.topStories : newsItems.slice(0, 10));
  renderSourceHealth(payload.sourceHealth);
  renderSourceHealthDetails(payload.sourceHealthDetails);
  renderTrends(payload.trends);
  renderDigestExport(payload, newsItems);
  renderNews(getFilteredNews(newsItems));
  sourceHealthToggle?.addEventListener("click", () => {
    const isHidden = sourceHealthPanel.hasAttribute("hidden");
    sourceHealthPanel.toggleAttribute("hidden", !isHidden);
    sourceHealthToggle.textContent = isHidden ? "收起来源详情" : "查看来源详情";
  });
  await renderSourcePools();
}

init();
