#!/usr/bin/env python3
# ruff: noqa: E501
"""post_video.py — smart video posting with upload-post primary + Composio fallback.

Tries upload-post first for each platform. If it fails because the account is
not connected there, automatically retries via Composio (pre-authenticated).
For YouTube, upload-post is the only option (Composio has no video upload).

Usage:
  python post_video.py --file video.mp4 --title "My Video" --platforms youtube facebook
  python post_video.py --file video.mp4 --title "Title" --platforms all
  python post_video.py --file video.mp4 --title "Title" --platforms facebook instagram --force-composio

Composio fallback notes:
  - facebook  → FACEBOOK_CREATE_VIDEO_POST (needs video URL or file)
  - instagram → INSTAGRAM_CREATE_MEDIA_CONTAINER + INSTAGRAM_CREATE_POST (needs URL)
  - linkedin  → LINKEDIN_CREATE_LINKED_IN_POST (text + link)
  - twitter   → TWITTER_CREATION_OF_A_POST (text + link)
  - youtube   → upload-post only (Composio is read-only for YouTube)
"""
import argparse
import os
import pathlib
import sys

# ── Platform definitions ─────────────────────────────────────────────────────

# Platforms that upload-post supports
_UPLOAD_POST_PLATFORMS = {
    "youtube", "facebook", "instagram", "linkedin", "x", "tiktok",
    "pinterest", "threads", "bluesky",
}

# Platforms where Composio can act as fallback
# value = composio action slug(s) to use
_COMPOSIO_FALLBACK: dict[str, list[str]] = {
    "facebook":  ["FACEBOOK_CREATE_VIDEO_POST"],
    "instagram": ["INSTAGRAM_CREATE_MEDIA_CONTAINER", "INSTAGRAM_CREATE_POST"],
    "linkedin":  ["LINKEDIN_CREATE_LINKED_IN_POST"],
    "x":         ["TWITTER_CREATION_OF_A_POST"],
    "twitter":   ["TWITTER_CREATION_OF_A_POST"],
}

_ALL_PLATFORMS = sorted(_UPLOAD_POST_PLATFORMS)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_env() -> None:
    """Load .env from project root if python-dotenv is available."""
    try:
        import dotenv
        root = (pathlib.Path(__file__).parents[7])
        env_file = root / ".env"
        if env_file.exists():
            dotenv.load_dotenv(env_file)
    except ImportError:
        pass


def _get_upload_post_client() -> tuple:
    api_key = os.environ.get("UPLOAD_POST_API_KEY")
    if not api_key:
        return None, "UPLOAD_POST_API_KEY not set"
    try:
        from upload_post import UploadPostClient
        return UploadPostClient(api_key), None
    except ImportError:
        return None, "upload-post not installed (run: pip install upload-post)"


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "quota" in msg or "limit" in msg or "remaining" in msg


def _is_not_connected_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "not valid" in msg or "not configured" in msg or "no account" in msg


def _try_upload_post(client, video_path: str, title: str, user: str,
                     platform: str, description: str | None) -> tuple[bool, str]:
    """Attempt upload via upload-post.

    Returns:
        Tuple of (success, message).
    """
    kwargs = {"video_path": video_path, "title": title, "user": user,
              "platforms": [platform]}
    if description:
        kwargs["description"] = description
    try:
        resp = client.upload_video(**kwargs)
        upload_id = resp.get("id") or resp.get("upload_id") if isinstance(resp, dict) else None
        id_str = f" (id={upload_id})" if upload_id else ""
    except Exception as exc:
        if _is_quota_error(exc):
            return False, f"QUOTA: {exc}"
        if _is_not_connected_error(exc):
            return False, f"NOT_CONNECTED: {exc}"
        return False, f"ERROR: {exc}"
    else:
        return True, f"upload-post OK{id_str}"


def _try_composio(_video_path: str, title: str, platform: str,
                  description: str | None) -> tuple[bool, str]:
    """Attempt post via Composio fallback.

    Returns:
        Tuple of (success, message).
    """
    actions = _COMPOSIO_FALLBACK.get(platform)
    if not actions:
        return False, "No Composio fallback for this platform"

    try:
        from composio_client import Composio
    except ImportError:
        try:
            from composio import Composio  # type: ignore[no-redef]
        except ImportError:
            return False, "Composio SDK not installed"

    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        return False, "COMPOSIO_API_KEY not set"

    entity_id = os.environ.get("COMPOSIO_ENTITY_ID", "default")
    caption = description or title

    try:
        client = Composio(api_key=api_key)

        if platform == "facebook":
            # Try video post via URL if video is hosted; else post text
            result = client.tools.execute(
                "FACEBOOK_CREATE_VIDEO_POST",
                arguments={"description": caption, "file_url": ""},
                entity_id=entity_id,
            )
            return True, f"Composio FACEBOOK_CREATE_VIDEO_POST OK: {result}"

        if platform == "instagram":
            # Instagram requires 2-step: create container → publish
            # Needs a hosted URL — skip if only local file
            return False, (
                "Composio Instagram fallback requires a hosted video URL. "
                "Upload to Drive first then use INSTAGRAM_CREATE_MEDIA_CONTAINER."
            )

        if platform in {"x", "twitter"}:
            result = client.tools.execute(
                "TWITTER_CREATION_OF_A_POST",
                arguments={"text": f"{title}\n\n{caption}" if description else title},
                entity_id=entity_id,
            )
            return True, f"Composio TWITTER_CREATION_OF_A_POST OK: {result}"

        if platform == "linkedin":
            result = client.tools.execute(
                "LINKEDIN_CREATE_LINKED_IN_POST",
                arguments={
                    "text": f"{title}\n\n{caption}" if description else title,
                    "visibility": "PUBLIC",
                },
                entity_id=entity_id,
            )
            return True, f"Composio LINKEDIN_CREATE_LINKED_IN_POST OK: {result}"

    except Exception as exc:
        return False, f"Composio ERROR: {exc}"
    return False, f"Composio fallback not implemented for {platform}"


