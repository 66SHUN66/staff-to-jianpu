# -*- coding: utf-8 -*-
"""离谱 Lilipu —— 把五线谱图片转换成简谱的桌面工具。

对外只暴露版本与产品标识，具体功能见子模块：
  lilipu.core     识别与转换
  lilipu.render   印刷级简谱渲染
  lilipu.ui       Tkinter 界面
"""

__version__ = "9.0.0"
APP_NAME = "离谱"
APP_SUBTITLE = "五线谱转简谱"
APP_ID = "Lilipu"

#: 旧版数据目录名，用于自动迁移历史记录
LEGACY_APP_ID = "ScoreConverter"
