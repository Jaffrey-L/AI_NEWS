const OPINION_ENDPOINT = "./data/opinion/latest.json";
const OPINION_STATUS_ENDPOINT = "./data/opinion/status.json";
const WEEKLY_INDEX_ENDPOINT = "./data/weekly/index.json";

const opinionMeta = document.getElementById("opinionMeta");
const opinionArticle = document.getElementById("opinionArticle");
const weekSelect = document.getElementById("weekSelect");
const weekArchive = document.getElementById("weekArchive");
function sourceLink(source, label) {
  const link = document.createElement("a");
  const url = new URL(source.url);
  if (!/^https?:$/.test(url.protocol)) throw new Error("invalid source URL");
  link.href = url.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = label;
  return link;
}

function renderOpinionArticle(article, status) {
  if (!article || !Array.isArray(article.sections) || !Array.isArray(article.sources)) {
    throw new Error("invalid opinion article");
  }
  const sourceMap = new Map(article.sources.map((source) => [source.id, source]));
  const content = document.createDocumentFragment();
  const title = document.createElement("h3");
  title.textContent = article.title;
  content.appendChild(title);
  const subtitle = document.createElement("p");
  subtitle.className = "opinion-subtitle";
  subtitle.textContent = article.subtitle;
  content.appendChild(subtitle);

  article.sections.forEach((section) => {
    const block = document.createElement("section");
    block.className = "opinion-section";
    const heading = document.createElement("h4");
    heading.textContent = section.heading;
    block.appendChild(heading);
    (section.paragraphs || []).forEach((paragraph) => {
      const body = document.createElement("p");
      body.textContent = paragraph.text;
      block.appendChild(body);
      const citations = document.createElement("div");
      citations.className = "opinion-citations";
      (paragraph.citations || []).forEach((citation) => {
        const source = sourceMap.get(citation.sourceId);
        if (!source) throw new Error("missing opinion source");
        const detail = document.createElement("details");
        const summary = document.createElement("summary");
        summary.appendChild(sourceLink(source, `${source.sourceName} · ${source.publishedAt} · 原文 ↗`));
        detail.appendChild(summary);
        if (citation.evidence) {
          const quote = document.createElement("blockquote");
          quote.textContent = citation.evidence;
          detail.appendChild(quote);
        }
        citations.appendChild(detail);
      });
      block.appendChild(citations);
    });
    content.appendChild(block);
  });
  const sources = document.createElement("section");
  sources.className = "opinion-sources";
  const sourcesTitle = document.createElement("h4");
  sourcesTitle.textContent = "本周原文";
  sources.appendChild(sourcesTitle);
  const sourceList = document.createElement("ol");
  article.sources.forEach((source) => {
    const item = document.createElement("li");
    item.appendChild(sourceLink(source, `${source.sourceName} · ${source.title}`));
    const published = document.createElement("time");
    published.textContent = source.publishedAt;
    item.appendChild(published);
    sourceList.appendChild(item);
  });
  sources.appendChild(sourceList);
  content.appendChild(sources);
  opinionArticle.replaceChildren(content);
  const stale = status?.state === "failed";
  const authorLabel = article.model === "assistant-seed" ? " · AI 示例首刊" : " · AI 自动撰写";
  const generated = Date.parse(article.generatedAt);
  const generatedLabel = Number.isNaN(generated)
    ? article.editionDate
    : new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(generated);
  const coverage = article.weekStart && article.weekEnd
    ? `${article.weekStart} 至 ${article.weekEnd}`
    : `资料窗口 ${article.windowDays} 天`;
  opinionMeta.textContent = `${coverage} · 发布 ${generatedLabel} · ${article.sources.length} 条原文${stale ? " · 本轮更新失败，显示上期文章" : authorLabel}`;
}

async function loadLegacyOpinion() {
  try {
    const [articleResponse, statusResponse] = await Promise.all([
      fetch(OPINION_ENDPOINT, { cache: "no-store" }),
      fetch(OPINION_STATUS_ENDPOINT, { cache: "no-store" })
    ]);
    if (!articleResponse.ok) throw new Error("no opinion article");
    const article = await articleResponse.json();
    const status = statusResponse.ok ? await statusResponse.json() : null;
    renderOpinionArticle(article, status);
  } catch (_) {
    opinionMeta.textContent = "本轮解读尚未生成，请稍后再试。";
    opinionArticle.textContent = "暂无可核引文的 AI 观点文章。";
  }
}

async function loadOpinionArticle() {
  let editions;
  try {
    const response = await fetch(WEEKLY_INDEX_ENDPOINT, { cache: "no-store" });
    if (!response.ok) throw new Error("no weekly index");
    const index = await response.json();
    editions = Array.isArray(index.weeks) ? index.weeks.filter((entry) =>
      /^\d{4}-W\d{2}$/.test(entry.week) &&
      entry.path === `./data/weekly/${entry.week}.json`
    ) : [];
  } catch (_) {
    editions = [];
  }
  if (!editions.length) {
    weekSelect.hidden = true;
    weekArchive.textContent = "历史周刊正在整理。";
    await loadLegacyOpinion();
    return;
  }

  const selected = new URLSearchParams(window.location.search).get("week");
  const initial = editions.find((entry) => entry.week === selected) || editions[0];
  weekSelect.replaceChildren(...editions.map((entry) => {
    const option = document.createElement("option");
    option.value = entry.week;
    option.textContent = `${entry.weekStart}—${entry.weekEnd} · ${entry.title}`;
    return option;
  }));
  weekSelect.value = initial.week;

  async function showWeek(entry) {
    const response = await fetch(entry.path, { cache: "no-store" });
    if (!response.ok) throw new Error("weekly article unavailable");
    const article = await response.json();
    if (article.week !== entry.week) throw new Error("weekly article mismatch");
    renderOpinionArticle(article, null);
    weekSelect.value = entry.week;
    weekArchive.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("active", button.dataset.week === entry.week);
      button.setAttribute("aria-current", button.dataset.week === entry.week ? "page" : "false");
    });
    const url = new URL(window.location.href);
    url.searchParams.set("week", entry.week);
    window.history.replaceState(null, "", url);
  }

  weekArchive.replaceChildren(...editions.map((entry) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "week-archive-btn";
    button.dataset.week = entry.week;
    button.textContent = `${entry.weekStart} · ${entry.title}`;
    button.addEventListener("click", () => {
      void showWeek(entry).catch(() => { opinionMeta.textContent = "这期解读暂时无法读取，请稍后重试。"; });
    });
    return button;
  }));
  weekSelect.addEventListener("change", () => {
    const entry = editions.find((item) => item.week === weekSelect.value);
    if (entry) void showWeek(entry).catch(() => { opinionMeta.textContent = "这期解读暂时无法读取，请稍后重试。"; });
  });
  try {
    await showWeek(initial);
  } catch (_) {
    opinionMeta.textContent = "本周解读暂时无法读取，请选择其他周次或稍后重试。";
    opinionArticle.textContent = "请选择其他周次，或稍后重试。";
  }
}

void loadOpinionArticle();
