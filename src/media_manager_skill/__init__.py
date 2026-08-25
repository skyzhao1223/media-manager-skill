"""media-manager-skill — 影视库命名扫描与整理（本地 / 云盘 / 各类 NAS）。"""

from media_manager_skill.scan import validate, walk_local, walk_zspace

__all__ = ["validate", "walk_local", "walk_zspace"]
__version__ = "0.1.0"
