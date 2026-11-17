# 桌面待办 DesktopTodo

macOS 风格的桌面待办清单，为 **Ubuntu 22.04 + GNOME Wayland** 原生打造（GTK4 / Python，无 Electron）。

## 功能

- ✅ **按 DDL 排序**：逾期 → 按截止时间升序；DDL 胶囊三档配色（逾期红 / 今天橙 / 以后灰）
- ✅ **日 / 周 / 月 三种视图**：分段控件切换；周/月按天分组，超出范围的任务归入「更晚」
- ✅ **详情页**：点击任意条目查看详细说明、完整截止时间与倒计时（还剩 X 小时 / 已逾期 X 天）
- ✅ **行内编辑**：标题、详细说明（多行）、截止日期（日历 + 居中时间输入 + 今天/明天/后天/下周一快捷键）
- ✅ **行级右键菜单**：标记完成 / 取消完成、编辑、删除；「已完成」分节保留在底部；空白处右键：新建 / 视图 / 设置
- ✅ **设置面板（顶栏 ⚙）**：中文 / English 全界面即时切换、窗口大小三档、开机自启
- ✅ **删除可撤销**：Toast 6 秒内可一键恢复
- ✅ **macOS 风格**：红绿灯窗口按钮、分段控件、圆形勾选、半透明圆角面板，自动跟随系统深浅色

## 运行

```bash
./run.sh            # 或：python3 main.py
```

依赖（Ubuntu 22.04 桌面版自带，缺失时执行）：

```bash
sudo apt install python3-gi gir1.2-gtk-4.0
```

## 安装

**方式一：deb 包（推荐）**

```bash
./build-deb.sh                # 构建 dist/desktoptodo_1.0.0_all.deb
sudo apt install ./dist/desktoptodo_1.0.0_all.deb
desktoptodo                   # 启动；应用列表里也有「桌面待办」
```

**方式二：源码安装到当前用户**

```bash
./install.sh                  # 安装图标 + 应用菜单入口
./install.sh --autostart      # 同时加入开机自启
```

其他用法：

```bash
python3 main.py --demo   # 演示模式（临时数据，可与真实实例并行，8 秒后自动退出）
python3 test_ui.py       # 38 项自动化交互测试
```

## 数据

保存在 `~/.local/share/desktoptodo/todos.json`（JSON，可手动备份/编辑）。
保存为**原子写**（临时文件 + fsync + rename），断电不会损坏数据；损坏的文件会自动备份为 `.corrupt` 并重建。

## 低功耗设计

- 无后台线程、无轮询循环；仅在**窗口可见**时有一个**每分钟**的定时器（对齐到整分）刷新倒计时文案，窗口隐藏立即停止
- 倒计时刷新只改标签文字，不重建控件
- 跨天（含休眠唤醒）自动整体重建分组
- 每次修改立即落盘（文件极小），关闭窗口即退出，零驻留

## Wayland 说明（GNOME 42）

- 窗口为无边框半透明悬浮窗，可自由拖动；位置由系统记忆
- 面板紧贴窗口边缘、无自带投影，由系统窗口阴影直接贴合圆角，
  呈现 GNOME 原生弹出面板（如快速设置）的观感
- GNOME Wayland 不允许应用自行「置顶」或「贴桌面」（协议层限制）；
  如需常驻，建议把它放到一个独立工作区，或用 `Super+PageUp/Down` 快速切换
- 半透明为真 ARGB；GNOME 合成器不支持窗口背后的实时模糊（毛玻璃），
  视觉上用高透明度面板模拟 macOS 观感

## 发布（GitHub）

```bash
./build-deb.sh 1.0.0                        # 产出 dist/desktoptodo_1.0.0_all.deb
git tag v1.0.0 && git push origin v1.0.0
gh release create v1.0.0 dist/desktoptodo_1.0.0_all.deb \
    --title "v1.0.0" --notes-file CHANGELOG.md
```

用户侧安装：`sudo apt install ./desktoptodo_1.0.0_all.deb`（自动解决依赖
`python3-gi`、`gir1.2-gtk-4.0`）。

## 代码结构

```
main.py          入口 / Gtk.Application（单实例）
window.py        主窗口、心跳、深色模式
list_view.py     列表页（分组、行、撤销 Toast）
detail_view.py   详情 / 行内编辑 / 日期弹层
store.py         数据层（校验、原子落盘）
util.py          日期文案工具
style.css        macOS 风格主题（浅/深）
test_ui.py       自动化交互测试
```
