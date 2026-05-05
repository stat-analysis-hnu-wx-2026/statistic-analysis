#!/usr/bin/env python3
"""Build and serve this project on localhost."""

from __future__ import annotations

import argparse
import os
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(ROOT, "build")


def run_build() -> None:
    print("[run_localhost] Running build.py ...")
    subprocess.run(["python", "build.py"], cwd=ROOT, check=True)


def serve(host: str, port: int) -> None:
    os.chdir(BUILD_DIR)
    handler = SimpleHTTPRequestHandler
    with ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"[run_localhost] Serving: http://{host}:{port}")
        print("[run_localhost] Press Ctrl+C to stop.")
        httpd.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and serve on localhost.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip running build.py and serve existing build/ directly.",
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Only run build.py, then exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_build:
        run_build()
    if args.build_only:
        print("[run_localhost] Build done.")
        return
    if not os.path.isdir(BUILD_DIR):
        raise SystemExit("[run_localhost] build/ not found. Run without --skip-build first.")
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
