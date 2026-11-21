# -*- coding: utf-8 -*-
"""端到端转换测试：用 music21 现场生成 MusicXML，再转成简谱。"""

from __future__ import annotations

import pytest

music21 = pytest.importorskip("music21")

from music21 import key, meter, note, stream  # noqa: E402

from lilipu.core.converter import JianpuConverter  # noqa: E402


@pytest.fixture
def musicxml_file(tmp_path):
    score = stream.Score()
    part = stream.Part()
    part.insert(0, meter.TimeSignature("4/4"))
    part.insert(0, key.Key("C"))
    for pitch in ["C5", "D5", "E5", "F5", "G5", "A5", "B5", "C6"]:
        part.append(note.Note(pitch, quarterLength=0.5))
    score.insert(0, part)

    path = tmp_path / "sample.musicxml"
    score.write("musicxml", fp=str(path))
    return str(path)


def test_convert_basic(musicxml_file):
    text, warnings, notes, meta = JianpuConverter().convert(musicxml_file, 1)

    assert text, "应输出简谱文本"
    # C 大调下 C5 记作 1，往后依次为 2..7
    assert text.startswith("1")
    assert "|" in text, "应包含小节线"
    assert meta["key"] == "1=C"
    assert meta["time"] == "4/4"
    assert len(notes) >= 8, "8 个音符应全部进入渲染数据"
    assert isinstance(warnings, list)


def test_convert_missing_file_returns_error(tmp_path):
    text, warnings, notes, meta = JianpuConverter().convert(str(tmp_path / "nope.musicxml"), 1)
    assert text is None
    assert warnings
