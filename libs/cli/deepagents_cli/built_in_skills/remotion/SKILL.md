---
name: remotion
description: >
  Create and render videos programmatically using React + Remotion. Generates
  MP4/WebM videos from code — animations, data visualizations, social media
  clips, explainer videos, slideshows. Use this skill when the user says "make
  a video", "create an animated clip", "render a video", "make a TikTok video",
  "animate this data", or "generate a short clip". Requires Node.js + ffmpeg
  installed. Pairs with upload-post skill to publish to social media.
license: MIT
compatibility: deepagents-cli
---

# Remotion Skill

Creates videos programmatically using React components. Every frame is a
React component — use CSS animations, SVG, Canvas, or WebGL.

## Requirements

```bash
# Check Node.js (must be 16+)
node --version

# Install ffmpeg (required for video encoding)
# Windows: winget install ffmpeg  OR  choco install ffmpeg
# Mac: brew install ffmpeg
# Linux: apt install ffmpeg

# Install Remotion in a project directory
npm install remotion @remotion/cli @remotion/renderer
```

## Quick Start — Render a Video

```bash
# Create a new Remotion project first
python scripts/create_project.py --title "My Video" --duration 5 --fps 30

# Then render it
python scripts/render_video.py --project ./remotion-project --out video.mp4
```

## Commands

### Create a new video project
```bash
python scripts/create_project.py --title "Video Title" --duration 10 --fps 30 --width 1920 --height 1080
python scripts/create_project.py --title "TikTok Clip" --duration 15 --fps 30 --width 1080 --height 1920 --template tiktok
```

### Render the video to MP4
```bash
python scripts/render_video.py --project ./remotion-project --out output.mp4
python scripts/render_video.py --project ./remotion-project --out clip.mp4 --codec h264 --quality 80
```

### Render specific frames (for preview)
```bash
python scripts/render_video.py --project ./remotion-project --out frame.png --frames 0
```

### List available templates
```bash
python scripts/create_project.py --list-templates
```

## Video Templates

| Template | Dimensions | Use case |
|----------|-----------|----------|
| `default` | 1920×1080 | General landscape video |
| `tiktok` | 1080×1920 | TikTok / Instagram Reels (9:16) |
| `square` | 1080×1080 | Instagram posts |
| `youtube` | 1920×1080 | YouTube videos |
| `twitter` | 1280×720 | Twitter/X videos |
| `slideshow` | 1920×1080 | Text/image slides |

## How It Works

```
React components (JSX/TSX)
    ↓
Remotion Studio (localhost:3000) — live preview
    ↓
npx remotion render → ffmpeg encodes frames
    ↓
output.mp4 (H.264)
    ↓
upload-post skill → publish to TikTok/Instagram/YouTube
```

## Agent Workflow Example

User: "Make a 15-second TikTok video showing crypto price data"

1. Create project: `python scripts/create_project.py --title "ETH Price" --duration 15 --fps 30 --template tiktok`
2. Edit `remotion-project/src/Composition.tsx` to show the data
3. Render: `python scripts/render_video.py --project ./remotion-project --out eth_price.mp4`
4. Post: use `upload-post` skill to publish

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `REMOTION_PROJECT_DIR` | Default output dir for projects (optional, defaults to `./remotion-projects`) |

## Tips

- Remotion renders every frame independently — it's deterministic and fast
- Use `spring()` for smooth animations: `import { spring, useCurrentFrame } from 'remotion'`
- `useCurrentFrame()` returns the current frame number (0-based)
- `interpolate(frame, [0, 30], [0, 1])` maps frame range to value range
- Commercial use requires a Remotion license — check remotion.dev/license
- After rendering, use the `upload-post` skill to publish to social platforms