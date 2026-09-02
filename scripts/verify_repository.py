#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent.parent
METADATA_JSON = ROOT / "metadata/index.json"
METADATA_CSV = ROOT / "metadata/index.csv"
LEARNING_CATALOG = ROOT / "学习目录.md"
EXPECTED_RECORDS = 161
EXPECTED_COMPLETED = 160
EXPECTED_UNAVAILABLE = 1
EXPECTED_PLATFORM_RECORDS = {"YouTube": 154, "Bilibili": 7}
EXPECTED_PLATFORM_TRANSCRIPTS = {"youtube": 153, "bilibili": 7}
EXPECTED_CATEGORIES = {
    "01 入门必看": 12,
    "02 读图基础、信号与复盘": 9,
    "03 市场结构、突破与反转": 17,
    "04 交易管理、早盘与市场策略": 20,
    "05 心理、职业与长期纪律": 6,
    "06 实盘与复盘案例": 92,
    "07 期权与补充资料": 4,
}
EXPECTED_FIELDS = [
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
MAX_FILE_SIZE = 1024 * 1024
TIMECODE_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]", re.MULTILINE)
LOCAL_LINK_RE = re.compile(r"\]\((<[^>]+>|[^)\s]+)\)")
CATALOG_TRANSCRIPT_LINK_RE = re.compile(
    r"\]\((transcripts/(?:youtube|bilibili)/[^)]+\.md)\)"
)
BANNED_SUFFIXES = {
    ".aac",
    ".avi",
    ".cache",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".part",
    ".temp",
    ".tmp",
    ".wav",
    ".webm",
}
BANNED_DIRECTORY_NAMES = {".cache", ".audio_transcription_cache", "__pycache__"}
BANNED_FILENAMES = {".DS_Store"}
RAW_METADATA_NAME_PARTS = {"api_response", "playlist.json", "response_dump"}


def repo_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(ROOT).parts
    )


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def seconds(parts: tuple[str, str, str]) -> int:
    hours, minutes, secs = map(int, parts)
    return hours * 3600 + minutes * 60 + secs


def expected_source_url(platform: str, video_id: str) -> str:
    if platform == "YouTube":
        return f"https://www.youtube.com/watch?v={video_id}"
    if platform == "Bilibili":
        return f"https://www.bilibili.com/video/{video_id}"
    return ""


def csv_value(value: object) -> str:
    return "" if value is None else str(value)


def read_metadata(errors: list[str]) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    if not METADATA_JSON.is_file():
        errors.append("缺少 metadata/index.json")
        return [], []
    if not METADATA_CSV.is_file():
        errors.append("缺少 metadata/index.csv")
        return [], []

    try:
        records = json.loads(METADATA_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        errors.append(f"metadata/index.json 无法读取：{exc}")
        return [], []
    if not isinstance(records, list):
        errors.append("metadata/index.json 顶层必须是数组")
        return [], []

    try:
        with METADATA_CSV.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            csv_records = list(reader)
            if reader.fieldnames != EXPECTED_FIELDS:
                errors.append(f"CSV 字段不正确：{reader.fieldnames}")
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        errors.append(f"metadata/index.csv 无法读取：{exc}")
        return records, []

    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"JSON 第 {index} 条记录不是对象")
            continue
        if list(record) != EXPECTED_FIELDS:
            errors.append(f"JSON 第 {index} 条字段不正确")
    if len(records) == len(csv_records):
        for index, (json_record, csv_record) in enumerate(
            zip(records, csv_records, strict=True), start=1
        ):
            normalized = {field: csv_value(json_record.get(field)) for field in EXPECTED_FIELDS}
            if normalized != csv_record:
                errors.append(f"JSON 与 CSV 第 {index} 条记录不一致")
    else:
        errors.append(f"JSON/CSV 数量不一致：{len(records)} / {len(csv_records)}")
    return records, csv_records


