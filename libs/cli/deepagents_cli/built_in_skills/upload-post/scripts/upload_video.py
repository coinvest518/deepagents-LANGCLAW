#!/usr/bin/env python3
"""
upload_video.py — upload a video to social media platforms via upload-post.

Usage:
  python upload_video.py --file video.mp4 --title "My Video" --platforms tiktok instagram
  python upload_video.py --file clip.mp4 --title "Clip" --platforms youtube --user Agents
  python upload_video.py --file video.mp4 --title "Sched" --platforms tiktok --schedule "2026-03-25T18:00:00"
"""
import argparse
import os
import sys


def get_client():
    api_key = os.environ.get("UPLOAD_POST_API_KEY")
    if not api_key:
        print("ERROR: UPLOAD_POST_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)
    try:
        from upload_post import UploadPostClient
    except ImportError:
        print("ERROR: upload-post not installed. Run: pip install upload-post", file=sys.stderr)
        sys.exit(1)
    return UploadPostClient(api_key)


def main():
    parser = argparse.ArgumentParser(description="Upload a video to social platforms")
    parser.add_argument("--file", required=True, help="Path to video file (.mp4, .mov, .webm)")
    parser.add_argument("--title", required=True, help="Video title / caption")
    parser.add_argument("--platforms", nargs="+", required=True,
                        choices=["tiktok", "instagram", "youtube", "linkedin", "facebook",
                                 "pinterest", "threads", "x", "bluesky"],
                        help="Target platforms")
    parser.add_argument("--user", default=os.environ.get("UPLOAD_POST_DEFAULT_USER", "Agents"),
                        help="Profile username (default: Agents)")
    parser.add_argument("--schedule", default=None,
                        help="Schedule date/time ISO 8601, e.g. 2026-03-25T18:00:00")
    parser.add_argument("--timezone", default=None,
                        help="Timezone for schedule, e.g. America/New_York")
    parser.add_argument("--description", default=None, help="Optional longer description")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    size_mb = os.path.getsize(args.file) / 1024 / 1024
    print(f"Uploading: {args.file} ({size_mb:.1f} MB)")
    print(f"Title    : {args.title}")
    print(f"Platforms: {', '.join(args.platforms)}")
    print(f"User     : {args.user}")
    if args.schedule:
        print(f"Scheduled: {args.schedule}" + (f" ({args.timezone})" if args.timezone else ""))
    print()

    client = get_client()

    kwargs = {
        "video_path": args.file,
        "title": args.title,
        "user": args.user,
        "platforms": args.platforms,
    }
    if args.description:
        kwargs["description"] = args.description
    if args.schedule:
        kwargs["schedule_date"] = args.schedule
    if args.timezone:
        kwargs["tz"] = args.timezone

    try:
        response = client.upload_video(**kwargs)
        print("Upload successful!")
        print(f"Response: {response}")

        # Extract upload ID if present
        if isinstance(response, dict):
            upload_id = response.get("id") or response.get("upload_id")
            if upload_id:
                print(f"\nUpload ID: {upload_id}")
                print(f"Check status: python check_status.py --id {upload_id}")
    except Exception as e:
        print(f"ERROR: Upload failed — {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()