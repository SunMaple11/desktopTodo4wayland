"""数据层：待办事项的加载、校验、增删改查与原子化落盘。

设计要点（防内存 / 防数据损坏）：
- 纯同步、单进程；没有任何后台线程或轮询。
- 保存时先写临时文件并 fsync，再 os.replace 原子替换，断电不会写坏文件。
- 加载时逐条校验，坏数据自动备份、跳过，不会让程序崩溃。
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import gi
from gi.repository import GObject

gi.require_version("Gtk", "4.0")

_DT_FMT = "%Y-%m-%dT%H:%M"          # 本地时间，精确到分钟（与 DDL 的语义一致）


def _parse_dt(s) -> datetime | None:
    if not isinstance(s, str):
        return None
    try:
        return datetime.strptime(s, _DT_FMT)
    except ValueError:
        return None


def _fmt_dt(d: datetime | None) -> str | None:
    return d.strftime(_DT_FMT) if d else None


@dataclass
class Todo:
    id: str
    title: str
    notes: str = ""
    due: datetime | None = None
    done: bool = False
    done_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)

    # ---------- 序列化 ----------
    @classmethod
    def from_dict(cls, d) -> "Todo | None":
        """从字典恢复；任何字段非法都返回 None（宁缺毋滥，绝不抛异常）。"""
        if not isinstance(d, dict):
            return None
        tid, title = d.get("id"), d.get("title")
        if not isinstance(tid, str) or not tid:
            return None
        if not isinstance(title, str) or not title.strip():
            return None
        notes = d.get("notes") if isinstance(d.get("notes"), str) else ""
        return cls(
            id=tid,
            title=title.strip(),
            notes=notes,
            due=_parse_dt(d.get("due")),
            done=bool(d.get("done", False)),
            done_at=_parse_dt(d.get("done_at")),
            created_at=_parse_dt(d.get("created_at")) or datetime.now(),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "notes": self.notes,
            "due": _fmt_dt(self.due),
            "done": self.done,
            "done_at": _fmt_dt(self.done_at),
            "created_at": _fmt_dt(self.created_at),
        }

    def copy(self) -> "Todo":
        """深拷贝，供「编辑草稿」使用，取消编辑时不影响原数据。"""
        return Todo(
            id=self.id, title=self.title, notes=self.notes,
            due=self.due, done=self.done, done_at=self.done_at,
            created_at=self.created_at,
        )


class TodoStore(GObject.GObject):
    """持有全部待办；任何修改后发射 `changed` 信号并立即落盘一次。"""

    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, path: Path | None = None):
        super().__init__()
        data_home = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        self.path = path or (data_home / "desktoptodo" / "todos.json")
        self.todos: list[Todo] = []
        self._load()

    # ---------- 加载 ----------
    def _load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            items = data.get("todos", []) if isinstance(data, dict) else []
        except FileNotFoundError:
            return
        except Exception:
            backup = self.path.with_suffix(".json.corrupt")
            try:
                shutil.copy2(self.path, backup)
                print(f"[desktoptodo] 数据文件损坏，已备份到 {backup}")
            except OSError:
                pass
            return

        for it in items if isinstance(items, list) else []:
            t = Todo.from_dict(it)
            if t is not None:
                self.todos.append(t)

    # ---------- 保存（原子写） ----------
    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                {"version": 1, "todos": [t.to_dict() for t in self.todos]},
                ensure_ascii=False, indent=2,
            )
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".todos-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)   # 原子替换：要么旧文件、要么新文件
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        except OSError as e:
            print(f"[desktoptodo] 保存失败: {e}")

    # ---------- 查询 ----------
    def get(self, tid: str) -> Todo | None:
        return next((t for t in self.todos if t.id == tid), None)

    def pending(self) -> list[Todo]:
        return [t for t in self.todos if not t.done]

    def completed(self) -> list[Todo]:
        return [t for t in self.todos if t.done]

    # ---------- 修改 ----------
    def add(self, todo: Todo) -> None:
        self.todos.append(todo)
        self._commit()

    def update(self, tid: str, **fields) -> None:
        t = self.get(tid)
        if t is None:
            return
        for k, v in fields.items():
            if hasattr(t, k):
                setattr(t, k, v)
        self._commit()

    def remove(self, tid: str) -> Todo | None:
        t = self.get(tid)
        if t is not None:
            self.todos.remove(t)
            self._commit()
        return t

    def toggle_done(self, tid: str) -> None:
        t = self.get(tid)
        if t is None:
            return
        t.done = not t.done
        t.done_at = datetime.now() if t.done else None
        self._commit()

    def _commit(self) -> None:
        self._save()
        self.emit("changed")
