#!/bin/sh
# 构建 .deb 包（无需 debhelper，仅用 dpkg-deb）
# 用法：./build-deb.sh [版本号]   →  dist/desktoptodo_<版本>_all.deb
set -e

VERSION="${1:-1.3.1}"
HERE="$(cd "$(dirname "$0")" && pwd)"
STAGE="$HERE/build/deb/desktoptodo"
OUT="$HERE/dist"

rm -rf "$HERE/build"
mkdir -p \
    "$STAGE/usr/lib/desktoptodo" \
    "$STAGE/usr/bin" \
    "$STAGE/usr/share/applications" \
    "$STAGE/usr/share/icons/hicolor/scalable/apps" \
    "$STAGE/usr/share/doc/desktoptodo" \
    "$STAGE/DEBIAN"

# ---- 程序文件（main.py 按自身路径定位 style.css，无需 cwd） ----
for f in main.py window.py list_view.py detail_view.py store.py util.py i18n.py style.css; do
    cp "$HERE/$f" "$STAGE/usr/lib/desktoptodo/$f"
done

# ---- 启动器 ----
cat > "$STAGE/usr/bin/desktoptodo" <<'EOF'
#!/bin/sh
# LANG 缺失时取系统默认，保证 GTK 内置菜单（文本右键等）语言正确
if [ -z "$LANG" ]; then
    . /etc/default/locale 2>/dev/null
    [ -n "$LANG" ] && export LANG
fi
exec /usr/bin/python3 /usr/lib/desktoptodo/main.py "$@"
EOF
chmod 755 "$STAGE/usr/bin/desktoptodo"

# ---- 桌面入口与图标 ----
cat > "$STAGE/usr/share/applications/desktoptodo.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=桌面待办
Name[en]=Desktop Todo
Comment=macOS 风格的桌面待办清单（原生 Wayland / GTK4）
Exec=desktoptodo
Icon=desktoptodo
Terminal=false
Categories=Utility;
Keywords=todo;task;ddl;待办;清单;截止;
StartupWMClass=com.sunmaple.desktodo
EOF
cp "$HERE/desktoptodo.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/desktoptodo.svg"

# ---- 文档 ----
cp "$HERE/LICENSE" "$STAGE/usr/share/doc/desktoptodo/copyright"
cat > "$STAGE/usr/share/doc/desktoptodo/changelog" <<EOF
desktoptodo ($VERSION) stable; urgency=medium

  * Release $VERSION, see CHANGELOG.md in the source repository.

 -- SunMaple <1193067705@qq.com>  $(date -R)
EOF
gzip -9n "$STAGE/usr/share/doc/desktoptodo/changelog"

# ---- 控制文件 ----
INSTALLED_SIZE="$(du -sk "$STAGE/usr" | cut -f1)"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: desktoptodo
Version: $VERSION
Architecture: all
Maintainer: SunMaple <1193067705@qq.com>
Installed-Size: $INSTALLED_SIZE
Depends: python3-gi, gir1.2-gtk-4.0
Section: utils
Priority: optional
Homepage: https://github.com/SunMaple11/desktopTodo4wayland
Description: macOS-style desktop todo list (native Wayland / GTK4)
 macOS 风格的桌面待办清单：按 DDL 排序，日/周/月视图，详情与倒计时，
 半透明圆角面板，跟随系统深浅色。无 Electron，低功耗（无轮询线程）。
EOF
chmod 644 "$STAGE/DEBIAN/control"

# ---- 权限规范化（644/755，不受本地 umask 影响） ----
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/usr/bin/desktoptodo"

# ---- 打包 ----
mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT/desktoptodo_${VERSION}_all.deb"

echo
echo "构建完成：dist/desktoptodo_${VERSION}_all.deb"
