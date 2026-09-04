<div align="center">

# media-manager-skill

[English](README.md) · **简体中文**

[![CI](https://github.com/skyzhao1223/media-manager-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/skyzhao1223/media-manager-skill/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/media-manager-skill)](https://pypi.org/project/media-manager-skill/)
[![Python](https://img.shields.io/pypi/pyversions/media-manager-skill)](https://pypi.org/project/media-manager-skill/)

</div>

**影视库命名扫描与整理 Agent Skill** — 深度扫描 + `old→new` 预览 + rename/move。**本地影音库、云盘（网盘）、各类 NAS（极空间 / 群晖 / 威联通 / 绿联 / 铁威马 / 华芸 / 西部数据 / 联想 / 海康威视 / TrueNAS / Unraid / OpenMediaVault …）都支持**，并且面向全球用户：内置中文（`cn`）与英文/Plex（`plex`）两套命名规范、多语言输出、库目录可配置。

> 命名规范来自 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)。  
> 核心校验逻辑是纯 Python，与存储后端无关；NAS 通过适配器接入（如极空间走 [zspace-cli](https://github.com/skyzhao1223/zspace-cli)）。

---

## 支持的场景

| 场景 | 数据源 | 说明 |
|------|--------|------|
| 本地影音库 | `--source local`（默认） | 纯 Python，扫本地目录，零依赖 |
| 极空间 NAS | `--source zspace` | 走 [zspace-cli](https://github.com/skyzhao1223/zspace-cli) 读桌面客户端登录态 |
| 其他 NAS | 挂载 + 本地模式 | 群晖 Synology、威联通 QNAP、绿联 UGREEN、铁威马 TerraMaster、华芸 ASUSTOR、西部数据 WD My Cloud、联想 Lenovo、海康威视 Hikvision、TrueNAS、Unraid、OpenMediaVault 等——挂载成本地盘符/目录，直接用 `--source local` |
| 云盘 / 网盘 | 挂载 + 本地模式 | rclone / WebDAV 等挂载为本地目录后用 `--source local` |

> 只要能把目录列成 `{path, name, is_dir}` 就能用本扫描器。挂载成本地目录是最简单的接入方式。

## 命名规范 Profile

| Profile | 说明 | 默认分区目录 |
|---------|------|--------------|
| `cn`（默认） | 中文规范：`中文名 English Name (年份) [分辨率]`，含审查规避、水印检查 | `电影` / `剧集` |
| `plex` | 英文/Plex 规范：`Name (Year)`、`Season 01/`、`S01E01` | `Movies` / `TV Shows` |

分区目录可配置：用 `--movie-zone` / `--series-zone` 匹配你自己的目录结构。

## 安装

```bash
pip install media-manager-skill          # 本地模式，零依赖
pip install "media-manager-skill[zspace]"  # 极空间模式（带上 zspace-cli）
> **注意**：需要 Python ≥3.9。

```bash
pip install "media-manager-skill[zspace]"   # 极空间模式（带上 zspace-cli）
pip install media-manager-skill             # 本地模式，零依赖

# 命令行入口
mm-scan --source local /path/to/影视
```

> 不安装直接跑脚本也行：`python scripts/scan.py --source local /path/to/影视`（本仓库即含完整实现）。

## 快速开始

```bash
# 中文库（默认）
mm-scan /path/to/影视

# 英文 / Plex 库
mm-scan --profile plex ~/Movies

# 极空间 NAS
zs check
mm-scan --source zspace /sata11/my/data/影视

# 英文输出（未指定时按 locale 自动检测）
mm-scan --lang en /path/to/library

# JSON 输出（稳定问题码，供程序处理）
mm-scan --json /path/to/library > /tmp/issues.json

# old→new 重命名建议
mm-scan --preview /path/to/library

# 自定义分区目录名
mm-scan --profile plex --movie-zone Films --series-zone Shows ~/Videos
```

## CLI 选项

| 选项 | 说明 |
|------|------|
| `root` | 扫描根目录（`--source local` 时必填） |
| `--source {local,zspace}` | 数据源；默认 `local` |
| `--profile {cn,plex}` | 命名规范；默认 `cn` |
| `--movie-zone NAME` | 电影分区目录名（默认随 profile） |
| `--series-zone NAME` | 剧集分区目录名（默认随 profile） |
| `--lang {auto,zh,en}` | 输出语言；`auto` 读取 `LC_ALL`/`LANG` |
| `--json` | stdout 输出 JSON |
| `--preview` | 输出 old→new 重命名建议 |

## 它能做什么

- **深度扫描**影视目录（电影 / 剧集），按所选命名规范逐项验证
- 识别：命名不规范、水印/站点标签、审查规避字符（cn）、占位符、文件/文件夹名不匹配、PT/Scene 原始命名、重复资源等问题
- 输出 `old→new` **预览映射表**（`--preview`），确认后再批量 rename / move
- JSON 输出使用**稳定问题码**（见下）；CLI/终端输出按语言本地化
- 数据源可插拔：本地文件系统（默认）或极空间 NAS（`--source zspace`）

## 问题码（JSON 契约）

`--json` 输出问题列表，每条含 `{path, name, is_dir, problems, new_name}`，其中 `problems` 是**稳定的机器可读码**（不随语言变化）：

| 码 | 含义 | cn | plex |
|----|------|:--:|:----:|
| `MOVIE_FOLDER_NAME` | 电影文件夹名不合规 | ✓ | ✓ |
| `COLLECTION_FOLDER` | 合集文件夹，应拆分为独立电影 | ✓ | — |
| `MOVIE_VIDEO_MISMATCH` | 电影视频文件名与文件夹不匹配 | ✓ | ✓ |
| `MOVIE_LOOSE_FILE` | 电影根目录下的散文件 | ✓ | ✓ |
| `SERIES_FOLDER_NAME` | 剧集文件夹名不合规 | ✓ | — |
| `SERIES_VIDEO_NAME` | 剧集文件名不合规 | ✓ | ✓ |
| `SERIES_SEASON_FOLDER` | 季目录不是 `Season NN` | — | ✓ |
| `BLACKLIST_CHAR` | 审查规避字符（`丨｜`） | ✓ | — |
| `LETTER_SUB` | 疑似字母替代汉字 | ✓ | — |
| `WATERMARK` | 水印/站点标签 | ✓ | ✓ |
| `PLACEHOLDER` | 占位符英文名 | ✓ | ✓ |
| `JUNK_FILE` | 垃圾文件（应删除） | ✓ | ✓ |
| `DOWNLOAD_RESIDUE` | 下载残留（`.bt.td`） | ✓ | ✓ |
| `PT_SCENE_NAME` | PT/Scene 原始命名 | ✓ | ✓ |
| `FORMAT_RESIDUE` | 格式转换残留 | ✓ | ✓ |
| `DUPLICATE` | 疑似重复资源（见 `dupe_count`） | ✓ | ✓ |

如需人类可读文案，可通过包的 `PROBLEM_MESSAGES[code][lang]` 映射，或直接运行不带 `--json` 的 CLI。

## 搭配使用

与 **Jellyfin / Emby / MoviePilot / nas-tools / 极影视** 搭配：入库或刮削前先扫描一遍，把命名问题一次暴露，避免刮削失败。见 [docs/integrations.md](docs/integrations.md)。

## 作为 Agent Skill

```bash
cp -r SKILL.md scripts ~/your-project/skills/media-manager/
```

然后对你的 Agent 说：「扫一下 `/sata11/my/data/影视` 的命名问题」（极空间）或「scan naming issues in `~/Movies`」（本地/plex）。

## 目录结构

```
media-manager-skill/
├── SKILL.md          # Agent skill 主文件（工作流 + 踩坑）
├── scripts/
│   └── scan.py       # 薄封装（同一份核心代码，不装包也能跑）
├── src/
│   └── media_manager_skill/
│       ├── scan.py   # 核心实现（profile、i18n、CLI）
│       └── __init__.py
├── tests/            # pytest 测试（cn + plex + i18n）
└── docs/
    └── integrations.md
```

## 原理与限制

- 核心校验逻辑是纯 Python（正则 + 规则），**与存储后端无关**——本地、云盘、各类 NAS 都可用
- 极空间模式通过 zspace-cli 读桌面客户端登录态访问文件 API，需 macOS 桌面客户端在线
- 其他 NAS / 云盘：挂载为本地目录即可用 `--source local`，或写一个十几行的遍历适配器接入
- 命名规范来自 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)
- 非官方项目，仅面向**本人账号、个人影视库**

## License

MIT
