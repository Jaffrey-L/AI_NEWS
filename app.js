
/* ============ 数据契约 ============
   payload.json = { weeks:[{week, weekStart, weekEnd, title, subtitle, generatedAt, model,
                            news[], watch[], learn[], sections[], sources[]}],
                    catalog:{companies[], creators[], soloBuilders[], gradedSources[]},
                    builtAt }
   每个 item = { text, src:[sourceId] }；text 一律是原文摘录，不生成。
   来源状态判定：
     live  = 本页任何一期的 sources 里出现过该 sourceName
     scan  = 在 catalog 名单里、有抓取路径、但 9 期还没被引用
     plan  = 尚无可核原文时明确标出边界，不填示例内容
*/
var DATA = window.AI_NEWS_DATA;
if (!DATA || !Array.isArray(DATA.weeks) || !DATA.weeks.length) {
  document.getElementById('v-week').textContent = '周读数据暂时不可用，请稍后重试。';
  throw new Error('Weekly reader data is missing');
}
var WEEKS = DATA.weeks;
var cur = WEEKS[0];

function el(tag, cls, txt){
  var n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt != null) n.textContent = txt;
  return n;
}
function fmtDate(s){ return s ? s.replace(/-/g,'.') : ''; }
function shortRange(w){ return fmtDate(w.weekStart) + ' – ' + fmtDate(w.weekEnd).slice(5); }
function srcName(w, id){
  for (var i=0;i<w.sources.length;i++) if (w.sources[i].id === id) return w.sources[i].sourceName;
  return id;
}
function srcUrl(w, id){
  for (var i=0;i<w.sources.length;i++) if (w.sources[i].id === id) return w.sources[i].url;
  return '';
}
function updateFailure(tab){
  var status = (DATA.updateStatus || {})[tab];
  return status && status.state === 'failed' ?
    el('div','empty','本周更新失败，显示的是 ' + (status.shownWeek || '上一期')) : null;
}

/* ---------- 来源统计：只按已发布内容算 ---------- */
var LIVE = {};      // sourceName -> {weeks:Set, count:number}
WEEKS.forEach(function(w){
  w.sources.forEach(function(s){
    var k = s.sourceName;
    if (!LIVE[k]) LIVE[k] = { weeks:[], count:0 };
    if (LIVE[k].weeks.indexOf(w.week) < 0) LIVE[k].weeks.push(w.week);
    LIVE[k].count++;
  });
});
var LIVE_NAMES = Object.keys(LIVE);

/* 实际在抓、但 9 期里没被引用的（来自 gradedSources 里 A/B 也可核，这里只列 catalog 里的公司/作者） */
var SCANNING = [
  { name:'Anthropic', via:'official-domain query' },
  { name:'Google DeepMind', via:'official-domain query' },
  { name:'Meta AI', via:'official-domain query' },
  { name:'NVIDIA', via:'A 级 RSS + 官网' },
  { name:'Microsoft AI', via:'RSS' },
  { name:'xAI', via:'official-domain query' },
  { name:'The Batch', via:'RSS' },
  { name:'Andrej Karpathy', via:'个人博客 / 订阅' },
  { name:'swyx', via:'个人博客 / 订阅' },
  { name:'Ethan Mollick', via:'个人博客 / 订阅' },
  { name:'Sebastian Raschka', via:'个人博客 / 订阅' },
  { name:'Simon Willison', via:'个人博客 / 订阅' }
].filter(function(x){ return LIVE_NAMES.indexOf(x.name) < 0; });

/* ---------- 周解读视图 ---------- */
function answerCard(kind, label, num, question, items, w){
  var box = el('div','ans '+kind);
  var h = el('h2'); h.appendChild(document.createTextNode(label)); h.appendChild(el('em',null,num));
  box.appendChild(h);
  box.appendChild(el('div','q', question));
  if (!items.length){
    box.appendChild(el('div','empty','本期原文里没有可核的条目。这里不补写内容，宁缺不造。'));
    return box;
  }
  var ol = el('ol');
  items.forEach(function(it){
    var li = el('li');
    if (it.ai) li.appendChild(el('strong','ai-label','AI 解读 · '));
    li.appendChild(document.createTextNode(it.text));
    var row = el('div','srcrow');
    it.src.forEach(function(id){
      var c = el('a','schip', id + ' ' + srcName(w, id));
      c.setAttribute('data-src', id);
      c.href = srcUrl(w, id);
      c.target = '_blank';
      c.rel = 'noopener noreferrer';
      c.title = '打开原文';
      row.appendChild(c);
    });
    li.appendChild(row);
    ol.appendChild(li);
  });
  box.appendChild(ol);
  return box;
}

