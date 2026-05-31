const POSTS_DIR = "src/content/blog";

export async function onRequest(context) {
  const { request } = context;

  try {
    if (!isAuthorized(request, context.env)) {
      return json({ error: "Unauthorized" }, 401);
    }

    if (request.method === "GET") return handleGet(context);
    if (request.method === "POST") return handlePost(context);

    return new Response("Method Not Allowed", {
      status: 405,
      headers: { allow: "GET, POST" },
    });
  } catch (error) {
    return json({ error: error.message || "Server error" }, error.status || 500);
  }
}

async function handleGet(context) {
  const url = new URL(context.request.url);
  const path = cleanPath(url.searchParams.get("path") || "");

  if (path) {
    const file = await githubRequest(context.env, `/repos/${repo(context.env)}/contents/${encodePath(path)}?ref=${branch(context.env)}`);
    return json({
      path,
      sha: file.sha,
      markdown: decodeBase64(file.content || ""),
      downloadUrl: file.download_url,
    });
  }

  const tree = await githubRequest(
    context.env,
    `/repos/${repo(context.env)}/git/trees/${branch(context.env)}?recursive=1`,
  );
  const files = (tree.tree || [])
    .filter((item) => item.type === "blob" && item.path.startsWith(`${POSTS_DIR}/`) && /\.mdx?$/i.test(item.path))
    .sort((a, b) => a.path.localeCompare(b.path, "zh-CN"));

  const posts = await Promise.all(files.map(async (item) => {
    try {
      const content = await githubRequest(context.env, `/repos/${repo(context.env)}/contents/${encodePath(item.path)}?ref=${branch(context.env)}`);
      const markdown = decodeBase64(content.content || "");
      return {
        path: item.path,
        sha: item.sha,
        filename: item.path.slice(POSTS_DIR.length + 1),
        ...readFrontmatter(markdown),
      };
    } catch {
      return {
        path: item.path,
        sha: item.sha,
        filename: item.path.slice(POSTS_DIR.length + 1),
        title: item.path.slice(POSTS_DIR.length + 1).replace(/\.(md|mdx)$/i, ""),
        description: "",
        pubDate: "",
        category: "",
        tags: [],
        draft: false,
      };
    }
  }));

  posts.sort((a, b) => String(b.pubDate || "").localeCompare(String(a.pubDate || "")));
  return json({ posts });
}

async function handlePost(context) {
  const body = await context.request.json().catch(() => null);

  if (!body || typeof body !== "object") {
    return json({ error: "Invalid JSON body" }, 400);
  }

  if (body.action === "delete") {
    const path = cleanPath(body.path || "");
    if (!path) return json({ error: "Missing path" }, 400);

    const existing = await getFile(context.env, path);
    if (!existing) return json({ error: "Post not found" }, 404);

    const result = await githubRequest(context.env, `/repos/${repo(context.env)}/contents/${encodePath(path)}`, {
      method: "DELETE",
      body: JSON.stringify({
        message: `Delete post: ${path.slice(POSTS_DIR.length + 1)}`,
        branch: branch(context.env),
        sha: existing.sha,
      }),
    });

    return json({ ok: true, commit: result.commit?.html_url });
  }

  const markdown = String(body.markdown || "").trimEnd() + "\n";
  const filename = safeFilename(body.filename || "");
  const currentPath = cleanPath(body.path || "");

  if (!markdown.trim()) return json({ error: "Missing markdown" }, 400);
  if (!filename) return json({ error: "Missing filename" }, 400);

  const nextPath = `${POSTS_DIR}/${filename}`;
  const existing = await getFile(context.env, currentPath || nextPath);
  const nextExisting = currentPath && currentPath !== nextPath ? await getFile(context.env, nextPath) : null;

  if (nextExisting) {
    return json({ error: "A post with that filename already exists" }, 409);
  }

  const result = await githubRequest(context.env, `/repos/${repo(context.env)}/contents/${encodePath(nextPath)}`, {
    method: "PUT",
    body: JSON.stringify({
      message: `${existing ? "Update" : "Create"} post: ${filename}`,
      branch: branch(context.env),
      content: encodeBase64(markdown),
      sha: existing && currentPath === nextPath ? existing.sha : undefined,
    }),
  });

  if (existing && currentPath && currentPath !== nextPath) {
    await githubRequest(context.env, `/repos/${repo(context.env)}/contents/${encodePath(currentPath)}`, {
      method: "DELETE",
      body: JSON.stringify({
        message: `Remove renamed post: ${currentPath.slice(POSTS_DIR.length + 1)}`,
        branch: branch(context.env),
        sha: existing.sha,
      }),
    });
  }

  return json({
    ok: true,
    path: nextPath,
    sha: result.content?.sha,
    commit: result.commit?.html_url,
  });
}

