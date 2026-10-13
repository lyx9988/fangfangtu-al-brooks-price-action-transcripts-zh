#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

sys.dont_write_bytecode = True
from transcript_paths import DISPLAY_TITLES


ROOT = Path(__file__).resolve().parent.parent
INDEX_JSON = ROOT / "metadata/index.json"
INDEX_CSV = ROOT / "metadata/index.csv"
CATALOG = ROOT / "学习目录.md"
FIELDS = [
    "platform",
    "author",
    "video_id",
    "title",
    "category",
    "learning_order",
    "duration_seconds",
    "status",
    "transcript_format",
    "transcription_source",
    "source_url",
    "transcript_path",
    "proofread_status",
    "proofread_at",
    "notes",
]
CHAPTER_DESCRIPTIONS = {
    "01 入门必看": "从学习方法和市场基础开始，再学习目标位、市场周期、止损、仓位与订单。",
    "02 读图基础、信号与复盘": "理解概率、回调与数 K 线，再进入信号 K、订单、蜡烛图和复盘。",
    "03 市场结构、突破与反转": "系统学习突破、市场周期、楔形、缺口等常见结构。",
    "04 交易管理、早盘与市场策略": "围绕止损、早盘判断、风险控制、订单和交易管理展开。",
    "05 心理、职业与长期纪律": "讨论交易心理、职业路径、一致性和长期纪律。",
    "06 实盘与复盘案例": "完成基础章节后，通过实盘讲解和历史复盘训练识别与执行。",
    "07 期权与补充资料": "期权及频道补充内容，可在主线完成后按需选学。",
}
HISTORY_START_VIDEO_ID = "pfR1t11tj2w"


def category_number(category: str) -> int:
    prefix = category.split(" ", 1)[0]
    return int(prefix) if prefix.isdigit() else 999


def duration_label(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def total_duration_label(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours} 小时 {minutes} 分钟" if hours else f"{minutes} 分钟"


def escape_markdown(text: str) -> str:
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def render(records: list[dict[str, object]]) -> str:
    completed = [row for row in records if row["status"] == "completed"]
    unavailable = [row for row in records if row["status"] == "unavailable"]
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in completed:
        grouped[str(row["category"])].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: int(row["learning_order"]))

    history_start = next(
        int(row["learning_order"])
        for row in grouped["06 实盘与复盘案例"]
        if row["video_id"] == HISTORY_START_VIDEO_ID
    )
    lines = [
        "# 方方土价格行为学学习目录｜Al Brooks Price Action",
        "",
        f"这里按主题和难度整理方方土 PriceAction 等公开来源中与 Al Brooks 价格行为学相关的视频，共 {len(records)} 条记录：{len(completed)} 条有完整、带时间码并已校对的中文转录稿，{len(unavailable)} 条目前无法公开访问。每个视频只保留一份规范转录稿。",
        "",
        "建议先完成 01～05，再进入 06 的实盘与复盘；07 是补充内容。目录中的勾选框可用于记录学习进度。",
        "",
        "[返回仓库首页](README.md) · [CSV 视频索引](metadata/index.csv) · [JSON 视频索引](metadata/index.json)",
        "",
        "## 章节概览",
        "",
        "| 章节 | 数量 | 合计时长 |",
        "|---|---:|---:|",
    ]
    for category in sorted(grouped, key=category_number):
        rows = grouped[category]
        total = sum(int(row["duration_seconds"]) for row in rows)
        anchor = category.replace(" ", "-").replace("、", "")
        lines.append(f"| [{category}](#{anchor}) | {len(rows)} | {total_duration_label(total)} |")

    for category in sorted(grouped, key=category_number):
        rows = grouped[category]
        total = sum(int(row["duration_seconds"]) for row in rows)
        lines.extend(
            [
                "",
                f"## {category}",
                "",
                CHAPTER_DESCRIPTIONS[category],
                "",
                f"共 {len(rows)} 条，合计约 {total_duration_label(total)}。",
                "",
            ]
        )
        for row in rows:
            order = int(row["learning_order"])
            if category == "06 实盘与复盘案例" and order == 1:
                lines.extend([f"### 近期实盘与边做边讲（01～{history_start - 1:02d}）", ""])
            if category == "06 实盘与复盘案例" and order == history_start:
                lines.extend(["", f"### 历史实盘与复盘（{history_start:02d}～{len(rows):02d}）", ""])
            title = escape_markdown(DISPLAY_TITLES.get(str(row["video_id"]), str(row["title"])))
            lines.append(
                f"- [ ] **{order:02d}** [{title}]({quote(str(row['transcript_path']), safe='/')}) · "
                f"[原视频]({row['source_url']}) · {row['platform']} · "
                f"{duration_label(int(row['duration_seconds']))}"
            )

    lines.extend(["", "## 无法公开访问的记录", ""])
    for row in unavailable:
        title = escape_markdown(str(row["title"]))
        lines.append(
            f"- [{title}]({row['source_url']}) · {row['platform']} · "
            f"未收录转录稿：{row['notes']}"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "本目录用于安排学习顺序，不代表收益承诺或交易建议。交易有风险，请独立判断并控制风险。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成规范化索引和学习目录")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查生成结果是否与当前文件一致，不写入文件",
    )
    args = parser.parse_args()
    records = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    records.sort(
        key=lambda row: (
            row["status"] != "completed",
            category_number(str(row["category"])),
            int(row["learning_order"] or 999),
            str(row["video_id"]),
        )
    )
    json_text = json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    csv_text = csv_buffer.getvalue()
    catalog_text = render(records)

    if args.check:
        stale = [
            path.name
            for path, expected in (
                (INDEX_JSON, json_text),
                (INDEX_CSV, csv_text),
                (CATALOG, catalog_text),
            )
            if not path.is_file() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            raise SystemExit(f"生成文件需要更新：{', '.join(stale)}")
        completed_count = sum(row["status"] == "completed" for row in records)
        print(f"catalog current records={len(records)} completed={completed_count}")
        return

    INDEX_JSON.write_text(json_text, encoding="utf-8")
    INDEX_CSV.write_text(csv_text, encoding="utf-8")
    CATALOG.write_text(catalog_text, encoding="utf-8")
    print(
        f"rendered records={len(records)} completed="
        f"{sum(row['status'] == 'completed' for row in records)}"
    )


if __name__ == "__main__":
    main()
