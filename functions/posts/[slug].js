export async function onRequest(context) {
  const { request, env, params } = context;

  if (request.method !== "GET") {
    return new Response("Method Not Allowed", {
      status: 405,
      headers: { allow: "GET" },
    });
  }

  if (!env.BLOG_BUCKET) {
    return new Response("BLOG_BUCKET binding is not configured", { status: 500 });
  }

  const slug = String(params.slug || "").trim();

  if (!slug) {
    return new Response("缺少文章 slug", { status: 400 });
  }

  const object = await env.BLOG_BUCKET.get(`posts/${slug}.md`);

  if (!object) {
    return new Response("文章不存在", { status: 404 });
  }

  const md = await object.text();

  const headers = new Headers({
    "content-type": "text/plain; charset=utf-8",
    "cache-control": "public, max-age=60",
  });

  if (object.httpEtag) {
    headers.set("etag", object.httpEtag);
  }

  return new Response(md, { headers });
}
