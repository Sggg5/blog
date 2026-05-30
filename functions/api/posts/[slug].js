export async function onRequest(context) {
  const { request, env, params } = context;

  if (request.method !== "GET") {
    return new Response("Method Not Allowed", {
      status: 405,
      headers: { allow: "GET" },
    });
  }

  if (!env.BLOG_BUCKET) {
    return json({ error: "BLOG_BUCKET binding is not configured" }, 500);
  }

  const slug = decodeURIComponent(String(params.slug || "").trim());

  if (!slug) {
    return json({ error: "缺少文章 slug" }, 400);
  }

  const key = `posts/${slug}.md`;
  const object = await env.BLOG_BUCKET.get(key);

  if (!object) {
    return json({ error: "文章不存在", key }, 404);
  }

  const md = await object.text();
  const headers = new Headers({
    "content-type": "text/plain; charset=utf-8",
    "cache-control": "public, max-age=60",
    "x-r2-key": key,
  });

  if (object.httpEtag) {
    headers.set("etag", object.httpEtag);
  }

  return new Response(md, { headers });
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