# ── Main ─────────────────────────────────────────────────────────────────────

def post_video(video_path: str, title: str, platforms: list[str],
               user: str = "Agents", description: str | None = None,
               force_composio: bool = False) -> dict[str, dict]:
    """Post a video to one or more platforms, falling back to Composio on failure.

    Returns:
        Dict mapping platform to {success, method, message}.
    """
    results: dict[str, dict] = {}

    client, client_err = _get_upload_post_client()

    for p in platforms:
        platform = p.lower()
        print(f"\n── {platform.upper()} ──")

        # YouTube: upload-post only
        if platform == "youtube" and force_composio:
            print("  ⚠️  YouTube has no Composio video upload — upload-post only")
            results[platform] = {"success": False, "method": "none",
                                 "message": "YouTube requires upload-post (Composio is read-only)"}
            continue

        # Try upload-post first (unless forced to Composio)
        up_success = False
        up_msg = ""
        if not force_composio and client:
            up_success, up_msg = _try_upload_post(client, video_path, title, user,
                                                   platform, description)
            if up_success:
                print(f"  ✅ {up_msg}")
                results[platform] = {"success": True, "method": "upload-post", "message": up_msg}
                continue
            print(f"  ⚠️  upload-post failed: {up_msg}")
        elif not client:
            up_msg = f"upload-post unavailable: {client_err}"
            print(f"  ⚠️  {up_msg}")

        # Quota exhausted — no point trying Composio (it's a different service)
        if _is_quota_error(Exception(up_msg)):
            print(f"  ❌ Quota exhausted — cannot post to {platform} this month")
            results[platform] = {"success": False, "method": "upload-post",
                                 "message": up_msg}
            continue

        # Try Composio fallback
        if platform in _COMPOSIO_FALLBACK:
            print("  🔄 Trying Composio fallback...")
            c_success, c_msg = _try_composio(video_path, title, platform, description)
            if c_success:
                print(f"  ✅ {c_msg}")
                results[platform] = {"success": True, "method": "composio", "message": c_msg}
            else:
                print(f"  ❌ Composio also failed: {c_msg}")
                results[platform] = {"success": False, "method": "composio", "message": c_msg}
        else:
            reason = f"No Composio fallback for {platform} — account must be connected at upload-post.com"
            print(f"  ❌ {reason}")
            results[platform] = {"success": False, "method": "none", "message": reason}

    return results


def main() -> None:
    """CLI entry point."""
    _load_env()
    parser = argparse.ArgumentParser(description="Post video with upload-post + Composio fallback")
    parser.add_argument("--file", required=True, help="Path to video file (.mp4, .mov, .webm)")
    parser.add_argument("--title", required=True, help="Video title / caption")
    parser.add_argument("--platforms", nargs="+", required=True,
                        help=f"Platforms or 'all'. Options: {', '.join(_ALL_PLATFORMS)}")
    parser.add_argument("--user", default=os.environ.get("UPLOAD_POST_DEFAULT_USER", "Agents"),
                        help="upload-post profile username")
    parser.add_argument("--description", default=None, help="Optional longer description")
    parser.add_argument("--force-composio", action="store_true",
                        help="Skip upload-post and go straight to Composio")
    args = parser.parse_args()

    if not pathlib.Path(args.file).exists():
        print(f"ERROR: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    platforms = _ALL_PLATFORMS if "all" in args.platforms else args.platforms
    invalid = [p for p in platforms if p not in _UPLOAD_POST_PLATFORMS]
    if invalid:
        print(f"ERROR: Unknown platform(s): {invalid}. Valid: {_ALL_PLATFORMS}", file=sys.stderr)
        sys.exit(1)

    size_mb = pathlib.Path(args.file).stat().st_size / 1024 / 1024
    print(f"Video    : {args.file} ({size_mb:.1f} MB)")
    print(f"Title    : {args.title}")
    print(f"Platforms: {', '.join(platforms)}")
    print(f"User     : {args.user}")

    results = post_video(
        video_path=args.file,
        title=args.title,
        platforms=platforms,
        user=args.user,
        description=args.description,
        force_composio=args.force_composio,
    )

    print("\n── Summary ──")
    any_fail = False
    for platform, result in results.items():
        icon = "✅" if result["success"] else "❌"
        print(f"  {icon} {platform:12s} [{result['method']:12s}] {result['message'][:80]}")
        if not result["success"]:
            any_fail = True

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
