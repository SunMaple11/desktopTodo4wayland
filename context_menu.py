"""统一的右键菜单控制器。

GTK4 的右键事件会在窗口、列表和行之间传播，Popover 还有自己的 grab/
autohide 机制。这里只在列表层处理一次右键，并用普通按钮回调执行操作，
不再把菜单生命周期绑定到会刷新的行控件。
"""
from __future__ import annotations

import gi
from gi.repository import Gdk, GLib, Gtk


class ContextMenuController:
    def __init__(self, owner: Gtk.Window):
        self.owner = owner
        self.popover: Gtk.Popover | None = None

    def close(self):
        pop = self.popover
        self.popover = None
        if pop is not None:
            try:
                pop.popdown()
            finally:
                # 不在点击回调里销毁父控件；让 GTK 在本轮事件结束后回收。
                GLib.idle_add(self._dispose, pop)

    @staticmethod
    def _dispose(pop):
        try:
            pop.unparent()
        except Exception:
            pass
        return GLib.SOURCE_REMOVE

    def show(self, parent: Gtk.Widget, items, x: float, y: float):
        self.close()
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("context-menu")
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        box.set_margin_start(5)
        box.set_margin_end(5)

        for label, callback in items:
            button = Gtk.Button(label=label)
            button.add_css_class("context-menu-item")
            button.set_has_frame(False)
            button.set_can_focus(True)
            button.connect("clicked", self._activate, callback)
            box.append(button)

        pop = Gtk.Popover(autohide=True)
        pop.add_css_class("context-menu-popover")
        pop.set_has_arrow(False)
        pop.set_child(box)
        pop.set_parent(parent)
        pop.set_pointing_to(rect)
        self.popover = pop
        # 等右键 release 完成再显示，避免 release 落到第一项。
        GLib.idle_add(self._show, pop)
        return pop

    def _show(self, pop):
        if self.popover is not pop:
            return GLib.SOURCE_REMOVE
        try:
            pop.popup()
        except Exception:
            pass
        return GLib.SOURCE_REMOVE

    def _activate(self, _button, callback):
        self.close()
        callback()
