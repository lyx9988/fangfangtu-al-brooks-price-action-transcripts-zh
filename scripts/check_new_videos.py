#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "metadata/index.json"
SOURCES_PATH = ROOT / "metadata/sources.json"
PLAYLIST_LIMIT = 50


def extractor_command() -> list[str]:
    if shutil.which("uvx"):
        return ["uvx", "--refresh", "yt-dlp"]
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    raise RuntimeError("未找到 uvx 或 yt-dlp")


def normalized_url(platform: str, video_id: str, raw_url: object) -> str:
    value = str(raw_url or "")
    if value.startswith("https://"):
        return value
    if platform == "YouTube":
        return f"https://www.youtube.com/watch?v={video_id}"
    if platform == "Bilibili":
        return f"https://www.bilibili.com/video/{video_id}"
    return value


def short_error(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return (lines[-1] if lines else "未知错误")[:500]


def inspect_source(
    source: dict[str, str], known: set[tuple[str, str]], command: list[str]
) -> dict[str, Any]:
    platform = source["platform"]
    args = command + [
        "--flat-playlist",
        "--playlist-end",
        str(PLAYLIST_LIMIT),
        "--dump-single-json",
        "--no-warnings",
        source["listing_url"],
    ]
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "platform": platform,
            "status": "error",
            "checked": 0,
            "new": [],
            "error": "公开清单请求超过 180 秒",
        }
    if result.returncode != 0:
        return {
            "platform": platform,
            "status": "error",
            "checked": 0,
            "new": [],
            "error": short_error(result.stderr),
        }
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "platform": platform,
            "status": "error",
            "checked": 0,
            "new": [],
            "error": f"公开清单不是有效 JSON：{exc}",
        }

    entries = data.get("entries") or []
    missing: list[dict[str, object]] = []
    for entry in entries:
        video_id = str(entry.get("id") or "")
        if not video_id or (platform, video_id) in known:
            continue
        missing.append(
            {
                "video_id": video_id,
                "title": str(entry.get("title") or ""),
                "duration_seconds": int(float(entry.get("duration") or 0)),
                "source_url": normalized_url(platform, video_id, entry.get("url")),
            }
        )
    return {
        "platform": platform,
        "status": "ok",
        "checked": len(entries),
        "new": missing,
        "error": "",
    }


def main() -> int:
    records = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    known = {(str(row["platform"]), str(row["video_id"])) for row in records}
    try:
        command = extractor_command()
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    results = [inspect_source(source, known, command) for source in sources]
    output = {
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "known_records": len(records),
        "playlist_limit": PLAYLIST_LIMIT,
        "new_total": sum(len(result["new"]) for result in results),
        "source_errors": sum(result["status"] == "error" for result in results),
        "sources": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if results and all(result["status"] == "error" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
