# zspace-media-manager

极空间（ZSpace）NAS **影视库命名扫描与整理** Agent Skill — 深度扫描 + `old→new` 预览 + rename/move。

> 依赖 [zspace-cli](https://github.com/skyzhao1223/zspace-cli)（零配置访问极空间）和 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)（命名规范）。

---

## 30 秒开始

```bash
# 1. 安装底座
pip install zspace-cli
zs check

# 2. 复制本 skill 到你的 Agent 项目
cp -r SKILL.md scripts ~/your-project/skills/zspace-media-manager/

# 3. 对你的 Agent 说
# 「扫一下 /sata11/my/data/影视 的命名问题」
```

## 它能做什么

- **深度扫描**影视目录（电影 / 剧集），按 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide) 规范逐项验证
- 识别：命名不规范、水印/站点标签、审查规避字符、占位符、文件/文件夹名不匹配等问题
- 输出 `old→new` **预览映射表**，确认后再批量 rename / move
- 处理极空间 API 的分页限制、重命名参数等**踩坑点**

## 使用方式

```bash
# 直接跑扫描脚本（默认扫 /sata11/my/data/影视）
python scripts/scan.py

# 指定目录
python scripts/scan.py /sata11/my/data/影视/电影

# 输出 JSON（供后续处理）
python scripts/scan.py --json /sata11/my/data/影视 > /tmp/issues.json
```

## 目录结构

```
zspace-media-manager/
├── SKILL.md          # Agent skill 主文件（工作流 + API 踩坑）
└── scripts/
    └── scan.py       # 命名扫描脚本
```

## 原理与限制

- 通过 zspace-cli 读桌面客户端登录态，访问极空间文件 API
- 命名规范来自 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide)
- 仅面向**本人账号、个人影视库**，非官方项目

## License

MIT
