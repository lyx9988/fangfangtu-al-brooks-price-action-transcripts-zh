# 勘误与贡献说明

本仓库欢迎可核验的转录勘误、链接修正和公开视频补充。提交前请先确认同一视频尚未存在于 [`metadata/index.json`](metadata/index.json) 中。

## 提交转录勘误

请在 GitHub Issue 或 Pull Request 中提供以下信息：

```text
平台：YouTube / Bilibili
视频 ID：
原视频链接：
时间码：例如 00:12:34
当前文字：
建议文字：
依据：上下文、画面文字、作者说明或可靠术语来源
```

只修改能够由原音、画面或上下文确定的错误，不为了文风改写原意。一个勘误涉及多个位置时，请逐条列出时间码。

## 补充公开视频

新增记录应满足以下条件：

- 来源无需登录即可公开访问；
- 与 Al Brooks 或价格行为交易学习直接相关；
- 包含稳定的平台视频 ID 和原视频链接；
- 每个视频只新增一份规范转录稿；
- 路径使用 `scripts/transcript_paths.py` 中的 `canonical_transcript_path()` 生成，保持“分类编号-学习顺序 中文标题 [视频ID].md”的命名规则；
- 转录稿包含时间码，并注明转录来源和校对状态；
- 更新 `metadata/index.json` 后运行 `python3 scripts/render_catalog.py`，同步生成 CSV 和学习目录。

## 不要提交

- 视频、音频、缓存、临时文件或平台原始 API 响应；
- Cookie、Token、API Key、请求头、邮箱、电话或其他私人信息；
- 付费、受限或无法确认公开授权范围的资料；
- 与现有视频重复的转录副本；
- 交易建议、荐股内容或收益承诺。

## 提交前检查

```bash
git diff --check
python3 scripts/verify_repository.py --allow-dirty
```

提交内容应保持 UTF-8 编码，不使用绝对本机路径，并保证所有 Markdown 本地链接有效。
