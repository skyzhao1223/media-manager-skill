#!/usr/bin/env python3
"""Media library naming scanner — local / ZSpace / any mounted backend.

核心思路 / Core idea: validate *against a compliant format* instead of
blacklisting dirty patterns, so nothing is missed.

Usage:
    python scan.py [root_path]                      # local
    python scan.py --source zspace /sata11/my/data/影视
    python scan.py --profile plex ~/Movies          # English/Plex conventions
    python scan.py --json /path/to/media > issues.json
    python scan.py --lang en /path/to/media         # English output
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Callable

DEFAULT_ROOT = "/sata11/my/data/影视"
MAX_DEPTH = 8

VIDEO_EXTS = {"mp4", "mkv", "avi", "ts", "rmvb", "flv", "wmv", "mov", "iso", "m2ts"}
SUB_EXTS = {"srt", "ass", "ssa", "sub", "idx"}
JUNK_EXTS = {"torrent", "nfo", "td", "htm", "html", "url", "txt", "jpg", "png", "nzb"}

# ── Problem codes & localisation ─────────────────────────

# Stable machine-readable issue codes. JSON output always uses these;
# CLI/terminal output renders them via PROBLEM_MESSAGES[code][lang].
#
# cn-profile only:   BLACKLIST_CHAR, LETTER_SUB
# plex-profile only: SERIES_SEASON_FOLDER

PROBLEM_MESSAGES: dict[str, dict[str, str]] = {
    "BLACKLIST_CHAR": {
        "zh": "审查规避字符(丨｜)",
        "en": "Censorship-evasion character (丨｜)",
    },
    "WATERMARK": {
        "zh": "水印/站点标签",
        "en": "Watermark / site tag",
    },
    "LETTER_SUB": {
        "zh": "疑似字母替代汉字",
        "en": "Possible letter-for-Chinese substitution",
    },
    "PLACEHOLDER": {
        "zh": "占位符英文名(需查找正确英文名)",
        "en": "Placeholder English name (look up the real one)",
    },
    "JUNK_FILE": {
        "zh": "垃圾文件",
        "en": "Junk file",
    },
    "DOWNLOAD_RESIDUE": {
        "zh": "下载残留",
        "en": "Download residue",
    },
    "MOVIE_FOLDER_NAME": {
        "zh": "电影文件夹名不合规",
        "en": "Movie folder name invalid",
    },
    "COLLECTION_FOLDER": {
        "zh": "合集文件夹(应拆分为独立文件夹)",
        "en": "Collection folder (split into individual movies)",
    },
    "MOVIE_VIDEO_MISMATCH": {
        "zh": "电影视频文件名不匹配文件夹",
        "en": "Movie video name does not match folder",
    },
    "MOVIE_LOOSE_FILE": {
        "zh": "电影散文件(应放入独立文件夹)",
        "en": "Loose movie file (belongs in its own folder)",
    },
    "SERIES_FOLDER_NAME": {
        "zh": "剧集文件夹名不合规",
        "en": "Series folder name invalid",
    },
    "SERIES_VIDEO_NAME": {
        "zh": "剧集视频文件名不合规",
        "en": "Series episode file name invalid",
    },
    "SERIES_SEASON_FOLDER": {
        "zh": "季文件夹名不合规(应为 Season NN)",
        "en": 'Season folder name invalid (expected "Season NN")',
    },
    "PT_SCENE_NAME": {
        "zh": "PT/Scene原始命名",
        "en": "PT/Scene raw naming",
    },
    "FORMAT_RESIDUE": {
        "zh": "格式转换残留",
        "en": "Format-conversion residue",
    },
    "DUPLICATE": {
        "zh": "疑似重复资源",
        "en": "Possible duplicate",
    },
}

CLI_MESSAGES: dict[str, dict[str, str]] = {
    "scanning": {"zh": "正在扫描 {root} ...\n", "en": "Scanning {root} ...\n"},
    "done": {
        "zh": "扫描完成: {dirs} 目录, {files} 文件\n",
        "en": "Scan complete: {dirs} dirs, {files} files\n",
    },
    "all_ok": {"zh": "✅ 全部合规，零问题！", "en": "✅ All compliant, no issues!"},
    "preview_title": {
        "zh": "── old → new 预览（{n} 项） ──",
        "en": "── old → new preview ({n} items) ──",
    },
    "issues_found": {"zh": "⚠  发现 {n} 个问题项:\n", "en": "⚠  {n} issue(s):\n"},
    "group_title": {"zh": "【{label}】{n} 项", "en": "({label}) {n} item(s)"},
    "more": {"zh": "  ... 还有 {n} 项", "en": "  ... and {n} more"},
    "dir_not_found": {"zh": "✗ 目录不存在: {root}", "en": "✗ Directory not found: {root}"},
    "need_zspace": {
        "zh": "✗ --source zspace 需要先安装 zspace-cli: pip install zspace-cli",
        "en": "✗ --source zspace requires zspace-cli: pip install zspace-cli",
    },
}


def tr(code: str, lang: str, **kw) -> str:
    """Localise a problem/CLI message for the given language."""
    table = PROBLEM_MESSAGES.get(code) or CLI_MESSAGES.get(code) or {lang: code}
    text = table.get(lang) or table.get("en") or code
    return text.format(**kw) if kw else text


def detect_lang(arg: str | None) -> str:
    """Resolve --lang: explicit choice, or auto-detect from locale env."""
    if arg in ("zh", "en"):
        return arg
    env = os.environ.get("LC_ALL", "") + " " + os.environ.get("LANG", "")
    return "zh" if "zh" in env.lower() else "en"


# ── Zones (configurable media directories) ───────────────


@dataclass(frozen=True)
class Zones:
    movie: str
    series: str


CN_ZONES = Zones(movie="电影", series="剧集")
PLEX_ZONES = Zones(movie="Movies", series="TV Shows")


def _in_zone(path: str, zone: str) -> bool:
    return f"/{zone}/" in path or path.endswith(f"/{zone}")


# ── cn profile regexes (Chinese naming conventions) ──────

# 电影文件夹名：中文名 English Name (年份) [分辨率 来源]
MOVIE_DIR_OK = re.compile(
    r"^[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\d·A-Za-z]+"  # 中文名（含标点、数字、英文如 ID/007）
    r"\s+"
    r"[\w][\w\s\':,.\-&!()0-9]+"  # 英文名/年份/标签
    r"(\s*\(\d{4}\))?"  # (年份) 可选
    r"(\s*\[.*\])?"  # [分辨率 来源] 可选
    r"(\s*(1-\d|\d-\d|CD\d|导演剪辑版|\[副本\d?\]))?"  # 合集/CD/标注
    r"$"
)


def movie_file_ok(filename, folder_name):
    """电影内部视频文件名：应与文件夹名一致（可有 CD1/CD2/_2 后缀）。"""
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


SERIES_DIR_OK = re.compile(
    r"^[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\d·A-Za-z]+"
    r"\s+"
    r"[\w][\w\s\':,.\-&!()0-9]+"
    r"(\s*S\d{2}(-S\d{2})?)?"
    r"(\s*\(\d{4}\))?"
    r"(\s*(特别篇|\d))?"
    r"$"
)

# 剧集内部文件名：纯集号（E01/S01E01）或 剧名 S01 E01
SERIES_FILE_OK = re.compile(
    r"^"
    r"([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\d·A-Za-z]+\s+[\w][\w\s\':,.\-&!()0-9]+\s+)?"
    r"("
    r"E\d{2,3}"
    r"|S\d{2}\s*E\d{2,3}"
    r"|E\d{2,3}-E\d{2,3}"
    r"|S\d{2}\s*E\d{2,3}-E\d{2,3}"
    r")"
    r"(\s*(END|V\d))?"
    r"(\s*\[[\w.\s]+\])?"
    r"\s*\."
    r"(mp4|mkv|avi|ts|rmvb|flv|wmv|mov)$",
    re.IGNORECASE,
)

# 特殊内容：SP（彩蛋/花絮/MV等）、花絮/特辑/番外等；纯「第1集」会被判不合规
SERIES_SPECIAL_OK = re.compile(
    r"^"
    r"([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\d·A-Za-z]+\s+[\w][\w\s\':,.\-&!()0-9]+\s+)?"
    r"(SP\d{2}(\s+[\u4e00-\u9fffA-Za-z]+)?"
    r"|花絮|特辑|彩蛋|预告|番外|幕后|特别篇|精华版|前传)"
    r"\.(mp4|mkv|avi|ts)$"
)

# 审查规避断词符（中文资源特有）
BLACKLIST_CHARS = re.compile(r"[丨｜]")

# 单字母替代汉字（中文资源特有，如 S探、Z义联盟）
LETTER_SUB = re.compile(
    r"(?:^[A-Z]{1,2}[\u4e00-\u9fff])"
    r"|(?:[\u4e00-\u9fff][A-Z]{1,3}[\u4e00-\u9fff])"
    r"|(?:[\u4e00-\u9fff][A-Z]{1,3}$)"
)

# ── plex profile regexes (English / Plex conventions) ────

# Movie folder: "Name (Year)" — year strongly expected; optional edition tag like
# "Name (Year) [Director's Cut]" is allowed, but tags before the year are not.
PLEX_MOVIE_DIR_OK = re.compile(r"^[^\[\]]+ \([12]\d{3}\)(\s*\[[^\]]+\])?$")


def plex_movie_file_ok(filename, folder_name):
    """Plex movie file: stem == folder name, allowing CD/part/_N suffixes."""
    stem = filename.rsplit(".", 1)[0]
    ext = filename.rsplit(".", 1)[-1].lower()
    if stem == folder_name:
        return True
    if stem.startswith(folder_name):
        suffix = stem[len(folder_name) :].strip()
        if re.match(r"^(-?\s*(CD\d+|part\d+|disc\d+|_\d+|\[.*\]))*$", suffix, re.IGNORECASE):
            return True
    return ext in SUB_EXTS and stem.startswith(folder_name)


# Episode file: must contain SxxEyy (or bare Eyy) and end with a video ext
PLEX_EPISODE_OK = re.compile(
    r"^(?=.*(?:\bS\d{1,2}E\d{2,3}\b|\bE\d{2,3}\b))"
    r"[^\n]*\.(mp4|mkv|avi|ts|rmvb|flv|wmv|mov)$",
    re.IGNORECASE,
)

# Season sub-folder (Plex: "Season 01" / "Season 1"; "Specials" allowed)
SEASON_DIR_OK = re.compile(r"^Season\s*\d+$", re.IGNORECASE)


# ── Generic blacklist (any profile) ──────────────────────

WATERMARK = re.compile(
    r"【|】|\[微信|\[公众号|￡|@圣城|Mp4Ba|XZYS|XunLeiJia|"
    r"kkkanba|字幕侠|霸王龙|压制组|微信|爱影哥|瞎看菌|雷锋菌|影喵儿|"
    r"情话菌|影视步行街|RARBG|STUTTERSHIT|SmY|CHAOSPACE",
    re.IGNORECASE,
)

PLACEHOLDER_ENGLISH = re.compile(
    r"\s+Erta\s*$|"
    r"\s+TBD\s*$|"
    r"\s+Unknown\s*$|"
    r"\s+XXX\s*$",
    re.IGNORECASE,
)


# ── old→new suggestions ─────────────────────────────────

_WATERMARK_TOKENS = re.compile(
    r"Mp4Ba|XZYS|XunLeiJia|kkkanba|字幕侠|霸王龙|压制组|"
    r"微信|爱影哥|瞎看菌|雷锋菌|影喵儿|情话菌|影视步行街|"
    r"RARBG|STUTTERSHIT|SmY|CHAOSPACE|圣城",
    re.IGNORECASE,
)


def _clean_name(name: str) -> str | None:
    """Remove mechanically fixable issues (watermarks/censorship/spaces)."""
    if not name:
        return None
    cleaned = _WATERMARK_TOKENS.sub("", name)
    cleaned = re.sub(r"【[^】]*】", "", cleaned)
    cleaned = re.sub(r"\[(微信|公众号)[^\]\[]*\]", "", cleaned)
    cleaned = re.sub(r"@圣城\S*", "", cleaned)
    cleaned = cleaned.replace("丨", "").replace("｜", "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    if cleaned == name or not cleaned:
        return None
    return cleaned


def suggest_new_name(name: str, is_dir: bool, folder_name: str | None = None) -> str | None:
    """Suggest a new name for one item; None when it cannot be fixed safely."""
    if not name:
        return None
    if is_dir and PLACEHOLDER_ENGLISH.search(name):
        return None
    if not is_dir:
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext in JUNK_EXTS or name.endswith(".bt.td"):
            return None
    return _clean_name(name)


def _suggest_series_filename(name: str, folder_name: str, plex: bool = False) -> str | None:
    """Rebuild an episode file name as `Show SXX EYY` (plex: `Show SXXEYY`)."""
    ext = name.rsplit(".", 1)[-1].lower()
    m = re.search(r"S(\d{1,2})\s*E(\d{2,3})|E(\d{2,3})", name, re.IGNORECASE)
    if not m:
        return None
    if m.group(1):
        season, ep = m.group(1), m.group(2)
        if "S" in folder_name.upper():
            base = f"{folder_name} E{ep}"
        elif plex:
            base = f"{folder_name} S{season.zfill(2)}E{ep}"
        else:
            base = f"{folder_name} S{season.zfill(2)} E{ep}"
    else:
        base = f"{folder_name} E{m.group(3)}"
    return f"{base}.{ext}"


def enrich_new_name(issue: dict, root: str, profile_key: str = "cn") -> str | None:
    """Attach a suggested new name for an issue; None if it can't be fixed."""
    path = issue["path"]
    name = issue["name"]
    is_dir = issue["is_dir"]
    problems = set(issue["problems"])
    plex = profile_key == "plex"

    cleaned = _clean_name(name)
    if cleaned:
        return cleaned

    if is_dir:
        return None

    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    parts = path.split("/")

    # movie video file → align to folder name
    if ext in VIDEO_EXTS and "MOVIE_VIDEO_MISMATCH" in problems and len(parts) >= 3:
        folder = parts[-2]
        if name.rsplit(".", 1)[0] != folder:
            return f"{folder}.{ext}"

    # series episode file → rebuild as  Show SXX EYY (plex: skip the "Season NN" level)
    if ext in VIDEO_EXTS and "SERIES_VIDEO_NAME" in problems and len(parts) >= 3:
        folder = parts[-2]
        if plex and len(parts) >= 4 and SEASON_DIR_OK.match(folder):
            folder = parts[-3]
        cand = _suggest_series_filename(name, folder, plex=plex)
        if cand:
            return cand

    return None


