"""设置持久化 + 开机自启管理。文件：~/.config/desktoptodo/settings.json"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

DEFAULTS = {"lang": "zh", "size": "medium", "autostart": False}

# 窗口尺寸预设
SIZES = {"small": (380, 560), "medium": (430, 700), "large": (500, 860)}


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path or (Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
                             / "desktoptodo" / "settings.json")
        self.data: dict = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in DEFAULTS:
                        self.data[k] = v
        except (OSError, ValueError):
            pass
        # 校正
        if self.data["lang"] not in ("zh", "en"):
            self.data["lang"] = "zh"
        if self.data["size"] not in SIZES:
            self.data["size"] = "medium"
        self.data["autostart"] = bool(self.data["autostart"])

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".settings-")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except OSError as e:
            print(f"[desktoptodo] 设置保存失败: {e}")

    def get(self, key: str):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    # ---------- 开机自启 ----------
    @property
    def autostart_path(self) -> Path:
        return Path.home() / ".config" / "autostart" / "desktoptodo.desktop"

    def apply_autostart(self, on: bool) -> None:
        try:
            if not on:
                self.autostart_path.unlink(missing_ok=True)
                return
            if Path("/usr/bin/desktoptodo").exists():      # deb 安装
                exec_line, path_line = "Exec=desktoptodo", ""
            else:                                          # 源码运行
                exec_line, path_line = "Exec=/usr/bin/python3 main.py", f"Path={HERE}"
            self.autostart_path.parent.mkdir(parents=True, exist_ok=True)
            self.autostart_path.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Desktop Todo\n"
                f"{exec_line}\n"
                f"{path_line}\n".rstrip() + "\n"
                "Icon=desktoptodo\n"
                "Terminal=false\n",
                encoding="utf-8")
        except OSError as e:
            print(f"[desktoptodo] 自启设置失败: {e}")