function renderWeek(){
  var v = document.getElementById('v-week');
  v.innerHTML = '';
  var failed = updateFailure('weekly');
  if (failed) v.appendChild(failed);

  var hero = el('section','hero');
  var kick = el('div','kicker');
  kick.appendChild(el('i'));
  kick.appendChild(document.createTextNode('第 ' + cur.week.split('-W')[1] + ' 周 · ' + fmtDate(cur.weekStart) + ' – ' + fmtDate(cur.weekEnd)));
  hero.appendChild(kick);
  hero.appendChild(el('h1',null,cur.title));
  hero.appendChild(el('p','sub',cur.subtitle));
  var hm = el('div','herometa');
  hm.appendChild(el('span','chip','本周原文 ' + cur.sources.length + ' 篇'));
  hm.appendChild(el('span','chip','来源 ' + new Set(cur.sources.map(function(s){return s.sourceName})).size + ' 个'));
  hm.appendChild(el('span','chip','生成 ' + (cur.generatedAt||'').slice(0,10)));
  hm.appendChild(el('span','chip mono',cur.model));
  hero.appendChild(hm);
  v.appendChild(hero);

  var an = el('div','answers');
  an.appendChild(answerCard('a1','01 发生了什么大事','WHAT', '这周真正发生了什么', cur.news, cur));
  an.appendChild(answerCard('a2','02 我需要注意的','WATCH', '哪些说法还不能当真', cur.watch, cur));
  an.appendChild(answerCard('a3','03 我需要学习的','LEARN', '哪些做法可以直接用', cur.learn, cur));
  v.appendChild(an);

  var cols = el('div','cols');

  /* 正文 */
  var left = el('div');
  var sh = el('div','sec-head');
  sh.appendChild(el('h3','','本周解读全文'));
  sh.appendChild(el('span','','每一句都带原文引用，点角标看来源'));
  left.appendChild(sh);
  var art = el('article','body');
  cur.sections.forEach(function(sec, i){
    var d = el('div','sec');
    var h = el('h4');
    h.appendChild(el('span','n', String(i+1).padStart(2,'0')));
    h.appendChild(document.createTextNode(sec.heading.replace(/^[一二三四五六七八九十]+、/,'')));
    d.appendChild(h);
    sec.paragraphs.forEach(function(p){
      var para = el('p');
      para.appendChild(document.createTextNode(p.text));
      (p.citations||[]).forEach(function(c){
        var a = el('span','cite', c.sourceId);
        a.setAttribute('data-src', c.sourceId);
        a.title = c.evidence || '';
        para.appendChild(a);
      });
      d.appendChild(para);
    });
    art.appendChild(d);
  });
  left.appendChild(art);
  cols.appendChild(left);

  /* 右栏 */
  var aside = el('aside');
  var p1 = el('div','panel');
  p1.appendChild(el('h5','','本周原文 · ' + cur.sources.length + ' 篇'));
  var ul = el('ul','srclist');
  cur.sources.forEach(function(s){
    var li = el('li');
    li.setAttribute('data-src', s.id);
    li.appendChild(el('span','sid', s.id));
    li.appendChild(el('span','t', s.title));
    li.appendChild(el('span','m', s.sourceName + ' · ' + fmtDate(s.publishedAt)));
    li.addEventListener('click', function(){ window.open(s.url, '_blank', 'noopener'); });
    ul.appendChild(li);
  });
  p1.appendChild(ul);
  aside.appendChild(p1);

  var p2 = el('div','panel');
  p2.appendChild(el('h5','','往期'));
  var ar = el('div','archive');
  WEEKS.forEach(function(w){
    var b = el('button');
    if (w.week === cur.week) b.className = 'on';
    b.appendChild(el('span','wk', w.week.replace('2026-','')));
    b.appendChild(el('span', null, fmtDate(w.weekEnd).slice(5)));
    b.addEventListener('click', function(){ selectWeek(w.week); });
    ar.appendChild(b);
  });
  p2.appendChild(ar);
  aside.appendChild(p2);
  cols.appendChild(aside);

  v.appendChild(cols);
  wireSrcHover();
}

