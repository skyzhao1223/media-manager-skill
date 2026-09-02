"""media-manager-skill — media library naming scanner (local / cloud / any NAS)."""

from media_manager_skill.scan import (
    PROBLEM_MESSAGES,
    Zones,
    detect_lang,
    find_duplicates,
    suggest_new_name,
    tr,
    validate,
    walk_local,
    walk_zspace,
)

__all__ = [
    "PROBLEM_MESSAGES",
    "Zones",
    "detect_lang",
    "find_duplicates",
    "suggest_new_name",
    "tr",
    "validate",
    "walk_local",
    "walk_zspace",
]
__version__ = "0.3.0"
