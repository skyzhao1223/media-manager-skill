# media-manager

**影视库命名扫描与整理** — 深度扫描 + `old→new` 预览 + rename/move。本地目录和极空间（ZSpace）NAS 都支持。

> 命名规范来自 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)。  
> 极空间数据源走 [zspace-cli](https://github.com/skyzhao1223/zspace-cli)（零配置访问）。

---

## 快速开始

```bash
# 本地目录（默认）
python scripts/scan.py /path/to/影视

# 极空间 NAS（需 zspace-cli）
pip install zspace-cli
zs check
python scripts/scan.py --source zspace /sata11/my/data/影视

# JSON 输出（供后续处理）
python scripts/scan.py --json /path/to/影视 > /tmp/issues.json
```

## 它能做什么

- **深度扫描**影视目录（电影 / 剧集），按 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide) 规范逐项验证
- 识别：命名不规范、水印/站点标签、审查规避字符、占位符、文件/文件夹名不匹配、重复资源等问题
- 输出 `old→new` **预览映射表**，确认后再批量 rename / move
- 数据源可插拔：本地文件系统（默认）或极空间 NAS（`--source zspace`）

## 作为 Agent Skill

```bash
cp -r SKILL.md scripts ~/your-project/skills/media-manager/
```

然后对你的 Agent 说：「扫一下 `/sata11/my/data/影视` 的命名问题」（极空间）或「扫一下 `~/Movies` 的命名问题」（本地）。

## 目录结构

```
media-manager/
├── SKILL.md          # Agent skill 主文件（工作流 + 踩坑）
└── scripts/
    └── scan.py       # 命名扫描脚本（本地 / 极空间双数据源）
```

## 原理与限制

- 核心校验逻辑是纯 Python（正则 + 规则），不绑定任何 NAS
- 极空间模式通过 zspace-cli 读桌面客户端登录态访问文件 API，需 macOS 桌面客户端在线
- 命名规范来自 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)
- 非官方项目，仅面向**本人账号、个人影视库**

## License

MIT
