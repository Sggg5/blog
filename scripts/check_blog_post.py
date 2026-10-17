#!/usr/bin/env python3
"""Fail closed on invalid new engineering blog articles; Python standard library."""
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "src/content/blog"

def parse(path):
    data = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", data, re.S)
    if not match:
        raise ValueError("missing YAML frontmatter")
    front = match.group(1)
    fields = {}
    for key in ("title", "description", "pubDate", "category", "coverImage", "coverAlt", "draft"):
        m = re.search(r"(?m)^" + key + r":\s*(.*)$", front)
        if m:
            fields[key] = m.group(1).strip().strip('"\'')
    block = re.search(r"(?ms)^tags:\s*\n((?:[ \t]+-.*\n?)+)", front)
    inline = re.search(r"(?m)^tags:\s*\[([^\]]*)\]", front)
    fields["tags"] = ([t.strip().strip('"\'') for t in re.findall(r"(?m)^[ \t]+-[ \t]+(.+)$", block.group(1))]
                      if block else [t.strip().strip('"\'') for t in inline.group(1).split(",") if t.strip()]
                      if inline else [])
    return fields, data[match.end():]

def dimensions(data):
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP" or len(data) < 30:
        raise ValueError("bad WebP header")
    if data[12:16] == b"VP8X":
        return int.from_bytes(data[24:27], "little")+1, int.from_bytes(data[27:30], "little")+1
    if data[12:16] == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
        return int.from_bytes(data[26:28], "little") & 16383, int.from_bytes(data[28:30], "little") & 16383
    if data[12:16] == b"VP8L" and data[20] == 47:
        n = int.from_bytes(data[21:25], "little")
        return (n & 16383)+1, ((n >> 14) & 16383)+1
    raise ValueError("unrecognized WebP format")

def validate(name):
    path = (ROOT / name).resolve()
    if path.parent != POSTS.resolve() or path.suffix != ".md" or not path.is_file():
        raise ValueError("not a new blog Markdown file")
    f, body = parse(path)
    if any(not f.get(field) for field in ("title", "description", "pubDate", "category")):
        raise ValueError("missing title, description, pubDate or category")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", f["pubDate"]):
        raise ValueError("invalid publication date")
    date.fromisoformat(f["pubDate"])
    n = len(re.findall(r"[\u3400-\u9fff]", body))
    if not 1200 <= n <= 2200:
        raise ValueError(f"article length {n} Chinese characters, expected 1200..2200")
    if not 2 <= len(f["tags"]) <= 6 or len(f["tags"]) != len(set(f["tags"])):
        raise ValueError("tags must be 2..6 unique values")
    if f.get("draft","").lower() == "true":
        raise ValueError("draft cannot be released")
    categories, titles = set(), set()
    for old in POSTS.glob("*.md"):
        if old.resolve() == path:
            continue
        try:
            info, _ = parse(old)
        except ValueError:
            continue
        categories.add(info.get("category"))
        titles.add(re.sub(r"\s+", "", info.get("title","")).casefold())
    if f["category"] not in categories:
        raise ValueError("category is not an existing blog value")
    if re.sub(r"\s+", "", f["title"]).casefold() in titles:
        raise ValueError("duplicate article title")
    cover = f.get("coverImage","")
    if not cover.startswith("/images/blog/") or not cover.endswith(".webp") or not f.get("coverAlt"):
        raise ValueError("local WebP cover and coverAlt required")
    root = (ROOT / "public/images/blog").resolve()
    cover_path = (ROOT / "public" / cover.lstrip("/")).resolve()
    if root not in cover_path.parents or not cover_path.is_file():
        raise ValueError("cover missing from repository")
    w,h = dimensions(cover_path.read_bytes())
    if w < 960 or h < 540 or abs(w/h-16/9) > .03:
        raise ValueError(f"cover geometry must be >=960x540 and 16:9, got {w}x{h}")
    urls = set(re.findall(r"!\[[^\]]*\]\((/images/blog/[^)\s]+)", body))
    urls.update(re.findall(r'<img\b[^>]*\bsrc\s*=\s*["\'](/images/blog/[^"\']+)', body, re.I))
    svgs = set()
    for url in urls:
        p = (ROOT / "public" / url.lstrip("/")).resolve()
        if root not in p.parents or not p.is_file() or p.stat().st_size == 0:
            raise ValueError(f"missing local picture: {url}")
        if p.suffix.lower() == ".svg":
            svg = ET.parse(p).getroot()
            if svg.tag.split("}")[-1] != "svg" or any(
                x.tag.split("}")[-1].lower() in ("script","foreignobject") for x in svg.iter()
            ):
                raise ValueError(f"invalid or unsafe SVG: {url}")
            svgs.add(url)
    if not 1 <= len(svgs) <= 3:
        raise ValueError("expected 1..3 original SVG engineering diagrams")
    print(f"PASS {name}: {n} Chinese characters, {w}x{h} WebP, {len(svgs)} SVG")

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            raise ValueError("usage: check_blog_post.py FILE.md [FILE.md...]")
        for name in sys.argv[1:]:
            validate(name)
    except Exception as exc:
        sys.exit(f"POST_VALIDATION_FAILED: {exc}")
