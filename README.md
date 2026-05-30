# FRANTA技术博客

基于 Astro 的静态技术博客，支持 Markdown 文章、文章详情页、分类、标签，并保持 Cloudflare Pages 静态部署兼容。

## 技术栈

- Astro 6
- Markdown 内容集合：`src/content/blog`
- 静态输出目录：`dist`

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

首页会自动显示文章列表；分类页和标签页会根据 frontmatter 自动生成。

## 项目结构

```text
src/
  content/
    blog/
      为什么沟槽接头会漏水.md
  layouts/
    BaseLayout.astro
  lib/
    blog.ts
  pages/
    index.astro
    blog/[slug].astro
    categories/index.astro
    categories/[category].astro
    tags/index.astro
    tags/[tag].astro
  styles/
    global.css
```

## Cloudflare Pages 部署

在 Cloudflare Pages 中连接 GitHub 仓库后，使用以下配置：

- Framework preset: `Astro`
- Build command: `npm run build`
- Build output directory: `dist`
- Root directory: `/`
- Node.js version: `20` 或更高

仓库也包含 `wrangler.toml`，其中声明了 Pages 输出目录：

```toml
pages_build_output_dir = "./dist"
```

如果线上仍显示旧页面，请在 Cloudflare Pages 项目中确认没有使用“直接上传/根目录发布”，并重新部署最新提交。

如果需要显式指定 Node 版本，可在 Cloudflare Pages 的环境变量中添加：

```text
NODE_VERSION=20
```

## 构建验证

```bash
npm run build
```

构建完成后，Cloudflare Pages 会直接发布 `dist` 目录中的静态文件。
