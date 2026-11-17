#!/bin/sh
# 启动桌面待办（原生 Wayland / GTK4）
# LANG 缺失时取系统默认，保证 GTK 内置菜单（文本右键等）语言正确
if [ -z "$LANG" ]; then
    . /etc/default/locale 2>/dev/null
    [ -n "$LANG" ] && export LANG
fi
cd "$(dirname "$0")" || exit 1
exec python3 main.py "$@"
