"""主窗口：顶栏（红绿灯 + 标题 + 新建 + 设置）、列表/详情页面栈、
行级右键动作、每分钟心跳（仅窗口可见时运行）、系统深色模式跟随、
双语与设置（语言 / 窗口大小 / 开机自启）。"""
from __future__ import annotations

from datetime import date

import gi
from gi.repository import Gio, GLib, Gtk

from detail_view import DetailView
from list_view import TodoList
from settings import SIZES, Settings
from store import Todo, TodoStore
import i18n
import util

gi.require_version("Gtk", "4.0")

APP_ID = "com.sunmaple.desktodo"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, store: TodoStore):
        super().__init__(application=app)
        self.store = store
        self.settings = Settings()
        i18n.set_lang(self.settings.get("lang"))

        self._tick_src = 0
        self._today = date.today()
        self._build_version = "1.3.0"

        self.set_title(i18n.t("app_title"))
        self.set_decorated(False)   # 去掉 GTK 自绘标题栏，只用红绿灯
        w, h = SIZES[self.settings.get("size")]
        self.set_default_size(w, h)
        self.set_size_request(360, 520)
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
        lights.append(self._traffic("tl-red", "window-close-symbolic", self.close))
        lights.append(self._traffic("tl-yellow", "window-minimize-symbolic", self.minimize))
        lights.append(self._traffic("tl-green", "window-maximize-symbolic", self._toggle_zoom))
        header.append(lights)

        tbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self.title_lbl = Gtk.Label(label=i18n.t("app_title"), halign=Gtk.Align.START)
        self.title_lbl.add_css_class("app-title")
        self.sub_lbl = Gtk.Label(label="", halign=Gtk.Align.START)
        self.sub_lbl.add_css_class("app-sub")
        tbox.append(self.title_lbl)
        tbox.append(self.sub_lbl)
        header.append(tbox)

        add = Gtk.Button(label="＋")
        add.add_css_class("btn-plain")
        add.set_halign(Gtk.Align.END)
        add.set_tooltip_text("")
        add.connect("clicked", lambda *_: self.open_new())
        header.append(add)

        gear = Gtk.Button(label="⚙")
        gear.add_css_class("btn-plain")
        gear.add_css_class("gear")
        gear.set_valign(Gtk.Align.CENTER)
        gear.connect("clicked", lambda *_: self._popup_settings(gear))
        header.append(gear)
        self.gear_btn = gear
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

        # ---------- 行级与列表级动作（右键菜单使用） ----------
        self.install_action("row.toggle", "s",
                            lambda _w, _n, p: self.store.toggle_done(p.get_string()))
        self.install_action("row.edit", "s",
                            lambda _w, _n, p: self.open_todo(p.get_string()))
        self.install_action("row.remove", "s", self._do_remove)
        self.install_action("list.new", None, lambda *_: self.open_new())
        self.install_action("list.view", "s",
                            lambda _w, _n, p: self.todo_list.set_mode(p.get_string()))
        self.install_action("list.settings", None,
                            lambda *_: self._popup_settings(self.gear_btn))

        # ---------- 心跳与外观 ----------
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)
        self.connect("destroy", self._on_destroy)
        self._watch_dark_mode()
        self._refresh_header()

    # ---------- 红绿灯（纯色圆点，不内置符号，观感协调优先） ----------
    @staticmethod
    def _traffic(css: str, _unused: str, cb) -> Gtk.Button:
        b = Gtk.Button()
        b.add_css_class("tl")
        b.add_css_class(css)
        b.set_has_frame(False)
        b.set_can_focus(False)
        b.connect("clicked", lambda *_: cb())
        return b

    def _toggle_zoom(self):
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()

    # ---------- 行级动作 ----------
    def _do_remove(self, _w, _name, param):
        tid = param.get_string()
        removed = self.store.remove(tid)
        if removed is not None:
            self.todo_list.show_undo(removed)

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

    # ---------- 设置弹层 ----------
    def _popup_settings(self, anchor: Gtk.Button):
        pop = Gtk.Popover(autohide=True)
        pop.set_position(Gtk.PositionType.BOTTOM)
        pop.set_child(self._build_settings())
        pop.set_parent(anchor)
        pop.popup()

    def _build_settings(self) -> Gtk.Box:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        outer.set_size_request(240, -1)

        # 语言（互斥分段；handler 必须全组共用一个，否则 guard 各自为政导致多选）
        outer.append(self._settings_label(i18n.t("set_lang")))
        lang_seg = Gtk.Box(spacing=2)
        lang_seg.add_css_class("segbar")
        lang_group: dict[str, Gtk.ToggleButton] = {}
        on_lang = self._mk_exclusive(lang_group, self._apply_lang_choice)
        for code, label in (("zh", i18n.t("set_lang_zh")), ("en", i18n.t("set_lang_en"))):
            b = Gtk.ToggleButton(label=label)
            b.add_css_class("seg")
            b.set_size_request(96, -1)
            b.set_active(i18n.get_lang() == code)
            b.connect("toggled", on_lang, code)
            lang_group[code] = b
            lang_seg.append(b)
        outer.append(lang_seg)

        # 窗口大小（互斥分段）
        outer.append(self._settings_label(i18n.t("set_size")))
        size_seg = Gtk.Box(spacing=2)
        size_seg.add_css_class("segbar")
        size_group: dict[str, Gtk.ToggleButton] = {}
        on_size = self._mk_exclusive(size_group, self._apply_size_choice)
        for key, label in (("small", i18n.t("set_size_s")), ("medium", i18n.t("set_size_m")),
                           ("large", i18n.t("set_size_l"))):
            b = Gtk.ToggleButton(label=label)
            b.add_css_class("seg")
            b.set_size_request(64, -1)
            b.set_active(self.settings.get("size") == key)
            b.connect("toggled", on_size, key)
            size_group[key] = b
            size_seg.append(b)
        outer.append(size_seg)

        # 开机自启
        row = Gtk.Box(spacing=8, margin_top=8)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        box.set_hexpand(True)
        l1 = Gtk.Label(label=i18n.t("set_autostart"), halign=Gtk.Align.START)
        l1.add_css_class("dt-value")
        l2 = Gtk.Label(label=i18n.t("set_autostart_hint"), halign=Gtk.Align.START)
        l2.add_css_class("app-sub")
        box.append(l1)
        box.append(l2)
        row.append(box)
        sw = Gtk.Switch()
        sw.set_valign(Gtk.Align.CENTER)
        sw.set_active(self.settings.get("autostart"))
        sw.connect("notify::active", self._on_autostart)
        row.append(sw)
        outer.append(row)
        return outer

    @staticmethod
    def _settings_label(text: str) -> Gtk.Label:
        l = Gtk.Label(label=text, halign=Gtk.Align.START, margin_top=6)
        l.add_css_class("card-label")
        return l

    # ---------- 互斥分段（点击已选项会弹回，绝不出现全不选/多选） ----------
    @staticmethod
    def _mk_exclusive(group: dict, apply_cb):
        state = {"switching": False}

        def handler(btn: Gtk.ToggleButton, key: str):
            if state["switching"]:
                return
            if not btn.get_active():        # 点击当前已选项：恢复选中
                state["switching"] = True
                btn.set_active(True)
                state["switching"] = False
                return
            state["switching"] = True
            for k, b in group.items():
                b.set_active(k == key)      # 强制其余全部取消
            state["switching"] = False
            apply_cb(key)
        return handler

    def _apply_lang_choice(self, code: str):
        if i18n.get_lang() != code:
            i18n.set_lang(code)
            self.settings.set("lang", code)
            self.apply_lang()

    def _apply_size_choice(self, key: str):
        if self.settings.get("size") != key:
            self.settings.set("size", key)
            w, h = SIZES[key]
            self.set_default_size(w, h)
            try:
                self.unmaximize()
                self.resize(w, h)
            except Exception:
                pass   # resize 在个别 GTK 版本不可用时仅影响即时生效

    def _on_autostart(self, sw, *_):
        on = sw.get_active()
        self.settings.set("autostart", on)
        self.settings.apply_autostart(on)

    # ---------- 语言即时生效 ----------
    def apply_lang(self):
        self.set_title(i18n.t("app_title"))
        self.title_lbl.set_text(i18n.t("app_title"))
        self._refresh_header()
        self.todo_list.apply_lang()
        self.detail.sync_from_fields()
        if self.stack.get_visible_child_name() == "detail":
            self.detail.rerender()

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
        self._tick_src = GLib.timeout_add_seconds(60 - now.get_second() + 1, self._tick)

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
        n_overdue = sum(1 for t in pending if t.due and t.due.date() < date.today())
        n_today = sum(1 for t in pending if t.due and t.due.date() == date.today())
        bits = [util.long_date(date.today())]
        if n_overdue:
            bits.append(i18n.t("sub_overdue", n=n_overdue))
        if n_today:
            bits.append(i18n.t("sub_today", n=n_today))
        if not n_overdue and not n_today and pending:
            bits.append(i18n.t("sub_pending", n=len(pending)))
        self.sub_lbl.set_text(" · ".join(bits))

    # ---------- 深色模式 ----------
    def _watch_dark_mode(self):
        self._apply_dark(self._read_dark())
        try:
            self._gs = Gio.Settings.new("org.gnome.desktop.interface")
            self._gs.connect("changed::color-scheme",
                             lambda *_: self._apply_dark(self._read_dark()))
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
