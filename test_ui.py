"""自动化交互测试：用临时数据驱动真实窗口，模拟增删改查 / 视图切换 / 心跳。
不依赖人工点击；任何断言失败或未捕获异常都会以非零码退出。"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from datetime import date, datetime, timedelta

import i18n
import util
from main import App
from store import Todo, TodoStore

FAILURES: list[str] = []


def check(cond: bool, msg: str):
    tag = "ok" if cond else "FAIL"
    print(f"  [{tag}] {msg}")
    if not cond:
        FAILURES.append(msg)


def make_store() -> TodoStore:
    tmp = Path(tempfile.mkdtemp(prefix="dt-test-"))
    return TodoStore(path=tmp / "todos.json")


def seed(store: TodoStore) -> list[str]:
    from datetime import date, time
    today = date.today()
    ids = []
    specs = [
        ("逾期任务", datetime.combine(today - timedelta(days=2), time(12, 0)), False),
        ("今天到期", datetime.combine(today, time(23, 59)), False),
        ("明天上午", datetime.combine(today + timedelta(days=1), time(9, 0)), False),
        ("下周任务", datetime.combine(today + timedelta(days=8), time(9, 0)), False),
        ("无日期任务", None, False),
        ("已完成任务", datetime.combine(today - timedelta(days=1), time(12, 0)), True),
    ]
    for title, due, done in specs:
        t = Todo(id=f"id-{title}", title=title, due=due,
                 notes=f"{title} 的详细说明" + ("\n第二行" if "逾期" in title else ""))
        t.done = done
        t.done_at = datetime.now() if done else None
        store.todos.append(t)
        ids.append(t.id)
    store._commit()
    return ids


def run_ui_checks(app: App) -> None:
    win = app.win
    store = win.store
    lst = win.todo_list
    i18n.set_lang("zh")
    win.apply_lang()
    print("== 数据种子 ==")
    ids = seed(store)
    check(len(store.todos) == 6, f"种子 6 条，实际 {len(store.todos)}")

    print("== 日视图分组 ==")
    secs = lst._sections()
    names = [s[0] for s in secs]
    print("   分节:", names)
    check("已逾期" in names and "今天" in names, "日视图含 已逾期/今天")
    check("无日期" in names, "日视图含 无日期")
    check(names[-1] == "已完成", "已完成 沉底")
    overdue_sec = next(s for s in secs if s[0] == "已逾期")
    check(all(t.due.date() < datetime.now().date() for t in overdue_sec[2]), "逾期分节内全部已过期")

    print("== 周视图 ==")
    lst._on_seg(lst._seg_btns["week"], "week")
    secs = lst._sections()
    names = [s[0] for s in secs]
    print("   分节:", names)
    check("今天" in names and "明天" in names, "周视图含 今天/明天")
    dated = {t.title for s in secs if s[0] not in ("更晚", "无日期", "已完成") for t in s[2]}
    check("下周任务" not in dated, "8 天后任务不进周视图的按日分节")
    check("更晚" in names and "下周任务" in
          {t.title for s in secs if s[0] == "更晚" for t in s[2]},
          "8 天后任务归入「更晚」分节")

    print("== 月视图 ==")
    lst._on_seg(lst._seg_btns["month"], "month")
    secs = lst._sections()
    flat = [t.title for s in secs for t in s[2]]
    check("下周任务" in flat, "8 天后任务出现在月视图")
    pend_secs = [s for s in secs if s[0] != "已完成" and s[0] != "无日期"]
    order = [t.due for s in pend_secs for t in s[2] if t.due]
    check(order == sorted(order), "严格按 DDL 升序")

    print("== 排序稳定性 ==")
    pend = sorted((t for t in store.pending() if t.due), key=lambda t: t.due)
    check(pend[0].title == "逾期任务", "最早 DDL 排最前")

    print("== 详情页 / 编辑保存 ==")
    win.open_todo(ids[0])
    check(win.stack.get_visible_child_name() == "detail", "进入详情页")
    dv = win.detail
    check(dv._draft.title == "逾期任务", "详情加载正确")
    dv._enter_edit()
    dv.title_entry.set_text("逾期任务（改）")
    dv._draft.due = datetime.now() + timedelta(days=3)
    dv._on_save()
    check(win.stack.get_visible_child_name() == "list", "保存后返回列表")
    t = store.get(ids[0])
    check(t.title == "逾期任务（改）" and t.due.date() == (datetime.now() + timedelta(days=3)).date(),
          "编辑结果已入库")

    print("== 勾选完成 ==")
    store.toggle_done(ids[1])
    check(store.get(ids[1]).done is True and store.get(ids[1]).done_at is not None, "toggle_done 落库")

    print("== 删除 + 撤销 ==")
    removed = store.remove(ids[2])
    lst.show_undo(removed)
    check(store.get(ids[2]) is None, "已删除")
    lst._on_undo()
    check(store.get(ids[2]) is not None, "撤销恢复（保留原 id）")

    print("== 新建（空标题=放弃 / 正常保存） ==")
    win.open_new()
    dv.title_entry.set_text("")
    dv._on_save()
    check(len(store.todos) == 6, f"空标题新建被丢弃，仍为 6 条（实际 {len(store.todos)}）")
    win.open_new()
    dv.title_entry.set_text("新增任务")
    dv.notes_tv.get_buffer().set_text("新增的详细说明", -1)
    dv._on_save()
    check(any(t.title == "新增任务" for t in store.todos), "正常新建入库")
    new_t = next(t for t in store.todos if t.title == "新增任务")
    check(new_t.notes == "新增的详细说明", "备注入库")

    print("== 心跳 ==")
    win._tick()
    check(win._tick_src != 0, "心跳已重新调度")

    print("== 行级右键动作 ==")
    from gi.repository import GLib as _GLib
    win.activate_action("row.toggle", _GLib.Variant("s", ids[3]))
    check(store.get(ids[3]).done is True, "row.toggle 动作生效")
    win.activate_action("row.remove", _GLib.Variant("s", ids[3]))
    check(store.get(ids[3]) is None and lst._undo_todo is not None,
          "row.remove 动作生效且弹出撤销 Toast")
    lst._on_undo()
    check(store.get(ids[3]) is not None, "撤销恢复")

    print("== 双语切换 ==")
    i18n.set_lang("en")
    win.apply_lang()
    names = [s[0] for s in lst._sections()]
    check({"Tomorrow", "No Date", "Completed"} <= set(names)
          and not any('一' <= ch <= '鿿' for n in names for ch in n),
          f"英文分节标题: {names}")
    check(lst._seg_btns["week"].get_label() == "Week", "分段控件双语")
    check("Nov" in util.long_date(date.today()), "顶栏日期本地化")
    i18n.set_lang("zh")
    win.apply_lang()
    names = [s[0] for s in lst._sections()]
    check("明天" in names and "无日期" in names, f"切回中文: {names}")

    print("== 设置持久化 ==")
    from pathlib import Path as _P
    from settings import Settings, SIZES
    s = Settings(path=_P(tempfile.mkdtemp(prefix="dt-set-")) / "settings.json")
    check(s.get("lang") == "zh" and s.get("size") in SIZES, "默认值")
    s.set("lang", "en")
    check(Settings(path=s.path).get("lang") == "en", "写入往返")

    print("== 空白处菜单动作 ==")
    win.activate_action("list.view", _GLib.Variant("s", "week"))
    check(lst.mode == "week", "list.view 切换周视图")
    win.activate_action("list.new", None)
    check(win.stack.get_visible_child_name() == "detail" and win.detail._is_new,
          "list.new 打开新建")
    win.show_list()

    print("== 设置互斥分段 ==")
    btns: dict = {}
    applied = []
    for k in ("a", "b", "c"):
        btns[k] = Gtk.ToggleButton(label=k)
    btns["a"].set_active(True)                     # 初始选中（先于 connect，同真实 UI）
    handler = win._mk_exclusive(btns, applied.append)
    for k in ("a", "b", "c"):
        btns[k].connect("toggled", handler, k)
    btns["b"].set_active(True)                     # 点 b → b 独占
    check(applied == ["b"], f"仅应用最后选择: {applied}")
    check(btns["b"].get_active() and not btns["a"].get_active()
          and not btns["c"].get_active(), "其余自动取消")
    btns["b"].set_active(False)                    # 点击已选项试图取消 → 弹回
    check(btns["b"].get_active() and applied == ["b"], "已选项不可取消（弹回）")

    print("== 设置面板真实互斥（此前漏测：handler 每钮一个导致多选） ==")

    def _find_toggles(w, out):
        ch = w.get_first_child()
        while ch is not None:
            if isinstance(ch, Gtk.ToggleButton):
                out.append(ch)
            _find_toggles(ch, out)
            ch = ch.get_next_sibling()

    panel = win._build_settings()
    toggles: list = []
    _find_toggles(panel, toggles)
    lang_t, size_t = toggles[:2], toggles[2:5]
    lang_t[1].set_active(True)                 # 点 English
    check(sum(b.get_active() for b in lang_t) == 1 and lang_t[1].get_active(),
          "语言组互斥（真实面板）")
    lang_t[1].set_active(False)                # 点已选项 → 弹回
    check(lang_t[1].get_active(), "已选项不可取消（真实面板）")
    size_t[1].set_active(True)                 # 点 中
    check(sum(b.get_active() for b in size_t) == 1, "大小组互斥（真实面板）")
    lang_t[0].set_active(True)                 # 恢复中文，避免影响后续断言

    print("== 右键菜单单实例（挂 listbox，弹新先收旧） ==")
    from list_view import TodoRow, _close_menu
    lst._on_blank_secondary(None, 0, 10, 800)
    check(lst._menu_pop is not None, "空白菜单弹出")
    p1 = lst._menu_pop
    lst._on_blank_secondary(None, 0, 10, 800)
    check(lst._menu_pop is not p1 and p1.get_parent() is None, "再次右键先收旧菜单")
    rows = [r for r in lst.listbox if isinstance(r, TodoRow)]
    if rows:
        rows[0]._on_secondary(None, 0, 5, 5)
        check(lst._menu_pop is not None, "行菜单经委托弹出")
    _close_menu(lst)

    print("== 持久化往返 ==")
    store2 = TodoStore(path=store.path)
    check(len(store2.todos) == len(store.todos), "重载条数一致")
    a = sorted(t.to_dict()["title"] for t in store.todos)
    b = sorted(t.to_dict()["title"] for t in store2.todos)
    check(a == b, "字段无损往返")

    print("== 空数据冒烟 ==")
    empty = make_store()
    empty_store = TodoStore(path=_P(tempfile.mkdtemp(prefix="dt-empty-")) / "t.json")
    from list_view import TodoList as _TL
    el = _TL(empty_store, on_open=lambda _id: None)
    el.refresh()

    app.quit()


def _safe_checks(app):
    """异常也算失败，绝不假通过。"""
    try:
        run_ui_checks(app)
    except Exception:
        import traceback
        traceback.print_exc()
        FAILURES.append("运行时异常（见上方 traceback）")
        app.quit()


def main() -> int:
    # 测试用独立 App + 临时数据文件（绝不触碰真实数据）
    tmp = Path(tempfile.mkdtemp(prefix="dt-test-"))
    # 独立 app id：避免被正在运行的真实实例抢注主实例（否则检查不会执行）
    app = App(store_path=tmp / "todos.json", app_id="com.sunmaple.desktodo.test")
    app.connect("activate", lambda a: GLib.idle_add(_safe_checks, a))
    GLib.timeout_add_seconds(30, app.quit)   # 兜底：30 秒强制退出
    code = app.run(None)
    if FAILURES:
        print(f"\n*** {len(FAILURES)} 项失败 ***")
        return 1
    print("\n全部通过 ✔")
    return code


if __name__ == "__main__":
    sys.exit(main())
