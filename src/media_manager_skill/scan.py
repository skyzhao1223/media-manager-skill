#!/usr/bin/env python3
"""影视目录命名正向校验 —— 通用版（本地 / 极空间皆可）。

核心思路：不是检测"脏模式"，而是验证每个文件/目录是否符合规范。
任何不匹配规范格式的，全部输出。这样不会漏掉任何问题。

Usage:
    python scan.py [root_path]                  # 默认扫本地当前影视目录
    python scan.py --source zspace /sata11/my/data/影视   # 扫极空间
    python scan.py --source local /path/to/影视  # 扫本地目录
    python scan.py --json /path/to/影视 > issues.json
"""

from __future__ import annotations

import json
import os
import re
import sys

DEFAULT_ROOT = "/sata11/my/data/影视"
MAX_DEPTH = 8

VIDEO_EXTS = {"mp4", "mkv", "avi", "ts", "rmvb", "flv", "wmv", "mov", "iso", "m2ts"}
SUB_EXTS = {"srt", "ass", "ssa", "sub", "idx"}
JUNK_EXTS = {"torrent", "nfo", "td", "htm", "html", "url", "txt", "jpg", "png", "nzb"}

# ── 合规格式定义 ──────────────────────────────────────────

# 电影文件夹名：中文名 English Name (年份) [分辨率 来源]
# 允许：中文名中混数字（毒液2）、CJK标点（：·）、数字开头（2001太空漫游）
MOVIE_DIR_OK = re.compile(
    r"^[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\d·A-Za-z]+"  # 中文名（含标点、数字、英文如 ID/007）
    r"\s+"
    r"[\w][\w\s\':,.\-&!()0-9]+"  # 英文名/年份/标签
    r"(\s*\(\d{4}\))?"  # (年份) 可选
    r"(\s*\[.*\])?"  # [分辨率 来源] 可选
    r"(\s*(1-\d|\d-\d|CD\d|导演剪辑版|\[副本\d?\]))?"  # 合集/CD/标注
    r"$"
)


# 电影内部视频文件名：应该与文件夹名一致（可以有 CD1/CD2/_2 后缀）
def movie_file_ok(filename, folder_name):
    stem = filename.rsplit(".", 1)[0]
    ext = filename.rsplit(".", 1)[-1].lower()
    if stem == folder_name:
        return True
    # 允许后缀：CD1, _2, [4K], [1080p], E{XX}, 语言标签, 前传1
    if stem.startswith(folder_name):
        suffix = stem[len(folder_name) :]
        if re.match(
            r"^(\s*(CD\d|_\d|\[\w+\]|E\d{2,3}|\[粤语\]|\[国语\]|\[v\d\]|前传\d?))*$", suffix
        ):
            return True
    # 合集文件夹（如 1-3、1-7）本身已标记为问题，内部文件不再单独校验
    if re.search(r"\d+-\d+$", folder_name):
        return True
    # 字幕文件允许语言标签
    return ext in SUB_EXTS and stem.startswith(folder_name)


# 剧集文件夹名
SERIES_DIR_OK = re.compile(
    r"^[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\d·A-Za-z]+"
    r"\s+"
    r"[\w][\w\s\':,.\-&!()0-9]+"
    r"(\s*S\d{2}(-S\d{2})?)?"
    r"(\s*\(\d{4}\))?"
    r"(\s*(特别篇|\d))?"
    r"$"
)

# 剧集内部文件名：
# 1) 纯集号: E01, S01E01, E01-E02
# 2) 带剧名前缀: 剧名 E01, 剧名 S01 E01
SERIES_FILE_OK = re.compile(
    r"^"
    r"([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\d·A-Za-z]+\s+[\w][\w\s\':,.\-&!()0-9]+\s+)?"  # 可选剧名前缀
    r"("
    r"E\d{2,3}"  # E01, E02
    r"|S\d{2}\s*E\d{2,3}"  # S01E01, S01 E01
    r"|E\d{2,3}-E\d{2,3}"  # E01-E02
    r"|S\d{2}\s*E\d{2,3}-E\d{2,3}"  # S01E01-E02
    r")"
    r"(\s*(END|V\d))?"  # END标记、V2等版本
    r"(\s*\[[\w.\s]+\])?"  # [4K] [国语] [粤语]
    r"\s*\."  # 允许扩展名前有空格
    r"(mp4|mkv|avi|ts|rmvb|flv|wmv|mov)$",
    re.IGNORECASE,
)

