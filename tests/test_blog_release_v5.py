"""Regression tests for the strict article checker and release gate (no network)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

strict = load("check_blog_post")
gate = load("verify_blog_release")

class StrictCoverTests(unittest.TestCase):
    def test_vp8x_size(self):
        header = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"VP8X" + b"\x00" * 8
        header += (959).to_bytes(3, "little") + (539).to_bytes(3, "little")
        self.assertEqual(strict.dimensions(header), (960, 540))
    def test_reject_fake_webp(self):
        with self.assertRaises(ValueError):
            strict.dimensions(b"not a real image")
    def test_missing_frontmatter(self):
        with tempfile.TemporaryDirectory() as directory:
            post = Path(directory) / "post.md"
            post.write_text("abc", encoding="utf-8")
            with self.assertRaises(ValueError):
                strict.parse(post)

class ReleaseGateTests(unittest.TestCase):
    def result(self, name, status="completed", conclusion="success", id=1):
        return {"name": name, "id": id, "status": status,
                "conclusion": conclusion, "details_url": "https://example.org/log"}

    def test_all_four_success(self):
        body = json.dumps({"check_runs": [self.result(name) for name in gate.REQUIRED]}).encode()
        with patch.object(gate, "fetch", return_value=body):
            checks, error = gate.poll_checks("Sggg5/blog", "a"*40, "token", 0)
        self.assertEqual(error, "")
        self.assertEqual(len(checks), 4)

    def test_cloudflare_failure_blocks(self):
        runs = [self.result(name) for name in gate.REQUIRED]
        runs[-1]["conclusion"] = "failure"
        with patch.object(gate, "fetch", return_value=json.dumps({"check_runs": runs}).encode()):
            _, error = gate.poll_checks("Sggg5/blog", "a"*40, "token", 0)
        self.assertIn("Cloudflare Pages", error)

    def test_pending_never_counts_as_success(self):
        runs = [self.result(name) for name in gate.REQUIRED[:-1]]
        runs += [self.result("Cloudflare Pages", "in_progress", None)]
        with patch.object(gate, "fetch", return_value=json.dumps({"check_runs": runs}).encode()):
            _, error = gate.poll_checks("Sggg5/blog", "a"*40, "token", 0)
        self.assertIn("timeout", error)

    def test_latest_check_overrides_old_success(self):
        runs = [self.result(name) for name in gate.REQUIRED]
        runs += [self.result("Cloudflare Pages", "completed", "failure", 2)]
        with patch.object(gate, "fetch", return_value=json.dumps({"check_runs": runs}).encode()):
            _, error = gate.poll_checks("Sggg5/blog", "a"*40, "token", 0)
        self.assertIn("Cloudflare Pages", error)

if __name__ == "__main__":
    unittest.main()
