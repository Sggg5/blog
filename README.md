# FRANTA技术博客

基于 Astro 和 Cloudflare Pages 的技术博客，支持 Markdown 文章、分类、标签，以及 Pages Functions 读取 R2 Markdown 内容。

## 技术栈

- Astro 6
- Cloudflare Pages
- Pages Functions
- R2 bucket: 通过 `BLOG_BUCKET` 绑定到你的 R2 bucket

## 本地开发

```bash
npm install
npm run dev
```

开发服务默认运行在 `http://localhost:4321`。

## 新建文章

在 `src/content/blog` 下创建 Markdown 文件，例如：

```md
---
title: 文章标题
description: 文章摘要
pubDate: 2026-05-30
category: 工艺研发
tags:
  - 不锈钢管道
  - 质量管理
---

正文内容。
```

首页、分类页和标签页会根据 Markdown frontmatter 自动生成。

## R2 文章读取

仓库包含 Pages Function：

```text
functions/posts/[slug].js
```

访问：

```text
/posts/为什么沟槽接头会漏水
```

会读取 R2 对象：

```text
posts/为什么沟槽接头会漏水.md
```

Cloudflare Pages 后台绑定：

```text
Settings -> Bindings -> R2 bucket bindings
Variable name: BLOG_BUCKET
Bucket: 选择你的 R2 bucket
```

## GitHub 自动同步到 R2

仓库包含 GitHub Actions workflow：

```text
.github/workflows/sync-r2.yml
```

每次 `main` 分支里的 `src/content/blog/**/*.md` 更新后，会上传到：

```text
R2 bucket: 使用 GitHub Variables 中的 R2_BUCKET_NAME
R2 prefix: posts/
```

需要在 GitHub 仓库 Secrets 中配置：

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
```

需要在 GitHub 仓库 Variables 中配置：

```text
R2_BUCKET_NAME
```

API Token 需要有 R2 对象写入权限。

## 文章后台

访问 `/admin/` 可以新建、编辑和删除 Markdown 文章。后台通过 Pages Function 调用 GitHub API，把文章提交到 `src/content/blog`，随后 Cloudflare Pages 会自动重新部署。

需要在 Cloudflare Pages 环境变量中配置：

```text
ADMIN_PASSWORD=后台登录密码
GITHUB_TOKEN=GitHub fine-grained token，需要 Contents: Read and write
GITHUB_REPO=Sggg5/blog
GITHUB_BRANCH=main
```

`GITHUB_REPO` 和 `GITHUB_BRANCH` 可省略，默认分别为 `Sggg5/blog` 和 `main`。

## Cloudflare Pages 部署

在 Cloudflare Pages 中连接 GitHub 仓库后，使用以下配置：

```text
Framework preset: Astro
Build command: npm run build
Build output directory: dist
Root directory: /
Node.js version: 20 或更高
```

如果需要显式指定 Node 版本，可在 Cloudflare Pages 的环境变量中添加：

```text
NODE_VERSION=20
```

## 构建验证

```bash
npm run build
```
迁移
测试

## 每日 AI 博客

仓库的 `.github/workflows/daily-blog.yml` 会在每天北京时间／新加坡时间 08:10（UTC `10 0 * * *`）运行，也可手动触发。它会扫描 `src/content/blog` 中既有文章的文件名、标题、分类和标签，避开近 30 天的高度相似主题，再调用 OpenAI Responses API（优先启用 Web Search）生成和校验一篇文章。通过校验后才会写入 Markdown、提交并推送 `main`；Cloudflare Pages 将重新部署，现有 R2 同步工作流随后上传文章。

在 GitHub 中进入 `Sggg5/blog -> Settings -> Secrets and variables -> Actions`，添加：

- Secret：`OPENAI_API_KEY`
- Variable：`BLOG_AI_MODEL`（填写你账户可用的 OpenAI 模型名称；脚本不会猜测默认模型。）

已有的 R2 同步仍需要 `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID` 和 `R2_BUCKET_NAME`。

首次测试可进入 `Actions -> Daily AI Blog -> Run workflow`。本地也可运行：

```bash
npm run blog:generate
npm run blog:generate -- --dry-run
```

`--dry-run` 会调用 AI 并输出预览，但不会写入 `src/content/blog`。