# ── data source walkers ──────────────────────────────────


def walk_local(root, depth=0):
    """Walk a local filesystem directory tree."""
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
    """Walk a ZSpace NAS directory via zspace-cli (50-item pagination)."""
    if depth > MAX_DEPTH:
        return
    start = 0
    while True:
        try:
            resp = client._post(
                "/v2/file/list", {"path": path, "start": start, "limit": 50, "show_hidden": 0}
            )
        except Exception:  # noqa: BLE001 - network/API error = end of listing
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


# ── profiles ─────────────────────────────────────────────


@dataclass(frozen=True)
class Profile:
    key: str
    zones: Zones
    validate: Callable[[dict, str, Zones], list[str]]


def _cn_checks(item) -> list[str]:
    """Profile-independent blacklist checks shared by all cn items."""
    name = item["name"]
    problems = []

    if BLACKLIST_CHARS.search(name):
        problems.append("BLACKLIST_CHAR")

    if WATERMARK.search(name):
        problems.append("WATERMARK")

    return problems


def validate(item, root, profile_key: str = "cn", zones: Zones | None = None) -> list[str]:
    """Return a list of stable problem codes. Empty list = compliant."""
    profile = PROFILES[profile_key]
    zones = zones or profile.zones
    return profile.validate(item, root, zones)


