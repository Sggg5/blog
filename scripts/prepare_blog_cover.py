#!/usr/bin/env python3
"""Prepare a photo cover and chunked base64 transport for GitHub create_blob.

Requires Pillow, available in ChatGPT's image runtime. The transport text is an
intermediate artifact to be read by files.read, not a repository asset.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--transport', type=Path, required=True)
    parser.add_argument('--width', type=int, default=960)
    parser.add_argument('--quality', type=int, default=72)
    args = parser.parse_args()
    if args.width < 480 or not (40 <= args.quality <= 90):
        parser.error('Use width >= 480 and quality between 40 and 90')
    size = (args.width, round(args.width * 9 / 16))
    with Image.open(args.source) as original:
        rgb = ImageOps.fit(original.convert('RGB'), size, method=Image.Resampling.LANCZOS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.transport.parent.mkdir(parents=True, exist_ok=True)
    rgb.save(args.output, 'WEBP', quality=args.quality, method=6)
    data = args.output.read_bytes()
    if not data.startswith(b'RIFF') or data[8:12] != b'WEBP':
        raise ValueError('Not a valid WebP signature')
    sha = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
    b64 = base64.b64encode(data).decode('ascii')
    if base64.b64decode(b64, validate=True) != data:
        raise ValueError('Encoding round-trip check failed')
    lines = [b64[i:i+3000] for i in range(0, len(b64), 3000)]
    args.transport.write_text('B64-BEGIN\n' + '\n'.join(lines) + '\nB64-END\n', encoding='ascii')
    print(json.dumps({'image': str(args.output), 'transport': str(args.transport),
                      'width': size[0], 'height': size[1], 'bytes': len(data),
                      'base64_length': len(b64), 'git_blob_sha': sha}, ensure_ascii=False))


if __name__ == '__main__':
    main()