"""GNOME Shell 窗口层级扩展的安装与 D-Bus 控制。

普通 GTK/Wayland 客户端无法自行置顶/置底，必须通过 Shell 扩展调用
compositor 的窗口 API。这里提供可选安装，不修改系统级文件。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import gi
from gi.repository import Gio, GLib

APP_ID = "com.sunmaple.desktodo"
EXT_UUID = "desktoptodo-layer@desktoptodo"
EXT_NAME = "Desktop Todo Window Layer"
DBUS_NAME = APP_ID
DBUS_PATH = "/com/sunmaple/desktodo/layer"
DBUS_IFACE = "com.sunmaple.desktodo.Layer"
HERE = Path(__file__).resolve().parent
SOURCE_EXT = HERE / "gnome-extension"
USER_EXT = Path.home() / ".local/share/gnome-shell/extensions" / EXT_UUID


class LayerError(RuntimeError):
    """扩展不可用或调用失败。"""


class LayerController:
    def __init__(self):
        self.proxy: Gio.DBusProxy | None = None

    @property
    def extension_dir(self) -> Path:
        return USER_EXT

    def is_installed(self) -> bool:
        return (self.extension_dir / "extension.js").is_file() and (
            self.extension_dir / "metadata.json").is_file()

    def is_enabled(self) -> bool:
        try:
            settings = Gio.Settings.new("org.gnome.shell")
            enabled = settings.get_strv("enabled-extensions")
            return EXT_UUID in enabled and self.is_installed()
        except Exception:
            return False

    def install(self) -> None:
        if not SOURCE_EXT.is_dir():
            raise LayerError(f"找不到扩展源文件：{SOURCE_EXT}")
        self.extension_dir.parent.mkdir(parents=True, exist_ok=True)
        # 只覆盖本应用自己的扩展目录，不触碰其它扩展。
        for filename in ("extension.js", "metadata.json"):
            shutil.copy2(SOURCE_EXT / filename, self.extension_dir / filename)
        # gnome-extensions enable 在 GNOME 42 会立即加载已存在的扩展。
        result = subprocess.run(
            ["gnome-extensions", "enable", EXT_UUID],
            capture_output=True, text=True, timeout=5, check=False)
        if result.returncode != 0:
            raise LayerError(result.stderr.strip() or "GNOME Shell 扩展启用失败")

    def ensure_available(self) -> None:
        if not self.is_installed() or not self.is_enabled():
            self.install()
        self._connect()

    def _connect(self):
        if self.proxy is not None:
            return
        try:
            self.proxy = Gio.DBusProxy.new_sync(
                Gio.bus_get_sync(Gio.BusType.SESSION, None),
                Gio.DBusProxyFlags.NONE,
                None, DBUS_NAME, DBUS_PATH, DBUS_IFACE, None)
        except GLib.Error as exc:
            self.proxy = None
            raise LayerError(f"无法连接窗口层级扩展：{exc.message}") from exc

    def ping(self) -> bool:
        try:
            self.ensure_available()
            value = self.proxy.call_sync("Ping", None, Gio.DBusCallFlags.NONE,
                                         2000, None)
            return bool(value and value.unpack()[0] == "desktoptodo-layer")
        except (GLib.Error, LayerError, TypeError, IndexError):
            return False

    def set_mode(self, mode: str) -> bool:
        if mode not in {"normal", "top", "bottom"}:
            raise ValueError(f"未知窗口层级：{mode}")
        self.ensure_available()
        try:
            value = self.proxy.call_sync(
                "SetMode", GLib.Variant("(s)", (mode,)),
                Gio.DBusCallFlags.NONE, 2000, None)
            return bool(value and value.unpack()[0])
        except GLib.Error as exc:
            raise LayerError(f"设置窗口层级失败：{exc.message}") from exc

    def get_mode(self) -> str:
        self.ensure_available()
        try:
            value = self.proxy.call_sync("GetMode", None, Gio.DBusCallFlags.NONE,
                                         2000, None)
            return value.unpack()[0] if value else "normal"
        except GLib.Error as exc:
            raise LayerError(f"读取窗口层级失败：{exc.message}") from exc

    def reset(self) -> None:
        """关闭应用时恢复普通层级，避免留下系统级置顶状态。"""
        if self.proxy is None:
            return
        try:
            self.proxy.call_sync("SetMode", GLib.Variant("(s)", ("normal",)),
                                 Gio.DBusCallFlags.NONE, 1000, None)
        except GLib.Error:
            pass
