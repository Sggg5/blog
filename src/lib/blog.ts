import { getCollection } from 'astro:content';

export const getPublishedPosts = async () => {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  return posts.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
};

export const getPostSlug = (id: string) => id.replace(/\.(md|mdx)$/i, '');

export const getCategories = (posts: Awaited<ReturnType<typeof getPublishedPosts>>) => {
  const counts = new Map<string, number>();
  posts.forEach((post) => counts.set(post.data.category, (counts.get(post.data.category) ?? 0) + 1));
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0], 'zh-CN'));
};

export const getTags = (posts: Awaited<ReturnType<typeof getPublishedPosts>>) => {
  const counts = new Map<string, number>();
  posts.forEach((post) => post.data.tags.forEach((tag) => counts.set(tag, (counts.get(tag) ?? 0) + 1)));
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0], 'zh-CN'));
};
