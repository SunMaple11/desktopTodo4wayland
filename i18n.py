"""轻量双语支持：所有 UI 文案经 t() 取值，切换语言后整体重建界面。"""
from __future__ import annotations

from pathlib import Path

_current = "zh"

ZH = {
    "app_title": "待办",
    "view_day": "日", "view_week": "周", "view_month": "月",
    "sec_overdue": "已逾期", "sec_today": "今天", "sec_tomorrow": "明天",
    "sec_after2": "后天", "sec_nodate": "无日期", "sec_later": "更晚",
    "sec_done": "已完成",
    "chip_nodate": "无日期", "chip_overdue": "逾期{n}天", "today": "今天",
    "sub_overdue": "{n} 项逾期", "sub_today": "今天 {n} 项",
    "sub_pending": "{n} 项待办",
    "empty": "这里空空如也，享受当下 ✨",
    "undo_deleted": "已删除「{t}」", "undo": "撤销",
    "act_done": "标记完成", "act_undone": "取消完成", "act_remove": "删除",
    "dt_back": "‹  返回", "dt_edit": "编辑", "dt_del": "删除",
    "dt_cancel": "取消", "dt_save": "保存",
    "dt_title_hint": "标题，例如：提交实验报告",
    "dt_due": "截止", "dt_due_time": "截止时间", "dt_notes": "详细说明",
    "dt_notes_hint": "点击填写详细说明…", "dt_add_due": "添加截止日期  ›",
    "dt_time": "时间", "dt_ok": "确定",
    "q_today": "今天", "q_tom": "明天 9:00", "q_after": "后天 9:00",
    "q_next_mon": "下周一 9:00",
    "m_new": "新建待办", "m_view": "视图", "m_settings": "设置",
    "cd_over_min": "已逾期 {n} 分钟", "cd_over_h": "已逾期 {n} 小时",
    "cd_over_d": "已逾期 {n} 天",
    "cd_left_min": "还剩 {n} 分钟", "cd_left_hm": "还剩 {h} 小时 {m} 分",
    "cd_left_d": "还剩 {n} 天",
    "set_title": "设置", "set_lang": "语言",
    "set_lang_zh": "中文", "set_lang_en": "English",
    "set_size": "窗口大小", "set_size_s": "小", "set_size_m": "中",
    "set_size_l": "大", "set_autostart": "开机自启",
    "set_autostart_hint": "登录系统时自动启动",
    "set_layer": "窗口层级", "layer_normal": "普通", "layer_top": "置顶",
    "layer_bottom": "置底",
    "layer_hint": "置顶/置底需要 GNOME Shell 扩展，首次选择会自动安装",
    "layer_unavailable": "扩展不可用，请注销后重新登录",
    "layer_failed": "窗口层级设置失败",
    "md_fmt": "{m}月{d}日", "long_fmt": "{md} {wfull}",
    "dh_fmt": "{md} · {wshort}",
    # 月份 / 星期（索引 0=周一）
    "wfull": "星期一 星期二 星期三 星期四 星期五 星期六 星期日".split(),
    "wshort": "周一 周二 周三 周四 周五 周六 周日".split(),
}

EN = {
    "app_title": "To-Dos",
    "view_day": "Day", "view_week": "Week", "view_month": "Month",
    "sec_overdue": "Overdue", "sec_today": "Today", "sec_tomorrow": "Tomorrow",
    "sec_after2": "In 2 days", "sec_nodate": "No Date", "sec_later": "Later",
    "sec_done": "Completed",
    "chip_nodate": "No date", "chip_overdue": "{n}d overdue", "today": "Today",
    "sub_overdue": "{n} overdue", "sub_today": "{n} today",
    "sub_pending": "{n} todos",
    "empty": "All clear. Enjoy ✨",
    "undo_deleted": "Deleted “{t}”", "undo": "Undo",
    "act_done": "Mark done", "act_undone": "Mark undone", "act_remove": "Delete",
    "dt_back": "‹  Back", "dt_edit": "Edit", "dt_del": "Delete",
    "dt_cancel": "Cancel", "dt_save": "Save",
    "dt_title_hint": "Title, e.g. Submit lab report",
    "dt_due": "Due", "dt_due_time": "Due Date", "dt_notes": "Notes",
    "dt_notes_hint": "Type your notes…", "dt_add_due": "Add due date  ›",
    "dt_time": "Time", "dt_ok": "OK",
    "q_today": "Today", "q_tom": "Tomorrow 9:00", "q_after": "In 2 days 9:00",
    "q_next_mon": "Next Mon 9:00",
    "m_new": "New To-Do", "m_view": "View", "m_settings": "Settings",
    "cd_over_min": "Overdue {n}m", "cd_over_h": "Overdue {n}h",
    "cd_over_d": "Overdue {n}d",
    "cd_left_min": "{n}m left", "cd_left_hm": "{h}h {m}m left",
    "cd_left_d": "{n}d left",
    "set_title": "Settings", "set_lang": "Language",
    "set_lang_zh": "中文", "set_lang_en": "English",
    "set_size": "Window Size", "set_size_s": "S", "set_size_m": "M",
    "set_size_l": "L", "set_autostart": "Start at login",
    "set_autostart_hint": "Launch automatically on sign-in",
    "set_layer": "Window Layer", "layer_normal": "Normal", "layer_top": "On Top",
    "layer_bottom": "Below",
    "layer_hint": "On Top/Below needs a GNOME Shell extension; installed on first use",
    "layer_unavailable": "Extension unavailable; sign out and back in",
    "layer_failed": "Failed to set window layer",
    "md_fmt": "{mon} {d}", "long_fmt": "{wshort}, {md}",
    "dh_fmt": "{wshort} · {md}",
    "wfull": "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split(),
    "wshort": "Mon Tue Wed Thu Fri Sat Sun".split(),
}

_MONTHS_EN = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_TABLES = {"zh": ZH, "en": EN}


def set_lang(code: str) -> None:
    global _current
    _current = code if code in _TABLES else "zh"


def get_lang() -> str:
    return _current


def t(key: str, **fmt) -> str:
    """取当前语言文案；fmt 参数做 .format 替换。"""
    v = _TABLES[_current].get(key)
    if v is None:
        return key
    return v.format(**fmt) if fmt else v


def month_name(m: int) -> str:
    if _current == "en":
        return _MONTHS_EN[m - 1]
    return str(m)


def month_day(d) -> str:
    """11月20日 / Nov 20"""
    return t("md_fmt", m=month_name(d.month), d=d.day, mon=month_name(d.month))


def week_short(wd: int) -> str:
    return _TABLES[_current]["wshort"][wd]


def week_full(wd: int) -> str:
    return _TABLES[_current]["wfull"][wd]