# 特殊内容：SP（彩蛋/花絮/MV等）、花絮/特辑/番外等
# 只认 SP{XX} 或明确的关键词；不带剧名的纯「第1集」「花絮1」会被判不合规
SERIES_SPECIAL_OK = re.compile(
    r"^"
    r"([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\d·A-Za-z]+\s+[\w][\w\s\':,.\-&!()0-9]+\s+)?"  # 可选剧名前缀
    r"(SP\d{2}(\s+[\u4e00-\u9fffA-Za-z]+)?"  # SP01, SP01 彩蛋, SP01 MV
    r"|花絮|特辑|彩蛋|预告|番外|幕后|特别篇|精华版|前传)"
    r"\.(mp4|mkv|avi|ts)$"
)

# ── 通用黑名单（任何位置都不应出现） ──────────────────────

BLACKLIST_CHARS = re.compile(r"[丨｜]")  # 审查规避用的特殊竖线

# 单字母替代汉字的模式（如 S探、Z义联盟、Q余Y年）
LETTER_SUB = re.compile(
    r"(?:^[A-Z]{1,2}[\u4e00-\u9fff])"  # 开头1-2个大写字母+汉字
    r"|(?:[\u4e00-\u9fff][A-Z]{1,3}[\u4e00-\u9fff])"  # 汉字+大写+汉字
    r"|(?:[\u4e00-\u9fff][A-Z]{1,3}$)"  # 汉字+大写结尾
)

WATERMARK = re.compile(
    r"【|】|\[微信|\[公众号|￡|@圣城|Mp4Ba|XZYS|XunLeiJia|"
    r"kkkanba|字幕侠|霸王龙|压制组|微信|爱影哥|瞎看菌|雷锋菌|影喵儿|"
    r"情话菌|影视步行街|RARBG|STUTTERSHIT|SmY|CHAOSPACE",
    re.IGNORECASE,
)

PLACEHOLDER_ENGLISH = re.compile(
    r"\s+Erta\s*$|"  # "Erta" 占位符
    r"\s+TBD\s*$|"  # "TBD"
    r"\s+Unknown\s*$|"  # "Unknown"
    r"\s+XXX\s*$",  # "XXX"
    re.IGNORECASE,
)


# ── old→new 建议（可机械修复的命名问题） ─────────────────

# 可从文件名中安全移除的水印/站点标签 token（与 WATERMARK 对应）
_WATERMARK_TOKENS = re.compile(
    r"Mp4Ba|XZYS|XunLeiJia|kkkanba|字幕侠|霸王龙|压制组|"
    r"微信|爱影哥|瞎看菌|雷锋菌|影喵儿|情话菌|影视步行街|"
    r"RARBG|STUTTERSHIT|SmY|CHAOSPACE|圣城",
    re.IGNORECASE,
)


def _clean_name(name: str) -> str | None:
    """清洗可机械修复的问题（水印/审查字符/多余空格）。无法安全处理的返回 None。"""
    if not name:
        return None
    cleaned = _WATERMARK_TOKENS.sub("", name)
    cleaned = re.sub(r"【[^】]*】", "", cleaned)  # 【水印】整段
    cleaned = re.sub(r"\[(微信|公众号)[^\]\[]*\]", "", cleaned)  # [微信xxx]
    cleaned = re.sub(r"@圣城\S*", "", cleaned)  # @圣城xxx
    cleaned = cleaned.replace("丨", "").replace("｜", "")  # 审查规避断词符
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    cleaned = re.sub(r"\s+\.", ".", cleaned)  # 删除扩展名前多余空格
    if cleaned == name or not cleaned:
        return None
    return cleaned


