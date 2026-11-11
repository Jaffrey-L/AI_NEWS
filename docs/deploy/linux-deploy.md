# 静态站点与自动更新

GitHub Pages 由 Actions 从 `main` 生成静态包并发布：<https://jaffrey-l.github.io/AI_NEWS/>。Pages 的构建来源须设为 **GitHub Actions**；工作流用 `GITHUB_TOKEN` 提交数据时不会触发旧的分支发布。页面只读取静态数据；服务器无需数据库、运行中的 Python 服务或模型密钥。

仓库 Actions 工作流每天 07:30 北京时间更新亚马逊期、每周一 08:30 更新上一个完整周读。它先采集、生成并验证，再提交 `data/`。失败时保留旧内容，提交失败状态并让工作流变红。维护人检查 Actions 失败日志和页面提示；修复来源或模型问题后，使用 `workflow_dispatch` 选择 `amazon` 或 `weekly` 重跑。不能把没有新文章当成采集失败。

需要在仓库 Actions secrets 中配置 `DEEPSEEK_API_KEY`。不要把值写进代码、日志或页面。GitHub Actions 的 `GITHUB_TOKEN` 需有 `contents: write` 权限；工作流已声明此权限。若分支规则阻止工作流推送，要按仓库现有审核规则调整发布路径。

发布后检查 Actions、Pages 构建、首页、两个页签的原文链接和更新提示。成功提交不等于 Pages 已完成部署。Linux 镜像站若有需要，可直接把含 `index.html`、`workspace.css`、`app.js` 和 `data/site-payload.js` 的目录作为静态根目录。