def verify_mapping(records: list[dict[str, object]], errors: list[str]) -> dict[str, Path]:
    if len(records) != EXPECTED_RECORDS:
        errors.append(f"索引记录数应为 {EXPECTED_RECORDS}，实际为 {len(records)}")

    statuses = Counter(str(record.get("status")) for record in records)
    if statuses != Counter({"completed": EXPECTED_COMPLETED, "unavailable": EXPECTED_UNAVAILABLE}):
        errors.append(f"状态数量不正确：{dict(statuses)}")

    platforms = Counter(str(record.get("platform")) for record in records)
    if dict(platforms) != EXPECTED_PLATFORM_RECORDS:
        errors.append(f"平台记录数不正确：{dict(platforms)}")

    keys = [(str(record.get("platform")), str(record.get("video_id"))) for record in records]
    if len(keys) != len(set(keys)):
        errors.append("索引存在重复的平台/视频 ID")

    expected_paths: dict[str, Path] = {}
    orders_by_category: dict[str, list[int]] = defaultdict(list)
    category_counts: Counter[str] = Counter()
    for record in records:
        platform = str(record.get("platform") or "")
        video_id = str(record.get("video_id") or "")
        title = str(record.get("title") or "")
        author = str(record.get("author") or "")
        status = str(record.get("status") or "")
        source_url = str(record.get("source_url") or "")
        transcript_path = str(record.get("transcript_path") or "")
        if not all((platform, video_id, title, author, source_url)):
            errors.append(f"记录缺少必填字段：{platform}/{video_id or '未知 ID'}")
        if source_url != expected_source_url(platform, video_id):
            errors.append(f"原视频链接不匹配：{platform}/{video_id}")

        if status == "unavailable":
            if transcript_path:
                errors.append(f"不可访问记录不应指向转录稿：{video_id}")
            if record.get("learning_order") is not None:
                errors.append(f"不可访问记录不应有学习顺序：{video_id}")
            if not str(record.get("notes") or ""):
                errors.append(f"不可访问记录缺少原因：{video_id}")
            continue
        if status != "completed":
            continue

        directory = {"YouTube": "youtube", "Bilibili": "bilibili"}.get(platform)
        expected_path = f"transcripts/{directory}/{video_id}.md" if directory else ""
        if transcript_path != expected_path:
            errors.append(f"转录路径不匹配：{platform}/{video_id} -> {transcript_path}")
            continue
        path = ROOT / transcript_path
        expected_paths[transcript_path] = path
        if not path.is_file():
            errors.append(f"缺少转录稿：{transcript_path}")

        category = str(record.get("category") or "")
        try:
            order = int(record.get("learning_order"))
        except (TypeError, ValueError):
            errors.append(f"学习顺序无效：{video_id}")
            continue
        orders_by_category[category].append(order)
        category_counts[category] += 1
        if record.get("proofread_status") != "completed" or not record.get("proofread_at"):
            errors.append(f"校对状态不完整：{video_id}")

    if dict(category_counts) != EXPECTED_CATEGORIES:
        errors.append(f"学习分类数量不正确：{dict(category_counts)}")
    for category, expected_count in EXPECTED_CATEGORIES.items():
        actual_orders = sorted(orders_by_category.get(category, []))
        if actual_orders != list(range(1, expected_count + 1)):
            errors.append(f"学习顺序不连续：{category}")

    actual_paths = {
        relative(path): path
        for platform in EXPECTED_PLATFORM_TRANSCRIPTS
        for path in (ROOT / "transcripts" / platform).glob("*.md")
    }
    if set(actual_paths) != set(expected_paths):
        missing = sorted(set(expected_paths) - set(actual_paths))
        extra = sorted(set(actual_paths) - set(expected_paths))
        errors.append(f"索引与转录文件不一致：缺少 {len(missing)}，多出 {len(extra)}")
    for platform, expected_count in EXPECTED_PLATFORM_TRANSCRIPTS.items():
        actual_count = sum(path.startswith(f"transcripts/{platform}/") for path in actual_paths)
        if actual_count != expected_count:
            errors.append(f"{platform} 转录数量应为 {expected_count}，实际为 {actual_count}")
    return expected_paths


