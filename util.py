"""日期 / 文案的格式化工具（列表与详情页共用，双语）。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import i18n


def day_header(d: date, today: date) -> str:
    """分节标题：今天 / 明天 / 后天 / 11月20日 · 周五"""
    n = (d - today).days
    if n == 0:
        return i18n.t("sec_today")
    if n == 1:
        return i18n.t("sec_tomorrow")
    if n == 2:
        return i18n.t("sec_after2")
    md = i18n.month_day(d)
    return i18n.t("dh_fmt", md=md, wshort=i18n.week_short(d.weekday()))


def due_chip_text(due: datetime, today: date) -> str:
    """列表行右侧的 DDL 短文案。"""
    d = due.date()
    hm = due.strftime("%H:%M")
    n = (d - today).days
    if n < 0:
        return i18n.t("chip_overdue", n=(today - d).days or 1)
    if n == 0:
        return f'{i18n.t("today")} {hm}'
    if n == 1:
        return f'{i18n.t("sec_tomorrow").split()[0]} {hm}' if i18n.get_lang() == "en" else f'明天 {hm}'
    if n < 7:
        return f"{i18n.week_short(d.weekday())} {hm}"
    return i18n.month_day(d)


def chip_class(due: datetime | None, today: date) -> str:
    """DDL 胶囊的配色档位。"""
    if due is None:
        return "none"
    n = (due.date() - today).days
    if n < 0:
        return "overdue"
    if n == 0:
        return "today"
    return "later"


def full_due_text(due: datetime) -> str:
    # 2026年11月20日 周五 14:00  /  Fri, Nov 20 2026 14:00
    if i18n.get_lang() == "zh":
        return f"{due.year}年{i18n.month_day(due)} {i18n.week_short(due.weekday())} {due.strftime('%H:%M')}"
    return (f"{i18n.week_short(due.weekday())}, {i18n.month_day(due)} "
            f"{due.year} {due.strftime('%H:%M')}")


def countdown_text(due: datetime, now: datetime) -> tuple[str, str]:
    """详情页倒计时文案 + 配色档（ok / soon / bad）。"""
    delta = due - now
    if delta.total_seconds() < 0:                      # 已逾期
        neg = -delta
        if neg < timedelta(hours=1):
            txt = i18n.t("cd_over_min", n=max(neg.seconds // 60, 1))
        elif neg < timedelta(days=1):
            txt = i18n.t("cd_over_h", n=neg.seconds // 3600)
        else:
            txt = i18n.t("cd_over_d", n=neg.days)
        return txt, "bad"
    if delta < timedelta(hours=1):
        return i18n.t("cd_left_min", n=max(delta.seconds // 60, 1)), "bad"
    if delta < timedelta(days=1):
        h, m = delta.seconds // 3600, (delta.seconds % 3600) // 60
        return i18n.t("cd_left_hm", h=h, m=m), "soon"
    return i18n.t("cd_left_d", n=delta.days), "soon" if delta < timedelta(days=3) else "ok"


def long_date(today: date) -> str:
    """顶栏日期：11月16日 星期日 / Sun, Nov 16"""
    md = i18n.month_day(today)
    if i18n.get_lang() == "zh":
        return i18n.t("long_fmt", md=md, wfull=i18n.week_full(today.weekday()))
    return i18n.t("long_fmt", md=md, wshort=i18n.week_short(today.weekday()))
