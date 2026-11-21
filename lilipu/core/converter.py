# -*- coding: utf-8 -*-
"""MusicXML → 简谱的核心算法。

只做“解析 + 映射”，不碰界面和文件导出：
- 调号取自谱面 ``KeySignature``，没有就回退到 1=C；
- 音级按调式音阶换算（C 大调的 C5 记作 ``1'``），升降号与音阶比对后按需标 ``#``/``b``；
- 时值交给 :mod:`lilipu.render.duration` 统一推导减时线/增时线/附点；
- 小节线按拍号长度自动插入。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..logging_setup import get_logger

logger = get_logger(__name__)

#: 简谱调名（升号写法，与 music21 的默认拼写一致）
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

_ACCIDENTAL_SYMBOL = {0: "", 1: "#", 2: "##", -1: "b", -2: "bb"}


# --------------------------------------------------------------------- 基础映射
def key_name_to_pc(name: str) -> int:
    """``"C#"`` → 1；无法识别时返回 0（按 C 处理）。"""
    name = (name or "C").strip()
    if name not in NOTE_NAMES:
        name = name.replace("♯", "#").replace("♭", "b")
        if name not in NOTE_NAMES:
            flat_map = {"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10}
            return flat_map.get(name, 0)
    return NOTE_NAMES.index(name)


def _key_object(meta: Optional[dict]):
    """从 ``meta`` 还原 music21 的 Key 对象（用于移调后重算音级）。"""
    from music21 import key

    meta = meta or {}
    raw = str(meta.get("key", "1=C")).split("=")[-1].strip() or "C"
    mode = str(meta.get("mode", "major") or "major")
    try:
        return key.Key(raw, mode)
    except Exception:
        return key.Key("C", "major")


def pitch_to_jianpu(pitch, key_obj) -> Tuple[str, int, str]:
    """把一个 music21 Pitch 映射成 ``(音级, 八度偏移, 升降号)``。

    八度偏移为正表示高八度（简谱加 ``'``），为负表示低八度（加 ``,``）。
    """
    from music21 import pitch as m21pitch

    tonic_pc = key_obj.tonic.pitchClass
    # 参照八度固定为 4，保证同一份谱子多次渲染结果稳定
    ref = m21pitch.Pitch(f"{key_obj.tonic.name}4")

    delta = pitch.diatonicNoteNum - ref.diatonicNoteNum
    degree = delta % 7 + 1
    octave = delta // 7

    scale = key_obj.getScale(key_obj.mode or "major").getPitches()
    natural_pc = scale[(degree - 1) % 7].pitchClass
    diff = (pitch.pitchClass - natural_pc + 6) % 12 - 6
    if abs(diff) > 2:
        diff = 0
    accidental = _ACCIDENTAL_SYMBOL.get(diff, "")

    if tonic_pc < 0:  # pragma: no cover - 理论上不会出现
        accidental = ""
    return str(degree), int(octave), accidental


def _octave_marks(octave: int) -> str:
    if octave > 0:
        return "'" * min(octave, 3)
    if octave < 0:
        return "," * min(-octave, 3)
    return ""


# --------------------------------------------------------------------- 文本输出
def note_token(element: dict) -> str:
    """单个音符在纯文本简谱里的写法。"""
    if element.get("type") == "bar":
        return "|"
    if element.get("type") == "rest":
        return "0"
    from ..render.duration import analyze_duration

    timing = analyze_duration(element.get("duration", 1.0), int(element.get("dots", 0) or 0))
    token = f"{element.get('accidental', '')}{element.get('num', '')}{_octave_marks(int(element.get('octave', 0) or 0))}"
    token += "." * timing["dots"]
    token += " -" * timing["dashes"]
    return token.strip()


def notes_to_text(notes: List[dict], measures_per_line: int = 4) -> str:
    """按小节分行输出纯文本简谱。"""
    if not notes:
        return ""
    measures: List[List[str]] = [[]]
    for element in notes:
        if element.get("type") == "bar":
            measures[-1].append("|")
            measures.append([])
        else:
            measures[-1].append(note_token(element))
    if measures and not measures[-1]:
        measures.pop()

    lines: List[str] = []
    for index in range(0, len(measures), max(1, measures_per_line)):
        chunk = measures[index:index + measures_per_line]
        parts = []
        for measure in chunk:
            tokens = [t for t in measure if t]
            if not tokens:
                continue
            parts.append(" ".join(tokens))
        if parts:
            lines.append(" ".join(parts))
    return "\n".join(lines)


# --------------------------------------------------------------------- 解析与转换
class JianpuConverter:
    """把 MusicXML（或含 MusicXML 的压缩包）转换成简谱数据。"""

    def __init__(self, measures_per_line: int = 4):
        self.measures_per_line = measures_per_line

    # -- 谱面信息 --
    @staticmethod
    def _first(stream_obj, cls):
        try:
            for element in stream_obj.recurse().getElementsByClass(cls):
                return element
        except Exception:
            pass
        return None

    def _detect_key(self, score, warnings: List[str]):
        from music21 import key

        key_sig = self._first(score, key.KeySignature)
        if key_sig is not None:
            try:
                return key_sig.asKey()
            except Exception:
                pass
        explicit = self._first(score, key.Key)
        if explicit is not None:
            return explicit

        warnings.append("谱面未标注调号，按 1=C 处理；如原谱是其他调，请在导出后手动移调。")
        return key.Key("C", "major")

    def _detect_time(self, score, warnings: List[str]):
        from music21 import meter

        ts = self._first(score, meter.TimeSignature)
        if ts is None:
            warnings.append("谱面未标注拍号，按 4/4 处理，小节线位置可能不准。")
            return "4/4", 4.0
        try:
            numerator, denominator = ts.numerator, ts.denominator
            return f"{numerator}/{denominator}", numerator * 4.0 / denominator
        except Exception:
            return "4/4", 4.0

    # -- 元素收集 --
    def _collect_elements(self, score, key_obj, measure_length: float,
                          warnings: List[str]) -> List[dict]:
        from music21 import chord, note as m21note

        parts = list(score.parts) if getattr(score, "parts", None) else [score]
        if len(parts) > 1:
            warnings.append(f"谱面包含 {len(parts)} 个声部，当前只转换第一个声部。")
        source = parts[0] if parts else score
        flat = source.flatten()
        events = list(flat.notesAndRests)

        elements: List[dict] = []
        chord_count = 0
        current_measure = 0

        for event in sorted(events, key=lambda e: float(getattr(e, "offset", 0.0) or 0.0)):
            offset = float(getattr(event, "offset", 0.0) or 0.0)
            measure_index = int(offset // measure_length + 1e-6)
            while measure_index > current_measure:
                elements.append({"type": "bar"})
                current_measure += 1

            duration = float(getattr(event.duration, "quarterLength", 1.0) or 1.0)
            dots = int(getattr(event.duration, "dots", 0) or 0)

            if isinstance(event, chord.Chord) and event.pitches:
                chord_count += 1
                pitch = max(event.pitches, key=lambda p: p.midi)
            elif isinstance(event, m21note.Note):
                pitch = event.pitch
            else:
                elements.append({"type": "rest", "num": "0", "duration": duration,
                                 "dots": dots, "offset": offset, "beat": offset})
                continue

            degree, octave, accidental = pitch_to_jianpu(pitch, key_obj)
            elements.append({
                "type": "note",
                "num": degree,
                "octave": octave,
                "accidental": accidental,
                "pname": pitch.nameWithOctave,
                "midi": int(pitch.midi),
                "duration": duration,
                "dots": dots,
                "beat": offset,
                "offset": offset,
            })

        if chord_count:
            warnings.append(f"发现 {chord_count} 处和弦，简谱线只保留最高音；需要完整和弦请导出 MusicXML 后另行处理。")
        if elements and elements[-1]["type"] != "bar":
            elements.append({"type": "bar"})
        return elements

    # -- 对外入口 --
    def convert(self, input_path: str, page: int = 1) -> Tuple[Optional[str], List[str], List[dict], dict]:
        """返回 ``(文本, 警告, 渲染数据, 元信息)``；失败时文本为 ``None``。"""
        warnings: List[str] = []
        try:
            from .music21_setup import configure_music21

            configure_music21()
            from music21 import converter as m21converter
        except Exception as exc:
            return None, [f"music21 不可用，无法解析 MusicXML：{exc}"], [], {}

        try:
            score = m21converter.parse(input_path)
        except Exception as exc:
            logger.exception("MusicXML 解析失败")
            return None, [f"无法解析谱面文件：{exc}"], [], {}

        try:
            key_obj = self._detect_key(score, warnings)
            time_label, measure_length = self._detect_time(score, warnings)
            notes = self._collect_elements(score, key_obj, measure_length, warnings)
        except Exception as exc:
            logger.exception("简谱映射失败")
            return None, [f"简谱转换失败：{exc}"], [], {}

        if not any(el.get("type") == "note" for el in notes):
            warnings.append("谱面中没有识别到音符。")
            return None, warnings, [], {}

        meta = {
            "key": f"1={key_obj.tonic.name}",
            "time": time_label,
            "mode": key_obj.mode or "major",
            "tonic_pc": int(key_obj.tonic.pitchClass),
            "measures": sum(1 for el in notes if el.get("type") == "bar"),
            "note_count": sum(1 for el in notes if el.get("type") == "note"),
        }
        text = notes_to_text(notes, self.measures_per_line)
        logger.info("转换完成: %s（%s，%d 个音符）", input_path, meta["key"], meta["note_count"])
        return text, warnings, notes, meta


# --------------------------------------------------------------------- 后处理工具
def transpose_notes(notes: List[dict], semitones: int, meta: Optional[dict]) -> Tuple[List[dict], dict]:
    """整体移调：保持调号不变，把音高上下移动若干半音，重新计算音级与升降号。"""
    from music21 import pitch as m21pitch

    if not semitones:
        return list(notes), dict(meta or {})
    key_obj = _key_object(meta)
    shifted: List[dict] = []
    for element in notes:
        if element.get("type") != "note" or not element.get("pname"):
            shifted.append(dict(element))
            continue
        pitch = m21pitch.Pitch(element["pname"]).transpose(int(semitones))
        degree, octave, accidental = pitch_to_jianpu(pitch, key_obj)
        item = dict(element)
        item.update({
            "num": degree,
            "octave": octave,
            "accidental": accidental,
            "pname": pitch.nameWithOctave,
            "midi": int(pitch.midi),
        })
        shifted.append(item)
    return shifted, dict(meta or {})


def autofix_notes(notes: List[dict]) -> Tuple[List[dict], List[str]]:
    """修掉明显不合理的数据，保证渲染不会因为脏数据崩掉。"""
    from ..render.duration import analyze_duration

    messages: List[str] = []
    fixed: List[dict] = []
    for element in notes:
        kind = element.get("type")
        if kind == "bar":
            if fixed and fixed[-1].get("type") == "bar":
                continue
            fixed.append(dict(element))
            continue
        if kind not in ("note", "rest"):
            continue
        num = str(element.get("num", "")).strip()
        if kind == "note" and num not in {"1", "2", "3", "4", "5", "6", "7"}:
            messages.append("丢弃了 1 个音级缺失的音符")
            continue
        item = dict(element)
        try:
            duration = float(item.get("duration", 1.0))
        except (TypeError, ValueError):
            duration = 1.0
        if duration <= 0:
            messages.append("修正了 1 个非法时值")
            duration = 1.0
        item["duration"] = analyze_duration(duration)["level"]
        fixed.append(item)
    if not fixed or fixed[-1].get("type") != "bar":
        fixed.append({"type": "bar"})
    return fixed, messages


def export_musicxml(notes: List[dict], meta: Optional[dict], output_path: str) -> str:
    """把当前简谱数据写回 MusicXML，方便进 MuseScore 继续编辑。"""
    from music21 import meter, note as m21note, stream as m21stream

    meta = meta or {}
    score = m21stream.Score()
    part = m21stream.Part()

    time_label = str(meta.get("time", "4/4"))
    try:
        numerator, denominator = (int(x) for x in time_label.split("/")[:2])
    except Exception:
        numerator, denominator = 4, 4
    part.insert(0, meter.TimeSignature(f"{numerator}/{denominator}"))

    offset = 0.0
    for element in notes:
        kind = element.get("type")
        if kind == "bar":
            continue
        duration = float(element.get("duration", 1.0) or 1.0)
        if kind == "rest":
            part.insert(offset, m21note.Rest(quarterLength=duration))
        else:
            pname = element.get("pname")
            if pname:
                part.insert(offset, m21note.Note(pname, quarterLength=duration))
            else:
                midi = int(element.get("midi", 60) or 60)
                part.insert(offset, m21note.Note(midi=midi, quarterLength=duration))
        offset += duration

    score.insert(0, part)
    score.write("musicxml", fp=output_path)
    return output_path
