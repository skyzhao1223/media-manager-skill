<div align="center">

# media-manager-skill

**English** · [简体中文](README.zh-CN.md)

[![PyPI - Version](https://img.shields.io/pypi/v/media-manager-skill?cacheSeconds=3600)](https://pypi.org/project/media-manager-skill/)
[![PyPI - Python](https://img.shields.io/pypi/pyversions/media-manager-skill?cacheSeconds=3600)](https://pypi.org/project/media-manager-skill/)
[![CI](https://github.com/skyzhao1223/media-manager-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/skyzhao1223/media-manager-skill/actions/workflows/ci.yml)

</div>

**Media library naming scanner & organizer** — deep scan + `old→new` preview + rename/move.
Works on **local disks, cloud drives, and any NAS** — ZSpace, Synology, QNAP, UGREEN,
TerraMaster, ASUSTOR, WD My Cloud, Lenovo, Hikvision, TrueNAS, Unraid, OpenMediaVault,
and more.
Built for a **global audience**: Chinese (`cn`) and English/Plex (`plex`) naming conventions,
localized output, and configurable library folders.

> Naming conventions live in [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide).
> The core is pure Python and backend-agnostic; NAS access goes through adapters
> (e.g. ZSpace via [zspace-cli](https://github.com/skyzhao1223/zspace-cli)).

---

## Supported scenarios

| Scenario | Source | Notes |
|----------|--------|-------|
| Local media library | `--source local` (default) | Pure Python, zero deps |
| ZSpace NAS | `--source zspace` | Reuses the desktop client login via [zspace-cli](https://github.com/skyzhao1223/zspace-cli) |
| Other NAS | mount + local | Synology, QNAP, UGREEN, TerraMaster, ASUSTOR, WD My Cloud, Lenovo, Hikvision, TrueNAS, Unraid, OMV… — mount as a local folder, then use `--source local` |
| Cloud drives | mount + local | rclone / WebDAV mounts work with `--source local` |

> Anything that can be listed as `{path, name, is_dir}` works with the scanner.
> Mounting as a local folder is the simplest integration.

## Naming convention profiles

Pick the ruleset that matches your library:

| Profile | Description | Default folders |
|---------|-------------|-----------------|
| `cn` (default) | Chinese conventions: `Chinese Title English Name (Year) [Quality]`, censorship-evasion & site-watermark checks | `电影` / `剧集` |
| `plex` | English/Plex conventions: `Name (Year)`, `Season 01/`, `S01E01` | `Movies` / `TV Shows` |

Folders are configurable — use `--movie-zone` / `--series-zone` to match your own layout.
The `cn` profile defaults to `电影` and `剧集`; the `plex` profile defaults to `Movies` and
`TV Shows`.

## Install

```bash
pip install media-manager-skill            # local mode, zero deps
pip install "media-manager-skill[zspace]"  # ZSpace mode (bundles zspace-cli)

# CLI entry point
mm-scan --source local /path/to/library
```

> No install needed to try it: `python scripts/scan.py --source local /path/to/library`
> (this repo ships the full implementation).

## Quick start

```bash
# Chinese library (default profile cn, folders 电影/剧集)
mm-scan /path/to/library

# English / Plex library
mm-scan --profile plex ~/Movies

# ZSpace NAS
zs check
mm-scan --source zspace /path/to/library

# English output (auto-detected from locale if not set)
mm-scan --lang en /path/to/library

# JSON output (machine-readable problem codes)
mm-scan --json /path/to/library > /tmp/issues.json

# old→new rename suggestions
mm-scan --preview /path/to/library

# Custom folder names
mm-scan --profile plex --movie-zone Films --series-zone Shows ~/Videos
```

## CLI options

| Option | Meaning |
|--------|---------|
| `root` | Scan root (required for `--source local`) |
| `--source {local,zspace}` | Data source; default `local` |
| `--profile {cn,plex}` | Naming conventions; default `cn` |
| `--movie-zone NAME` | Movie root folder name (default from profile) |
| `--series-zone NAME` | Series root folder name (default from profile) |
| `--lang {auto,zh,en}` | Output language; `auto` reads `LC_ALL`/`LANG` |
| `--json` | Emit JSON to stdout |
| `--preview` | Show `old→new` rename suggestions |

## What it does

- Deep-scans a media library (movies / series) against the selected naming convention
- Detects: invalid folder/file names, watermarks/site tags, censorship-evasion characters
  (cn), placeholders, folder/file name mismatches, PT/Scene raw names, duplicates
- Outputs an `old→new` **preview** (`--preview`) before you rename/move in bulk
- JSON output uses **stable problem codes** (see below); CLI/terminal output is localized
- Pluggable sources: local filesystem (default) or ZSpace NAS (`--source zspace`)

## Problem codes (JSON contract)

`--json` emits a list of issues. Each item: `{path, name, is_dir, problems, new_name}` where
`problems` is a list of stable machine-readable codes (they never change across locales):

| Code | Meaning | cn | plex |
|------|---------|:--:|:----:|
| `MOVIE_FOLDER_NAME` | Movie folder name invalid | ✓ | ✓ |
| `COLLECTION_FOLDER` | Collection folder; split into single movies | ✓ | — |
| `MOVIE_VIDEO_MISMATCH` | Movie video name ≠ folder name | ✓ | ✓ |
| `MOVIE_LOOSE_FILE` | Loose movie file in the movie root | ✓ | ✓ |
| `SERIES_FOLDER_NAME` | Series folder name invalid | ✓ | — |
| `SERIES_VIDEO_NAME` | Series episode file name invalid | ✓ | ✓ |
| `SERIES_SEASON_FOLDER` | Season folder not `Season NN` | — | ✓ |
| `BLACKLIST_CHAR` | Censorship-evasion character (full-width bars `丨｜`) | ✓ | — |
| `LETTER_SUB` | Letter-for-Chinese substitution | ✓ | — |
| `WATERMARK` | Watermark / site tag | ✓ | ✓ |
| `PLACEHOLDER` | Placeholder English name | ✓ | ✓ |
| `JUNK_FILE` | Junk file (delete it) | ✓ | ✓ |
| `DOWNLOAD_RESIDUE` | Download residue (`.bt.td`) | ✓ | ✓ |
| `PT_SCENE_NAME` | PT/Scene raw naming | ✓ | ✓ |
| `FORMAT_RESIDUE` | Format-conversion residue | ✓ | ✓ |
| `DUPLICATE` | Possible duplicate title (see `dupe_count`) | ✓ | ✓ |

For human-readable text, map codes through `PROBLEM_MESSAGES[code][lang]` (exported by the
package) or just run the CLI without `--json`.

## Pairing with other tools

Use before Jellyfin / Emby / MoviePilot / nas-tools / ZSpace media ingesting or scraping to
surface naming problems in one pass. See [docs/integrations.md](docs/integrations.md).

## As an Agent Skill

```bash
cp -r SKILL.md scripts ~/your-project/skills/media-manager/
```

Then ask your agent: "scan naming issues in `~/Movies`" (local/plex) or
"scan naming issues in `/path/to/library`" (ZSpace).

## Repository layout

```
media-manager-skill/
├── SKILL.md          # Agent skill entry (workflow + gotchas)
├── scripts/
│   └── scan.py       # Thin wrapper (same core, runnable without install)
├── src/
│   └── media_manager_skill/
│       ├── scan.py   # Core implementation (profiles, i18n, CLI)
│       └── __init__.py
├── tests/            # pytest suite (cn + plex + i18n)
└── docs/
    └── integrations.md
```

## How it works & limitations

- Core validation is pure Python (regex + rules), backend-agnostic — local, cloud, any NAS
- ZSpace mode reads the desktop client login via zspace-cli; the macOS client must be online
- Other NAS / cloud: mount as a local folder, or write a small walker adapter
- Naming conventions come from [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)
- Unofficial project, intended for personal libraries

## License

MIT
