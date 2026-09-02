# Integrations

media-manager-skill is a **pre-ingest check**: run a naming scan before import/scraping so all
problems surface in one pass. It does not replace any player/scraper — it complements them.
（中文说明见各小节末尾的「推荐流程」。）

## Jellyfin / Emby

Jellyfin and Emby have strict structural requirements (one folder per movie; episodes as
`SxxExx`). Non-compliant names fail to scrape metadata.

**Recommended flow**:
1. Scan first: `mm-scan --profile plex /path/to/library` (English library) or
   `mm-scan /path/to/影视` (Chinese library)
2. Fix per the [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide) checklist
3. Then add to Jellyfin/Emby so the scraper gets it right the first time

**Example**: `Movies/Watermark[WeChat]xx.mp4` — a loose file with a watermark tag and no own
folder. Jellyfin will fail to identify it; the scanner flags it immediately.

## MoviePilot / nas-tools

MoviePilot and friends handle **auto-organizing** (identify, rename, hardlink). They depend on
recognizable input — a messy library causes misjudgments.

**Recommended flow**:
1. Use `mm-scan` to clear naming/watermark/censorship issues first
2. Hand off to MoviePilot / nas-tools for automatic organization
3. Run `mm-scan` periodically as an incremental check for newly added content

## 极影视 (ZSpace / 极空间)

ZSpace's own media player also needs proper names to scrape. ZSpace files are reached via the
desktop client, so scan the NAS directly with `--source zspace`:

```bash
pip install media-manager-skill zspace-cli
zs check
mm-scan --source zspace /sata11/my/data/影视
```

## Local library / cloud drives

Local directories use `--source local` (zero deps). Cloud drives (Baidu/Ali/115 …) can be
mounted locally via rclone/WebDAV and scanned the same way:

```bash
# rclone mount example
rclone mount mydrive:media ~/mnt/mydrive --vfs-cache-mode writes &
mm-scan --source local ~/mnt/mydrive/影视
```

## Why scan first?

- **Surface everything at once** — not one-by-one rejections from the scraper
- **Preview old→new**: `--json` emits the issue list with stable codes; confirm before bulk fixing
- **Regression-friendly**: rescan after fixes; zero issues = done; re-scan new content periodically
- **Cross-backend**: same conventions for local, cloud, and any NAS; change environments freely
