#!/usr/bin/env python3
"""Check a blog Markdown post before deployment (stdlib only).

Usage: python3 scripts/validate_blog_assets.py src/content/blog/article.md [...]
Paths are resolved relative to the repository root.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("title", "description", "pubDate", "category", "tags")
IMG_MD = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
IMG_HTML = re.compile(r"<img\b[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]", re.I)


def field(frontmatter: str, key: str) -> str | None:
    m = re.search(r"(?m)^" + re.escape(key) + r":\s*(.*)$", frontmatter)
    return m.group(1).strip().strip('"\'') if m else None


def validate(path: Path) -> list[str]:
    issues: list[str] = []
    if not path.is_file():
        return [f"{path}: Markdown file missing"]
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    if not m:
        return [f"{path}: missing or invalid YAML frontmatter"]
    front = m.group(1)
    for key in REQUIRED:
        if not field(front, key):
            issues.append(f"{path}: missing frontmatter field {key}")
    pub = field(front, "pubDate")
    if pub:
        try:
            date.fromisoformat(pub[:10])
        except ValueError:
            issues.append(f"{path}: pubDate must be YYYY-MM-DD")
    tags_line = field(front, "tags")
    if tags_line:
        if tags_line.startswith("[") and tags_line.endswith("]"):
            tags = [t.strip() for t in tags_line[1:-1].split(",") if t.strip()]
        else:
            tm = re.search(r"(?ms)^tags:\s*\n((?:[ \t]+-.*\n?)+)", front)
            tags = re.findall(r"(?m)^\s+-\s+\S", tm.group(1)) if tm else []
        if not 2 <= len(tags) <= 6:
            issues.append(f"{path}: expected 2-6 tags, got {len(tags)}")

    cover = field(front, "coverImage")
    alt = field(front, "coverAlt")
    if bool(cover) != bool(alt):
        issues.append(f"{path}: coverImage and coverAlt must either both exist or both be absent")

    urls = set(IMG_MD.findall(text) + IMG_HTML.findall(text))
    if cover:
        urls.add(cover)
        if Path(cover).suffix.lower() not in {".webp", ".jpg", ".jpeg", ".png"}:
            issues.append(f"{path}: cover must be a WebP/JPG/PNG photograph, not an SVG")

    for url in sorted(urls):
        if url.startswith(("https://", "http://")):
            continue
        if not url.startswith("/images/blog/"):
            issues.append(f"{path}: unexpected local image URL {url!r}")
            continue
        rel = url.lstrip("/")
        asset = ROOT / "public" / rel
        if not asset.is_file() or asset.stat().st_size == 0:
            issues.append(f"{path}: missing or zero-byte asset public/{rel}")
    return issues


def main(paths: list[str]) -> int:
    if not paths:
        print("Usage: validate_blog_assets.py POST.md [POST2.md ...]", file=sys.stderr)
        return 2
    all_issues: list[str] = []
    for name in paths:
        all_issues.extend(validate(ROOT / name))
    if all_issues:
        for issue in all_issues:
            print("ERROR:", issue, file=sys.stderr)
        return 1
    print(f"PASS: validated {len(paths)} post(s), frontmatter and all local image references.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
