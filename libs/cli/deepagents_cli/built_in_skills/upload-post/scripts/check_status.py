#!/usr/bin/env python3
"""
check_status.py — check upload status or view history via upload-post.

Usage:
  python check_status.py --id <upload_id>
  python check_status.py --history
  python check_status.py --cancel <upload_id>
"""
import argparse
import json
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
    parser = argparse.ArgumentParser(description="Check upload status or history")
    parser.add_argument("--id", default=None, help="Upload ID to check status")
    parser.add_argument("--history", action="store_true", help="Show upload history")
    parser.add_argument("--cancel", default=None, help="Cancel a scheduled upload by ID")
    parser.add_argument("--limit", type=int, default=20, help="History limit (default: 20)")
    args = parser.parse_args()

    if not any([args.id, args.history, args.cancel]):
        print("ERROR: Provide --id, --history, or --cancel", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    client = get_client()

    if args.cancel:
        try:
            response = client.cancel_post(upload_id=args.cancel)
            print(f"Cancelled upload {args.cancel}")
            print(f"Response: {response}")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.id:
        try:
            status = client.get_upload_status(args.id)
            print(f"Status for {args.id}:")
            print(json.dumps(status, indent=2) if isinstance(status, dict) else status)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.history:
        try:
            history = client.get_upload_history()
            if isinstance(history, list):
                items = history[:args.limit]
                print(f"Upload history (last {len(items)}):")
                for item in items:
                    if isinstance(item, dict):
                        uid = item.get("id", "?")
                        title = item.get("title", "?")
                        status = item.get("status", "?")
                        platforms = item.get("platforms", [])
                        print(f"  [{uid}] {title} — {status} — {', '.join(platforms) if isinstance(platforms, list) else platforms}")
                    else:
                        print(f"  {item}")
            else:
                print(json.dumps(history, indent=2) if isinstance(history, dict) else history)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()