def _validate_cn(item, root, zones: Zones) -> list[str]:
    """Chinese naming conventions (cn profile)."""
    path = item["path"]
    name = item["name"]
    is_dir = item["is_dir"]
    problems = _cn_checks(item)

    rel = path.replace(root + "/", "") if path.startswith(root) else path
    ext = name.rsplit(".", 1)[-1].lower() if "." in name and not is_dir else ""
    stem = name.rsplit(".", 1)[0] if ext else name
    parts = rel.split("/")

    in_movie = _in_zone(path, zones.movie)
    in_series = _in_zone(path, zones.series)
    movie_dir = f"{root}/{zones.movie}/{name}"
    series_dir = f"{root}/{zones.series}/{name}"

    if not in_movie and not in_series:
        return []

    # 字母替代汉字检查 — 排除已知合规的模式
    clean_stem = re.sub(r"\[.*?\]|\(.*?\)", "", stem)
    if (
        LETTER_SUB.search(clean_stem)
        and not re.match(r"^[ES]\d", name)
        and not re.match(r"^(CD|4K|3D|2D|TV|HD|MP|ID)\d*", clean_stem)
        and not re.search(r"[a-z][A-Z]", clean_stem)
    ):
        problems.append("LETTER_SUB")

    if is_dir and PLACEHOLDER_ENGLISH.search(name):
        problems.append("PLACEHOLDER")

    if not is_dir and name.endswith(".bt.td"):
        problems.append("DOWNLOAD_RESIDUE")
        return problems

    if not is_dir and ext in JUNK_EXTS:
        problems.append("JUNK_FILE")
        return problems

    if in_movie:
        if is_dir and path == movie_dir and not MOVIE_DIR_OK.match(name):
            problems.append("MOVIE_FOLDER_NAME")
        if is_dir and path == movie_dir and re.search(r"\d+-\d+$", name):
            problems.append("COLLECTION_FOLDER")

        # 花絮子目录合规（花絮, 花絮 - XXX）
        if is_dir and re.match(r"^花絮(\s*-\s*.+)?$", name):
            return []

        if not is_dir and ext in VIDEO_EXTS:
            if any(re.match(r"^花絮", p) for p in parts[1:]):
                return []
            if len(parts) >= 3:
                folder = parts[1]
                if not movie_file_ok(name, folder):
                    problems.append("MOVIE_VIDEO_MISMATCH")

        if not is_dir and ext in SUB_EXTS and any(re.match(r"^花絮", p) for p in parts[1:]):
            return []

        # 散文件（直接在电影根目录）
        if not is_dir and path == movie_dir and ext in VIDEO_EXTS:
            problems.append("MOVIE_LOOSE_FILE")

    if in_series:
        if is_dir and path == series_dir and not SERIES_DIR_OK.match(name):
            problems.append("SERIES_FOLDER_NAME")

        if (
            not is_dir
            and ext in VIDEO_EXTS
            and len(parts) >= 3
            and not SERIES_FILE_OK.match(name)
            and not SERIES_SPECIAL_OK.match(name)
        ):
            problems.append("SERIES_VIDEO_NAME")

    if (
        not is_dir
        and ext in (VIDEO_EXTS | SUB_EXTS)
        and re.match(r"^[A-Za-z][\w.]+\.\d{4}\.", name)
    ):
        problems.append("PT_SCENE_NAME")

    if re.search(r"\.qsv\.|\.flv\.mp4$", name):
        problems.append("FORMAT_RESIDUE")

    return problems


