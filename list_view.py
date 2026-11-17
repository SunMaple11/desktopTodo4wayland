"""主列表页：按 日 / 周 / 月 分节展示待办，含行级右键菜单、空状态与撤销 Toast。"""
from __future__ import annotations

from datetime import date, datetime

import gi
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from store import Todo, TodoStore
import i18n
import util

gi.require_version("Gtk", "4.0")


def _popup_menu(owner: Gtk.Widget, menu: Gio.Menu, x: float, y: float, parent: Gtk.Widget):
    """统一的右键菜单弹出。

    关键点：
    - 生命周期挂在 owner 上（下次弹出/销毁时才 unparent），绝不在 closed 时
      unparent——那会在菜单项的 action 派发完成前销毁菜单，导致点了没反应；
    - popup 延迟到 idle，避开本次按键自身的 release 事件。
    """
    _close_menu(owner)
    rect = Gdk.Rectangle()
    rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
    pop = Gtk.PopoverMenu.new_from_model(menu)
    pop.set_has_arrow(False)
    pop.set_parent(parent)
    pop.set_pointing_to(rect)
    owner._menu_pop = pop
    GLib.idle_add(pop.popup)


def _close_menu(owner: Gtk.Widget):
    pop = getattr(owner, "_menu_pop", None)
    if pop is not None:
        try:
            pop.unparent()
        except Exception:
            pass
        owner._menu_pop = None


class TodoRow(Gtk.ListBoxRow):
    """单条待办行（含右键菜单：完成 / 取消完成、编辑、删除）。"""

    def __init__(self, store: TodoStore, todo: Todo, on_open):
        super().__init__()
        self.store = store
        self.todo_id = todo.id
        self.set_activatable(True)
        self.add_css_class("todo-row")

        self._due = todo.due
        self._done = todo.done

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(2)

        # 勾选圆
        self.chk = Gtk.Button(label="✓")
        self.chk.add_css_class("chk")
        self.chk.set_valign(Gtk.Align.CENTER)
        self.chk.set_can_focus(False)
        self.chk.set_has_frame(False)
        self.chk.connect("clicked", self._on_toggle)
        box.append(self.chk)

        # 标题 + 备注预览
        mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        mid.set_hexpand(True)
        self.title_lbl = Gtk.Label(label=todo.title, halign=Gtk.Align.START, xalign=0)
        self.title_lbl.add_css_class("todo-title")
        self.title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_lbl.set_max_width_chars(18)
        mid.append(self.title_lbl)
        if todo.notes.strip():
            note = Gtk.Label(label=todo.notes.strip().replace("\n", " "),
                             halign=Gtk.Align.START, xalign=0)
            note.add_css_class("todo-notes")
            note.set_ellipsize(Pango.EllipsizeMode.END)
            note.set_max_width_chars(24)
            mid.append(note)
        box.append(mid)

        # DDL 胶囊
        self.chip = Gtk.Label(label="")
        self.chip.add_css_class("chip")
        self.chip.set_valign(Gtk.Align.CENTER)
        box.append(self.chip)

        self.set_child(box)
        self._apply_done()
        self._refresh_chip()
        self.connect("activate", lambda *_: on_open(self.todo_id))

        # 右键菜单（行级 + 空白处）
        click = Gtk.GestureClick()
        click.set_button(Gdk.BUTTON_SECONDARY)
        click.connect("pressed", self._on_secondary)
        self.add_controller(click)
        self.connect("destroy", self._on_destroy)
        self._menu_pop = None

    # ---- 右键菜单（行级） ----
    def _on_secondary(self, _g, _n, x, y):
        menu = Gio.Menu()
        for label, action in (
            (i18n.t("act_undone") if self._done else i18n.t("act_done"), "row.toggle"),
            (i18n.t("dt_edit"), "row.edit"),
            (i18n.t("act_remove"), "row.remove"),
        ):
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value(f"win.{action}",
                                             GLib.Variant.new_string(self.todo_id))
            menu.append_item(item)
        _popup_menu(self, menu, x, y, self)

    def _on_destroy(self, *_):
        _close_menu(self)

    # ---- 状态 ----
    def _on_toggle(self, *_):
        self._done = not self._done
        self._apply_done()          # 先更新自己，避免 store 信号触发重建后操作已销毁控件
        self.store.toggle_done(self.todo_id)

    def _apply_done(self):
        if self._done:
            self.add_css_class("done")
            self.chk.add_css_class("done")
        else:
            self.remove_css_class("done")
            self.chk.remove_css_class("done")
        attrs = Pango.AttrList()
        if self._done:
            attrs.insert(Pango.attr_strikethrough_new(True))
        self.title_lbl.set_attributes(attrs)

    def _refresh_chip(self, today=None):
        today = today or datetime.now().date()
        if self._due is None:
            self.chip.set_text(i18n.t("chip_nodate"))
            cls = "none"
        else:
            self.chip.set_text(util.due_chip_text(self._due, today))
            cls = util.chip_class(self._due, today)
        for c in ("later", "today", "overdue", "none"):
            if c != cls:
                self.chip.remove_css_class(c)
        self.chip.add_css_class(cls)

    def tick(self, today: date):
        """每分钟刷新 DDL 文案（廉价：只改标签文本，不重建控件）。"""
        self._refresh_chip(today)