def verify_transcripts(
    records: list[dict[str, object]], expected_paths: dict[str, Path], errors: list[str]
) -> int:
    hashes: dict[str, list[str]] = defaultdict(list)
    checked = 0
    by_path = {
        str(record.get("transcript_path")): record
        for record in records
        if record.get("status") == "completed"
    }
    for transcript_path, path in expected_paths.items():
        if not path.is_file():
            continue
        checked += 1
        data = path.read_bytes()
        hashes[hashlib.sha256(data).hexdigest()].append(transcript_path)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"转录稿不是 UTF-8：{transcript_path}")
            continue
        record = by_path[transcript_path]
        required_lines = [
            f"- 平台: {record['platform']}",
            f"- 作者: {record['author']}",
            f"- 视频 ID: {record['video_id']}",
            f"- URL: {record['source_url']}",
            "## 完整字幕（含时间码）",
        ]
        for required in required_lines:
            if required not in text:
                errors.append(f"转录稿头部映射缺失：{transcript_path} -> {required}")
        timestamps = [seconds(match) for match in TIMECODE_RE.findall(text)]
        if len(timestamps) < 2:
            errors.append(f"时间码不足：{transcript_path}")
            continue
        if timestamps != sorted(timestamps):
            errors.append(f"时间码顺序错误：{transcript_path}")
        duration = int(record.get("duration_seconds") or 0)
        if duration >= 60 and timestamps[-1] < duration * 0.8:
            errors.append(
                f"时间码覆盖不足：{transcript_path} ({timestamps[-1]}/{duration} 秒)"
            )
    duplicates = [paths for paths in hashes.values() if len(paths) > 1]
    if duplicates:
        errors.append(f"发现 {len(duplicates)} 组重复转录稿")
    return checked


def verify_markdown_links(records: list[dict[str, object]], errors: list[str]) -> int:
    local_link_count = 0
    for markdown in ROOT.rglob("*.md"):
        if ".git" in markdown.relative_to(ROOT).parts:
            continue
        text = markdown.read_text(encoding="utf-8")
        for match in LOCAL_LINK_RE.finditer(text):
            destination = match.group(1).strip("<>")
            parsed = urlparse(destination)
            if parsed.scheme in {"http", "https", "mailto"} or destination.startswith("#"):
                continue
            if parsed.scheme or destination.startswith("/"):
                errors.append(f"Markdown 使用绝对或未知链接：{relative(markdown)} -> {destination}")
                continue
            local_link_count += 1
            target_text = unquote(destination.split("#", 1)[0].split("?", 1)[0])
            target = (markdown.parent / target_text).resolve()
            if not target.exists():
                errors.append(f"Markdown 本地链接失效：{relative(markdown)} -> {destination}")

    if not LEARNING_CATALOG.is_file():
        errors.append("缺少 学习目录.md")
        return local_link_count
    catalog = LEARNING_CATALOG.read_text(encoding="utf-8")
    transcript_links = CATALOG_TRANSCRIPT_LINK_RE.findall(catalog)
    if len(transcript_links) != EXPECTED_COMPLETED or len(set(transcript_links)) != EXPECTED_COMPLETED:
        errors.append(
            f"学习目录的规范转录链接应为 {EXPECTED_COMPLETED} 个且不重复，实际为 "
            f"{len(transcript_links)} 个/{len(set(transcript_links))} 个唯一"
        )
    if "分类整理/" in catalog:
        errors.append("学习目录仍指向重复分类副本")
    for record in records:
        source_url = str(record.get("source_url") or "")
        if catalog.count(f"]({source_url})") != 1:
            errors.append(f"学习目录中的原视频链接数量不为 1：{record.get('video_id')}")
        transcript_path = str(record.get("transcript_path") or "")
        if transcript_path and catalog.count(f"]({transcript_path})") != 1:
            errors.append(f"学习目录中的转录链接数量不为 1：{record.get('video_id')}")
    return local_link_count