def _validate_plex(item, root, zones: Zones) -> list[str]:
    """English / Plex naming conventions (plex profile)."""
    path = item["path"]
    name = item["name"]
    is_dir = item["is_dir"]
    problems = []

    if WATERMARK.search(name):
        problems.append("WATERMARK")

    rel = path.replace(root + "/", "") if path.startswith(root) else path
    ext = name.rsplit(".", 1)[-1].lower() if "." in name and not is_dir else ""
    parts = rel.split("/")

    in_movie = _in_zone(path, zones.movie)
    in_series = _in_zone(path, zones.series)
    movie_dir = f"{root}/{zones.movie}/{name}"

    if not in_movie and not in_series:
        return []

    if is_dir and PLACEHOLDER_ENGLISH.search(name):
        problems.append("PLACEHOLDER")

    if not is_dir and name.endswith(".bt.td"):
        problems.append("DOWNLOAD_RESIDUE")
        return problems

    if not is_dir and ext in JUNK_EXTS:
        problems.append("JUNK_FILE")
        return problems

    if in_movie:
        # movie folder: "Name (Year)"
        if is_dir and path == movie_dir and not PLEX_MOVIE_DIR_OK.match(name):
            problems.append("MOVIE_FOLDER_NAME")

        # movie video file: stem must match its folder name
        if not is_dir and ext in VIDEO_EXTS and len(parts) >= 3:
            folder = parts[-2]
            if not plex_movie_file_ok(name, folder):
                problems.append("MOVIE_VIDEO_MISMATCH")

        # loose movie file directly in the Movies root
        if not is_dir and path == movie_dir and ext in VIDEO_EXTS:
            problems.append("MOVIE_LOOSE_FILE")

    if in_series:
        # season sub-folder: "Season 01" (or "Specials")
        if (
            is_dir
            and len(parts) == 3
            and parts[0] == zones.series
            and not SEASON_DIR_OK.match(name)
            and name.lower() != "specials"
        ):
            problems.append("SERIES_SEASON_FOLDER")

        # episode file: must contain SxxEyy / Eyy
        if not is_dir and ext in VIDEO_EXTS and len(parts) >= 3 and not PLEX_EPISODE_OK.match(name):
            problems.append("SERIES_VIDEO_NAME")

    if (
        not is_dir
        and ext in (VIDEO_EXTS | SUB_EXTS)
        and re.match(r"^[A-Za-z][\w.]+\.\d{4}\.", name)
    ):
        problems.append("PT_SCENE_NAME")

    if re.search(r"\.qsv\.|\.flv\.mp4$", name):
        problems.append("FORMAT_RESIDUE")

    return problems