class TodoList(Gtk.Box):
    """列表页：分段视图（日/周/月）+ 撤销 Toast。"""

    MODES = ("day", "week", "month")
    SPAN = {"day": 1, "week": 7, "month": 31}

    def __init__(self, store: TodoStore, on_open):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.store = store
        self.on_open = on_open
        self.mode = "day"

        # 分段控制器
        segbar = Gtk.Box(spacing=2)
        segbar.add_css_class("segbar")
        segbar.set_halign(Gtk.Align.CENTER)
        segbar.set_margin_top(2)
        segbar.set_margin_bottom(6)
        self._seg_btns: dict[str, Gtk.ToggleButton] = {}
        self._switching = False
        for key in ("day", "week", "month"):
            b = Gtk.ToggleButton(label=i18n.t(f"view_{key}"))
            b.add_css_class("seg")
            b.set_size_request(64, -1)
            b.connect("toggled", self._on_seg, key)
            segbar.append(b)
            self._seg_btns[key] = b
        self._seg_btns["day"].set_active(True)
        self.append(segbar)

        # 列表 + Toast 覆盖层
        self.overlay = Gtk.Overlay()
        self.overlay.set_vexpand(True)
        self.listbox = Gtk.ListBox()
        self.listbox.add_css_class("listbox")
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        try:
            self.listbox.set_activate_on_single_click(True)
        except AttributeError:
            pass  # 极旧 GTK：回退为双击激活
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.add_css_class("list-scroll")
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_child(self.listbox)
        self.overlay.set_child(self.scroll)

        self.undo_revealer = Gtk.Revealer(valign=Gtk.Align.END, halign=Gtk.Align.CENTER,
                                          margin_bottom=8)
        self.undo_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.undo_revealer.set_reveal_child(False)
        self.overlay.add_overlay(self.undo_revealer)
        self.append(self.overlay)

        self._undo_todo: Todo | None = None
        self._undo_src = 0
        self._menu_pop = None

        store.connect("changed", lambda *_: self.refresh())

        # 空白处右键菜单（行上有自己的菜单：命中行则让行处理）
        blank = Gtk.GestureClick()
        blank.set_button(Gdk.BUTTON_SECONDARY)
        blank.connect("pressed", self._on_blank_secondary)
        self.listbox.add_controller(blank)
        self.listbox.connect("destroy", self._on_destroy)

    def _on_destroy(self, *_):
        _close_menu(self)

    def _on_blank_secondary(self, _g, _n, x, y):
        if self.listbox.get_row_at_y(int(y)) is not None:
            return                      # 点在行上：由行的菜单处理
        menu = Gio.Menu()
        menu.append(i18n.t("m_new"), "win.list.new")
        view = Gio.Menu()
        for key in self.MODES:
            it = Gio.MenuItem.new(i18n.t(f"view_{key}"), None)
            it.set_action_and_target_value("win.list.view",
                                           GLib.Variant.new_string(key))
            view.append_item(it)
        menu.append_submenu(i18n.t("m_view"), view)
        menu.append(i18n.t("m_settings"), "win.list.settings")
        _popup_menu(self, menu, x, y, self.listbox)

    def set_mode(self, mode: str):
        """供动作调用（与点击分段按钮等效）。"""
        if mode in self.MODES:
            self._seg_btns[mode].set_active(True)

    # ---------- 分段切换 ----------
    def _on_seg(self, btn, key):
        if self._switching:
            return
        self._switching = True
        for k, b in self._seg_btns.items():
            b.set_active(k == key)
        self._switching = False
        if self.mode != key:
            self.mode = key
            self.refresh()

    def apply_lang(self):
        for key, b in self._seg_btns.items():
            b.set_label(i18n.t(f"view_{key}"))
        self.refresh()

    # ---------- 数据分组 ----------
    def _sections(self):
        """返回 [(标题, 是否逾期节, [Todo…]), …]，严格按 DDL 升序。"""
        today = datetime.now().date()
        span = self.SPAN[self.mode]

        pending = sorted(
            (t for t in self.store.pending() if t.due is not None),
            key=lambda t: t.due)
        no_due = [t for t in self.store.pending() if t.due is None]

        secs: list[tuple[str, bool, list]] = []
        overdue = [t for t in pending if t.due.date() < today]
        if overdue:
            secs.append((i18n.t("sec_overdue"), True, overdue))

        by_day: dict = {}
        for t in pending:
            n = (t.due.date() - today).days
            if self.mode == "day":
                if n == 0:
                    by_day.setdefault(today, []).append(t)
            elif 0 <= n < span:
                by_day.setdefault(t.due.date(), []).append(t)

        for d in sorted(by_day):
            secs.append((util.day_header(d, today), False, by_day[d]))
        if self.mode != "day":
            far = [t for t in pending if (t.due.date() - today).days >= span]
            if far:                      # 超出周/月范围的待办也要能找到
                secs.append((i18n.t("sec_later"), False, far))

        if no_due:
            secs.append((i18n.t("sec_nodate"), False, no_due))

        done = sorted(self.store.completed(),
                      key=lambda t: t.done_at or t.created_at, reverse=True)[:50]
        if done:
            secs.append((i18n.t("sec_done"), False, done))
        return secs

    # ---------- 渲染 ----------
    def refresh(self):
        for row in list(self.listbox):
            self.listbox.remove(row)

        secs = self._sections()
        if not secs:
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                            valign=Gtk.Align.CENTER, vexpand=True,
                            margin_top=60)
            e1 = Gtk.Label(label="🗒️")
            e1.add_css_class("empty-emoji")
            e2 = Gtk.Label(label=i18n.t("empty"))
            e2.add_css_class("empty")
            empty.append(e1)
            empty.append(e2)
            lbrow = Gtk.ListBoxRow(activatable=False, selectable=False)
            lbrow.set_child(empty)
            self.listbox.append(lbrow)
            return

        for title, is_overdue, items in secs:
            self.listbox.append(self._section_header(title, is_overdue, len(items)))
            for t in items:
                self.listbox.append(TodoRow(self.store, t, self.on_open))

    def _section_header(self, title: str, is_overdue: bool, count: int) -> Gtk.ListBoxRow:
        box = Gtk.Box(spacing=7, margin_start=8)
        box.add_css_class("sec-head")
        t = Gtk.Label(label=title)
        t.add_css_class("sec-title")
        if is_overdue:
            t.add_css_class("overdue")
        box.append(t)
        c = Gtk.Label(label=str(count))
        c.add_css_class("sec-count")
        if is_overdue:
            c.add_css_class("overdue")
        box.append(c)
        row = Gtk.ListBoxRow(activatable=False, selectable=False)
        row.set_child(box)
        return row

    # ---------- 每分钟心跳 ----------
    def tick(self):
        """只刷新 DDL 胶囊文案；跨天由 Window 负责触发整体重建。"""
        today = datetime.now().date()
        for row in self.listbox:
            if isinstance(row, TodoRow):
                row.tick(today)

    # ---------- 撤销 ----------
    def show_undo(self, todo: Todo):
        self._undo_todo = todo
        if self._undo_src:
            GLib.source_remove(self._undo_src)

        title = todo.title if len(todo.title) <= 12 else todo.title[:12] + "…"
        bar = Gtk.Box(spacing=6)
        bar.add_css_class("toast")
        bar.append(Gtk.Label(label=i18n.t("undo_deleted", t=title)))
        btn = Gtk.Button(label=i18n.t("undo"))
        btn.add_css_class("btn-plain")
        btn.connect("clicked", self._on_undo)
        bar.append(btn)
        self.undo_revealer.set_child(bar)
        self.undo_revealer.set_reveal_child(True)
        self._undo_src = GLib.timeout_add_seconds(6, self._hide_undo)

    def _on_undo(self, *_):
        if self._undo_todo is not None:
            self.store.add(self._undo_todo)   # 保留原 id 与 created_at
        self._hide_undo()

    def _hide_undo(self):
        self.undo_revealer.set_reveal_child(False)
        self._undo_todo = None
        self._undo_src = 0
        return GLib.SOURCE_REMOVE
