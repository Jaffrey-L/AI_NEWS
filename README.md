# AI 周读

静态站点：<https://jaffrey-l.github.io/AI_NEWS/>。周读整理已结束的一周；亚马逊页每天补充正在进行的一周。每条 AI 解读都与原站标题、摘要分开显示，并链接到原文。

## 自动更新

`.github/workflows/refresh-editions.yml` 在北京时间每天 07:30 刷新亚马逊页，每周一 08:30 刷新上一完整周的 AI 周读。GitHub Actions 的定时任务可能延迟；公开仓库长期无活动时可能被自动停用，需要检查 Actions 状态。

工作流使用仓库 Secret `DEEPSEEK_API_KEY`，模型为 `deepseek-flash`。密钥只传给生成脚本，不进入页面或版本库。采集使用公开网页和 RSS，不调用付费 X 接口。

每块最多三条。生成内容必须引用本次输入的 HTTPS 原文，且引用摘录必须逐字出现在输入中。未达到条件的条目不发布。来源没有当周新文章是正常的空结果。若采集、生成或引用校验失败，保留上一期内容，页面显示失败和保留的周次；工作流标红供维护人处理。

本地复现：

```bash
AI_NEWS_PROVIDER=deepseek AI_NEWS_MODEL=deepseek-flash DEEPSEEK_API_KEY=... python3 scripts/run_auto_update.py --mode amazon
AI_NEWS_PROVIDER=deepseek AI_NEWS_MODEL=deepseek-flash DEEPSEEK_API_KEY=... python3 scripts/run_auto_update.py --mode weekly
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m http.server 8000
```

失败命令返回非零，同时写入 `data/update-status.json` 并重建 `data/site-payload.js`。提交并发布这两个文件后读者才会看到故障提示。旧的手工周读和文章归档仍在 `data/weekly/`；自动任务只处理目标周次，不重写已发布周读。

## 费用估算

按每月 4 次周读文章、约 34 次三块摘要请求估算，假设总输入 20 万 tokens、输出 10 万 tokens，并在非高峰时运行，[DeepSeek Flash 当前价格](https://api-docs.deepseek.com/quick_start/pricing/)折合约 **$0.09/月**。留出采集波动和重复失败重试，预计 **$0.10–$0.30/月**；实际费用以服务商用量记录为准。

## 页面验证

```bash
npm ci
npx playwright install chromium
npm run validate:frontend
```

部署和失败处置见 [docs/deploy/linux-deploy.md](docs/deploy/linux-deploy.md)。