PROFILES: dict[str, Profile] = {
    "cn": Profile(key="cn", zones=CN_ZONES, validate=_validate_cn),
    "plex": Profile(key="plex", zones=PLEX_ZONES, validate=_validate_plex),
}


def find_duplicates(repeat_source, root, profile_key: str = "cn"):
    """Detect likely duplicate title folders by base-name de-duplication."""
    root = os.path.abspath(root)
    zones = PROFILES[profile_key].zones
    # 扫描点可以是父目录（电影/A）或 zone 目录本身（A）
    # 前者层级 = root+2，后者 = root+1
    root_is_zone = root.rstrip("/").rsplit("/", 1)[-1] in (zones.movie, zones.series)
    target_level = root.count("/") + (1 if root_is_zone else 2)
    dir_names = {}
    for item in repeat_source():
        item_path = os.path.abspath(item["path"])
        if item["is_dir"] and item_path.count("/") == target_level:
            name = item["name"]
            base = re.sub(r"\s*\[.*?\]", "", name)  # 去 [4K] [1080p] 等分辨率标签
            base = re.sub(r"\s*\(副本\d?\)", "", base)  # 去 (副本1) 后缀
            dir_names.setdefault(base.strip(), []).append((item_path, name))

    dups = []
    for base, entries in dir_names.items():
        if len(entries) > 1:
            for item_path, name in entries:
                dups.append(
                    {
                        "path": os.path.relpath(item_path, root),
                        "name": name,
                        "is_dir": True,
                        "problems": ["DUPLICATE"],
                        "dupe_count": len(entries),
                    }
                )
    return dups


