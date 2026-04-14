import re
import logging
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from shared import config

logger = logging.getLogger(__name__)


def _client():
    return build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)


def parse_iso8601_duration(duration: str) -> int:
    """Convert ISO 8601 duration string (e.g. PT4M13S) to total seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match:
        return 0
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 3600 + m * 60 + s


def resolve_channel(url_or_id: str) -> Optional[dict]:
    """
    Accept a YouTube channel URL, @handle, or channel ID (UC...).
    Returns {"youtube_channel_id", "display_name", "thumbnail_url"} or None.
    """
    yt = _client()
    channel_id: Optional[str] = None

    try:
        # Direct channel ID: starts with UC and is ~24 chars
        if re.match(r"^UC[\w-]{20,}$", url_or_id.strip()):
            channel_id = url_or_id.strip()

        # URL containing /channel/UC...
        elif "/channel/" in url_or_id:
            m = re.search(r"/channel/(UC[\w-]+)", url_or_id)
            if m:
                channel_id = m.group(1)

        # @handle or URL containing /@handle
        elif "@" in url_or_id:
            m = re.search(r"@([\w.-]+)", url_or_id)
            if m:
                handle = "@" + m.group(1)
                resp = yt.channels().list(part="snippet", forHandle=handle).execute()
                return _extract_channel(resp)

        # Legacy /c/ or /user/ custom URL — try forUsername
        else:
            username = url_or_id.rstrip("/").split("/")[-1]
            resp = yt.channels().list(part="snippet", forUsername=username).execute()
            return _extract_channel(resp)

        if channel_id:
            resp = yt.channels().list(part="snippet", id=channel_id).execute()
            return _extract_channel(resp)

    except HttpError as exc:
        logger.error("YouTube API error resolving channel '%s': %s", url_or_id, exc)

    return None


def _extract_channel(api_response: dict) -> Optional[dict]:
    items = api_response.get("items", [])
    if not items:
        return None
    item = items[0]
    snippet = item["snippet"]
    thumb = (
        snippet.get("thumbnails", {}).get("default", {}).get("url")
        or snippet.get("thumbnails", {}).get("medium", {}).get("url")
    )
    return {
        "youtube_channel_id": item["id"],
        "display_name": snippet["title"],
        "thumbnail_url": thumb,
    }


def fetch_channel_videos(youtube_channel_id: str, max_results: int = 50) -> list[dict]:
    """
    Return up to max_results recent videos for a channel.
    Each dict: {youtube_video_id, title, thumbnail_url, published_at, duration_seconds}
    """
    yt = _client()
    try:
        # Step 1: uploads playlist ID
        ch = yt.channels().list(part="contentDetails", id=youtube_channel_id).execute()
        if not ch.get("items"):
            return []
        uploads_id = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Step 2: recent playlist items
        pl = (
            yt.playlistItems()
            .list(part="snippet", playlistId=uploads_id, maxResults=min(max_results, 50))
            .execute()
        )
        items = pl.get("items", [])
        video_ids = [i["snippet"]["resourceId"]["videoId"] for i in items]
        if not video_ids:
            return []

        # Step 3: duration + enriched snippet
        vd = (
            yt.videos()
            .list(part="contentDetails,snippet", id=",".join(video_ids))
            .execute()
        )

        results = []
        for item in vd.get("items", []):
            snippet = item["snippet"]
            duration = parse_iso8601_duration(
                item.get("contentDetails", {}).get("duration", "")
            )
            thumbnails = snippet.get("thumbnails", {})
            thumb = (
                thumbnails.get("medium", {}).get("url")
                or thumbnails.get("default", {}).get("url")
            )
            results.append(
                {
                    "youtube_video_id": item["id"],
                    "title": snippet["title"],
                    "thumbnail_url": thumb,
                    "published_at": snippet.get("publishedAt"),
                    "duration_seconds": duration,
                    "live_broadcast_content": snippet.get("liveBroadcastContent", "none"),
                }
            )
        return results

    except HttpError as exc:
        logger.error(
            "YouTube API error fetching videos for channel %s: %s",
            youtube_channel_id,
            exc,
        )
        return []
