#!/usr/bin/env python3
"""影视目录命名正向校验 —— 薄封装，真实实现见 media-manager-skill 包。

这样无论 `python scripts/scan.py` 还是 `pip install media-manager-skill` 后的
`mm-scan` 命令，跑的都是同一份核心代码。
"""

import sys

# 支持不安装直接跑本脚本：把仓库根的 src/ 加入 path
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from media_manager_skill.scan import main

if __name__ == "__main__":
    main()
