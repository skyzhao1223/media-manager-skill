# 搭配使用

media-manager-skill 是**影视整理流程的前置检查**：入库/刮削前先跑一遍命名扫描，把问题一次性暴露出来。它不替代任何播放器/刮削器，而是它们的补充。

## Jellyfin / Emby

Jellyfin、Emby 对「电影/剧集」有严格的结构要求（每部电影一个文件夹、剧集按 SxxExx 命名），命名不合规会导致刮削不到元数据。

**推荐流程**：
1. 先扫描命名问题：`mm-scan --source local /path/to/媒体库`
2. 按 [media-naming-guide](https://github.com/skyzhao1223/media-naming-guide) 的清单修正
3. 再入库 Jellyfin / Emby，让刮削器一次到位

**例子**：`电影/水印片[微信]xx.mp4` 这种带水印标签、且没独立文件夹的散文件，Jellyfin 会识别失败；扫描器会直接标出来。

## MoviePilot / nas-tools

MoviePilot 这类工具负责**自动整理**（识别、重命名、硬链接）。但它依赖输入本身可识别，命名混乱的库会让它误判。

**推荐流程**：
1. 用 `mm-scan` 把库里「命名不规范 / 水印 / 审查字符」先清一遍
2. 再交给 MoviePilot / nas-tools 做自动整理
3. 定期跑 `mm-scan` 做增量检查，防止新入库内容又出问题

## 极影视（ZSpace / 极空间）

极空间自带极影视，同样要求规范命名才能刮削。极空间文件通过桌面客户端访问，用 `--source zspace` 直接扫 NAS：

```bash
pip install media-manager-skill zspace-cli
zs check
mm-scan --source zspace /sata11/my/data/影视
```

## 本地影音库 / 网盘

本地目录直接用 `--source local`（零依赖）；网盘（百度/阿里/115 等）通过 rclone / WebDAV 挂载为本地目录后同样适用：

```bash
# rclone 挂载示例
rclone mount mydrive:媒体库 ~/mnt/mydrive --vfs-cache-mode writes &
mm-scan --source local ~/mnt/mydrive/影视
```

## 为什么「先扫描」有价值

- **一次性暴露所有问题**：不是入库时一个一个被刮削器弹回来
- **预览 old→new**：`--json` 输出问题清单，批量修复前先确认
- **可回归**：修完重扫，问题数为 0 才算完成；新增内容后可定期复扫
- **跨后端**：本地、网盘、各类 NAS 同一套规范，换了环境也能用
