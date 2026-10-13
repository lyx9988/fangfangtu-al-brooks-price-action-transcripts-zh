"""Shared, deterministic naming for canonical transcript files."""

from __future__ import annotations

import re

TRANSCRIPT_ROOT = "转录稿"
SOURCE_DIRECTORIES = {"YouTube": "YouTube-方方土", "Bilibili": "Bilibili-z说交易"}
DISPLAY_TITLES = {"nFKiwGHqpsA": "踏上交易之路(8)：避免巨亏的入场规则"}
_UNSAFE = str.maketrans({'/': '／', '\\': '＼', ':': '：', '*': '＊', '?': '？', '"': '＂', '<': '＜', '>': '＞', '|': '｜'})


def readable_title(title: str) -> str:
    title = re.sub(r"^【价格行为学】\s*", "", title.strip())
    title = re.sub(r"\s+", " ", title.translate(_UNSAFE)).strip(" .")
    title = re.sub(r"：\s+", "：", title)
    if len(title.encode("utf-8")) > 190:
        title = title.encode("utf-8")[:187].decode("utf-8", errors="ignore").rstrip() + "…"
    return title


def canonical_transcript_path(record: dict[str, object]) -> str:
    if record.get("status") != "completed":
        return ""
    directory = SOURCE_DIRECTORIES[str(record["platform"])]
    category_number = int(str(record["category"]).split(" ", 1)[0])
    order = int(record["learning_order"])
    title = DISPLAY_TITLES.get(str(record['video_id']), str(record['title']))
    filename = f"{category_number:02d}-{order:03d} {readable_title(title)} [{record['video_id']}].md"
    return f"{TRANSCRIPT_ROOT}/{directory}/{filename}"
