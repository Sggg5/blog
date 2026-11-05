#!/usr/bin/env python3
"""Assemble a staged Base64 WebP cover into public/images/blog after strict SHA validation."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = (ROOT / "tmp/blog-asset-staging").resolve()
ASSET_ROOT = (ROOT / "public/images/blog").resolve()

def git_blob_sha(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\\0"
    return hashlib.sha1(header + data).hexdigest()

def webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("invalid RIFF/WEBP header")
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise ValueError("RIFF size does not match file size")
    if data[12:16] == b"VP8X":
        return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    if data[12:16] == b"VP8 " and data[23:26] == b"\\x9d\\x01\\x2a":
        return int.from_bytes(data[26:28], "little") & 16383, int.from_bytes(data[28:30], "little") & 16383
    if data[12:16] == b"VP8L" and data[20] == 47:
        n = int.from_bytes(data[21:25], "little")
        return (n & 16383) + 1, ((n >> 14) & 16383) + 1
    raise ValueError("unsupported WebP bitstream")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", default="tmp/blog-asset-staging/manifest.json")
    args = parser.parse_args()
    manifest_path = (ROOT / args.manifest).resolve()
    if STAGING not in manifest_path.parents or not manifest_path.is_file():
        raise ValueError("manifest must be inside tmp/blog-asset-staging")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = manifest.get("target_path", "")
    if not isinstance(target, str) or not target.startswith("public/images/blog/") or not target.endswith(".webp"):
        raise ValueError("target_path must be a local public/images/blog/*.webp path")
    target_path = (ROOT / target).resolve()
    if ASSET_ROOT not in target_path.parents:
        raise ValueError("target_path escapes public/images/blog")
    count = manifest.get("chunk_count")
    size = manifest.get("expected_size")
    expected_sha = manifest.get("expected_git_blob_sha")
    if not isinstance(count, int) or not 1 <= count <= 100:
        raise ValueError("chunk_count must be 1..100")
    if not isinstance(size, int) or size < 1:
        raise ValueError("expected_size must be positive")
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("expected_git_blob_sha must be a lowercase SHA-1")
    encoded = []
    for index in range(count):
        chunk_path = STAGING / f"chunk-{index:03d}.b64"
        if not chunk_path.is_file() or chunk_path.is_symlink():
            raise ValueError(f"missing or unsafe chunk: {chunk_path.name}")
        chunk = chunk_path.read_text(encoding="ascii").strip()
        if not chunk or re.search(r"\\s", chunk):
            raise ValueError(f"empty/whitespace in {chunk_path.name}")
        encoded.append(chunk)
    data = base64.b64decode("".join(encoded), validate=True)
    actual_sha = git_blob_sha(data)
    if len(data) != size:
        raise ValueError(f"size mismatch: expected {size}, got {len(data)}")
    if actual_sha != expected_sha:
        raise ValueError(f"Git blob SHA mismatch: expected {expected_sha}, got {actual_sha}")
    width, height = webp_dimensions(data)
    if width < 960 or height < 540 or abs(width / height - 16 / 9) > 0.03:
        raise ValueError(f"cover must be >=960x540 and 16:9, got {width}x{height}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        existing = target_path.read_bytes()
        if git_blob_sha(existing) != expected_sha:
            raise ValueError("target already exists with different content; refusing overwrite")
        result = "already-present"
    else:
        target_path.write_bytes(data)
        result = "assembled"
    print(json.dumps({
        "result": result,
        "path": target,
        "size": len(data),
        "git_blob_sha": actual_sha,
        "width": width,
        "height": height
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