def suggest_new_name(name: str, is_dir: bool, folder_name: str | None = None) -> str | None:
    """为单个名称生成建议新名；无法自动确定的返回 None。"""
    if not name:
        return None
    if is_dir and PLACEHOLDER_ENGLISH.search(name):
        return None  # 需查找正确英文名，不自动改
    if not is_dir:
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext in JUNK_EXTS or name.endswith(".bt.td"):
            return None  # 垃圾文件应删除而非改名
    cleaned = _clean_name(name)
    return cleaned


def _suggest_series_filename(name: str, folder_name: str) -> str | None:
    """剧集文件名重组为 `剧名 SXX EYY`，提取不出集号返回 None。"""
    ext = name.rsplit(".", 1)[-1].lower()
    m = re.search(r"S(\d{2})\s*E(\d{2,3})|E(\d{2,3})", name, re.IGNORECASE)
    if not m:
        return None
    if m.group(1):
        season, ep = m.group(1), m.group(2)
        if "S" in folder_name.upper():
            base = f"{folder_name} E{ep}"
        else:
            base = f"{folder_name} S{season} E{ep}"
    else:
        base = f"{folder_name} E{m.group(3)}"
    return f"{base}.{ext}"


def enrich_new_name(issue: dict, root: str) -> str | None:
    """为问题项补充建议新名 new_name；无法自动给出的返回 None。"""
    path = issue["path"]
    name = issue["name"]
    is_dir = issue["is_dir"]
    problems = set(issue["problems"])

    # 1) 通用清洗（水印/审查字符/空格）
    cleaned = _clean_name(name)
    if cleaned:
        return cleaned

    if is_dir:
        return None

    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    parts = path.split("/")

    # 2) 电影内部文件对齐文件夹名
    if ext in VIDEO_EXTS and "电影视频文件名不匹配文件夹" in problems and len(parts) >= 3:
        folder = parts[-2]
        if name.rsplit(".", 1)[0] != folder:
            return f"{folder}.{ext}"

    # 3) 剧集文件名重组为 剧名 SXX EYY
    if ext in VIDEO_EXTS and "剧集视频文件名不合规" in problems and len(parts) >= 3:
        cand = _suggest_series_filename(name, parts[-2])
        if cand:
            return cand

    return None


# ── 数据源遍历 ────────────────────────────────────────────


def walk_local(root, depth=0):
    """遍历本地文件系统目录。"""
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


def walk_zspace(client, path, depth=0):
    """遍历极空间 NAS 目录（zspace-cli 数据源，处理 50 条分页）。"""
    if depth > MAX_DEPTH:
        return
    start = 0
    while True:
        try:
            resp = client._post(
                "/v2/file/list", {"path": path, "start": start, "limit": 50, "show_hidden": 0}
            )
        except Exception:  # noqa: BLE001 - 网络/API 异常一律视为分页结束
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


# ── 验证逻辑 ─────────────────────────────────────────────


