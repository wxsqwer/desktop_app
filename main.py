import json
import shutil
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "文件整理工具"
CONFIG_FILE = Path(__file__).with_name("config.json")

CATEGORY_EXTENSIONS = {
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "文档": {".pdf", ".doc", ".docx", ".txt", ".md", ".xls", ".xlsx", ".ppt", ".pptx"},
    "视频": {".mp4", ".mov", ".avi", ".mkv", ".wmv"},
    "音频": {".mp3", ".wav", ".flac", ".aac"},
    "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "代码": {".py", ".js", ".html", ".css", ".json", ".xml", ".java", ".cpp", ".c"},
}


@dataclass(frozen=True)
class FileMovePreview:
    source: Path
    category: str
    target: Path


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def save_config(source_dir: Path) -> None:
    data = {"last_source_dir": str(source_dir)}
    with CONFIG_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_category(path: Path) -> str:
    extension = path.suffix.lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if extension in extensions:
            return category
    return "其他"


def get_unique_target_path(target: Path, reserved_targets: set[Path] | None = None) -> Path:
    reserved_targets = reserved_targets or set()
    if not target.exists() and target not in reserved_targets:
        return target

    index = 1
    while True:
        candidate = target.with_name(f"{target.stem} ({index}){target.suffix}")
        if not candidate.exists() and candidate not in reserved_targets:
            return candidate
        index += 1


def scan_directory(source_dir: Path) -> list[FileMovePreview]:
    previews: list[FileMovePreview] = []
    reserved_targets: set[Path] = set()

    for item in sorted(source_dir.iterdir(), key=lambda path: path.name.lower()):
        if not item.is_file():
            continue

        category = get_category(item)
        target_dir = source_dir / category
        target = get_unique_target_path(target_dir / item.name, reserved_targets)
        reserved_targets.add(target)
        previews.append(FileMovePreview(source=item, category=category, target=target))

    return previews


def move_files(previews: list[FileMovePreview]) -> tuple[int, list[str]]:
    moved_count = 0
    errors: list[str] = []

    for preview in previews:
        try:
            preview.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(preview.source), str(preview.target))
            moved_count += 1
        except OSError as error:
            errors.append(f"{preview.source.name}: {error}")

    return moved_count, errors


class FileOrganizerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.minsize(920, 560)

        self.source_dir = tk.StringVar()
        self.status_text = tk.StringVar(value="请选择要整理的文件夹。")
        self.previews: list[FileMovePreview] = []
        self.preview_source_dir: Path | None = None

        config = load_config()
        last_source_dir = config.get("last_source_dir")
        if isinstance(last_source_dir, str) and Path(last_source_dir).exists():
            self.source_dir.set(last_source_dir)

        self._build_ui()
        self._refresh_action_state()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top_frame = ttk.Frame(self, padding=(12, 12, 12, 6))
        top_frame.grid(row=0, column=0, sticky="ew")
        top_frame.columnconfigure(1, weight=1)

        ttk.Label(top_frame, text="源文件夹").grid(row=0, column=0, padx=(0, 8), sticky="w")

        path_entry = ttk.Entry(top_frame, textvariable=self.source_dir)
        path_entry.grid(row=0, column=1, sticky="ew")

        ttk.Button(top_frame, text="选择...", command=self.choose_directory).grid(
            row=0, column=2, padx=(8, 0)
        )
        self.scan_button = ttk.Button(top_frame, text="扫描/预览", command=self.scan)
        self.scan_button.grid(row=0, column=3, padx=(8, 0))
        self.move_button = ttk.Button(top_frame, text="执行整理", command=self.confirm_and_move)
        self.move_button.grid(row=0, column=4, padx=(8, 0))

        list_frame = ttk.Frame(self, padding=(12, 6, 12, 6))
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        columns = ("source", "category", "target")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=18)
        self.tree.heading("source", text="原文件路径")
        self.tree.heading("category", text="目标分类")
        self.tree.heading("target", text="目标路径")
        self.tree.column("source", width=330, anchor="w")
        self.tree.column("category", width=100, anchor="center")
        self.tree.column("target", width=330, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        status_frame = ttk.Frame(self, padding=(12, 6, 12, 12))
        status_frame.grid(row=2, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)

        ttk.Label(status_frame, textvariable=self.status_text).grid(row=0, column=0, sticky="w")

    def choose_directory(self) -> None:
        initial_dir = self.source_dir.get() or str(Path.home())
        selected = filedialog.askdirectory(title="选择要整理的文件夹", initialdir=initial_dir)
        if not selected:
            self.status_text.set("已取消选择文件夹。")
            return

        self.source_dir.set(selected)
        self.previews = []
        self.preview_source_dir = None
        self._clear_tree()
        self.status_text.set("已选择文件夹，请点击扫描/预览。")
        self._refresh_action_state()

        try:
            save_config(Path(selected))
        except OSError as error:
            self.status_text.set(f"已选择文件夹，但保存配置失败：{error}")

    def scan(self) -> None:
        source_dir = Path(self.source_dir.get()).expanduser()
        if not source_dir.exists() or not source_dir.is_dir():
            messagebox.showerror(APP_TITLE, "请选择一个有效的源文件夹。")
            self.status_text.set("源文件夹无效。")
            self.previews = []
            self.preview_source_dir = None
            self._clear_tree()
            self._refresh_action_state()
            return

        try:
            self.previews = scan_directory(source_dir)
            self.preview_source_dir = source_dir
        except OSError as error:
            messagebox.showerror(APP_TITLE, f"扫描失败：{error}")
            self.status_text.set("扫描失败。")
            self.previews = []
            self.preview_source_dir = None
            self._clear_tree()
            self._refresh_action_state()
            return

        self._clear_tree()
        for preview in self.previews:
            self.tree.insert(
                "",
                tk.END,
                values=(str(preview.source), preview.category, str(preview.target)),
            )

        try:
            save_config(source_dir)
        except OSError as error:
            self.status_text.set(f"扫描完成，但保存配置失败：{error}")
        else:
            if self.previews:
                self.status_text.set(f"扫描完成，共找到 {len(self.previews)} 个可整理文件。")
            else:
                self.status_text.set("该文件夹第一层没有可整理的文件。")

        self._refresh_action_state()

    def confirm_and_move(self) -> None:
        if not self.previews:
            messagebox.showinfo(APP_TITLE, "请先扫描并生成预览。")
            return

        current_source_dir = Path(self.source_dir.get()).expanduser()
        if self.preview_source_dir != current_source_dir:
            messagebox.showinfo(APP_TITLE, "源文件夹已变化，请重新扫描后再执行整理。")
            self.status_text.set("源文件夹已变化，请重新扫描。")
            self.previews = []
            self.preview_source_dir = None
            self._clear_tree()
            self._refresh_action_state()
            return

        confirmed = messagebox.askyesno(
            APP_TITLE,
            f"确认移动 {len(self.previews)} 个文件到对应分类文件夹吗？",
        )
        if not confirmed:
            self.status_text.set("已取消整理操作。")
            return

        moved_count, errors = move_files(self.previews)
        self.previews = []
        self.preview_source_dir = None
        self._clear_tree()
        self._refresh_action_state()

        if errors:
            messagebox.showwarning(
                APP_TITLE,
                f"已移动 {moved_count} 个文件，{len(errors)} 个文件失败。\n\n"
                + "\n".join(errors[:8]),
            )
            self.status_text.set(f"整理完成：成功 {moved_count} 个，失败 {len(errors)} 个。")
        else:
            messagebox.showinfo(APP_TITLE, f"整理完成，已移动 {moved_count} 个文件。")
            self.status_text.set(f"整理完成，已移动 {moved_count} 个文件。")

    def _clear_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _refresh_action_state(self) -> None:
        self.move_button.configure(state=tk.NORMAL if self.previews else tk.DISABLED)


if __name__ == "__main__":
    app = FileOrganizerApp()
    app.mainloop()


