---
name: upload-post
description: >
  Publish videos, photos, and text posts to social media platforms — TikTok,
  Instagram, YouTube, LinkedIn, Facebook, Pinterest, Threads, X (Twitter),
  Reddit, Bluesky. Use this skill when the user says "post this video", "share
  to TikTok", "upload to Instagram", "publish on YouTube", "schedule a post",
  "post to social media", or "share this clip". Requires UPLOAD_POST_API_KEY
  in env. Default profile user is "Agents" (UPLOAD_POST_DEFAULT_USER).
license: MIT
compatibility: deepagents-cli
---

# Upload-Post Skill

Publishes content to 10+ social platforms with one API call.
Supports videos, photos, text posts, and documents.
Pairs with the `remotion` skill for full video-creation-to-publication workflow.

## Install

```bash
pip install upload-post
```

## Commands

### Upload a video
```bash
python scripts/upload_video.py --file video.mp4 --title "My Video" --platforms tiktok instagram
python scripts/upload_video.py --file video.mp4 --title "ETH Update" --platforms youtube --user Agents
python scripts/upload_video.py --file clip.mp4 --title "Clip" --platforms tiktok instagram youtube --schedule "2026-03-25T14:30:00"
```

### Upload photos
```bash
python scripts/upload_media.py --type photos --files photo1.jpg photo2.jpg --platforms instagram facebook
```

### Post text
```bash
python scripts/upload_media.py --type text --text "Hello world! 🚀" --platforms x linkedin threads
```

### Check post status
```bash
python scripts/check_status.py --id <upload_id>
```

### View upload history
```bash
python scripts/check_status.py --history
```

### Cancel a scheduled post
```bash
python scripts/check_status.py --cancel <upload_id>
```

## Supported Platforms

| Platform | Video | Photo | Text |
|----------|-------|-------|------|
| `tiktok` | ✅ | ✅ | ❌ |
| `instagram` | ✅ | ✅ | ❌ |
| `youtube` | ✅ | ❌ | ❌ |
| `linkedin` | ✅ | ✅ | ✅ |
| `facebook` | ✅ | ✅ | ✅ |
| `pinterest` | ✅ | ✅ | ❌ |
| `threads` | ✅ | ✅ | ✅ |
| `x` | ✅ | ✅ | ✅ |
| `reddit` | ❌ | ✅ | ✅ |
| `bluesky` | ✅ | ✅ | ✅ |

## Full Workflow with Remotion

```bash
# 1. Create video
python ../remotion/scripts/create_project.py --title "ETH Price Today" --duration 15 --template tiktok

# 2. Edit src/Composition.tsx with your content, then render
python ../remotion/scripts/render_video.py --project ./remotion-projects/eth-price-today --out eth.mp4

# 3. Publish
python scripts/upload_video.py --file eth.mp4 --title "ETH Price Today" --platforms tiktok instagram
```

## Scheduling

Pass ISO 8601 date string for scheduled publishing:
```bash
python scripts/upload_video.py --file video.mp4 --title "Title" \
  --platforms tiktok instagram \
  --schedule "2026-03-25T18:00:00" \
  --timezone "America/New_York"
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `UPLOAD_POST_API_KEY` | upload-post API key (required) |
| `UPLOAD_POST_DEFAULT_USER` | Default profile username (default: `Agents`) |

Both are already configured in `.env`.

## Tips

- Profiles must be connected at upload-post.com before uploading
- For TikTok the video must be ≤ 10 min; for YouTube Shorts ≤ 60 sec
- Schedule posts up to 30 days in advance
- Use `--history` to see all past uploads and their status