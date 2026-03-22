#!/usr/bin/env python3
"""
upload_media.py — upload photos or post text to social platforms via upload-post.

Usage:
  python upload_media.py --type photos --files photo1.jpg photo2.jpg --platforms instagram facebook
  python upload_media.py --type text --text "Hello world!" --platforms x linkedin threads
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
    parser = argparse.ArgumentParser(description="Upload photos or text to social platforms")
    parser.add_argument("--type", required=True, choices=["photos", "text"], help="Content type")
    parser.add_argument("--files", nargs="+", help="Photo file paths (for --type photos)")
    parser.add_argument("--text", help="Post text content (for --type text)")
    parser.add_argument("--platforms", nargs="+", required=True,
                        choices=["tiktok", "instagram", "youtube", "linkedin", "facebook",
                                 "pinterest", "threads", "x", "reddit", "bluesky"],
                        help="Target platforms")
    parser.add_argument("--user", default=os.environ.get("UPLOAD_POST_DEFAULT_USER", "Agents"),
                        help="Profile username (default: Agents)")
    parser.add_argument("--title", default=None, help="Optional title/caption")
    parser.add_argument("--schedule", default=None, help="Schedule ISO 8601 e.g. 2026-03-25T18:00:00")
    parser.add_argument("--timezone", default=None, help="Timezone for schedule")
    args = parser.parse_args()

    client = get_client()

    if args.type == "photos":
        if not args.files:
            print("ERROR: --files required for --type photos", file=sys.stderr)
            sys.exit(1)
        for f in args.files:
            if not os.path.exists(f):
                print(f"ERROR: File not found: {f}", file=sys.stderr)
                sys.exit(1)
        print(f"Uploading {len(args.files)} photo(s) to: {', '.join(args.platforms)}")
        kwargs = {
            "file_paths": args.files,
            "user": args.user,
            "platforms": args.platforms,
        }
        if args.title:
            kwargs["title"] = args.title
        if args.schedule:
            kwargs["schedule_date"] = args.schedule
        if args.timezone:
            kwargs["tz"] = args.timezone
        try:
            response = client.upload_photos(**kwargs)
            print(f"Upload successful! Response: {response}")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.type == "text":
        if not args.text:
            print("ERROR: --text required for --type text", file=sys.stderr)
            sys.exit(1)
        print(f"Posting text to: {', '.join(args.platforms)}")
        print(f"Content: {args.text[:80]}{'...' if len(args.text) > 80 else ''}")
        kwargs = {
            "text": args.text,
            "platforms": args.platforms,
        }
        if args.schedule:
            kwargs["schedule_date"] = args.schedule
        if args.timezone:
            kwargs["tz"] = args.timezone
        try:
            response = client.upload_text(**kwargs)
            print(f"Post successful! Response: {response}")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()