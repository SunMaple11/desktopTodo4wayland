"""DesktopTodo —— 原生 Wayland 桌面待办小组件（GTK4 / GNOME）。

用法：
    python3 main.py            正常启动
    python3 main.py --smoke    冒烟测试：1.5 秒后自动退出（用于自检）
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from store import TodoStore  # noqa: E402
from window import APP_ID, MainWindow  # noqa: E402

HERE = Path(__file__).resolve().parent


class App(Gtk.Application):
    def __init__(self, store_path=None):
        super().__init__(application_id=APP_ID)
        self.store_path = store_path   # 测试可注入临时路径
        self.win: MainWindow | None = None

    def do_activate(self):   # noqa: N802（GTK 命名约定）
        if self.win is not None:
            self.win.present()       # 二次启动：只把已有窗口带到前台
            return
        import os
        css_path = os.environ.get("DESKTOPTODO_CSS") or (HERE / "style.css")
        css = Gtk.CssProvider()
        css.load_from_path(str(css_path))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        store = TodoStore(path=self.store_path) if self.store_path else TodoStore()
        self.win = MainWindow(self, store)
        self.win.present()


def _seed_demo(store: "TodoStore") -> None:
    """演示数据（仅 --demo / --demo-dark 时写入临时文件，不碰真实数据）。"""
    from datetime import timedelta
    from store import Todo

    now = datetime.now()
    specs = [
        ("补交实验报告", timedelta(days=-2, hours=-4), True),
        ("给导师回复邮件", timedelta(hours=3), True),
        ("健身 · 跑步 5km", timedelta(hours=6), False),
        ("买生日礼物", timedelta(days=1), True),
        ("整理月度账单", timedelta(days=3), False),
        ("预约下周体检", timedelta(days=9), True),
        ("读《置身事内》第 3 章", None, False),
        ("收拾书桌", timedelta(days=-1), False),
    ]
    for title, delta, has_notes in specs:
        t = Todo(id="", title=title,
                 due=(now + delta) if delta else None,
                 notes=f"关于「{title}」的详细说明：\n· 具体步骤一\n· 具体步骤二" if has_notes else "")
        store.todos.append(t)
    t_done = Todo(id="", title="缴房租", due=now - timedelta(days=1), notes="")
    t_done.done = True
    t_done.done_at = now - timedelta(hours=20)
    store.todos.append(t_done)
    store._commit()


def main() -> int:
    argv = sys.argv[1:]
    app: App
    if "--demo" in argv:
        import tempfile
        from pathlib import Path as _P

        tmp = _P(tempfile.mkdtemp(prefix="dt-demo-")) / "todos.json"
        app = App(store_path=tmp)
        app.connect("activate", lambda a: _seed_demo(a.win.store) if a.win else None)
    else:
        app = App()
    if "--smoke" in argv or "--demo" in argv:
        GLib.timeout_add(8000, app.quit)   # 演示/冒烟 8 秒后自动退出
    return app.run(None)


if __name__ == "__main__":
    sys.exit(main())
