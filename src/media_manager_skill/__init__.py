"""media-manager-skill — 影视库命名扫描与整理（本地 / 云盘 / 各类 NAS）。"""

from media_manager_skill.scan import (
    find_duplicates,
    suggest_new_name,
    validate,
    walk_local,
    walk_zspace,
)

__all__ = ["find_duplicates", "suggest_new_name", "validate", "walk_local", "walk_zspace"]
__version__ = "0.2.0"