def sensitive_patterns() -> list[tuple[str, re.Pattern[str]]]:
    return [
        ("absolute_user_path", re.compile("/" + "Users/")),
        ("file_url", re.compile("file" + "://", re.IGNORECASE)),
        (
            "local_service_url",
            re.compile(r"https?://(?:local" + r"host|127\.0\.0\.1)(?::\d+)?", re.IGNORECASE),
        ),
        ("private_key", re.compile("BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY")),
        ("authorization_header", re.compile("Authori" + r"zation\s*:", re.IGNORECASE)),
        ("cookie_header", re.compile("Coo" + r"kie\s*:", re.IGNORECASE)),
        (
            "bearer_credential",
            re.compile(r"\bBea" + r"rer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
        ),
        (
            "secret_assignment",
            re.compile(
                r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret)"
                r"\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{8,}",
                re.IGNORECASE,
            ),
        ),
        (
            "email_address",
            re.compile(
                r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
                re.IGNORECASE,
            ),
        ),
        ("china_mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
        ("china_id", re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")),
        ("ipv4_address", re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")),
    ]


def verify_filesystem(errors: list[str]) -> dict[str, int]:
    empty_files: list[str] = []
    large_files: list[str] = []
    banned_files: list[str] = []
    binary_files: list[str] = []
    sensitive_matches: list[tuple[str, int, str]] = []
    symlinks = [relative(path) for path in ROOT.rglob("*") if path.is_symlink()]
    patterns = sensitive_patterns()

    for path in repo_files():
        rel = relative(path)
        stat = path.stat()
        if stat.st_size == 0:
            empty_files.append(rel)
        if stat.st_size > MAX_FILE_SIZE:
            large_files.append(rel)
        lower_name = path.name.lower()
        lower_parts = {part.lower() for part in path.relative_to(ROOT).parts}
        if (
            path.name in BANNED_FILENAMES
            or path.suffix.lower() in BANNED_SUFFIXES
            or lower_parts & BANNED_DIRECTORY_NAMES
            or any(part in lower_name for part in RAW_METADATA_NAME_PARTS)
        ):
            banned_files.append(rel)
        data = path.read_bytes()
        if b"\x00" in data:
            binary_files.append(rel)
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            binary_files.append(rel)
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in patterns:
                if pattern.search(line):
                    sensitive_matches.append((rel, line_number, label))

    if empty_files:
        errors.append(f"发现 {len(empty_files)} 个空文件：{', '.join(empty_files[:5])}")
    if large_files:
        errors.append(f"发现 {len(large_files)} 个超过 1 MiB 的文件：{', '.join(large_files[:5])}")
    if banned_files:
        errors.append(f"发现 {len(banned_files)} 个缓存/媒体/原始响应文件：{', '.join(banned_files[:5])}")
    if binary_files:
        errors.append(f"发现 {len(binary_files)} 个二进制或非 UTF-8 文件：{', '.join(binary_files[:5])}")
    if symlinks:
        errors.append(f"发现 {len(symlinks)} 个符号链接：{', '.join(symlinks[:5])}")
    if sensitive_matches:
        summary = ", ".join(f"{path}:{line}({label})" for path, line, label in sensitive_matches[:8])
        errors.append(f"发现 {len(sensitive_matches)} 处潜在敏感信息：{summary}")
    return {
        "empty_files": len(empty_files),
        "large_files": len(large_files),
        "banned_files": len(banned_files),
        "binary_files": len(binary_files),
        "symlinks": len(symlinks),
        "sensitive_matches": len(sensitive_matches),
    }


def verify_git(errors: list[str]) -> str:
    if not (ROOT / ".git").exists():
        return "not-initialized"
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if branch != "main":
        errors.append(f"Git 分支应为 main，实际为 {branch or 'detached'}")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if status:
        errors.append("Git 工作区不干净")
        return "dirty"
    return "clean"


def main() -> int:
    errors: list[str] = []
    records, csv_records = read_metadata(errors)
    expected_paths = verify_mapping(records, errors) if records else {}
    transcripts_checked = verify_transcripts(records, expected_paths, errors) if records else 0
    local_links = verify_markdown_links(records, errors) if records else 0
    filesystem = verify_filesystem(errors)
    git_state = verify_git(errors)

    if errors:
        print(f"验收失败，共 {len(errors)} 项：")
        for error in errors:
            print(f"- {error}")
        return 1

    print("验收通过：")
    print(f"- records={len(records)}")
    print(f"- csv_records={len(csv_records)}")
    print(f"- transcripts={transcripts_checked}")
    print(f"- markdown_local_links={local_links}")
    print("- duplicate_transcripts=0")
    print(f"- empty_files={filesystem['empty_files']}")
    print(f"- large_files={filesystem['large_files']}")
    print(f"- banned_files={filesystem['banned_files']}")
    print(f"- sensitive_matches={filesystem['sensitive_matches']}")
    print(f"- git_worktree={git_state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
