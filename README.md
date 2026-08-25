# media-manager-skill

**影视库命名扫描与整理 Agent Skill** — 深度扫描 + `old→new` 预览 + rename/move。**本地影音库、云盘（网盘）、各类 NAS（极空间 / 群晖 / 威联通 …）都支持**。

> 命名规范来自 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)。  
> 核心校验逻辑是纯 Python，与存储后端无关；NAS 通过适配器接入（如极空间走 [zspace-cli](https://github.com/skyzhao1223/zspace-cli)）。

---

## 支持的场景

| 场景 | 数据源 | 说明 |
|------|--------|------|
| 本地影音库 | `--source local`（默认） | 纯 Python，扫本地目录，零依赖 |
| 极空间 NAS | `--source zspace` | 走 [zspace-cli](https://github.com/skyzhao1223/zspace-cli) 读桌面客户端登录态 |
| 其他 NAS（群晖/威联通等） | 挂载 + 本地模式 | 挂载成本地盘符/目录，直接用 `--source local` |
| 云盘 / 网盘 | 挂载 + 本地模式 | rclone / WebDAV 等挂载为本地目录后用 `--source local` |

> 只要能把目录列成 `{path, name, is_dir}` 就能用本扫描器。挂载成本地目录是最简单的接入方式。

---

## 安装

```bash
pip install media-manager-skill          # 本地模式，零依赖
pip install "media-manager-skill[zspace]"  # 极空间模式（带上 zspace-cli）

# 命令行入口
mm-scan --source local /path/to/影视
```

> 不安装直接跑脚本也行：`python scripts/scan.py --source local /path/to/影视`（本仓库即含完整实现）。

## 快速开始

```bash
# 本地目录（默认）
mm-scan --source local /path/to/影视

# 极空间 NAS
zs check
mm-scan --source zspace /sata11/my/data/影视

# JSON 输出（供后续处理）
mm-scan --json /path/to/影视 > /tmp/issues.json
```

## 它能做什么

- **深度扫描**影视目录（电影 / 剧集），按 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide) 规范逐项验证
- 识别：命名不规范、水印/站点标签、审查规避字符、占位符、文件/文件夹名不匹配、重复资源等问题
- 输出 `old→new` **预览映射表**，确认后再批量 rename / move
- 数据源可插拔：本地文件系统（默认）或极空间 NAS（`--source zspace`）

## 搭配使用

与 **Jellyfin / Emby / MoviePilot / nas-tools / 极影视** 搭配：入库或刮削前先扫描一遍，把命名问题一次暴露，避免刮削失败。见 [docs/integrations.md](docs/integrations.md)。

## 作为 Agent Skill

```bash
cp -r SKILL.md scripts ~/your-project/skills/media-manager/
```

然后对你的 Agent 说：「扫一下 `/sata11/my/data/影视` 的命名问题」（极空间）或「扫一下 `~/Movies` 的命名问题」（本地）。

## 目录结构

```
media-manager-skill/
├── SKILL.md          # Agent skill 主文件（工作流 + 踩坑）
├── scripts/
│   └── scan.py       # 薄封装（同一份核心代码，不装包也能跑）
├── src/
│   └── media_manager_skill/
│       └── scan.py   # 核心实现（pip 安装后由 mm-scan 调用）
└── docs/
    └── integrations.md  # 与 Jellyfin / MoviePilot / 极影视等搭配使用
```

## 原理与限制

- 核心校验逻辑是纯 Python（正则 + 规则），**与存储后端无关**——本地、云盘、各类 NAS 都可用
- 极空间模式通过 zspace-cli 读桌面客户端登录态访问文件 API，需 macOS 桌面客户端在线
- 其他 NAS / 云盘：挂载为本地目录即可用 `--source local`，或写一个十几行的遍历适配器接入
- 命名规范来自 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)
- 非官方项目，仅面向**本人账号、个人影视库**

## License

MIT
