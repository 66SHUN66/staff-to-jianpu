# -*- coding: utf-8 -*-
"""转换历史：只存文本与元信息，不存图片/音频路径，避免文件被清理后指向失效。"""

from __future__ import annotations

import json
import os
import time
import uuid

from ..logging_setup import get_logger
from ..paths import app_data_dir, legacy_data_dir

logger = get_logger(__name__)

MAX_TEXT = 20000


class HistoryManager:
    """最多保留 ``limit`` 条记录的 JSON 历史。"""

    def __init__(self, path: str | None = None, limit: int = 100):
        self.path = path or os.path.join(app_data_dir(), "history.json")
        self.limit = limit
        self._items = None

    # ---- 读写 ----
    def load(self) -> list:
        if self._items is not None:
            return self._items
        data = self._read(self.path)
        if data:
            self._items = data
        else:
            self._items = self._migrate_legacy()
        return self._items

    @staticmethod
    def _read(path: str) -> list:
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception as exc:
            logger.warning("历史记录读取失败: %s", exc)
            return []
        items = raw.get("items") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return []
        return [it for it in items if isinstance(it, dict)]

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"items": self._items}, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception as exc:
            logger.warning("历史记录保存失败: %s", exc)

    def _migrate_legacy(self) -> list:
        """首次升级时把旧版 ScoreConverter 目录下的历史接过来。"""
        legacy = os.path.join(legacy_data_dir(), "history.json")
        items = self._read(legacy)
        if items:
            self._items = items[: self.limit]
            self._save()
            logger.info("已从旧版目录迁移 %d 条历史记录", len(self._items))
        return items[: self.limit]

    # ---- 操作 ----
    def add(self, source: str, text: str, meta: dict | None = None,
            engine: str = "", warnings: list | None = None) -> dict:
        entry = {
            "id": uuid.uuid4().hex[:12],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            "source": os.path.basename(source or ""),
            "engine": engine,
            "text": (text or "")[:MAX_TEXT],
            "meta": meta or {},
            "warnings": list(warnings or []),
        }
        items = self.load()
        items.insert(0, entry)
        del items[self.limit:]
        self._items = items
        self._save()
        return entry

    def all(self) -> list:
        return list(self.load())

    def latest(self, count: int = 1) -> list:
        return self.load()[:count]

    def get(self, entry_id: str) -> dict | None:
        for item in self.load():
            if item.get("id") == entry_id:
                return item
        return None

    def delete(self, entry_id: str) -> bool:
        items = self.load()
        keep = [it for it in items if it.get("id") != entry_id]
        if len(keep) == len(items):
            return False
        self._items = keep
        self._save()
        return True

    def clear(self) -> None:
        self._items = []
        self._save()