# ── CLI ──────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Media library naming scanner (local / ZSpace / mounted backends)"
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="Scan root (required for --source local; default for zspace is /sata11/my/data/影视)",
    )
    parser.add_argument(
        "--source",
        choices=("local", "zspace"),
        default="local",
        help="Data source: local directory (default) or zspace NAS (needs zspace-cli)",
    )
    parser.add_argument(
        "--profile",
        choices=("cn", "plex"),
        default="cn",
        help="Naming conventions: cn=Chinese (default), plex=English/Plex",
    )
    parser.add_argument(
        "--movie-zone",
        default=None,
        help="Movie root folder name (default depends on profile: 电影 / Movies)",
    )
    parser.add_argument(
        "--series-zone",
        default=None,
        help="Series root folder name (default depends on profile: 剧集 / TV Shows)",
    )
    parser.add_argument(
        "--lang",
        choices=("auto", "zh", "en"),
        default="auto",
        help="Output language: auto (from locale), zh, or en",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    parser.add_argument("--preview", action="store_true", help="Show old→new rename suggestions")
    args = parser.parse_args()

    lang = detect_lang(args.lang if args.lang != "auto" else None)
    profile = PROFILES[args.profile]
    zones = Zones(
        movie=args.movie_zone or profile.zones.movie,
        series=args.series_zone or profile.zones.series,
    )

    def validate_item(item, root):
        return profile.validate(item, root, zones)

    def norm_root(r):
        return os.path.normpath(r) if r else r

    if args.source == "zspace":
        try:
            from zspace_cli import ZSpaceClient
        except ImportError:
            print(tr("need_zspace", lang), file=sys.stderr)
            sys.exit(1)
        root = norm_root(args.root or DEFAULT_ROOT)
        with ZSpaceClient() as c:
            _run(
                walk_zspace(c, root),
                validate_item,
                root,
                args.json,
                args.preview,
                lang,
                args.profile,
                lambda: walk_zspace(c, root),
            )
    else:
        root = norm_root(args.root or ".")
        if not os.path.isdir(root):
            print(tr("dir_not_found", lang, root=root), file=sys.stderr)
            sys.exit(1)
        _run(
            walk_local(root),
            validate_item,
            root,
            args.json,
            args.preview,
            lang,
            args.profile,
            lambda: walk_local(root),
        )


def _run(scan_all, validate_item, root, output_json, preview, lang, profile_key, repeat_source):
    root = os.path.normpath(root)
    print(tr("scanning", lang, root=root), file=sys.stderr)

    stats = {"dirs": 0, "files": 0}
    issues = []

    for item in scan_all:
        if item["is_dir"]:
            stats["dirs"] += 1
        else:
            stats["files"] += 1

        problems = validate_item(item, root)
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

    print(tr("done", lang, dirs=stats["dirs"], files=stats["files"]), file=sys.stderr)

    issues.extend(find_duplicates(repeat_source, root, profile_key))

    for issue in issues:
        issue["new_name"] = enrich_new_name(issue, root, profile_key)

    if output_json:
        json.dump(issues, sys.stdout, ensure_ascii=False, indent=2)
        return

    if not issues:
        print(tr("all_ok", lang))
        return

    if preview:
        previewable = [i for i in issues if i.get("new_name")]
        if previewable:
            print(tr("preview_title", lang, n=len(previewable)))
            for item in previewable:
                tag = "📁" if item["is_dir"] else "  "
                print(f"  {tag} {item['path']}")
                print(f"       → {item['new_name']}")
            print()

    by_type = {}
    for issue in issues:
        for p in issue["problems"]:
            by_type.setdefault(p, []).append(issue)

    print(tr("issues_found", lang, n=len(issues)))

    for ptype, items in sorted(by_type.items(), key=lambda x: -len(x[1])):
        label = tr(ptype, lang)
        print(tr("group_title", lang, label=label, n=len(items)))
        for item in items[:8]:
            tag = "📁" if item["is_dir"] else "  "
            print(f"  {tag} {item['path']}")
        if len(items) > 8:
            print(tr("more", lang, n=len(items) - 8))
        print()


if __name__ == "__main__":
    main()