function isAuthorized(request, env) {
  const password = env.ADMIN_PASSWORD;
  if (!password) return false;

  const headerPassword = request.headers.get("x-admin-password");
  if (headerPassword === password) return true;

  const auth = request.headers.get("authorization") || "";
  if (!auth.startsWith("Basic ")) return false;

  try {
    const token = auth.split(" ")[1];
    const decoded = atob(token);
    const index = decoded.indexOf(":");
    return decoded.slice(index + 1) === password;
  } catch {
    return false;
  }
}

async function getFile(env, path) {
  if (!path) return null;
  try {
    return await githubRequest(env, `/repos/${repo(env)}/contents/${encodePath(path)}?ref=${branch(env)}`);
  } catch (error) {
    if (error.status === 404) return null;
    throw error;
  }
}

async function githubRequest(env, pathname, init = {}) {
  const token = env.GITHUB_TOKEN;
  if (!token) {
    const error = new Error("Missing GITHUB_TOKEN");
    error.status = 500;
    throw error;
  }

  const response = await fetch(`https://api.github.com${pathname}`, {
    ...init,
    headers: {
      accept: "application/vnd.github+json",
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
      "user-agent": "franta-blog-admin",
      "x-github-api-version": "2022-11-28",
      ...(init.headers || {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    const error = new Error(detail || response.statusText);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

function repo(env) {
  return env.GITHUB_REPO || "Sggg5/blog";
}

function branch(env) {
  return env.GITHUB_BRANCH || "main";
}

function cleanPath(path) {
  const value = String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
  if (!value || value.includes("..") || !value.startsWith(`${POSTS_DIR}/`)) return "";
  if (!/\.mdx?$/i.test(value)) return "";
  return value;
}

function safeFilename(filename) {
  const value = String(filename || "")
    .trim()
    .replace(/\\/g, "/")
    .split("/")
    .pop()
    .replace(/[<>:"|?*\u0000-\u001F]/g, "")
    .replace(/\s+/g, "-")
    .replace(/\.mdx?$/i, "")
    .slice(0, 120)
    .trim();

  return value ? `${value}.md` : "";
}

function encodePath(path) {
  return path.split("/").map(encodeURIComponent).join("/");
}

function encodeBase64(value) {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
}

function decodeBase64(value) {
  const binary = atob(String(value).replace(/\s/g, ""));
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function readFrontmatter(markdown) {
  const match = markdown.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!match) {
    return { title: "", description: "", pubDate: "", category: "", tags: [], draft: false };
  }

  const frontmatter = match[1];
  const field = (name) => {
    const found = frontmatter.match(new RegExp(`^${name}:\\s*(.*)$`, "m"));
    return found ? found[1].trim().replace(/^["']|["']$/g, "") : "";
  };
  const tagsBlock = frontmatter.match(/^tags:\s*\n((?:\s+- .*\n?)*)/m);
  const tags = tagsBlock
    ? tagsBlock[1].split("\n").map((line) => line.replace(/^\s*-\s*/, "").trim()).filter(Boolean)
    : [];

  return {
    title: field("title"),
    description: field("description"),
    pubDate: field("pubDate"),
    category: field("category"),
    tags,
    draft: field("draft") === "true",
  };
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
