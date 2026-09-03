---
name: media-manager
description: >-
  Organize movies and TV series across many storage backends: local disk,
  cloud drives, or NAS (ZSpace, Synology, QNAP, UGREEN, TerraMaster, ASUSTOR,
  WD My Cloud, Lenovo, Hikvision, TrueNAS, Unraid, OpenMediaVault, etc.). Deep-scan a
  media library against naming conventions, preview old→new changes, then
  rename/move. Naming conventions live in media-naming-guide; a generic
  scanner walks local folders, and NAS sources plug in via adapters (e.g.
  ZSpace via zspace-cli). Two convention profiles: cn (Chinese) and plex
  (English/Plex). Localized output via --lang. Use when 影视整理, 影视命名扫描,
  media library organize, media rename, NAS 影视管理, 网盘影视整理.
---

# Media library organization

Organize a media library across storage backends — **local disk, cloud drives, and any NAS**
(ZSpace, Synology, QNAP, UGREEN, TerraMaster, ASUSTOR, WD My Cloud, Lenovo, Hikvision,
TrueNAS, Unraid, OpenMediaVault …). Validate names against a chosen naming convention, preview
`old→new` changes, then rename/move. The skill also understands Chinese trigger phrases
(e.g. 影视整理, 影视命名扫描).

> **Conventions**: [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)  
> **Sources**: local directory (default, universal); NAS via adapters (e.g. `--source zspace` uses
> zspace-cli). Any other NAS / cloud drive can plug in a small directory walker and reuse all checks.

## Profiles & zones

Two naming-convention profiles are built in:

| Profile | Conventions | Default zones |
|---------|-------------|---------------|
| `cn` (default) | `中文名 English Name (年份) [分辨率]`, censorship & watermark checks | `电影` / `剧集` |
| `plex` | `Name (Year)`, `Season 01/`, `S01E01` | `Movies` / `TV Shows` |

Zone folder names are configurable (`--movie-zone` / `--series-zone`) to match your layout.

## Prerequisites

- Local mode: Python 3.9+
- ZSpace mode: `pip install zspace-cli`, `zs check` passes, ZSpace macOS client logged in
- Generic file ops on ZSpace via the [`zspace-nas`](https://github.com/skyzhao1223/zspace-cli/tree/main/skills/zspace-nas) skill (ships with zspace-cli)

## Workflow

### Step 1: Scan

```bash
# Local (mm-scan needs `pip install media-manager-skill`; or run the in-repo script)
mm-scan --source local /path/to/library
python scripts/scan.py --source local /path/to/library

# Chinese library (default profile cn, folders 电影/剧集)
mm-scan /path/to/library

# English / Plex library
mm-scan --profile plex ~/Movies

# ZSpace NAS (needs zspace-cli)
mm-scan --source zspace /path/to/library

# Custom zone folder names
mm-scan --profile plex --movie-zone Films --series-zone Shows ~/Videos

# JSON output (stable problem codes)
mm-scan --json /path/to/library > /tmp/issues.json

# old→new rename suggestions
mm-scan --preview /path/to/library

# Force output language
mm-scan --lang en /path/to/library
```

> JSON `problems` are stable machine-readable codes (e.g. `MOVIE_FOLDER_NAME`,
> `SERIES_VIDEO_NAME`, `DUPLICATE`) — the same for every locale. Duplicate detection runs in
> both JSON and text modes.

### Step 2: Fix

Fix order follows the
[media-naming-guide checklist](https://github.com/skyzhao1223/media-naming-guide/blob/main/SKILL.md#整理操作清单).

### Step 3: Verify

Rescan; zero issues means done.

## Source walking

`scan.py` ships two sources sharing one validation core:

**Local** (`walk_local`, default):

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
        yield {"path": item_path, "name": name, "is_dir": is_dir, "depth": depth}
        if is_dir:
            yield from walk_local(item_path, depth + 1)
```

**ZSpace NAS** (`walk_zspace`, needs `--source zspace`): the ZSpace API
`/v2/file/list` returns at most 50 items per call, so page with `start` + `limit`.

```python
def walk_zspace(client, path, depth=0):
    if depth > MAX_DEPTH:
        return
    start = 0
    while True:
        try:
            resp = client._post(
                "/v2/file/list", {"path": path, "start": start, "limit": 50, "show_hidden": 0}
            )
        except Exception:
            break
        data = resp.get("data", resp) if isinstance(resp, dict) else {}
        items = data.get("list", []) if isinstance(data, dict) else []
        if not items:
            break
        for item in items:
            name = item.get("name", "")
            item_path = item.get("path", f"{path}/{name}")
            is_dir = str(item.get("is_dir", "0")) == "1"
            yield {"path": item_path, "name": name, "is_dir": is_dir, "depth": depth}
            if is_dir:
                yield from walk_zspace(client, item_path, depth + 1)
        if len(items) < 50:
            break
        start += 50
```

## File ops (ZSpace adapter)

rename/move on ZSpace goes through zspace-cli (generic ops in the
[`zspace-nas`](https://github.com/skyzhao1223/zspace-cli/tree/main/skills/zspace-nas) skill);
local folders use `os.rename` / `shutil.move`.

## Video metadata checks (optional)

When a filename is untrustworthy, verify with metadata. **ZSpace mode** via the API:

```python
info = c._post("/v2/file/info", {"path": video_path})
data = info.get("data", info)
duration_min = int(data.get("duration", 0)) // 60
resolution = f"{data.get('width')}x{data.get('height')}"
size_mb = int(data.get("size", 0)) // (1024 * 1024)
```

**Use**: rule out obvious mismatches (a 22-minute file is not a 131-minute movie).

**Local mode**: use `ffprobe` (from ffmpeg):

```bash
ffprobe -v error -show_entries format=duration -show_entries stream=width,height -of json "video.mp4"
```

**Fallback**: ask the user to confirm the content in the ZSpace App/Web UI (or a local player).

## Gotchas

| Gotcha | Symptom | Fix |
|--------|---------|-----|
| Only scans one level | Season/4K subfolders missed | recursive walk `max_depth=8` |
| Mixed zh/en folders | movie/series misdetected | keep `电影`/`剧集` or `Movies`/`TV Shows` zones, or pass `--movie-zone`/`--series-zone` |
| rename arg (ZSpace) | path in 2nd arg breaks | 2nd arg is a **bare filename**, no path |
| API pagination (ZSpace) | `c.ls()` caps at 50 | `_post` + `start`/`limit` loop |
| token expiry (ZSpace) | scan fails mid-way | re-init `ZSpaceClient` |
| Default zone mismatch | English library flagged as cn junk | use `--profile plex` for English/Plex libraries |

## Notes

- **Preview first** (old→new map), then bulk execute
- Large batch rename/move: pace it, add delays
- ZSpace `rename` 2nd arg is a bare filename (no path)
- Rescan after adding content
- Done = zero issues on rescan
