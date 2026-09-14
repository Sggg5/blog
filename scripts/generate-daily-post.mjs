import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import OpenAI from 'openai';

const root = process.cwd();
const postsDir = path.join(root, 'src', 'content', 'blog');
const isDryRun = process.argv.includes('--dry-run');
const model = process.env.BLOG_AI_MODEL || process.env.OPENAI_MODEL;
const today = new Date().toISOString().slice(0, 10);
const forbiddenPhrases = ['作为ai', '作为人工智能', '根据我的知识截止时间', '我无法', 'system prompt', '提示词'];
const topicCandidates = [
  '不锈钢焊缝氧化色与耐腐蚀性：为什么颜色变浅仍不能当作合格依据',
  '不锈钢酸洗、钝化与机械抛光：三种焊后处理分别解决什么问题',
  '双相不锈钢焊接热输入控制：为什么不能只盯着焊缝外观',
  '不锈钢薄壁管涡流探伤：缺陷信号、工艺波动与验证样管如何区分',
  '卡压连接密封失效的排查顺序：从管端、密封圈到压接轮廓',
  '不锈钢管水压试验的现场误区：稳压、排气与泄漏判定',
  '不锈钢焊管在线固溶后的表面问题：氧化、变形和耐蚀性如何一起评估',
  'EPDM 密封圈在热水系统中的失效分析：介质、温度与装配应力',
  '不锈钢制造中的 MSA：量具重复性不足时，过程能力数据还能不能用',
  '用 AI 辅助制造业 8D：如何让问题描述、证据和措施可追溯',
  '基于 ESP32 的设备状态采集：振动、温度信号上云前应先确认什么',
  '不锈钢管焊接保护气的验证方法：不要只看流量表读数',
  '不锈钢冲压件毛刺异常：从模具间隙、材料到润滑的排查逻辑',
  '双相不锈钢选材中的点蚀风险：PREN 只能说明什么，不能说明什么',
  '不锈钢表面粗糙度与耐腐蚀性：为什么 Ra 不是唯一判断依据'
];

function unquote(value = '') {
  return value.trim().replace(/^['"]|['"]$/g, '');
}

function parseFrontmatter(source) {
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---/);
  if (!match) return {};
  const lines = match[1].split(/\r?\n/);
  const data = { tags: [] };
  let inTags = false;
  for (const line of lines) {
    const tag = line.match(/^\s*-\s+(.+)$/);
    if (inTags && tag) { data.tags.push(unquote(tag[1])); continue; }
    const field = line.match(/^([A-Za-z][\w]*):\s*(.*)$/);
    if (!field) continue;
    inTags = field[1] === 'tags';
    if (!inTags) data[field[1]] = unquote(field[2]);
  }
  return data;
}

async function readPosts() {
  const names = (await fs.readdir(postsDir)).filter((name) => /\.mdx?$/i.test(name));
  return Promise.all(names.map(async (name) => {
    const content = await fs.readFile(path.join(postsDir, name), 'utf8');
    return { filename: name, ...parseFrontmatter(content) };
  }));
}

function dateWithinDays(value, days) {
  const date = new Date(value);
  return !Number.isNaN(date.valueOf()) && (Date.now() - date.valueOf()) <= days * 86400000 && date <= new Date();
}

function normalize(value = '') {
  return value.toLowerCase().replace(/[\s，。、“”‘’：:；;、！？!?（）()\-—_]/g, '');
}

function bigrams(value) {
  const text = normalize(value);
  const result = new Set();
  for (let i = 0; i < text.length - 1; i += 1) result.add(text.slice(i, i + 2));
  return result;
}

function similarity(a, b) {
  const left = bigrams(a);
  const right = bigrams(b);
  if (!left.size || !right.size) return 0;
  let common = 0;
  for (const token of left) if (right.has(token)) common += 1;
  return common / (left.size + right.size - common);
}

function topicText(post) {
  return [post.filename.replace(/\.mdx?$/i, ''), post.title, post.category, ...(post.tags || [])].filter(Boolean).join(' ');
}

function safeFilename(title) {
  return title.replace(/[\\/:*?"<>|]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 120);
}

function yamlQuote(value) {
  return JSON.stringify(String(value));
}

function formatMarkdown(post) {
  const sourceLines = post.sources.length
    ? `\n\n## 参考资料\n\n${post.sources.map((source) => `- [${source.name}](${source.url})`).join('\n')}`
    : '';
  return `---\ntitle: ${yamlQuote(post.title)}\ndescription: ${yamlQuote(post.description)}\npubDate: ${today}\ncategory: ${yamlQuote(post.category)}\ntags:\n${post.tags.map((tag) => `  - ${yamlQuote(tag)}`).join('\n')}\n---\n\n${post.article.trim()}${sourceLines}\n`;
}

function validateArticle(post, posts, categories) {
  if (!post || typeof post !== 'object') throw new Error('Article validation failed: response is not an object.');
  if (!post.title?.trim() || !post.description?.trim()) throw new Error('Article validation failed: title or description is empty.');
  if (!categories.has(post.category)) throw new Error(`Article validation failed: unsupported category "${post.category}".`);
  if (!Array.isArray(post.tags) || post.tags.length < 2 || post.tags.length > 6 || post.tags.some((tag) => !String(tag).trim())) throw new Error('Article validation failed: tags must contain 2 to 6 non-empty items.');
  if (typeof post.article !== 'string' || post.article.replace(/\s/g, '').length < 1200) throw new Error('Article validation failed: article body is shorter than 1200 characters.');
  const allText = `${post.title}\n${post.description}\n${post.article}`.toLowerCase();
  if (forbiddenPhrases.some((phrase) => allText.includes(phrase))) throw new Error('Article validation failed: prohibited AI boilerplate was found.');
  if (posts.some((existing) => normalize(existing.title) === normalize(post.title))) throw new Error('Article validation failed: title already exists.');
  const recent = posts.filter((existing) => dateWithinDays(existing.pubDate, 30));
  if (recent.some((existing) => similarity(post.title, topicText(existing)) >= 0.5)) throw new Error('Article validation failed: title is too similar to a topic from the last 30 days.');
  if (!Array.isArray(post.sources)) throw new Error('Article validation failed: sources must be an array.');
}

function schema() {
  return {
    type: 'object', additionalProperties: false,
    required: ['title', 'description', 'category', 'tags', 'article', 'sources'],
    properties: {
      title: { type: 'string' }, description: { type: 'string' }, category: { type: 'string' },
      tags: { type: 'array', minItems: 2, maxItems: 6, items: { type: 'string' } },
      article: { type: 'string' },
      sources: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['name', 'url'], properties: { name: { type: 'string' }, url: { type: 'string' } } } }
    }
  };
}

async function createResponse(client, prompt) {
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await client.responses.create({
        model,
        store: false,
        tools: [{ type: 'web_search' }],
        text: { format: { type: 'json_schema', name: 'daily_technical_post', strict: true, schema: schema() } },
        input: prompt
      });
      if (!response.output_text?.trim()) throw new Error('API returned an empty response.');
      return { post: JSON.parse(response.output_text), rawOutput: JSON.stringify(response.output) };
    } catch (error) {
      lastError = error;
      console.error(`Article generation attempt ${attempt}/3 failed: ${error.message}`);
      if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, attempt * 1500));
    }
  }
  throw new Error(`Article generation failed after 3 attempts: ${lastError?.message || 'unknown error'}`);
}

