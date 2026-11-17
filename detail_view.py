"""详情页：查看 / 行内编辑单条待办，含截止日期弹层编辑器。

约定：
- show_read(todo_id)  展示既有待办
- show_new()          新建（点「保存」才真正入库，取消则丢弃）
- 操作结束后发射 "done" 信号，由主窗口切回列表
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import gi
from gi.repository import Gdk, GLib, GObject, Gtk, Pango

from store import Todo, TodoStore
import i18n
import util

gi.require_version("Gtk", "4.0")


class DetailView(Gtk.Box):
    __gsignals__ = {"done": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, store: TodoStore, on_deleted=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.store = store
        self.on_deleted = on_deleted
        self._draft: Todo | None = None
        self._is_new = False
        self._editing = False

        # Esc 返回列表
        keyc = Gtk.EventControllerKey()
        keyc.connect("key-released", self._on_key)
        self.add_controller(keyc)

        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.body.set_margin_top(4)
        self.body.set_margin_bottom(16)
        self.body.set_margin_start(16)
        self.body.set_margin_end(16)
        self.body.set_vexpand(True)
        self.append(self.body)

    # =========================================================
    # 公共入口
    # =========================================================
    def show_read(self, todo_id: str):
        t = self.store.get(todo_id)
        if t is None:
            return
        self._draft = t.copy()
        self._is_new = False
        self._editing = False
        self._render()

    def show_new(self):
        self._draft = Todo(id="", title="")     # id 为空 = 尚未入库
        self._is_new = True
        self._editing = True
        self._render()
        GLib.idle_add(self._focus_title)

    # ---------- 语言切换支持 ----------
    def sync_from_fields(self):
        """切换语言前，把输入框中的未保存内容收回草稿，避免重建时丢失。"""
        if self._editing and self._draft is not None:
            if hasattr(self, "title_entry") and self.title_entry.get_parent() is not None:
                self._draft.title = self.title_entry.get_text()
            if hasattr(self, "notes_tv") and self.notes_tv.get_parent() is not None:
                self._draft.notes = self._read_notes()

    def rerender(self):
        self._render()

    # =========================================================
    # 渲染
    # =========================================================
    def _clear(self):
        # 先解除 Popover 的父子关系，避免控件销毁时 GTK 警告
        if getattr(self, "pop", None) is not None:
            try:
                self.pop.unparent()
            except Exception:
                pass
            self.pop = None
        while (child := self.body.get_first_child()) is not None:
            self.body.remove(child)

    def _render(self):
        self._clear()
        if self._editing:
            self._render_edit()
        else:
            self._render_read()

    # ---------- 查看模式 ----------
    def _render_read(self):
        d = self._draft
        assert d is not None

        # 顶部工具行
        top = Gtk.Box(spacing=4)
        back = Gtk.Button(label=i18n.t("dt_back"))
        back.add_css_class("btn-plain")
        back.connect("clicked", lambda *_: self.emit_done())
        top.append(back)
        end = Gtk.Box(spacing=2, halign=Gtk.Align.END)
        edit = Gtk.Button(label=i18n.t("dt_edit"))
        edit.add_css_class("btn-plain")
        edit.connect("clicked", lambda *_: self._enter_edit())
        dele = Gtk.Button(label=i18n.t("dt_del"))
        dele.add_css_class("btn-plain")
        dele.add_css_class("danger")
        dele.connect("clicked", self._on_delete)
        end.append(edit)
        end.append(dele)
        top.append(end)
        self.body.append(top)

        # 标题行（勾选圆 + 大标题）
        trow = Gtk.Box(spacing=12, margin_top=6)
        self.chk = Gtk.Button(label="✓")
        self.chk.add_css_class("chk")
        self.chk.set_has_frame(False)
        self.chk.set_valign(Gtk.Align.START)
        self.chk.set_margin_top(2)
        self.chk.connect("clicked", self._on_toggle)
        trow.append(self.chk)
        ttl = Gtk.Label(label=d.title, halign=Gtk.Align.START, xalign=0, wrap=True)
        ttl.add_css_class("dt-title")
        ttl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        trow.append(ttl)
        self.body.append(trow)

        # 截止信息卡
        if d.due is not None:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card.add_css_class("card")
            card.set_margin_top(6)
            lbl = Gtk.Label(label=i18n.t("dt_due_time"), halign=Gtk.Align.START)
            lbl.add_css_class("card-label")
            card.append(lbl)
            val = Gtk.Label(label=util.full_due_text(d.due), halign=Gtk.Align.START)
            val.add_css_class("dt-value")
            card.append(val)
            self.countdown_lbl = Gtk.Label(label="", halign=Gtk.Align.START)
            self.countdown_lbl.add_css_class("dt-countdown")
            card.append(self.countdown_lbl)
            self.body.append(card)

        # 详细说明卡
        if d.notes.strip():
            ncard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            ncard.add_css_class("card")
            ncard.set_margin_top(2)
            nl = Gtk.Label(label=i18n.t("dt_notes"), halign=Gtk.Align.START)
            nl.add_css_class("card-label")
            ncard.append(nl)
            scroll = Gtk.ScrolledWindow(vexpand=True)
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            tv = Gtk.TextView()
            tv.add_css_class("notes-text")
            tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            tv.set_editable(False)
            tv.set_cursor_visible(False)
            buf = tv.get_buffer()
            buf.set_text(d.notes.strip(), -1)
            scroll.set_child(tv)
            ncard.append(scroll)
            self.body.append(ncard)

        self._apply_done_ui()
        self.tick()

    # ---------- 编辑模式 ----------
    def _render_edit(self):
        d = self._draft
        assert d is not None

        top = Gtk.Box(spacing=4)
        cancel = Gtk.Button(label=i18n.t("dt_cancel"))
        cancel.add_css_class("btn-plain")
        cancel.connect("clicked", lambda *_: self._on_cancel())
        top.append(cancel)
        spacer = Gtk.Box(hexpand=True)
        top.append(spacer)
        save = Gtk.Button(label=i18n.t("dt_save"))
        save.add_css_class("btn-primary")
        save.connect("clicked", lambda *_: self._on_save())
        top.append(save)
        self.body.append(top)

        self.title_entry = Gtk.Entry()
        self.title_entry.add_css_class("field")
        self.title_entry.set_placeholder_text(i18n.t("dt_title_hint"))
        self.title_entry.set_text(d.title)
        self.title_entry.set_margin_top(6)
        self.title_entry.connect("activate", lambda *_: self._on_save())
        self.body.append(self.title_entry)

        # 截止日期行
        due_box = Gtk.Box(spacing=8, margin_top=4)
        due_box.add_css_class("card")
        due_box.set_margin_top(6)
        dlbl = Gtk.Label(label=i18n.t("dt_due"))
        dlbl.add_css_class("card-label")
        dlbl.set_margin_start(12)
        due_box.append(dlbl)
        self.due_btn = Gtk.Button(label="")
        self.due_btn.add_css_class("btn-plain")
        self.due_btn.set_halign(Gtk.Align.END)
        self.due_btn.set_hexpand(True)
        due_box.append(self.due_btn)
        self.body.append(due_box)

        # 详细说明输入
        ncard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ncard.add_css_class("card")
        ncard.set_margin_top(6)
        ncard.set_vexpand(True)
        nl = Gtk.Label(label=i18n.t("dt_notes"))
        nl.add_css_class("card-label")
        nl.set_margin_start(12)
        ncard.append(nl)

        holder = Gtk.Overlay()
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_margin_start(8)
        scroll.set_margin_end(8)
        scroll.set_margin_bottom(8)
        self.notes_tv = Gtk.TextView()
        self.notes_tv.add_css_class("notes-text")
        self.notes_tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.notes_tv.set_top_margin(6)
        self.notes_tv.set_bottom_margin(6)
        self.notes_tv.get_buffer().set_text(d.notes, -1)
        scroll.set_child(self.notes_tv)
        holder.set_child(scroll)
        self.notes_hint = Gtk.Label(label=i18n.t("dt_notes_hint"), xalign=0, yalign=0)
        self.notes_hint.add_css_class("notes-hint")
        self.notes_hint.set_margin_top(30)
        self.notes_hint.set_margin_start(12)
        self.notes_hint.set_can_target(False)
        holder.add_overlay(self.notes_hint)
        self.notes_tv.get_buffer().connect("changed", self._on_notes_changed)
        ncard.append(holder)
        self.body.append(ncard)

        self._build_due_popover()
        self._sync_due_btn()

    # ---------- 截止日期弹层 ----------
    def _build_due_popover(self):
        self.pop = Gtk.Popover(autohide=True)
        self.pop.set_position(Gtk.PositionType.BOTTOM)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)

        # 快捷胶囊
        quick = Gtk.Box(spacing=6)
        for name, fn in self._quick_dates():
            b = Gtk.Button(label=i18n.t(name))
            b.add_css_class("quick")
            b.connect("clicked", self._on_quick, fn)
            quick.append(b)
        box.append(quick)

        self.cal = Gtk.Calendar()
        now = datetime.now()
        base = self._draft.due or now
        self.cal.select_day(GLib.DateTime.new_local(
            base.year, base.month, base.day, 0, 0, 0.0))
        box.append(self.cal)

        # 时间
        trow = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        hour, minute = (base.hour, base.minute) if self._draft.due else (9, 0)
        self.spin_h = self._spin(0, 23, hour)
        self.spin_m = self._spin(0, 59, minute)
        trow.append(Gtk.Label(label=i18n.t("dt_time")))
        trow.append(self.spin_h)
        trow.append(Gtk.Label(label=":"))
        trow.append(self.spin_m)
        box.append(trow)

        ok = Gtk.Button(label=i18n.t("dt_ok"))
        ok.add_css_class("btn-primary")
        ok.set_halign(Gtk.Align.CENTER)
        ok.connect("clicked", self._apply_popover)
        box.append(ok)

        self.pop.set_child(box)
        self.pop.set_parent(self.due_btn)
        self.due_btn.connect("clicked", lambda *_: self.pop.popup())

    @staticmethod
    def _spin(lo, hi, val) -> Gtk.SpinButton:
        s = Gtk.SpinButton.new_with_range(lo, hi, 1)
        s.set_value(val)
        s.set_wrap(True)
        s.add_css_class("time-spin")
        s.set_width_chars(2)
        try:                       # 数字居中（GtkEditable.xalign，GTK ≥ 4.2）
            s.set_property("xalign", 0.5)
        except Exception:
            pass
        return s

    def _quick_dates(self):
        now = datetime.now()
        nxt_half = (now + timedelta(hours=1)).replace(minute=0 if now.minute < 30 else 30)
        monday = now.date() + timedelta(days=(7 - now.weekday()) % 7 or 7)

        def q(dt):
            return lambda: dt

        return [
            ("q_today", q(nxt_half)),
            ("q_tom", q((now + timedelta(days=1)).replace(hour=9, minute=0))),
            ("q_after", q((now + timedelta(days=2)).replace(hour=9, minute=0))),
            ("q_next_mon", q(datetime(monday.year, monday.month, monday.day, 9, 0))),
        ]

    def _on_quick(self, _b, fn):
        self._draft.due = fn()
        self._sync_due_btn()
        # 同步日历显示
        d = self._draft.due
        self.cal.select_day(GLib.DateTime.new_local(d.year, d.month, d.day, 0, 0, 0.0))
        self.spin_h.set_value(d.hour)
        self.spin_m.set_value(d.minute)

    def _apply_popover(self, *_):
        gdt = self.cal.get_date()
        self._draft.due = datetime(
            gdt.get_year(), gdt.get_month(), gdt.get_day_of_month(),
            int(self.spin_h.get_value()), int(self.spin_m.get_value()),
        )
        self._sync_due_btn()
        self.pop.popdown()

    def _clear_due(self):
        self._draft.due = None
        self._sync_due_btn()

    def _sync_due_btn(self):
        if self._draft.due is None:
            self.due_btn.set_label(i18n.t("dt_add_due"))
        else:
            today = datetime.now().date()
            self.due_btn.set_label(
                f"{util.day_header(self._draft.due.date(), today)} "
                f"{self._draft.due.strftime('%H:%M')}")

    # =========================================================
    # 事件
    # =========================================================
    def _focus_title(self):
        if hasattr(self, "title_entry"):
            self.title_entry.grab_focus()
        return GLib.SOURCE_REMOVE

    def _on_key(self, _c, keyval, *_):
        if keyval == Gdk.KEY_Escape:
            if self._editing:
                self._on_cancel()
            else:
                self.emit_done()
            return True
        return False

    def _enter_edit(self):
        self._editing = True
        if not self._is_new:
            fresh = self.store.get(self._draft.id)
            self._draft = fresh.copy() if fresh is not None else self._draft
        self._render()
        GLib.idle_add(self._focus_title)

    def _on_cancel(self):
        if self._is_new:
            self.emit_done()
        else:
            self._editing = False
            self.show_read(self._draft.id)

    def _on_save(self):
        d = self._draft
        assert d is not None
        title = self.title_entry.get_text().strip()
        notes = self._read_notes()

        if self._is_new:
            if not title:            # 新建时空标题 = 放弃
                self.emit_done()
                return
            d.id = uuid4().hex
            d.title, d.notes = title, notes
            self.store.add(d)
        else:
            d.title = title or d.title   # 编辑时不允许清空标题，其余照存
            d.notes = notes
            self.store.update(d.id, title=d.title, notes=d.notes, due=d.due)
        self._editing = False
        self.emit_done()

    def _read_notes(self) -> str:
        buf = self.notes_tv.get_buffer()
        start, end = buf.get_bounds()
        return buf.get_text(start, end, False).strip()

    def _on_notes_changed(self, *_):
        self.notes_hint.set_visible(self.notes_tv.get_buffer().get_char_count() == 0)

    def _on_toggle(self, *_):
        self.store.toggle_done(self._draft.id)
        self._draft = self.store.get(self._draft.id) or self._draft
        self._apply_done_ui()
        self.tick()

    def _on_delete(self, *_):
        removed = self.store.remove(self._draft.id)
        if removed is not None and self.on_deleted:
            self.on_deleted(removed)
        self.emit_done()

    # ---------- 外观 / 心跳 ----------
    def _apply_done_ui(self):
        if self._draft.done:
            self.chk.add_css_class("done")
        else:
            self.chk.remove_css_class("done")

    def tick(self):
        """每分钟刷新倒计时（仅查看模式）。"""
        if self._editing or self._draft is None or self._draft.due is None:
            return
        if hasattr(self, "countdown_lbl") and self.countdown_lbl.get_parent() is not None:
            txt, cls = util.countdown_text(self._draft.due, datetime.now())
            self.countdown_lbl.set_text(txt)
            for c in ("ok", "soon", "bad"):
                if c != cls:
                    self.countdown_lbl.remove_css_class(c)
            self.countdown_lbl.add_css_class(cls)

    def emit_done(self):
        self.emit("done")
