#!/usr/bin/env python3
"""
render_video.py — render a Remotion project to MP4/WebM/PNG.

Usage:
  python render_video.py --project ./remotion-projects/my-video --out video.mp4
  python render_video.py --project ./remotion-projects/clip --out clip.mp4 --codec h264 --quality 80
  python render_video.py --project ./proj --out frame.png --frames 0
"""
import argparse
import os
import subprocess
import sys


def check_deps():
    errors = []
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        ver = result.stdout.strip()
        major = int(ver.lstrip("v").split(".")[0])
        if major < 16:
            errors.append(f"Node.js 16+ required, found {ver}")
        else:
            print(f"Node.js: {ver}")
    except FileNotFoundError:
        errors.append("Node.js not found — install from nodejs.org")

    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        print(f"ffmpeg: {result.stdout.splitlines()[0]}")
    except FileNotFoundError:
        errors.append("ffmpeg not found — install with: winget install ffmpeg  OR  brew install ffmpeg")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def install_deps(project_dir: str):
    node_modules = os.path.join(project_dir, "node_modules")
    if not os.path.exists(node_modules):
        print("Installing npm dependencies...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=project_dir,
            capture_output=False,
        )
        if result.returncode != 0:
            print("ERROR: npm install failed", file=sys.stderr)
            sys.exit(1)
        print("Dependencies installed.")
    else:
        print("node_modules exists, skipping npm install.")


def render(project_dir: str, out: str, composition: str, codec: str,
           quality: int, frames: str | None, concurrency: int):
    abs_project = os.path.abspath(project_dir)
    abs_out = os.path.abspath(out)
    os.makedirs(os.path.dirname(abs_out) if os.path.dirname(abs_out) else ".", exist_ok=True)

    # Detect entry point
    for candidate in ["src/index.ts", "src/index.tsx", "src/Root.tsx"]:
        if os.path.exists(os.path.join(abs_project, candidate)):
            entry = candidate
            break
    else:
        entry = "src/index.ts"

    # On Windows npx is npx.cmd; on Linux/Mac it's npx
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    cmd = [
        npx, "remotion", "render",
        entry,
        composition,
        abs_out,
        f"--codec={codec}",
        f"--concurrency={concurrency}",
        # Chrome Headless Shell needs --no-sandbox on Windows and headless Linux servers
        "--browser-args=--no-sandbox",
    ]
    if quality != 80:
        cmd.append(f"--crf={100 - quality}")
    if frames is not None:
        cmd.append(f"--frames={frames}")

    print(f"Rendering: {' '.join(cmd)}")
    print(f"Project  : {abs_project}")
    print(f"Output   : {abs_out}")
    print()

    result = subprocess.run(cmd, cwd=abs_project)
    if result.returncode != 0:
        print(f"\nERROR: Render failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)

    size = os.path.getsize(abs_out) if os.path.exists(abs_out) else 0
    size_mb = size / 1024 / 1024
    print(f"\nRender complete: {abs_out} ({size_mb:.1f} MB)")
    return abs_out


def main():
    parser = argparse.ArgumentParser(description="Render a Remotion project to video")
    parser.add_argument("--project", required=True, help="Path to Remotion project directory")
    parser.add_argument("--out", required=True, help="Output file path (e.g. video.mp4)")
    parser.add_argument("--composition", default="MyComposition", help="Composition ID (default: MyComposition)")
    parser.add_argument("--codec", default="h264", choices=["h264", "h265", "vp8", "vp9", "prores", "gif"], help="Video codec")
    parser.add_argument("--quality", type=int, default=80, help="Quality 0-100 (default: 80)")
    parser.add_argument("--frames", default=None, help="Render specific frames, e.g. '0' or '0-30'")
    parser.add_argument("--concurrency", type=int, default=4, help="Parallel rendering threads (default: 4)")
    parser.add_argument("--skip-deps-check", action="store_true", help="Skip Node.js/ffmpeg check")
    args = parser.parse_args()

    if not args.skip_deps_check:
        check_deps()

    if not os.path.exists(args.project):
        print(f"ERROR: Project directory not found: {args.project}", file=sys.stderr)
        sys.exit(1)

    install_deps(args.project)
    render(
        project_dir=args.project,
        out=args.out,
        composition=args.composition,
        codec=args.codec,
        quality=args.quality,
        frames=args.frames,
        concurrency=args.concurrency,
    )


if __name__ == "__main__":
    main()