async function main() {
  if (!process.env.OPENAI_API_KEY) throw new Error('OPENAI_API_KEY is required.');
  if (!model) throw new Error('BLOG_AI_MODEL or OPENAI_MODEL is required; no default model is assumed.');
  const posts = await readPosts();
  const categories = new Set(posts.map((post) => post.category).filter(Boolean));
  if (!categories.size) throw new Error('Topic generation failed: no existing categories were found.');
  const recentTopics = posts.filter((post) => dateWithinDays(post.pubDate, 30)).map(topicText);
  const candidate = topicCandidates[new Date(`${today}T00:00:00Z`).getUTCDate() % topicCandidates.length];
  const prompt = `你是面向制造业工程师的中文技术编辑。今天日期是 ${today}。请围绕候选方向生成一篇新的技术博客文章，但如候选方向与已有主题重复，请自行换成同一领域中不重复、可长期使用的基础技术主题。\n\n候选方向：${candidate}\n\n已有文章主题（文件名、标题、分类和标签；禁止语义重复，尤其是近30天主题）：\n${posts.map(topicText).join('\n')}\n\n允许的分类（必须原样选一个）：${[...categories].join('、')}\n\n要求：正文 1500-3000 个中文字符，直接进入工程问题；给出机理、现场判断方法、改善建议和常见误区。不得编造标准编号、条款、精确化学成分、力学数据、法规或试验数值。焊后表面处理必须区分机械抛光、酸洗、钝化和酸洗钝化；不得把表面光亮度等同于耐腐蚀性。优先使用 web search 检索权威一手技术资料；仅在确实使用并能确认链接时填写 sources，否则返回空数组。不要写营销文、标题党、AI 自述或任何 frontmatter。article 必须是 Markdown 正文，含清晰的二级标题。`;
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY, timeout: 120000, maxRetries: 0 });
  const { post, rawOutput } = await createResponse(client, prompt);
  // Do not publish source links that the API response did not expose as retrieved material.
  post.sources = post.sources.filter((source) => /^https:\/\//.test(source.url) && rawOutput.includes(source.url));
  validateArticle(post, posts, categories);
  const filename = `${safeFilename(post.title)}.md`;
  if (!filename || filename === '.md') throw new Error('Article validation failed: unsafe filename.');
  const target = path.join(postsDir, filename);
  try { await fs.access(target); throw new Error(`Article validation failed: ${filename} already exists; refusing to overwrite.`); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  const markdown = formatMarkdown(post);
  if (isDryRun) { console.log(`Dry run: ${filename}\n\n${markdown}`); return; }
  await fs.writeFile(target, markdown, { encoding: 'utf8', flag: 'wx' });
  console.log(`Generated: ${path.relative(root, target)}`);
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });
