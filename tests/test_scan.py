"""media-manager-skill 核心校验逻辑测试（cn + plex profile + i18n）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from media_manager_skill.scan import (
    Zones,
    detect_lang,
    enrich_new_name,
    find_duplicates,
    suggest_new_name,
    tr,
    validate,
    walk_local,
)


def _item(root: str, rel: str, is_dir: bool):
    return {
        "path": os.path.join(root, rel),
        "name": rel.rsplit("/", 1)[-1],
        "is_dir": is_dir,
        "depth": rel.count("/"),
    }


# ── 数据源遍历 ───────────────────────────────────────────


def test_walk_local_recursive(tmp_path: Path):
    (tmp_path / "剧集").mkdir()
    (tmp_path / "剧集" / "三体 Three-Body S01").mkdir()
    (tmp_path / "剧集" / "三体 Three-Body S01" / "E01.mp4").write_text("x")
    (tmp_path / "电影").mkdir()

    names = [i["name"] for i in walk_local(str(tmp_path))]
    assert "剧集" in names
    assert "三体 Three-Body S01" in names
    assert "E01.mp4" in names


# ── i18n ─────────────────────────────────────────────────


def test_tr_localizes_codes():
    assert tr("JUNK_FILE", "zh") == "垃圾文件"
    assert tr("JUNK_FILE", "en") == "Junk file"
    assert tr("DUPLICATE", "en") == "Possible duplicate"


def test_detect_lang():
    assert detect_lang("zh") == "zh"
    assert detect_lang("en") == "en"
    assert detect_lang(None) in ("zh", "en")


# ── 电影目录（cn） ───────────────────────────────────────


def test_valid_movie_folder(tmp_path: Path):
    name = "好东西 Her Story (2024) [4K]"
    assert validate(_item(str(tmp_path), f"电影/{name}", True), str(tmp_path)) == []


def test_invalid_movie_folder_missing_english(tmp_path: Path):
    problems = validate(_item(str(tmp_path), "电影/好东西 (2024)", True), str(tmp_path))
    assert "MOVIE_FOLDER_NAME" in problems


def test_movie_collection_folder(tmp_path: Path):
    problems = validate(_item(str(tmp_path), "电影/钢铁侠 Iron Man 1-3", True), str(tmp_path))
    assert "COLLECTION_FOLDER" in problems


def test_movie_video_matches_folder(tmp_path: Path):
    folder = "好东西 Her Story (2024) [4K]"
    problems = validate(_item(str(tmp_path), f"电影/{folder}/{folder}.mkv", False), str(tmp_path))
    assert problems == []


def test_movie_video_matches_folder_with_cd_suffix(tmp_path: Path):
    folder = "好东西 Her Story (2024) [4K]"
    problems = validate(
        _item(str(tmp_path), f"电影/{folder}/{folder} CD1.mkv", False), str(tmp_path)
    )
    assert problems == []


def test_movie_video_mismatch_folder(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "电影/好东西 Her Story (2024)/wrong name.mkv", False), str(tmp_path)
    )
    assert "MOVIE_VIDEO_MISMATCH" in problems


def test_movie_loose_file(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "电影/好东西 Her Story (2024).mkv", False), str(tmp_path)
    )
    assert "MOVIE_LOOSE_FILE" in problems


# ── 剧集目录（cn） ───────────────────────────────────────


def test_valid_series_folder(tmp_path: Path):
    assert (
        validate(_item(str(tmp_path), "剧集/三体 Three-Body (2023) S01", True), str(tmp_path)) == []
    )


def test_invalid_series_folder(tmp_path: Path):
    problems = validate(_item(str(tmp_path), "剧集/三体", True), str(tmp_path))
    assert "SERIES_FOLDER_NAME" in problems


def test_valid_series_file_with_prefix(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "剧集/三体 Three-Body S01/三体 Three-Body S01 E01.mp4", False),
        str(tmp_path),
    )
    assert problems == []


def test_valid_series_file_no_prefix(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "剧集/三体 Three-Body S01/E01.mp4", False), str(tmp_path)
    )
    assert problems == []


def test_lowercase_series_file_ok(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "剧集/三体 Three-Body S01/s01e02.mp4", False), str(tmp_path)
    )
    assert problems == []


def test_invalid_series_file(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "剧集/三体 Three-Body S01/第1集.mp4", False), str(tmp_path)
    )
    assert "SERIES_VIDEO_NAME" in problems


def test_series_special(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "剧集/三体 Three-Body S01/三体 Three-Body SP01 彩蛋.mp4", False),
        str(tmp_path),
    )
    assert problems == []


# ── 黑名单 / 水印 / 占位符（cn） ────────────────────────


def test_blacklist_char(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "电影/让丨子弹飞 让子弹飞 (2010)", True), str(tmp_path)
    )
    assert "BLACKLIST_CHAR" in problems


def test_watermark(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "电影/好东西 Her Story (2024)【Mp4Ba】.mkv", False), str(tmp_path)
    )
    assert "WATERMARK" in problems


def test_placeholder_english(tmp_path: Path):
    problems = validate(_item(str(tmp_path), "电影/好东西 Erta", True), str(tmp_path))
    assert "PLACEHOLDER" in problems


def test_junk_file(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "电影/好东西 Her Story (2024)/bad.torrent", False), str(tmp_path)
    )
    assert "JUNK_FILE" in problems


def test_pt_scene_name(tmp_path: Path):
    problems = validate(
        _item(
            str(tmp_path), "剧集/三体 Three-Body S01/Game.of.Thrones.S01E01.2011.720p.mkv", False
        ),
        str(tmp_path),
    )
    assert "PT_SCENE_NAME" in problems


# ── 区域外不检查 ────────────────────────────────────────


def test_outside_media_zone_ignored(tmp_path: Path):
    (tmp_path / "其它").mkdir()
    problems = validate(_item(str(tmp_path), "其它/随便一个文件.txt", False), str(tmp_path))
    assert problems == []


# ── plex profile（英文规范） ─────────────────────────────


def test_plex_valid_movie_folder(tmp_path: Path):
    name = "The Shawshank Redemption (1994)"
    problems = validate(
        _item(str(tmp_path), f"Movies/{name}", True), str(tmp_path), profile_key="plex"
    )
    assert problems == []


def test_plex_invalid_movie_folder_missing_year(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "Movies/The Shawshank Redemption", True),
        str(tmp_path),
        profile_key="plex",
    )
    assert "MOVIE_FOLDER_NAME" in problems


def test_plex_valid_movie_file(tmp_path: Path):
    folder = "The Shawshank Redemption (1994)"
    problems = validate(
        _item(str(tmp_path), f"Movies/{folder}/{folder}.mkv", False),
        str(tmp_path),
        profile_key="plex",
    )
    assert problems == []


def test_plex_movie_file_cd_suffix(tmp_path: Path):
    folder = "The Shawshank Redemption (1994)"
    problems = validate(
        _item(str(tmp_path), f"Movies/{folder}/{folder} - CD1.mkv", False),
        str(tmp_path),
        profile_key="plex",
    )
    assert problems == []


def test_plex_movie_file_mismatch(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "Movies/The Shawshank Redemption (1994)/wrong.mkv", False),
        str(tmp_path),
        profile_key="plex",
    )
    assert "MOVIE_VIDEO_MISMATCH" in problems


def test_plex_loose_movie_file(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "Movies/Inception (2010).mkv", False),
        str(tmp_path),
        profile_key="plex",
    )
    assert "MOVIE_LOOSE_FILE" in problems


def test_plex_valid_season_folder(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "TV Shows/Breaking Bad/Season 01", True),
        str(tmp_path),
        profile_key="plex",
    )
    assert problems == []


def test_plex_invalid_season_folder(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "TV Shows/Breaking Bad/Seasonone", True),
        str(tmp_path),
        profile_key="plex",
    )
    assert "SERIES_SEASON_FOLDER" in problems


def test_plex_valid_episode(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "TV Shows/Breaking Bad/Season 01/Breaking.Bad.S01E01.720p.mkv", False),
        str(tmp_path),
        profile_key="plex",
    )
    assert problems == []


def test_plex_invalid_episode(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "TV Shows/Breaking Bad/Season 01/episode1.mkv", False),
        str(tmp_path),
        profile_key="plex",
    )
    assert "SERIES_VIDEO_NAME" in problems


def test_plex_no_censorship_checks(tmp_path: Path):
    # 字母替代汉字 / 断词符检查是 cn 专属，plex 不判
    problems = validate(
        _item(str(tmp_path), "Movies/S探 Something (2020)", True), str(tmp_path), profile_key="plex"
    )
    assert "LETTER_SUB" not in problems
    assert "BLACKLIST_CHAR" not in problems


# ── 分区目录可配置 ───────────────────────────────────────


def test_custom_zones(tmp_path: Path):
    zones = Zones(movie="Films", series="Shows")
    name = "The Matrix (1999)"
    problems = validate(
        _item(str(tmp_path), f"Films/{name}", True), str(tmp_path), profile_key="plex", zones=zones
    )
    assert problems == []
    problems = validate(
        _item(str(tmp_path), "Films/NoYear", True), str(tmp_path), profile_key="plex", zones=zones
    )
    assert "MOVIE_FOLDER_NAME" in problems


def test_custom_zones_cn(tmp_path: Path):
    zones = Zones(movie="影片", series="连续剧")
    problems = validate(
        _item(str(tmp_path), "影片/好东西 (2024)", True), str(tmp_path), zones=zones
    )
    assert "MOVIE_FOLDER_NAME" in problems


# ── 重复资源检测 ─────────────────────────────────────────


def test_find_duplicates(tmp_path: Path):
    root = str(tmp_path)
    dirs = [
        {"path": f"{root}/电影/A (2024) [4K]", "name": "A (2024) [4K]", "is_dir": True, "depth": 2},
        {
            "path": f"{root}/电影/A (2024) [1080p]",
            "name": "A (2024) [1080p]",
            "is_dir": True,
            "depth": 2,
        },
        {"path": f"{root}/电影/B (2024)", "name": "B (2024)", "is_dir": True, "depth": 2},
    ]
    dups = find_duplicates(lambda: iter(dirs), root)
    dup_paths = {d["name"] for d in dups}
    assert dup_paths == {"A (2024) [4K]", "A (2024) [1080p]"}
    assert all(d["problems"] == ["DUPLICATE"] for d in dups)
    assert all(d["dupe_count"] == 2 for d in dups)


def test_find_duplicates_keeps_year_distinct(tmp_path: Path):
    # 同名不同年份是两部电影，不应判重复
    root = str(tmp_path)
    dirs = [
        {"path": f"{root}/电影/哥斯拉 (1998)", "name": "哥斯拉 (1998)", "is_dir": True, "depth": 2},
        {"path": f"{root}/电影/哥斯拉 (2014)", "name": "哥斯拉 (2014)", "is_dir": True, "depth": 2},
    ]
    assert find_duplicates(lambda: iter(dirs), root) == []


# ── old→new 建议 ────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "is_dir", "expected"),
    [
        ("煎饼侠 Jian Bing Man (2015) Mp4Ba.mkv", False, "煎饼侠 Jian Bing Man (2015).mkv"),
        ("让丨子弹飞 让子弹飞 (2010)", True, "让子弹飞 让子弹飞 (2010)"),
        ("好东西 Her Story (2024) Erta", True, None),  # 占位符需人工
        ("垃圾.torrent", False, None),  # 垃圾文件应删除
    ],
)
def test_suggest_new_name(name, is_dir, expected):
    assert suggest_new_name(name, is_dir) == expected


def test_enrich_new_name_movie_alignment():
    issue = {
        "path": "电影/好东西 Her Story (2024)/wrong name.mkv",
        "name": "wrong name.mkv",
        "is_dir": False,
        "problems": ["MOVIE_VIDEO_MISMATCH"],
    }
    assert enrich_new_name(issue, "root") == "好东西 Her Story (2024).mkv"


def test_enrich_new_name_series_alignment():
    issue = {
        "path": "剧集/三体 Three-Body S01/第5集.mkv",
        "name": "第5集.mkv",
        "is_dir": False,
        "problems": ["SERIES_VIDEO_NAME"],
    }
    assert enrich_new_name(issue, "root") is None  # 提取不出集号，不自动改


def test_enrich_new_name_series_with_episode():
    issue = {
        "path": "剧集/三体 Three-Body S01/Three.Body.2011.S01E01.720p.mkv",
        "name": "Three.Body.2011.S01E01.720p.mkv",
        "is_dir": False,
        "problems": ["SERIES_VIDEO_NAME", "PT_SCENE_NAME"],
    }
    # PT 名不合规，但可提取 S01E01 重组为规范名
    assert enrich_new_name(issue, "root") == "三体 Three-Body S01 E01.mkv"


def test_enrich_new_name_clean_watermark():
    issue = {
        "path": "电影/煎饼侠 Jian Bing Man (2015)/煎饼侠 Jian Bing Man (2015) Mp4Ba.mkv",
        "name": "煎饼侠 Jian Bing Man (2015) Mp4Ba.mkv",
        "is_dir": False,
        "problems": ["WATERMARK"],
    }
    assert enrich_new_name(issue, "root") == "煎饼侠 Jian Bing Man (2015).mkv"


def test_enrich_new_name_plex_episode_uses_show_not_season():
    # plex 结构 TV Shows/Show/Season 01/file —— 剧名取 Show 而非 Season 01
    issue = {
        "path": "TV Shows/Breaking Bad/Season 01/three.body.S01E01.mkv",
        "name": "three.body.S01E01.mkv",
        "is_dir": False,
        "problems": ["SERIES_VIDEO_NAME"],
    }
    assert enrich_new_name(issue, "root", profile_key="plex") == "Breaking Bad S01E01.mkv"


def test_enrich_new_name_plex_flat_episode(tmp_path: Path):
    # plex 单季无 Season 层：TV Shows/Show/file
    issue = {
        "path": "TV Shows/Breaking Bad/s01e01.mkv",
        "name": "s01e01.mkv",
        "is_dir": False,
        "problems": ["SERIES_VIDEO_NAME"],
    }
    assert enrich_new_name(issue, "root", profile_key="plex") == "Breaking Bad S01E01.mkv"


# ── JSON 输出包含重复资源与码（回归） ───────────────────


def test_json_mode_includes_duplicates(tmp_path: Path, capsys):
    root = str(tmp_path)
    (tmp_path / "电影" / "A (2024) [4K]").mkdir(parents=True)
    (tmp_path / "电影" / "A (2024) [1080p]").mkdir()

    from media_manager_skill.scan import _run

    _run(
        walk_local(root),
        lambda item, r: validate(item, r),
        root,
        output_json=True,
        preview=False,
        lang="en",
        profile_key="cn",
        repeat_source=lambda: walk_local(root),
    )
    out = json.loads(capsys.readouterr().out)
    paths = [i["path"] for i in out]
    assert "电影/A (2024) [4K]" in paths
    assert "电影/A (2024) [1080p]" in paths
    assert any("DUPLICATE" in i["problems"] for i in out)
