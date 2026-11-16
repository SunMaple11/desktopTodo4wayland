"""主窗口：顶栏（macOS 红绿灯 + 标题 + 新建）、列表/详情页面栈、
每分钟心跳（仅在窗口可见时运行）、系统深色模式跟随。"""
from __future__ import annotations

from datetime import date

import gi
from gi.repository import Gio, GLib, Gtk

from detail_view import DetailView
from list_view import TodoList
from store import Todo, TodoStore
import util

gi.require_version("Gtk", "4.0")

APP_ID = "com.sunmaple.desktodo"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, store: TodoStore):
        super().__init__(application=app)
        self.store = store
        self._tick_src = 0
        self._today = date.today()

        self.set_title("桌面待办")
        self.set_default_size(430, 700)
        self.set_size_request(380, 520)
        self.add_css_class("shell")

        handle = Gtk.WindowHandle()
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.add_css_class("shell-box")
        handle.set_child(root)
        self.set_child(handle)

        # ---------- 顶栏 ----------
        header = Gtk.Box(spacing=10)
        header.add_css_class("header")

        lights = Gtk.Box(spacing=7)
        lights.set_valign(Gtk.Align.CENTER)
        self.btn_close = self._traffic("tl-red", "×", self.close)
        self.btn_min = self._traffic("tl-yellow", "–", self.minimize)
        self.btn_zoom = self._traffic("tl-green", "+", self._toggle_zoom)
        lights.append(self.btn_close)
        lights.append(self.btn_min)
        lights.append(self.btn_zoom)
        header.append(lights)

        tbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self.title_lbl = Gtk.Label(label="待办", halign=Gtk.Align.START)
        self.title_lbl.add_css_class("app-title")
        self.sub_lbl = Gtk.Label(label="", halign=Gtk.Align.START)
        self.sub_lbl.add_css_class("app-sub")
        tbox.append(self.title_lbl)
        tbox.append(self.sub_lbl)
        header.append(tbox)

        add = Gtk.Button(label="＋")
        add.add_css_class("btn-plain")
        add.set_halign(Gtk.Align.END)
        add.set_hexpand(True)
        add.set_tooltip_text("新建待办")
        add.connect("clicked", lambda *_: self.open_new())
        header.append(add)
        root.append(header)

        # ---------- 页面栈：列表 / 详情 ----------
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(280)
        root.append(self.stack)

        self.todo_list = TodoList(store, on_open=self.open_todo)
        self.stack.add_named(self.todo_list, "list")

        self.detail = DetailView(store, on_deleted=self._on_deleted)
        self.detail.connect("done", lambda *_: self.show_list())
        self.stack.add_named(self.detail, "detail")

        self.stack.set_visible_child_name("list")

        # ---------- 心跳与外观 ----------
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)
        self.connect("destroy", self._on_destroy)
        self._watch_dark_mode()
        self._refresh_header()

    # ---------- 红绿灯 ----------
    @staticmethod
    def _traffic(css: str, glyph: str, cb) -> Gtk.Button:
        b = Gtk.Button(label=glyph)
        b.add_css_class("tl")
        b.add_css_class(css)
        b.set_has_frame(False)
        b.set_can_focus(False)
        b.set_tooltip_text("")
        b.connect("clicked", lambda *_: cb())
        return b

    def _toggle_zoom(self):
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()

    # ---------- 页面切换 ----------
    def show_list(self):
        self.stack.set_visible_child_name("list")

    def open_todo(self, todo_id: str):
        self.detail.show_read(todo_id)
        self.stack.set_visible_child_name("detail")

    def open_new(self):
        self.detail.show_new()
        self.stack.set_visible_child_name("detail")

    def _on_deleted(self, todo: Todo):
        self.todo_list.show_undo(todo)

    # ---------- 心跳（可见时每分钟对齐一次，窗口隐藏即停） ----------
    def _on_map(self, *_):
        today = date.today()
        if today != self._today:          # 跨天（含休眠唤醒）：整体重建
            self._today = today
            self.todo_list.refresh()
            self._refresh_header()
        self.todo_list.tick()
        self.detail.tick()
        self._schedule_tick()

    def _on_unmap(self, *_):
        if self._tick_src:
            GLib.source_remove(self._tick_src)
            self._tick_src = 0

    def _schedule_tick(self):
        if self._tick_src:
            return
        now = GLib.DateTime.new_now_local()
        to_next_min = 60 - now.get_second()
        self._tick_src = GLib.timeout_add_seconds(to_next_min + 1, self._tick)

    def _tick(self):
        self._tick_src = 0
        if not self.get_mapped():         # 双保险：不可见就不再自我调度
            return GLib.SOURCE_REMOVE
        today = date.today()
        if today != self._today:
            self._today = today
            self.todo_list.refresh()
            self._refresh_header()
        else:
            self.todo_list.tick()
        self.detail.tick()
        self._schedule_tick()
        return GLib.SOURCE_REMOVE

    def _on_destroy(self, *_):
        if self._tick_src:
            GLib.source_remove(self._tick_src)
            self._tick_src = 0

    # ---------- 顶栏日期 ----------
    def _refresh_header(self):
        pending = self.store.pending()
        n_overdue = sum(
            1 for t in pending if t.due and t.due.date() < date.today())
        n_today = sum(
            1 for t in pending if t.due and t.due.date() == date.today())
        bits = [util.long_date(date.today())]
        if n_overdue:
            bits.append(f"{n_overdue} 项逾期")
        if n_today:
            bits.append(f"今天 {n_today} 项")
        if not n_overdue and not n_today and pending:
            bits.append(f"{len(pending)} 项待办")
        self.sub_lbl.set_text(" · ".join(bits))

    # ---------- 深色模式 ----------
    def _watch_dark_mode(self):
        self._apply_dark(self._read_dark())
        try:
            self._gs = Gio.Settings.new("org.gnome.desktop.interface")
            self._gs.connect("changed::color-scheme", lambda *_: self._apply_dark(self._read_dark()))
        except Exception:
            self._gs = None   # 非 GNOME 桌面时保持浅色，无害

    @staticmethod
    def _read_dark() -> bool:
        try:
            gs = Gio.Settings.new("org.gnome.desktop.interface")
            return gs.get_string("color-scheme").startswith("prefer-dark")
        except Exception:
            pass
        try:  # 旧式判断：主题名带 -dark
            gs = Gio.Settings.new("org.gnome.desktop.interface")
            return "-dark" in gs.get_string("gtk-theme").lower()
        except Exception:
            return False

    def _apply_dark(self, dark: bool):
        if dark:
            self.add_css_class("dark")
        else:
            self.remove_css_class("dark")
