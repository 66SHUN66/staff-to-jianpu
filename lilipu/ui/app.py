# -*- coding: utf-8 -*-
"""桌面界面：文件列表 + 简谱文本 / 预览图 / 历史记录。

原则是“说清楚能力边界”：
- 标题栏显示真实版本号（唯一来源 ``lilipu.__version__``）；
- 右上角引擎标签可点击，解释当前引擎能做什么、不能做什么；
- OpenCV 草图模式的结果页会插入醒目的能力提示。
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import APP_NAME, APP_SUBTITLE, __version__
from ..core.converter import autofix_notes, export_musicxml, notes_to_text, transpose_notes
from ..core.environment import EnvironmentChecker
from ..core.pipeline import ScoreConverter
from ..logging_setup import get_logger, setup_logging
from ..paths import cleanup_temp_dir, resource_path, temp_dir
from ..render import render_to_png

logger = get_logger(__name__)

IMAGE_TYPES = [("图片", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"), ("所有文件", "*.*")]
ALL_TYPES = [("谱面文件", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.pdf"), ("所有文件", "*.*")]

SKETCH_TITLE = "⚠ 音高草图模式"
SKETCH_DETAIL = (
    "OpenCV 模式只按纵向位置估算音高，没有调号、节拍、小节线与和弦信息。\n"
    "想要可用简谱：安装 Audiveris（自带 Java）后重启本程序即可。"
)


class LilipuApp:
    """主窗口。"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{__version__} · {APP_SUBTITLE}")
        self.root.geometry("1180x780")
        self.root.minsize(980, 640)
        self._set_window_icon()

        self.converter = ScoreConverter()
        self.history = self.converter.history
        self.paths: list[str] = []
        self.result = None
        self.results: list = []
        self.env_info: dict = {}
        self._queue: queue.Queue = queue.Queue()
        self._busy = False
        self._preview_image = None

        self._build_style()
        self._build_widgets()
        self._refresh_history()
        self._start_env_probe()
        self.root.after(120, self._poll_queue)

    # ---------------------------------------------------------------- 外观
    def _set_window_icon(self) -> None:
        try:
            from ..icon import ensure_icon

            icon = ensure_icon()
            if icon:
                self.root.iconbitmap(default=icon)
        except Exception:
            logger.debug("窗口图标设置失败，忽略", exc_info=True)

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Toolbar.TFrame", background="#f4f4f6")
        style.configure("Header.TLabel", font=("Microsoft YaHei UI", 16, "bold"))
        style.configure("Sub.TLabel", font=("Microsoft YaHei UI", 9), foreground="#666")
        style.configure("Warn.TLabel", foreground="#b45309", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Status.TLabel", foreground="#555")

    def _build_widgets(self) -> None:
        header = ttk.Frame(self.root, padding=(14, 10, 14, 6))
        header.pack(fill="x")

        ttk.Label(header, text=f"{APP_NAME} · {APP_SUBTITLE}",
                  style="Header.TLabel").pack(side="left")
        ttk.Label(header, text=f"v{__version__}", style="Sub.TLabel").pack(side="left", padx=(8, 0))

        self.engine_label = ttk.Label(header, text="引擎：检测中…", foreground="#7c3aed", cursor="hand2")
        self.engine_label.pack(side="right")
        self.engine_label.bind("<Button-1>", lambda _e: self._show_engine_help())

        toolbar = ttk.Frame(self.root, padding=(14, 0, 14, 8), style="Toolbar.TFrame")
        toolbar.pack(fill="x")

        self.btn_add = ttk.Button(toolbar, text="添加图片/PDF", command=self._add_files)
        self.btn_add.pack(side="left")
        ttk.Button(toolbar, text="示例", command=self._load_example).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="清空", command=self._clear).pack(side="left", padx=(6, 0))

        ttk.Label(toolbar, text="引擎").pack(side="left", padx=(16, 4))
        self.engine_var = tk.StringVar(value="auto")
        ttk.Combobox(toolbar, textvariable=self.engine_var, width=10, state="readonly",
                     values=["auto", "audiveris", "opencv"]).pack(side="left")

        self.btn_run = ttk.Button(toolbar, text="开始识别", command=self._run)
        self.btn_run.pack(side="left", padx=(12, 0))

        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=14, pady=(0, 8))

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        left = ttk.Frame(body)
        body.add(left, weight=1)
        ttk.Label(left, text="待识别文件").pack(anchor="w")
        list_wrap = ttk.Frame(left)
        list_wrap.pack(fill="both", expand=True, pady=(4, 0))
        self.file_list = tk.Listbox(list_wrap, activestyle="none", selectmode="extended")
        scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scroll.set)
        self.file_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        right = ttk.Frame(body)
        body.add(right, weight=4)
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        text_tab = ttk.Frame(self.notebook)
        self.notebook.add(text_tab, text="简谱文本")
        self.text = tk.Text(text_tab, wrap="word", font=("Consolas", 15), undo=True)
        text_scroll = ttk.Scrollbar(text_tab, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=text_scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        text_scroll.pack(side="right", fill="y")

        image_tab = ttk.Frame(self.notebook)
        self.notebook.add(image_tab, text="简谱图片")
        self.canvas = tk.Canvas(image_tab, background="#ededed", highlightthickness=0)
        canvas_scroll = ttk.Scrollbar(image_tab, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=canvas_scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        canvas_scroll.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", lambda _e: self._render_preview())

        history_tab = ttk.Frame(self.notebook)
        self.notebook.add(history_tab, text="历史记录")
        columns = ("time", "source", "key", "time2", "count")
        self.history_tree = ttk.Treeview(history_tab, columns=columns, show="headings", height=12)
        for column, title, width in (
            ("time", "时间", 150), ("source", "来源", 260), ("key", "调号", 90),
            ("time2", "拍号", 80), ("count", "音符数", 80),
        ):
            self.history_tree.heading(column, text=title)
            self.history_tree.column(column, width=width, anchor="w")
        self.history_tree.pack(side="left", fill="both", expand=True)
        history_side = ttk.Frame(history_tab, padding=8)
        history_side.pack(side="right", fill="y")
        ttk.Button(history_side, text="载入选中", command=self._load_history_item).pack(fill="x")
        ttk.Button(history_side, text="清空历史", command=self._clear_history).pack(fill="x", pady=(6, 0))
        self.history_tree.bind("<Double-1>", lambda _e: self._load_history_item())

        actions = ttk.Frame(self.root, padding=(14, 0, 14, 6))
        actions.pack(fill="x")
        for text, command in (
            ("复制文本", self._copy_text),
            ("导出TXT", self._export_text),
            ("导出PNG", self._export_png),
            ("导出SVG", self._export_svg),
            ("导出MusicXML", self._export_musicxml),
        ):
            ttk.Button(actions, text=text, command=command).pack(side="left", padx=(0, 6))

        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Button(actions, text="降半音", command=lambda: self._transpose(-1)).pack(side="left", padx=(0, 4))
        ttk.Button(actions, text="升半音", command=lambda: self._transpose(1)).pack(side="left", padx=(0, 4))
        ttk.Button(actions, text="自动修复", command=self._autofix).pack(side="left", padx=(0, 4))
        ttk.Button(actions, text="播放(MIDI)", command=self._play).pack(side="left")

        self.status = ttk.Label(self.root, text="就绪", style="Status.TLabel", padding=(14, 4))
        self.status.pack(fill="x")

    # ---------------------------------------------------------------- 引擎信息
    def _start_env_probe(self) -> None:
        def probe():
            try:
                info = EnvironmentChecker(probe_version=False).check()
            except Exception as exc:  # pragma: no cover - 界面兜底
                info = {"engine_label": f"引擎检测失败：{exc}", "suggestion": str(exc)}
            self._queue.put(("env", info))

        threading.Thread(target=probe, daemon=True).start()

    def _show_engine_help(self) -> None:
        info = self.env_info or {}
        messagebox.showinfo(
            "引擎说明",
            f"{info.get('engine_label', '引擎状态未知')}\n\n{info.get('suggestion', '')}\n\n"
            "Audiveris 模式：识别调号、拍号、升降号、和弦，可导出 MusicXML。\n"
            "OpenCV 模式：只估音高轮廓，不识别调号/节奏/小节线，仅供快速参考。",
        )

    # ---------------------------------------------------------------- 文件
    def _add_files(self) -> None:
        selected = filedialog.askopenfilenames(title="选择谱面图片或 PDF", filetypes=ALL_TYPES)
        if selected:
            self._append_files(list(selected))

    def _append_files(self, paths: list[str]) -> None:
        for path in paths:
            if path and path not in self.paths:
                self.paths.append(path)
                self.file_list.insert("end", os.path.basename(path))
        self._set_status(f"已添加 {len(self.paths)} 个文件")

    def _load_example(self) -> None:
        example_dir = resource_path("assets", "examples")
        if not os.path.isdir(example_dir):
            messagebox.showinfo("没有示例", "当前安装包未附带示例图片，你可以直接添加自己的谱面。")
            return
        files = [os.path.join(example_dir, name) for name in sorted(os.listdir(example_dir))]
        files = [f for f in files if os.path.splitext(f)[1].lower() in (
            ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".pdf")]
        if not files:
            messagebox.showinfo("没有示例", "示例目录里没有图片文件。")
            return
        self._append_files(files)

    def _clear(self) -> None:
        self.paths.clear()
        self.file_list.delete(0, "end")
        self.result = None
        self.results = []
        self.text.delete("1.0", "end")
        self.canvas.delete("all")
        self._preview_image = None
        self.progress["value"] = 0
        self._set_status("就绪")

    # ---------------------------------------------------------------- 运行
    def _run(self) -> None:
        if self._busy:
            return
        if not self.paths:
            messagebox.showinfo("还没有文件", "先点「添加图片/PDF」选择谱面。")
            return

        self._busy = True
        self.btn_run.configure(state="disabled")
        self.results = []
        engine = self.engine_var.get()

        def worker():
            def progress(stage: str, fraction: float):
                self._queue.put(("progress", (stage, fraction)))

            try:
                results = self.converter.convert_files(self.paths, engine, progress)
                self._queue.put(("done", results))
            except Exception as exc:
                logger.exception("批量转换失败")
                self._queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "env":
                    self.env_info = payload
                    self.engine_label.configure(text=payload.get("engine_label", "引擎：未知"))
                elif kind == "progress":
                    stage, fraction = payload
                    self.progress["value"] = max(0, min(100, fraction * 100))
                    self._set_status(stage)
                elif kind == "done":
                    self._on_done(payload)
                elif kind == "error":
                    self._on_error(payload)
        except queue.Empty:
            pass
        finally:
            self.root.after(120, self._poll_queue)

    def _on_done(self, results: list) -> None:
        self._busy = False
        self.btn_run.configure(state="normal")
        self.results = results
        ok_results = [r for r in results if r.ok]
        failed = [r for r in results if not r.ok]

        if ok_results:
            self.result = ok_results[0]
            self._show_result(self.result)
            self._refresh_history()
            self.progress["value"] = 100
            self._set_status(f"完成：成功 {len(ok_results)}，失败 {len(failed)}")
        else:
            self.progress["value"] = 0
            self._set_status(f"全部失败（{len(failed)} 个）")
            detail = "\n\n".join(f"{os.path.basename(r.source)}：{r.error}" for r in failed[:5])
            messagebox.showwarning("识别失败", detail or "没有可用结果。")

        if failed and ok_results:
            messagebox.showinfo("部分文件失败", "\n".join(
                f"{os.path.basename(r.source)}：{r.error}" for r in failed[:5]))

    def _on_error(self, message: str) -> None:
        self._busy = False
        self.btn_run.configure(state="normal")
        self.progress["value"] = 0
        self._set_status("失败")
        messagebox.showerror("出错了", message)

    # ---------------------------------------------------------------- 展示
    def _show_result(self, result) -> None:
        warnings = list(result.warnings or [])
        text = result.text or ""
        if result.has_sketch():
            text = f"{SKETCH_TITLE}\n{SKETCH_DETAIL}\n\n{text}"
        elif warnings:
            text = "提示：\n" + "\n".join(f"- {w}" for w in warnings) + "\n\n" + text

        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.notebook.select(0)
        self._render_preview()

    def _render_preview(self) -> None:
        self.canvas.delete("all")
        self._preview_image = None
        if not self.result or not self.result.png_path or not os.path.exists(self.result.png_path):
            self.canvas.create_text(30, 30, anchor="nw", text="（还没有预览图）", fill="#777")
            return
        try:
            from PIL import Image, ImageTk

            image = Image.open(self.result.png_path)
            width = max(200, self.canvas.winfo_width() - 24)
            if image.width > width:
                ratio = width / image.width
                image = image.resize((int(image.width * ratio), int(image.height * ratio)), Image.LANCZOS)
            self._preview_image = ImageTk.PhotoImage(image)
            self.canvas.create_image(12, 12, anchor="nw", image=self._preview_image)
            self.canvas.configure(scrollregion=(0, 0, image.width + 24, image.height + 24))
        except Exception as exc:
            logger.exception("预览渲染失败")
            self.canvas.create_text(30, 30, anchor="nw", text=f"预览失败：{exc}", fill="#b45309")

    # ---------------------------------------------------------------- 导出
    def _require_result(self):
        if not self.result or not self.result.ok:
            messagebox.showinfo("没有结果", "先识别出一份谱面。")
            return None
        return self.result

    def _copy_text(self) -> None:
        content = self.text.get("1.0", "end").strip()
        if not content:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self._set_status("简谱文本已复制到剪贴板")

    def _export_text(self) -> None:
        result = self._require_result()
        if not result:
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            initialfile=self._stem(result) + ".txt",
                                            filetypes=[("文本", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"{result.meta.get('key', '')} {result.meta.get('time', '')}\n".strip() + "\n\n")
            fh.write(result.text or "")
        self._set_status(f"已导出：{path}")

    def _export_png(self) -> None:
        result = self._require_result()
        if not result:
            return
        if not result.png_path or not os.path.exists(result.png_path):
            messagebox.showwarning("无法导出", "这次结果没有生成 PNG。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile=self._stem(result) + ".png",
                                            filetypes=[("PNG", "*.png")])
        if not path:
            return
        shutil.copyfile(result.png_path, path)
        self._set_status(f"已导出：{path}")

    def _export_svg(self) -> None:
        result = self._require_result()
        if not result:
            return
        if not result.svg_path or not os.path.exists(result.svg_path):
            messagebox.showwarning("无法导出", "这次结果没有生成 SVG。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".svg",
                                            initialfile=self._stem(result) + ".svg",
                                            filetypes=[("SVG", "*.svg")])
        if not path:
            return
        shutil.copyfile(result.svg_path, path)
        self._set_status(f"已导出：{path}")

    def _export_musicxml(self) -> None:
        results = [r for r in (self.results or [self.result]) if r and r.ok and r.notes]
        if not results:
            messagebox.showinfo("没有结果", "先识别出一份谱面。")
            return

        # 有原始 MusicXML 就优先搬过来，保证和弦/力度等细节不丢
        direct = [r for r in results if r.xml_path and os.path.exists(r.xml_path)]
        if len(direct) == len(results) and len(results) == 1:
            path = filedialog.asksaveasfilename(defaultextension=".musicxml",
                                                initialfile=self._stem(results[0]) + ".musicxml",
                                                filetypes=[("MusicXML", "*.musicxml *.xml *.mxl")])
            if not path:
                return
            shutil.copyfile(direct[0].xml_path, path)
            self._set_status(f"已导出：{path}")
            return

        folder = filedialog.askdirectory(title="选择导出文件夹")
        if not folder:
            return
        count = 0
        for result in results:
            target = os.path.join(folder, self._stem(result) + ".musicxml")
            try:
                if result.xml_path and os.path.exists(result.xml_path):
                    shutil.copyfile(result.xml_path, target)
                else:
                    export_musicxml(result.notes, result.meta, target)
                count += 1
            except Exception as exc:
                logger.exception("MusicXML 导出失败")
                messagebox.showwarning("导出失败", f"{os.path.basename(result.source)}：{exc}")
        self._set_status(f"已导出 {count} 个 MusicXML 到 {folder}")

    @staticmethod
    def _stem(result) -> str:
        return os.path.splitext(os.path.basename(result.source or "jianpu"))[0]

    # ---------------------------------------------------------------- 后处理
    def _transpose(self, semitones: int) -> None:
        result = self._require_result()
        if not result:
            return
        if result.has_sketch():
            messagebox.showinfo("不可移调", "音高草图模式没有调号信息，移调结果不可靠。请先用 Audiveris 识别。")
            return
        notes, meta = transpose_notes(result.notes, semitones, result.meta)
        result.notes = notes
        result.meta = meta
        result.text = notes_to_text(notes)
        self._rerender(result)
        self._show_result(result)
        self._set_status(f"已整体移调 {semitones:+d} 个半音")

    def _autofix(self) -> None:
        result = self._require_result()
        if not result:
            return
        notes, messages = autofix_notes(result.notes)
        result.notes = notes
        result.text = notes_to_text(notes)
        self._rerender(result)
        self._show_result(result)
        self._set_status("；".join(messages) if messages else "没有发现需要修复的问题")

    def _rerender(self, result) -> None:
        path = os.path.join(temp_dir("out"), f"{self._stem(result)}_edit.png")
        try:
            if render_to_png(result.notes, result.meta, path) is not None:
                result.png_path = path
        except Exception:
            logger.exception("重新渲染失败")

    def _play(self) -> None:
        result = self._require_result()
        if not result:
            return
        try:
            from music21 import converter as m21converter

            tmp = os.path.join(temp_dir("midi"), f"{self._stem(result)}.musicxml")
            if result.xml_path and os.path.exists(result.xml_path):
                shutil.copyfile(result.xml_path, tmp)
            else:
                export_musicxml(result.notes, result.meta, tmp)
            score = m21converter.parse(tmp)
            midi_path = os.path.splitext(tmp)[0] + ".mid"
            score.write("midi", fp=midi_path)
            self._open_file(midi_path)
            self._set_status("已生成 MIDI，正在用系统播放器打开")
        except Exception as exc:
            logger.exception("MIDI 播放失败")
            messagebox.showwarning("无法播放", f"生成 MIDI 失败：{exc}\n可先导出 MusicXML 用 MuseScore 播放。")

    @staticmethod
    def _open_file(path: str) -> None:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    # ---------------------------------------------------------------- 历史
    def _refresh_history(self) -> None:
        try:
            items = self.history.all()
        except Exception:
            items = []
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        for item in items:
            meta = item.get("meta") or {}
            self.history_tree.insert("", "end", iid=item.get("id"), values=(
                item.get("created_at", ""),
                item.get("source", ""),
                meta.get("key", ""),
                meta.get("time", ""),
                meta.get("note_count", ""),
            ))

    def _load_history_item(self) -> None:
        selected = self.history_tree.selection()
        if not selected:
            return
        item = self.history.get(selected[0])
        if not item:
            return
        self.result = None
        self.text.delete("1.0", "end")
        header = f"{item.get('source', '')}  {item.get('created_at', '')}\n\n"
        self.text.insert("1.0", header + (item.get("text") or ""))
        self.notebook.select(0)
        self._set_status("已载入历史记录（只读文本，重新导出请重新识别）")

    def _clear_history(self) -> None:
        if not messagebox.askyesno("清空历史", "确定清空全部历史记录？此操作不可撤销。"):
            return
        self.history.clear()
        self._refresh_history()
        self._set_status("历史记录已清空")

    # ---------------------------------------------------------------- 杂项
    def _set_status(self, message: str) -> None:
        self.status.configure(text=message)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    import importlib.util

    if importlib.util.find_spec("tkinter") is None:
        print(
            "无法启动图形界面：当前 Python 缺少 tkinter。\n"
            "Windows 安装包自带 Tk；源码运行时请安装带 Tk 的 Python（官方安装包默认勾选 tcl/tk）。"
        )
        return 1
    try:
        import tkinter as _tk  # noqa: F401
        _tk.Tk  # 确认 Tk 真的可用（部分发行版只有 tcl 没 tk）
    except Exception as exc:
        print(
            f"无法启动图形界面：{exc}\n"
            "Windows 安装包自带 Tk；源码运行时请安装带 Tk 的 Python（官方安装包默认勾选 tcl/tk）。"
        )
        return 1

    setup_logging()
    removed = cleanup_temp_dir(7)
    if removed:
        logger.info("已清理 %d 个过期临时文件", removed)

    try:
        app = LilipuApp()
    except Exception:
        logger.exception("界面初始化失败")
        raise
    app.run()
    return 0
