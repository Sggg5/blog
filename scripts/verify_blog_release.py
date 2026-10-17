#!/usr/bin/env python3
"""Fail-closed exact-SHA Cloudflare + CI + live webpage release gate (stdlib only)."""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

REQUIRED = ("validate", "sync-r2", "build", "Cloudflare Pages")

def fetch(url, token=None):
    headers = {"User-Agent": "sggg-blog-v5", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    with urlopen(Request(url, headers=headers), timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"{response.status} {url}")
        return response.read()

def poll_checks(repo, sha, token, seconds):
    deadline = time.monotonic() + seconds
    old = ""
    while True:
        response = json.loads(fetch(f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs?per_page=100", token))
        runs = {}
        for item in response.get("check_runs", []):
            name = item.get("name")
            if name in REQUIRED and (name not in runs or item["id"] > runs[name]["id"]):
                runs[name] = item
        states = [(name, runs.get(name,{}).get("status","missing"),
                   runs.get(name,{}).get("conclusion")) for name in REQUIRED]
        state = json.dumps(states, ensure_ascii=False)
        if state != old:
            print("CHECKS "+state, flush=True)
            old = state
        failures = [name for name in REQUIRED if runs.get(name,{}).get("status") == "completed"
                    and runs[name].get("conclusion") != "success"]
        if failures:
            return runs, "check failed: " + ",".join(failures)
        if all(runs.get(name,{}).get("status") == "completed" and
               runs[name].get("conclusion") == "success" for name in REQUIRED):
            return runs, ""
        if time.monotonic() >= deadline:
            return runs, "timeout waiting for completed/success checks"
        time.sleep(15)

def find_posts(before, after, supplied):
    if supplied:
        return [supplied]
    if not before or set(before) == {"0"}:
        raise ValueError("no previous commit; workflow_dispatch requires --post")
    changed = subprocess.check_output(
        ["git", "diff", "--diff-filter=AM", "--name-only", "-z", before, after, "--", "src/content/blog/"],
        text=True).split("\0")
    return [x for x in changed if x.endswith(".md")]

def poll_site(base, posts, seconds=150):
    deadline = time.monotonic() + seconds
    results = {}
    while True:
        for post in posts:
            match = re.search(r"(?m)^title:\s*(.*)$", Path(post).read_text(encoding="utf-8"))
            if not match:
                raise ValueError(f"missing title: {post}")
            expected = match.group(1).strip().strip('"\'')
            url = base.rstrip("/") + "/blog/" + quote(Path(post).stem, safe="") + "/"
            try:
                page = html.unescape(fetch(url).decode("utf-8"))
                results[post] = ("success: " if expected in page else "missing title: ") + url
            except Exception as exc:
                results[post] = f"{type(exc).__name__}: {exc} at {url}"
        if all(x.startswith("success: ") for x in results.values()):
            return results, ""
        if time.monotonic() >= deadline:
            return results, "site page unreachable or expected title absent"
        time.sleep(10)

def report(sha, checks, pages, error):
    lines = ["## Exact-SHA blog publication audit", "SHA: \`"+sha+"\`", "",
             "| Gate | Status | Logs |","|---|---|---|"]
    for name in REQUIRED:
        item = checks.get(name,{})
        status = item.get("status","missing") + "/" + str(item.get("conclusion") or "pending")
        link = item.get("details_url") or item.get("html_url") or ""
        lines.append(f"| {name} | {status} | {link} |")
    lines.extend("- "+name+": "+status for name,status in pages.items())
    lines.append("\n**"+("RELEASE FAILED: "+error if error else "WEBSITE_RELEASE_SUCCESS")+"**")
    output = "\n".join(lines)+"\n"
    print(output, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as file:
            file.write(output)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", required=True)
    parser.add_argument("--before", default="")
    parser.add_argument("--post", default="")
    parser.add_argument("--site", default="https://blog.sggg.cc.cd")
    parser.add_argument("--timeout", type=int, default=720)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("GITHUB_TOKEN/checks:read unavailable")
    posts = find_posts(args.before, args.sha, args.post)
    if not posts or any(not Path(x).is_file() for x in posts):
        raise ValueError("no existing changed Markdown posts to verify")
    checks, problem = poll_checks(os.environ.get("GITHUB_REPOSITORY", "Sggg5/blog"),
                                  args.sha, token, args.timeout)
    pages = {}
    if not problem:
        pages, problem = poll_site(args.site, posts)
    report(args.sha, checks, pages, problem)
    if problem:
        raise RuntimeError(problem)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit("RELEASE_NOT_CONFIRMED: "+str(exc))