def validate(item, root):
    """返回问题列表。空列表=合规。"""
    path = item["path"]
    name = item["name"]
    is_dir = item["is_dir"]
    problems = []

    rel = path.replace(root + "/", "") if path.startswith(root) else path
    ext = name.rsplit(".", 1)[-1].lower() if "." in name and not is_dir else ""
    stem = name.rsplit(".", 1)[0] if ext else name
    parts = rel.split("/")

    # 确定所在区域
    in_movie = "/电影/" in path or path.endswith("/电影")
    in_series = "/剧集/" in path or path.endswith("/剧集")

    if not in_movie and not in_series:
        return []  # 非影视区域不检查

    # ── 通用黑名单检查（对所有文件/目录都做） ──
    if BLACKLIST_CHARS.search(name):
        problems.append("审查规避字符(丨｜)")

    if WATERMARK.search(name):
        problems.append("水印/站点标签")

    # 字母替代汉字检查 — 排除已知合规的模式
    clean_stem = re.sub(r"\[.*?\]|\(.*?\)", "", stem)  # 去掉方括号和圆括号内容
    if (
        LETTER_SUB.search(clean_stem)
        and not re.match(r"^[ES]\d", name)  # 排除 E01、S01E01 等集号格式
        and not re.match(r"^(CD|4K|3D|2D|TV|HD|MP|ID)\d*", clean_stem)  # 排除 CD1、4K 等合规标签
        and not re.search(r"[a-z][A-Z]", clean_stem)  # 排除合规英文名中间的大写 (如 "The XX")
    ):
        problems.append("疑似字母替代汉字")

    # ── 占位符英文名 ──
    if is_dir and PLACEHOLDER_ENGLISH.search(name):
        problems.append("占位符英文名(需查找正确英文名)")

    # ── 垃圾文件 ──
    if not is_dir and ext in JUNK_EXTS:
        problems.append("垃圾文件")
        return problems

    if not is_dir and name.endswith(".bt.td"):
        problems.append("下载残留")
        return problems

    # ── 电影区域验证 ──
    if in_movie:
        # 一级子目录（电影文件夹）
        if is_dir and path == f"{root}/电影/{name}" and not MOVIE_DIR_OK.match(name):
            problems.append("电影文件夹名不合规")
        if is_dir and path == f"{root}/电影/{name}" and re.search(r"\d+-\d+$", name):
            problems.append("合集文件夹(应拆分为独立文件夹)")

        # 花絮子目录合规（花絮, 花絮 - XXX）
        if is_dir and re.match(r"^花絮(\s*-\s*.+)?$", name):
            return []

        # 电影内部文件
        if not is_dir and ext in VIDEO_EXTS:
            # 跳过花絮子目录内的文件（花絮内文件名自成体系）
            if any(re.match(r"^花絮", p) for p in parts[1:]):
                return []
            if len(parts) >= 3:  # 电影/文件夹/文件
                folder = parts[1]
                if not movie_file_ok(name, folder):
                    problems.append("电影视频文件名不匹配文件夹")

        # 花絮子目录内的字幕文件也合规
        if not is_dir and ext in SUB_EXTS and any(re.match(r"^花絮", p) for p in parts[1:]):
            return []

        # 散文件（直接在电影根目录）
        if not is_dir and path == f"{root}/电影/{name}" and ext in VIDEO_EXTS:
            problems.append("电影散文件(应放入独立文件夹)")

    # ── 剧集区域验证 ──
    if in_series:
        # 一级子目录（剧集文件夹）
        if is_dir and path == f"{root}/剧集/{name}" and not SERIES_DIR_OK.match(name):
            problems.append("剧集文件夹名不合规")

        # 剧集内部视频文件
        if (
            not is_dir
            and ext in VIDEO_EXTS
            and len(parts) >= 3
            and not SERIES_FILE_OK.match(name)
            and not SERIES_SPECIAL_OK.match(name)
        ):
            # 纯数字也不行
            problems.append("剧集视频文件名不合规")

    # ── PT/Scene 原始命名 ──
    if (
        not is_dir
        and ext in (VIDEO_EXTS | SUB_EXTS)
        and re.match(r"^[A-Za-z][\w.]+\.\d{4}\.", name)
    ):
        problems.append("PT/Scene原始命名")

    # ── 格式转换残留 ──
    if re.search(r"\.qsv\.|\.flv\.mp4$", name):
        problems.append("格式转换残留")

    return problems


