#!/bin/sh
# 安装：图标 + 应用菜单入口（可选 --autostart 加入开机自启）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

# 图标
mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
cp -f "$HERE/desktoptodo.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/desktoptodo.svg"

# 菜单入口（写入实际路径）
mkdir -p "$HOME/.local/share/applications"
sed "s|^Path=.*|Path=$HERE|" "$HERE/desktoptodo.desktop" \
    > "$HOME/.local/share/applications/desktoptodo.desktop"

if [ "$1" = "--autostart" ]; then
    mkdir -p "$HOME/.config/autostart"
    cp -f "$HOME/.local/share/applications/desktoptodo.desktop" \
          "$HOME/.config/autostart/desktoptodo.desktop"
    echo "已加入开机自启"
fi

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "安装完成：应用列表里搜索「桌面待办」即可"
