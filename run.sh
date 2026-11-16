#!/bin/sh
# 启动桌面待办（原生 Wayland / GTK4）
cd "$(dirname "$0")" || exit 1
exec python3 main.py "$@"
