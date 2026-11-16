"""日期 / 文案的格式化工具（列表与详情页共用）。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

WEEK_CN = "一二三四五六日"


def week_label(d: date) -> str:
    return "周" + WEEK_CN[d.weekday()]


def day_header(d: date, today: date) -> str:
    """分节标题：今天 / 明天 / 后天 / 11月20日 · 周五"""
    n = (d - today).days
    if n == 0:
        return "今天"
    if n == 1:
        return "明天"
    if n == 2:
        return "后天"
    return f"{d.month}月{d.day}日 · {week_label(d)}"


def due_chip_text(due: datetime, today: date) -> str:
    """列表行右侧的 DDL 短文案。"""
    d = due.date()
    hm = due.strftime("%H:%M")
    n = (d - today).days
    if n < 0:
        days = today - d
        return f"逾期{days.days}天" if days.days > 1 else "逾期1天"
    if n == 0:
        return f"今天 {hm}"
    if n == 1:
        return f"明天 {hm}"
    if n < 7:
        return f"{week_label(d)} {hm}"
    return f"{d.month}月{d.day}日"


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
    return f"{due.year}年{due.month}月{due.day}日 {week_label(due.date())} {due.strftime('%H:%M')}"


def countdown_text(due: datetime, now: datetime) -> tuple[str, str]:
    """详情页倒计时文案 + 配色档（ok / soon / bad）。"""
    delta = due - now
    if delta.total_seconds() < 0:                      # 已逾期
        neg = -delta
        if neg < timedelta(hours=1):
            txt = f"已逾期 {neg.seconds // 60} 分钟"
        elif neg < timedelta(days=1):
            txt = f"已逾期 {neg.seconds // 3600} 小时"
        else:
            txt = f"已逾期 {neg.days} 天"
        return txt, "bad"
    if delta < timedelta(hours=1):
        return f"还剩 {max(delta.seconds // 60, 1)} 分钟", "bad"
    if delta < timedelta(days=1):
        h, m = delta.seconds // 3600, (delta.seconds % 3600) // 60
        return f"还剩 {h} 小时 {m} 分", "soon"
    if delta < timedelta(days=3):
        return f"还剩 {delta.days} 天", "soon"
    return f"还剩 {delta.days} 天", "ok"


def long_date(today: date) -> str:
    """顶栏日期：11月16日 星期日"""
    wk = "星期" + WEEK_CN[today.weekday()]
    return f"{today.month}月{today.day}日 {wk}"