# ── 主程序 ────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="影视目录命名正向校验（本地 / 极空间）")
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="扫描根目录（--source local 时必填；--source zspace 默认 /sata11/my/data/影视）",
    )
    parser.add_argument(
        "--source",
        choices=("local", "zspace"),
        default="local",
        help="数据源：local=本地目录（默认），zspace=极空间 NAS（需 zspace-cli）",
    )
    parser.add_argument("--json", action="store_true", help="stdout 输出 JSON")
    parser.add_argument("--preview", action="store_true", help="输出 old→new 重命名建议")
    args = parser.parse_args()
    output_json = args.json
    preview = args.preview

    if args.source == "zspace":
        # 惰性导入，仅在需要极空间时才要求 zspace-cli
        try:
            from zspace_cli import ZSpaceClient
        except ImportError:
            print(
                "✗ --source zspace 需要先安装 zspace-cli: pip install zspace-cli", file=sys.stderr
            )
            sys.exit(1)
        root = args.root or DEFAULT_ROOT
        with ZSpaceClient() as c:
            scan_all = walk_zspace(c, root)
            _run(
                scan_all,
                validate,
                root,
                output_json,
                preview,
                repeat_source=lambda: walk_zspace(c, root),
            )
    else:
        root = args.root or "."
        if not os.path.isdir(root):
            print(f"✗ 目录不存在: {root}", file=sys.stderr)
            sys.exit(1)
        scan_all = walk_local(root)
        _run(scan_all, validate, root, output_json, preview, repeat_source=lambda: walk_local(root))


def _run(scan_all, validate, root, output_json, preview, repeat_source):
    print(f"正在扫描 {root} ...\n", file=sys.stderr)

    stats = {"dirs": 0, "files": 0}
    issues = []

    for item in scan_all:
        if item["is_dir"]:
            stats["dirs"] += 1
        else:
            stats["files"] += 1

        problems = validate(item, root)
        if problems:
            rel = item["path"].replace(root + "/", "")
            issues.append(
                {
                    "path": rel,
                    "name": item["name"],
                    "is_dir": item["is_dir"],
                    "problems": problems,
                }
            )

    print(f"扫描完成: {stats['dirs']} 目录, {stats['files']} 文件\n", file=sys.stderr)

    # 重复资源检测（JSON / 文本两种输出都执行）
    issues.extend(find_duplicates(repeat_source, root))

    # 为每个问题项补充建议新名
    for issue in issues:
        issue["new_name"] = enrich_new_name(issue, root)

    if output_json:
        json.dump(issues, sys.stdout, ensure_ascii=False, indent=2)
        return

    if not issues:
        print("✅ 全部合规，零问题！")
        return

    if preview:
        previewable = [i for i in issues if i.get("new_name")]
        if previewable:
            print(f"── old → new 预览（{len(previewable)} 项） ──")
            for item in previewable:
                tag = "📁" if item["is_dir"] else "  "
                print(f"  {tag} {item['path']}")
                print(f"       → {item['new_name']}")
            print()

    # 按问题类型分组
    by_type = {}
    for issue in issues:
        for p in issue["problems"]:
            by_type.setdefault(p, []).append(issue)

    print(f"⚠  发现 {len(issues)} 个问题项:\n")

    for ptype, items in sorted(by_type.items(), key=lambda x: -len(x[1])):
        print(f"【{ptype}】{len(items)} 项")
        for item in items[:8]:
            tag = "📁" if item["is_dir"] else "  "
            print(f"  {tag} {item['path']}")
        if len(items) > 8:
            print(f"  ... 还有 {len(items) - 8} 项")
        print()


def find_duplicates(repeat_source, root):
    """基于中文名去重，检测疑似重复资源目录。"""
    dir_names = {}
    for item in repeat_source():
        if item["is_dir"] and item["path"].count("/") == root.count("/") + 2:
            name = item["name"]
            base = re.sub(r"\s*\[.*?\]", "", name)
            base = re.sub(r"\s*\(副本\d?\)", "", base)
            dir_names.setdefault(base, []).append(name)

    dups = []
    for base, names in dir_names.items():
        if len(names) > 1:
            for n in names:
                dups.append(
                    {
                        "path": n,
                        "name": n,
                        "is_dir": True,
                        "problems": [f"疑似重复资源({len(names)}个)"],
                    }
                )
    return dups


if __name__ == "__main__":
    main()