function wireSrcHover(){
  document.querySelectorAll('[data-src]').forEach(function(n){
    if (n.tagName === 'LI') return;
    n.addEventListener('mouseenter', function(){
      document.querySelectorAll('.srclist li').forEach(function(li){
        li.classList.toggle('hi', li.getAttribute('data-src') === n.getAttribute('data-src'));
      });
    });
    n.addEventListener('mouseleave', function(){
      document.querySelectorAll('.srclist li').forEach(function(li){ li.classList.remove('hi'); });
    });
    n.addEventListener('click', function(){
      if (n.tagName === 'A') return;
      var id = n.getAttribute('data-src');
      var source = cur.sources.find(function(s){ return s.id === id; });
      if (source && source.url) window.open(source.url, '_blank', 'noopener');
    });
  });
}

/* ---------- AI 承接（来源）视图 ---------- */
var ST = DATA.srcStatus;

function feedState(f){
  return f.cited > 0
    ? { cls:'dot-live', txt:'已引用 ' + f.cited + ' 篇' }
    : { cls:'dot-scan', txt:f.firstEligibleWeek && WEEKS[0].week < f.firstEligibleWeek
        ? '新接入，下期起参与' : '本期未引用' };
}

function renderSources(){
  var v = document.getElementById('v-sources');
  if (v.dataset.done) return;
  v.innerHTML = '';

  var hd = el('div','view-head');
  hd.appendChild(el('h2',null,'AI 承接：消息从哪里来'));
  hd.appendChild(el('p',null,'三层分开写，不把没接通的说成已有内容：第一层是能直接读到原文的订阅源，第二层是官网查询和新闻兜底，第三层是明确还没接的。已经出现在周解读里的，标出被引用了几篇、在哪几期。'));
  v.appendChild(hd);

  /* 一、直接订阅 */
  var b1 = el('div','card-blk');
  var h1 = el('h3'); h1.appendChild(document.createTextNode('一、直接订阅（' + ST.direct.length + ' 个 RSS / Atom）'));
  h1.appendChild(el('span','tag','原文可读'));
  b1.appendChild(h1);
  b1.appendChild(el('p','note','这些来源提供公开订阅。右边是已发布周读引用的篇数；引用为 0 不代表抓取失败。'));
  var tl = el('div','feedtable');
  ST.direct.forEach(function(f){
    var st = feedState(f);
    var r = el('div','frow');
    var l = el('div','fl');
    l.appendChild(el('span','g','A'));
    var nm = el('div');
    nm.appendChild(el('div','fnm', f.sourceName || f.feed));
    nm.appendChild(el('div','furl', f.url.replace(/^https?:\/\//,'')));
    l.appendChild(nm);
    r.appendChild(l);
    var s = el('span','fst');
    s.appendChild(el('i', st.cls));
    s.appendChild(document.createTextNode(st.txt));
    r.appendChild(s);
    tl.appendChild(r);
  });
  b1.appendChild(tl);
  v.appendChild(b1);

  /* 二、官网查询 */
  var b2 = el('div','card-blk');
  var h2 = el('h3'); h2.appendChild(document.createTextNode('二、官网查询 + 新闻兜底（' + ST.query.length + ' 个）'));
  h2.appendChild(el('span','tag','B 级'));
  b2.appendChild(h2);
  b2.appendChild(el('p','note','官方域名检索：RSS 覆盖不到的公告，用这一层补。Google DeepMind 同时有 RSS，这里保留查询作为补充。Google News 只是兜底，不单独当成一篇原文引用。'));
  var qs = el('div','pills');
  ST.query.forEach(function(q){
    var p = el('span','pill', q.feed.replace(' official-domain query','') + ' · 官方域名');
    qs.appendChild(p);
  });
  b2.appendChild(qs);
  v.appendChild(b2);

  /* 三、来源边界 */
  var b3 = el('div','card-blk');
  var h3 = el('h3'); h3.appendChild(document.createTextNode('三、来源边界'));
  h3.appendChild(el('span','tag','如实标识'));
  b3.appendChild(h3);
  b3.appendChild(el('p','note','亚马逊页已收录公开网站文章与官方订阅。网站文章不代表社交平台原帖。付费 X 接口未启用。'));
  var amazonFeeds = el('div','feedtable');
  var uniqueSites = {};
  var siteDates = {};
  (DATA.amazon.articles || []).forEach(function(article){
    try {
      var host = new URL(article.sourceUrl).hostname.replace(/^www\./, '');
      if (!siteDates[host] || siteDates[host] < article.date) siteDates[host] = article.date;
    } catch(e) {}
  });
  ST.amazonSources.forEach(function(s){
    if (!uniqueSites[s.publicUrl]) uniqueSites[s.publicUrl] = [];
    uniqueSites[s.publicUrl].push(s.name);
  });
  Object.keys(uniqueSites).forEach(function(url){
    var row = el('div','frow');
    var left = el('div','fl');
    left.appendChild(el('span','g','站'));
    var label = el('div');
    label.appendChild(el('div','fnm',uniqueSites[url].join('／')));
    label.appendChild(el('div','furl',url));
    left.appendChild(label);
    row.appendChild(left);
    var sourceHost = new URL(url).hostname.replace(/^www\./, '');
    row.appendChild(el('span','fst',siteDates[sourceHost] ? '最近 ' + fmtDate(siteDates[sourceHost]) : '暂无已核日期'));
    amazonFeeds.appendChild(row);
  });
  ST.amazonOfficialSources.forEach(function(s){
    var row = el('div','frow');
    var left = el('div','fl');
    left.appendChild(el('span','g','R'));
    var label = el('div');
    label.appendChild(el('div','fnm',s.name));
    label.appendChild(el('div','furl',s.url));
    left.appendChild(label);
    row.appendChild(left);
    var officialDates = (DATA.amazon.articles || []).filter(function(a){ return a.sourceName === s.name; }).map(function(a){ return a.date; });
    row.appendChild(el('span','fst',officialDates.length ? '最近 ' + fmtDate(officialDates.sort().pop()) : '暂无已核日期'));
    amazonFeeds.appendChild(row);
  });
  b3.appendChild(amazonFeeds);
  var sl = el('div','slot');
  ST.pending.forEach(function(s){
    var d = el('div','s');
    var hh = el('div','h');
    hh.appendChild(el('span',null,s.name));
    hh.appendChild(el('span','b',s.group === '社交平台' ? '原帖未采' : '待接入'));
    d.appendChild(hh);
    d.appendChild(el('p',null,s.what));
    var w = el('p',null,s.why);
    w.style.cssText = 'margin-top:6px;color:#9aa3b2;font-size:12.2px';
    d.appendChild(w);
    sl.appendChild(d);
  });
  b3.appendChild(sl);
  v.appendChild(b3);

  /* 完整名单 */
  var b4 = el('div','card-blk');
  var h4 = el('h3'); h4.appendChild(document.createTextNode('完整关注名单'));
  h4.appendChild(el('span','tag','名字在名单里 ≠ 已有内容'));
  b4.appendChild(h4);
  b4.appendChild(el('p','note','蓝色实心 = 已经产出过被引用的原文。其余是关注对象，不是来源。'));
  var groups = [['公司', ST.catalog.companies], ['作者 / 媒体', ST.catalog.creators], ['独立开发者', ST.catalog.soloBuilders]];
  var liveSet = {};
  ST.cited.forEach(function(c){ liveSet[c.name] = 1; });
  groups.forEach(function(g){
    var t = el('div');
    t.style.cssText = 'margin-top:14px';
    t.appendChild(el('h5','', g[0] + ' · ' + g[1].length + ' 个'));
    var row = el('div','pills');
    g[1].forEach(function(n){
      row.appendChild(el('span', 'pill' + (liveSet[n] ? ' hit' : ''), n));
    });
    t.appendChild(row);
    b4.appendChild(t);
  });
  v.appendChild(b4);

  v.dataset.done = '1';
}

/* ---------- 亚马逊公开网站文章 ---------- */
function amazonTitle(article){
  return article.title.replace(/\s*-\s*AMZ123跨境导航\s*$/i, '').trim();
}

var amazonSelectedWeek = null;
function selectAmazonWeek(week){
  amazonSelectedWeek = week;
  var view = document.getElementById('v-amazon');
  delete view.dataset.done;
  renderAmazon();
  try { history.replaceState(null,'','?amazon=' + week); } catch(e){}
}

function renderAmazon(){
  var v = document.getElementById('v-amazon');
  if (v.dataset.done) return;
  v.innerHTML = '';
  var failed = updateFailure('amazon');
  if (failed) v.appendChild(failed);
  var current = DATA.amazon.ai || {};
  var archive = DATA.amazon.weeks || [];
  var issues = [current].concat(archive);
  var issue = issues.find(function(row){ return row.week === amazonSelectedWeek; }) || current;
  var day = issue.date || (DATA.amazon.updatedAt || '').slice(0,10);
  var monday = new Date(day + 'T00:00:00Z');
  monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7));
  var weekStart = monday.toISOString().slice(0,10);
  var sunday = new Date(monday); sunday.setUTCDate(sunday.getUTCDate() + 6);
  var weekEnd = sunday.toISOString().slice(0,10);
  var article = issue.article || null;
  var sources = issue.sources || [];
  var byId = {};
  sources.forEach(function(source){ byId[source.id] = source; });
  var hero = el('section','hero amz');
  var kick = el('div','kicker'); kick.appendChild(el('i'));
  kick.appendChild(document.createTextNode('亚马逊 / 跨境 · 公开来源'));
  hero.appendChild(kick);
  hero.appendChild(el('h1',null,article ? article.title : '亚马逊周读'));
  hero.appendChild(el('p','sub',article ? article.subtitle : '本周暂无可发布的完整解读。'));
  var hm = el('div','herometa');
  hm.appendChild(el('span','chip',issue.week + ' · ' + fmtDate(weekStart).slice(5) + '–' + fmtDate(weekEnd).slice(5) +
    (issue === current ? '（截至 ' + fmtDate(day).slice(5) + '，本周进行中）' : '（已归档）')));
  hm.appendChild(el('span','chip','原文 ' + sources.length + ' 篇'));
  hm.appendChild(el('span','chip','官方订阅 ' + DATA.srcStatus.amazonOfficialSources.length + ' 个'));
  hero.appendChild(hm);
  v.appendChild(hero);

  var groups = [['a1','01 发生了什么大事','WHAT','平台和行业这周发生了什么','news'],
                ['a2','02 我需要注意的','WATCH','政策、规则、费用与物流','watch'],
                ['a3','03 我需要学习的','LEARN','哪些卖家实践值得研究','learn']];
  var grid = el('div','answers');
  groups.forEach(function(group){
    var box = el('div','ans ' + group[0]);
    var h = el('h2'); h.appendChild(document.createTextNode(group[1])); h.appendChild(el('em',null,group[2]));
    box.appendChild(h); box.appendChild(el('div','q',group[3]));
    var rows = ((issue.cards || {})[group[4]] || []).slice(0,3);
    if (!rows.length) box.appendChild(el('div','empty',group[4] === 'learn'
      ? '本周暂无合适的实操案例' : '本周没有可核的对应原文。'));
    var ol = el('ol');
    rows.forEach(function(row){
      var original = byId[(row.src || [])[0]];
      if (!original || !original.url) return;
      var li = el('li');
      li.appendChild(el('strong','ai-label','AI 解读 · '));
      li.appendChild(document.createTextNode(row.text));
      var link = el('a','ai-original','原文：' + amazonTitle(original));
      link.href = original.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      li.appendChild(link);
      li.appendChild(el('div','srcrow',original.sourceName + ' · ' + fmtDate(original.publishedAt)));
      ol.appendChild(li);
    });
    box.appendChild(ol); grid.appendChild(box);
  });
  v.appendChild(grid);

  if (article && article.sections && article.sections.length) {
    var cols = el('div','cols');
    var left = el('div');
    var sh = el('div','sec-head');
    sh.appendChild(el('h3',null,'本周解读全文'));
    sh.appendChild(el('span',null,'AI 解读 · 每段可打开原文'));
    left.appendChild(sh);
    var body = el('article','body');
    article.sections.forEach(function(section, index){
      var sec = el('div','sec');
      var heading = el('h4'); heading.appendChild(el('span','n',String(index+1).padStart(2,'0')));
      heading.appendChild(document.createTextNode(section.heading)); sec.appendChild(heading);
      section.paragraphs.forEach(function(paragraph){
        var p = el('p'); p.appendChild(document.createTextNode(paragraph.text));
        var citedHere = new Set();
        paragraph.citations.forEach(function(citation){
          if (citedHere.has(citation.sourceId)) return;
          var original = byId[citation.sourceId];
          if (!original) return;
          citedHere.add(citation.sourceId);
          var link = el('a','cite',citation.sourceId);
          link.href = original.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
          link.title = '打开原文：' + original.title;
          p.appendChild(link);
        });
        sec.appendChild(p);
      });
      body.appendChild(sec);
    });
    left.appendChild(body); cols.appendChild(left);
    var aside = el('aside');
    var panel = el('div','panel');
    panel.appendChild(el('h5',null,'本周原文 · ' + sources.length + ' 篇'));
    var list = el('ul','srclist');
    sources.forEach(function(source){
      var li = el('li'); li.appendChild(el('span','sid',source.id));
      li.appendChild(el('span','t',amazonTitle(source)));
      li.appendChild(el('span','m',source.sourceName + ' · ' + fmtDate(source.publishedAt)));
      li.addEventListener('click',function(){ window.open(source.url,'_blank','noopener'); });
      list.appendChild(li);
    });
    panel.appendChild(list); aside.appendChild(panel);
    var past = el('div','panel'); past.appendChild(el('h5',null,'往期'));
    var buttons = el('div','archive');
    issues.forEach(function(row){
      if (row === current || !row.week || !row.article) return;
      var button = el('button',row.week === issue.week ? 'on' : null,row.week);
      button.addEventListener('click',function(){ selectAmazonWeek(row.week); });
      buttons.appendChild(button);
    });
    past.appendChild(buttons);
    if (!buttons.children.length) past.appendChild(el('p','empty','首期收尾后出现'));
    aside.appendChild(past);
    cols.appendChild(aside); v.appendChild(cols);
  } else {
    v.appendChild(el('p','empty','本周解读尚未生成；已发布的上一期会保留。'));
    if (archive.length) {
      var pastIssues = el('div','panel'); pastIssues.appendChild(el('h5',null,'往期'));
      var archivedButtons = el('div','archive');
      archive.forEach(function(row){
        if (!row.week || !row.article) return;
        var button = el('button',null,row.week);
        button.addEventListener('click',function(){ selectAmazonWeek(row.week); });
        archivedButtons.appendChild(button);
      });
      pastIssues.appendChild(archivedButtons); v.appendChild(pastIssues);
    }
  }
  v.dataset.done = '1';
}

/* ---------- 读者旅途 ---------- */
function renderJourney(){
  var v = document.getElementById('v-journey');
  if (v.dataset.done) return;
  var hd = el('div','view-head');
  hd.appendChild(el('h2',null,'读者旅途：一次周读应该怎么走'));
  hd.appendChild(el('p',null,'从「周一一早打开」到「这周做一个决定」，页面要在这五步里各给一句能用的东西。三步回答（大事 / 注意 / 学习）就是第 3、4 步的产出。'));
  v.appendChild(hd);

  var steps = [
    ['STEP 1','打开，30 秒知道这周值不值得读','看标题、副标题、本周原文篇数和来源数；换周不刷新页面。','如果没有值得读的，页面上要能看出来，而不是靠文字硬撑。'],
    ['STEP 2','扫三条大事，判断跟自己有没有关系','每期最多 3 条，全部是原文摘录，带来源角标。','多了就不叫「大事」。宁可 2 条，不凑第 3 条。'],
    ['STEP 3','看「我需要注意的」，知道哪些说法不能当真','限定语原句：需说明、不宜据此、资料未给出、事实与推断之分。','这条是本周的质量底线：抽不出来就写「本期没有可核的注意项」。'],
    ['STEP 4','看「我需要学习的」，拿到能直接用的动作','带行动语气的原句：评估时优先问什么、选型时看哪几项。','不写泛泛的「多学习」，只摘原文里具体的动作。'],
    ['STEP 5','要细节再往下读全文，或点开原文','正文每一句都有引用角标；右栏是本周原文清单，可点开。','已经是读者的最后一步，不在这里再做新功能。']
  ];
  var jr = el('div','jr');
  steps.forEach(function(s){
    var d = el('div','step');
    d.appendChild(el('div','k', s[0]));
    d.appendChild(el('div','t', s[1]));
    d.appendChild(el('div','w', s[2]));
    var g = el('div','g');
    g.appendChild(el('b',null,'设计约束：'));
    g.appendChild(document.createTextNode(s[3]));
    d.appendChild(g);
    jr.appendChild(d);
  });
  v.appendChild(jr);

  var b = el('div','card-blk'); b.style.marginTop = '18px';
  b.appendChild(el('h3',null,'这一版没做的'));
  var ul = el('ul'); ul.style.cssText='list-style:none;display:flex;flex-direction:column;gap:8px;font-size:13.6px;color:var(--ink2);line-height:1.7;margin-top:8px';
  ['不做站内搜索和标签筛选：9 期原文体量还不需要，加了反而是负债。',
   '不做「猜你喜欢」之类推荐：没有用户行为数据，做了也是编的。',
   '不做登录和个人收藏：先确认大家是不是真的每周回来看。',
   '不接付费接口：X 用免费方案，接不上就明确写待接入。'].forEach(function(t){
    var li = el('li', null, '· ' + t); ul.appendChild(li);
  });
  b.appendChild(ul);
  v.appendChild(b);

  v.dataset.done = '1';
}

/* ---------- 交互 ---------- */
function selectWeek(wk){
  var w = null;
  WEEKS.forEach(function(x){ if (x.week === wk) w = x; });
  if (!w) return;
  cur = w;
  document.getElementById('wkpick').value = wk;
  renderWeek();
  try { history.replaceState(null,'','?week=' + wk); } catch(e){}
}

document.getElementById('tabs').addEventListener('click', function(e){
  var b = e.target.closest('.tab'); if (!b) return;
  document.querySelectorAll('.tab').forEach(function(t){ t.classList.toggle('on', t === b); });
  var v = b.dataset.v;
  document.getElementById('v-week').classList.toggle('hide', v !== 'week');
  document.getElementById('v-sources').classList.toggle('hide', v !== 'sources');
  document.getElementById('v-amazon').classList.toggle('hide', v !== 'amazon');
  document.getElementById('v-journey').classList.toggle('hide', v !== 'journey');
  document.getElementById('wkpick').classList.toggle('hide', v !== 'week');
  if (v === 'sources') renderSources();
  if (v === 'amazon') renderAmazon();
  if (v === 'journey') renderJourney();
  window.scrollTo({top:0, behavior:'smooth'});
});

var sel = document.getElementById('wkpick');
WEEKS.forEach(function(w){
  var o = document.createElement('option');
  o.value = w.week; o.textContent = w.week.replace('2026-','') + ' · ' + fmtDate(w.weekEnd).slice(5);
  sel.appendChild(o);
});
sel.addEventListener('change', function(){ selectWeek(sel.value); });

document.getElementById('updated').textContent = '更新于 ' + (DATA.builtAt||'').slice(0,10);

var m = location.search.match(/week=(2026-W\d+)/);
var start = m ? m[1] : WEEKS[0].week;
selectWeek(start);
