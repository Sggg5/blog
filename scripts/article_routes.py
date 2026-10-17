#!/usr/bin/env python3
"""Resolve published article URLs from rendered homepage instead of guessing Astro slug rules."""
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

def article_title(path):
    text = Path(path).read_text(encoding="utf-8")
    m = re.search(r"(?m)^title:\s*(.+)$", text)
    if not m:
        raise ValueError(f"missing frontmatter title: {path}")
    return m.group(1).strip().strip('"\'')

class BlogLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.href = None
        self.in_title = False
        self.parts = []
        self.titles = {}
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            url = dict(attrs).get("href", "")
            self.href = url if url.startswith("/blog/") else None
        if tag == "h3" and self.href:
            self.in_title = True
            self.parts = []
    def handle_data(self, data):
        if self.in_title:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == "h3" and self.in_title:
            title = "".join(self.parts).strip()
            if title:
                self.titles[title] = self.href
            self.in_title = False
        if tag == "a":
            self.href = None

def article_links(homepage):
    parser = BlogLinks()
    parser.feed(homepage)
    return parser.titles

def generated_html_path(href, dist=Path("dist")):
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/blog/"):
        raise ValueError(f"unexpected blog URL: {href}")
    relative = unquote(parsed.path).lstrip("/")
    candidate = (dist / relative / "index.html") if not relative.endswith(".html") else dist / relative
    candidate = candidate.resolve()
    if dist.resolve() not in candidate.parents:
        raise ValueError(f"path traversal: {href}")
    return candidate
