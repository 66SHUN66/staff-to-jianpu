# -*- coding: utf-8 -*-
"""路径与清理逻辑测试。"""

from __future__ import annotations

import os

from lilipu import APP_ID
from lilipu.paths import app_data_dir, cleanup_temp_dir, temp_dir


def test_app_data_dir_exists():
    path = app_data_dir()
    assert os.path.isdir(path)
    assert os.path.basename(path) == APP_ID


def test_temp_dir_exists():
    path = temp_dir()
    assert os.path.isdir(path)


def test_cleanup_temp_dir_returns_count():
    removed = cleanup_temp_dir(max_age_days=0)
    assert isinstance(removed, int)
    assert removed >= 0
