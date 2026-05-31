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
