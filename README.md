# 方方土价格行为学｜Al Brooks 公开视频中文转录

这是一个面向学习和检索的中文转录资料库，整理 Al Brooks、价格行为学相关公开视频。内容以方方土 PriceAction 的 YouTube 视频为主，也包含 Bilibili 来源。

本仓库不是 Al Brooks、视频作者或平台的官方项目。

## 收录情况

| 来源 | 视频记录 | 完整转录 | 无法公开访问 |
|---|---:|---:|---:|
| YouTube | 157 | 156 | 1 |
| Bilibili | 7 | 7 | 0 |
| **合计** | **164** | **163** | **1** |

163 份转录稿均包含时间码，并已完成逐行语义校对。另有 1 条视频目前无法公开访问，因此只保留索引记录和原视频链接。

## 如何使用

- 按顺序学习：打开 [学习目录](学习目录.md)。
- 查找视频与转录稿的对应关系：查看 [CSV 索引](metadata/index.csv) 或 [JSON 索引](metadata/index.json)。
- 转录稿按来源分别保存在 [YouTube](transcripts/youtube) 和 [Bilibili](transcripts/bilibili) 目录，文件名使用视频 ID。

每个视频只保存一份规范转录稿。学习分类和顺序由 Markdown 目录及元数据表达，不再复制文件。

## 仓库结构

```text
.
├── README.md
├── 学习目录.md
├── transcripts/
│   ├── youtube/      # 156 份
│   └── bilibili/     # 7 份
├── metadata/
│   ├── index.csv     # 164 条记录
│   ├── index.json    # 164 条记录
│   └── sources.json  # 公开来源清单
└── scripts/
    ├── check_new_videos.py
    ├── render_catalog.py
    └── verify_repository.py
```

仓库不包含视频、音频、缓存、平台原始 API 响应或重复分类副本。可以运行下面的命令检查数量、映射、时间码、本地链接、重复文件、大文件和常见敏感信息：

```bash
python3 scripts/verify_repository.py
```

## 更新检查

下面的命令会读取两个公开来源的最新视频清单，并与现有索引比较。它不使用浏览器 Cookie 或登录状态；如果某个平台暂时拒绝公开请求，会明确报告错误。

```bash
python3 scripts/check_new_videos.py
```

更新索引后，可以重新生成 CSV 和学习目录：

```bash
python3 scripts/render_catalog.py
```

## 版权与风险说明

本仓库仅供学习与检索。视频、字幕及原始内容的版权归原作者和相关平台所有；建议通过索引中的原视频链接观看和支持原作者。

本仓库内容不构成投资建议，也不承诺任何收益。交易可能造成重大损失，请独立判断并严格控制风险。
