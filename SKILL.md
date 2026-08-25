---
name: media-manager
description: >-
  Organize movies and TV series on a NAS or local disk. Deep-scan a media
  library against naming conventions, preview old→new changes, then rename/move.
  Naming conventions live in media-naming-guide; works with local folders or
  ZSpace (极空间) NAS via zspace-cli.
  Use when 影视整理, 影视命名扫描, media library organize, media rename, NAS 影视管理.
---

# 影视文件管理

先扫描影视库（本地目录或极空间 NAS），按 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide) 规范校验命名，出 `old→new` 预览，再执行 rename/move。

> **命名规范**见 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)  
> **数据源**：本地目录（默认）或极空间 NAS（`--source zspace`，走 zspace-cli）。

## Prerequisites

- 本地模式：Python 3.9+
- 极空间模式：`pip install zspace-cli` + `zs check` 通过，极空间 macOS 桌面客户端已登录
- 通用文件操作可用 [`zspace-nas`](https://github.com/skyzhao1223/zspace-cli/tree/main/skills/zspace-nas)（zspace-cli 自带）

## 工作流程

### Step 1: 扫描

```bash
# 本地目录
python scripts/scan.py /path/to/影视

# 极空间 NAS（需 zspace-cli）
python scripts/scan.py --source zspace /sata11/my/data/影视

# JSON 输出（供后续处理）
python scripts/scan.py --json /path/to/影视 > /tmp/issues.json
```

### Step 2: 修复

修复顺序见 [media-naming-guide SKILL.md 整理操作清单](https://github.com/skyzhao1223/media-naming-guide/blob/main/SKILL.md#整理操作清单)。

### Step 3: 验证

重新扫描，问题数 = 0 即完成。

## 数据源遍历

`scan.py` 内置两种数据源，核心校验逻辑共用：

**本地目录**（`walk_local`，默认）：

```python
def walk_local(root, depth=0):
    if depth > MAX_DEPTH:
        return
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name)
    except OSError:
        return
    for entry in entries:
        name = entry.name
        item_path = os.path.join(root, name)
        is_dir = entry.is_dir()
        yield {'path': item_path, 'name': name, 'is_dir': is_dir, 'depth': depth}
        if is_dir:
            yield from walk_local(item_path, depth + 1)
```

**极空间 NAS**（`walk_zspace`，需 `--source zspace`）：极空间 API `/v2/file/list` 每次最多返回 50 条，用 `start` + `limit` 分页遍历。

```python
def walk_zspace(client, path, depth=0):
    if depth > MAX_DEPTH:
        return
    start = 0
    while True:
        try:
            resp = client._post('/v2/file/list', {
                'path': path, 'start': start, 'limit': 50, 'show_hidden': 0
            })
        except Exception:
            break
        data = resp.get('data', resp) if isinstance(resp, dict) else {}
        items = data.get('list', []) if isinstance(data, dict) else []
        if not items:
            break
        for item in items:
            name = item.get('name', '')
            item_path = item.get('path', f'{path}/{name}')
            is_dir = str(item.get('is_dir', '0')) == '1'
            yield {'path': item_path, 'name': name, 'is_dir': is_dir, 'depth': depth}
            if is_dir:
                yield from walk_zspace(client, item_path, depth + 1)
        if len(items) < 50:
            break
        start += 50
```

## 文件操作 API（极空间适配）

执行 rename/move 时走 zspace-cli（通用文件操作见 [`zspace-nas`](https://github.com/skyzhao1223/zspace-cli/tree/main/skills/zspace-nas)）。本地目录用 `os.rename` / `shutil.move` 即可。

## 视频内容验证（极空间适配）

文件名不可信时，可获取视频元数据辅助判断。**极空间模式**通过 API 获取：

```python
info = c._post('/v2/file/info', {'path': video_path})
data = info.get('data', info)
duration_min = int(data.get('duration', 0)) // 60
resolution = f"{data.get('width')}x{data.get('height')}"
size_mb = int(data.get('size', 0)) // (1024 * 1024)
```

**用途**：排除明显不匹配的情况（如 22 分钟的文件不可能是 131 分钟的电影）。

**本地模式**：用 `ffprobe`（ffmpeg 自带）读时长/分辨率：

```bash
ffprobe -v error -show_entries format=duration -show_entries stream=width,height -of json "video.mp4"
```

**替代方案**：请用户在极空间 App/Web 界面（或本地播放器）打开视频确认。

## 踩坑记录

| 坑 | 表现 | 解决 |
|----|------|------|
| 只扫一层 | Season/4K 子目录遗漏 | 递归遍历 `max_depth=8` |
| 中英混排目录 | 电影/剧集判定不准确 | 目录结构保持 `电影/`、`剧集/` 分区 |
| rename 参数（极空间） | 第二参数含路径导致失败 | 第二参数是**纯文件名**，不含路径 |
| API 分页（极空间） | `c.ls()` 最多返回 50 条 | 用 `_post` + `start`/`limit` 循环遍历 |
| token 过期（极空间） | 扫描中途失败 | 重新初始化 `ZSpaceClient` |

## 注意事项

- 操作前**先预览**（生成 old → new 映射表），确认后再批量执行
- 大批量 rename/move 注意总耗时（建议分批、间隔）
- `rename` 第二参数是纯文件名不含路径（极空间）
- 新增资源后需重新跑扫描确认
- 扫描结果为 0 问题才算完成
