"""media-manager-skill 核心校验逻辑测试。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from media_manager_skill.scan import (
    enrich_new_name,
    find_duplicates,
    suggest_new_name,
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


# ── 电影目录 ─────────────────────────────────────────────


def test_valid_movie_folder(tmp_path: Path):
    name = "好东西 Her Story (2024) [4K]"
    assert validate(_item(str(tmp_path), f"电影/{name}", True), str(tmp_path)) == []


def test_invalid_movie_folder_missing_english(tmp_path: Path):
    problems = validate(_item(str(tmp_path), "电影/好东西 (2024)", True), str(tmp_path))
    assert "电影文件夹名不合规" in problems


def test_movie_collection_folder(tmp_path: Path):
    problems = validate(_item(str(tmp_path), "电影/钢铁侠 Iron Man 1-3", True), str(tmp_path))
    assert "合集文件夹(应拆分为独立文件夹)" in problems


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
    assert "电影视频文件名不匹配文件夹" in problems


def test_movie_loose_file(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "电影/好东西 Her Story (2024).mkv", False), str(tmp_path)
    )
    assert "电影散文件(应放入独立文件夹)" in problems


# ── 剧集目录 ─────────────────────────────────────────────


def test_valid_series_folder(tmp_path: Path):
    assert (
        validate(_item(str(tmp_path), "剧集/三体 Three-Body (2023) S01", True), str(tmp_path)) == []
    )


def test_invalid_series_folder(tmp_path: Path):
    problems = validate(_item(str(tmp_path), "剧集/三体", True), str(tmp_path))
    assert "剧集文件夹名不合规" in problems


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
    assert "剧集视频文件名不合规" in problems


def test_series_special(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "剧集/三体 Three-Body S01/三体 Three-Body SP01 彩蛋.mp4", False),
        str(tmp_path),
    )
    assert problems == []


# ── 黑名单 / 水印 / 占位符 ──────────────────────────────


def test_blacklist_char(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "电影/让丨子弹飞 让子弹飞 (2010)", True), str(tmp_path)
    )
    assert "审查规避字符(丨｜)" in problems


def test_watermark(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "电影/好东西 Her Story (2024)【Mp4Ba】.mkv", False), str(tmp_path)
    )
    assert "水印/站点标签" in problems


def test_placeholder_english(tmp_path: Path):
    problems = validate(_item(str(tmp_path), "电影/好东西 Erta", True), str(tmp_path))
    assert "占位符英文名(需查找正确英文名)" in problems


def test_junk_file(tmp_path: Path):
    problems = validate(
        _item(str(tmp_path), "电影/好东西 Her Story (2024)/bad.torrent", False), str(tmp_path)
    )
    assert "垃圾文件" in problems


def test_pt_scene_name(tmp_path: Path):
    problems = validate(
        _item(
            str(tmp_path), "剧集/三体 Three-Body S01/Game.of.Thrones.S01E01.2011.720p.mkv", False
        ),
        str(tmp_path),
    )
    assert "PT/Scene原始命名" in problems


# ── 区域外不检查 ────────────────────────────────────────


def test_outside_media_zone_ignored(tmp_path: Path):
    (tmp_path / "其它").mkdir()
    problems = validate(_item(str(tmp_path), "其它/随便一个文件.txt", False), str(tmp_path))
    assert problems == []


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
    assert any("疑似重复资源(2个)" in d["problems"][0] for d in dups)


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
        "problems": ["电影视频文件名不匹配文件夹"],
    }
    assert enrich_new_name(issue, "root") == "好东西 Her Story (2024).mkv"


def test_enrich_new_name_series_alignment():
    issue = {
        "path": "剧集/三体 Three-Body S01/第5集.mkv",
        "name": "第5集.mkv",
        "is_dir": False,
        "problems": ["剧集视频文件名不合规"],
    }
    assert enrich_new_name(issue, "root") is None  # 提取不出集号，不自动改


def test_enrich_new_name_series_with_episode():
    issue = {
        "path": "剧集/三体 Three-Body S01/Three.Body.2011.S01E01.720p.mkv",
        "name": "Three.Body.2011.S01E01.720p.mkv",
        "is_dir": False,
        "problems": ["剧集视频文件名不合规", "PT/Scene原始命名"],
    }
    # PT 名不合规，但可提取 S01E01 重组为规范名
    assert enrich_new_name(issue, "root") == "三体 Three-Body S01 E01.mkv"


def test_enrich_new_name_clean_watermark():
    issue = {
        "path": "电影/煎饼侠 Jian Bing Man (2015)/煎饼侠 Jian Bing Man (2015) Mp4Ba.mkv",
        "name": "煎饼侠 Jian Bing Man (2015) Mp4Ba.mkv",
        "is_dir": False,
        "problems": ["水印/站点标签"],
    }
    assert enrich_new_name(issue, "root") == "煎饼侠 Jian Bing Man (2015).mkv"


# ── JSON 输出包含重复资源（回归：原本 --json 漏检） ─────


def test_json_mode_includes_duplicates(tmp_path: Path, capsys):
    root = str(tmp_path)
    (tmp_path / "电影" / "A (2024) [4K]").mkdir(parents=True)
    (tmp_path / "电影" / "A (2024) [1080p]").mkdir()

    from media_manager_skill.scan import _run

    _run(
        walk_local(root),
        validate,
        root,
        output_json=True,
        preview=False,
        repeat_source=lambda: walk_local(root),
    )
    out = json.loads(capsys.readouterr().out)
    paths = [i["path"] for i in out]
    assert "电影/A (2024) [4K]" in paths
    assert "电影/A (2024) [1080p]" in paths
    assert any("疑似重复资源" in " ".join(i["problems"]) for i in out)
